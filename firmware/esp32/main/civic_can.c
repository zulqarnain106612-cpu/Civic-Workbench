#include "civic_can.h"
#include "civic_safety.h"
#include "civic_safety_internal.h"

#include <stdint.h>
#include <string.h>
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#if defined(CONFIG_CIVIC_RECEIVE_ONLY_BENCH) && CONFIG_CIVIC_RECEIVE_ONLY_BENCH
#define CIVIC_RECEIVE_ONLY 1
#if defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX) && CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX
#error "CIVIC_RECEIVE_ONLY_BENCH and CIVIC_ALLOW_HARDWARE_CAN_TX are mutually exclusive"
#endif
#else
#define CIVIC_RECEIVE_ONLY 0
#endif

#if !CIVIC_RECEIVE_ONLY && defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX) && CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX \
    && defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT) && CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT \
    && defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED) && CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED
#define CIVIC_TX_BUILD 1
#if !defined(CONFIG_CIVIC_TX_MIN_INTERVAL_MS) || !defined(CONFIG_CIVIC_TX_MAX_FRAMES_PER_ARM)
#error "TX builds require CIVIC_TX_MIN_INTERVAL_MS and CIVIC_TX_MAX_FRAMES_PER_ARM"
#endif
#else
#define CIVIC_TX_BUILD 0
#endif

static const char *TAG = "civic_can";
static bool s_driver_installed;
static bool s_hardware_ready;
static bool s_tx_capable;
static bool s_software_armed;
static bool s_hardware_configuration_accepted;
static QueueHandle_t s_frame_queue;
static TaskHandle_t s_rx_task;
static portMUX_TYPE s_counter_lock = portMUX_INITIALIZER_UNLOCKED;
static uint64_t s_rx_frames_dequeued;
static uint64_t s_software_dropped_frames;
static uint64_t s_malformed_frames;
#if CIVIC_TX_BUILD
/* Firmware-side TX bounds, independent of host policy: minimum spacing and a per-arm budget. */
static uint32_t s_tx_frames_this_arm;
static bool s_tx_has_last;
static int64_t s_tx_last_us;
static uint32_t s_tx_audit_sequence;

static void tx_audit(const civic_can_tx_request_t *request, const char *result)
{
    ++s_tx_audit_sequence;
    ESP_LOGW(TAG, "TX_AUDIT seq=%lu id=0x%08lx ext=%u rtr=%u dlc=%u frames_this_arm=%lu result=%s",
             (unsigned long)s_tx_audit_sequence, (unsigned long)request->arbitration_id,
             request->extended_id ? 1U : 0U, request->remote_frame ? 1U : 0U, (unsigned)request->dlc,
             (unsigned long)s_tx_frames_this_arm, result);
}
#endif

#if !CIVIC_RECEIVE_ONLY
static uint64_t gpio_pin_mask(int gpio_num)
{
    /* Caller validates the pin before use; avoid a compile-time -1 shift warning. */
    return UINT64_C(1) << (unsigned int)gpio_num;
}
#endif

static bool gpio_is_flash_reserved(int gpio)
{
    return gpio >= 6 && gpio <= 11;
}

static bool gpio_is_strapping(int gpio)
{
    return gpio == 0 || gpio == 2 || gpio == 5 || gpio == 12 || gpio == 15;
}

static bool gpio_is_console_reserved(int gpio)
{
    /* The CW1 serial transport shares UART0; don't assign GPIO1 (TX) or GPIO3 (RX) to CAN. */
    return gpio == 1 || gpio == 3;
}

static bool interlock_is_active(void)
{
    const int gpio_num = CONFIG_CIVIC_INTERLOCK_SENSE_GPIO;
    if (gpio_num < 0 || gpio_num > 39) {
        return false;
    }
    return gpio_get_level((gpio_num_t)gpio_num) == CONFIG_CIVIC_INTERLOCK_ACTIVE_LEVEL;
}

static void increment_software_drop(void)
{
    portENTER_CRITICAL(&s_counter_lock);
    ++s_software_dropped_frames;
    portEXIT_CRITICAL(&s_counter_lock);
}

static void increment_malformed_frame(void)
{
    portENTER_CRITICAL(&s_counter_lock);
    ++s_malformed_frames;
    portEXIT_CRITICAL(&s_counter_lock);
}

static void increment_rx_frame(void)
{
    portENTER_CRITICAL(&s_counter_lock);
    ++s_rx_frames_dequeued;
    portEXIT_CRITICAL(&s_counter_lock);
}

static bool software_armed_state(void)
{
    bool armed;
    portENTER_CRITICAL(&s_counter_lock);
    armed = s_software_armed;
    portEXIT_CRITICAL(&s_counter_lock);
    return armed;
}

static void set_software_armed_state(bool armed)
{
    portENTER_CRITICAL(&s_counter_lock);
    s_software_armed = armed;
    portEXIT_CRITICAL(&s_counter_lock);
}

static void read_software_counters(
    uint64_t *rx_frames,
    uint64_t *software_drops,
    uint64_t *malformed_frames
)
{
    portENTER_CRITICAL(&s_counter_lock);
    *rx_frames = s_rx_frames_dequeued;
    *software_drops = s_software_dropped_frames;
    *malformed_frames = s_malformed_frames;
    portEXIT_CRITICAL(&s_counter_lock);
}

static civic_can_controller_state_t map_controller_state(twai_state_t state)
{
    switch (state) {
    case TWAI_STATE_RUNNING:
        return CIVIC_CAN_CONTROLLER_RUNNING;
    case TWAI_STATE_STOPPED:
        return CIVIC_CAN_CONTROLLER_STOPPED;
    case TWAI_STATE_BUS_OFF:
        return CIVIC_CAN_CONTROLLER_BUS_OFF;
    case TWAI_STATE_RECOVERING:
        return CIVIC_CAN_CONTROLLER_RECOVERING;
    default:
        return CIVIC_CAN_CONTROLLER_ERROR;
    }
}

static bool twai_message_is_valid(const twai_message_t *message)
{
    if (message == NULL || message->data_length_code > 8U) {
        return false;
    }
    if (message->extd) {
        return message->identifier <= 0x1FFFFFFFU;
    }
    return message->identifier <= 0x7FFU;
}

static void civic_can_rx_pump(void *unused)
{
    (void)unused;
    ESP_LOGI(TAG, "Receive pump started; app queue depth=%u", (unsigned)CONFIG_CIVIC_APP_RX_QUEUE_DEPTH);

    for (;;) {
        if (software_armed_state() && !interlock_is_active()) {
            ESP_LOGW(TAG, "Physical interlock opened; disarming firmware TX request");
            (void)civic_can_set_software_armed(false);
        }

        twai_message_t message;
        const esp_err_t receive_err = twai_receive(&message, pdMS_TO_TICKS(50U));
        if (receive_err == ESP_ERR_TIMEOUT) {
            continue;
        }
        if (receive_err != ESP_OK) {
            twai_status_info_t status;
            if (twai_get_status_info(&status) == ESP_OK
                && status.state == TWAI_STATE_BUS_OFF
                && software_armed_state()) {
                ESP_LOGE(TAG, "TWAI entered BUS_OFF; forcing TX inhibit");
                (void)civic_can_set_software_armed(false);
            } else if (receive_err != ESP_ERR_INVALID_STATE) {
                ESP_LOGW(TAG, "TWAI receive failed: %s", esp_err_to_name(receive_err));
            }
            vTaskDelay(pdMS_TO_TICKS(20U));
            continue;
        }

        if (!twai_message_is_valid(&message)) {
            increment_malformed_frame();
            ESP_LOGW(TAG, "Discarded malformed TWAI frame (DLC/identifier out of range)");
            continue;
        }

        civic_can_frame_t frame;
        memset(&frame, 0, sizeof(frame));
        frame.observed_monotonic_us = (uint64_t)esp_timer_get_time();
        frame.arbitration_id = message.identifier;
        frame.dlc = message.data_length_code;
        frame.extended_id = message.extd;
        frame.remote_frame = message.rtr;
        if (!message.rtr && message.data_length_code > 0U) {
            memcpy(frame.data, message.data, message.data_length_code);
        }

        uint64_t rx_frames = 0U;
        uint64_t software_drops = 0U;
        uint64_t malformed_frames = 0U;
        read_software_counters(&rx_frames, &software_drops, &malformed_frames);
        (void)rx_frames;
        (void)malformed_frames;
        frame.dropped_frames_before = software_drops;

        /* Count every valid frame pulled from TWAI, including a later app-queue drop. */
        increment_rx_frame();
        if (xQueueSend(s_frame_queue, &frame, 0U) != pdTRUE) {
            increment_software_drop();
            if (software_armed_state()) {
                ESP_LOGE(TAG, "Application RX queue overflow while armed; forcing TX inhibit");
                (void)civic_can_set_software_armed(false);
            }
            continue;
        }
    }
}

bool civic_can_controller_ready(void)
{
    return s_driver_installed && s_hardware_ready;
}

esp_err_t civic_can_init(void)
{
    if (s_driver_installed || s_frame_queue != NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    s_driver_installed = false;
    s_hardware_ready = false;
    s_tx_capable = false;
    s_software_armed = false;
    s_hardware_configuration_accepted = false;

    esp_err_t err = ESP_OK;
#if CIVIC_RECEIVE_ONLY
    /* Receive-only bench build: hardware holds the transceiver in Silent mode and TXD is not
     * wired (hardware Rev B). No TX gate or interlock GPIO exists, so none is configured. */
    ESP_LOGW(TAG, "Receive-only bench build: TX gate/interlock not used; listen-only enforced");
#else
    /* Safe-state output is initialized before any TWAI controller setup. */
    err = civic_safety_init_inhibited();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "TX gate pin is not safely configured; refusing TWAI startup");
        return err;
    }
#endif

#if !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT) || !CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT
    ESP_LOGW(TAG, "Hardware CAN startup disabled by default configuration");
    return ESP_ERR_INVALID_STATE;
#endif
#if !defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED) || !CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED
    ESP_LOGE(TAG, "Bitrate evidence is not confirmed; refusing TWAI startup");
    return ESP_ERR_INVALID_STATE;
#endif

    if (CONFIG_CIVIC_TWAI_TX_GPIO < 0 || CONFIG_CIVIC_TWAI_TX_GPIO > 33
        || CONFIG_CIVIC_TWAI_RX_GPIO < 0 || CONFIG_CIVIC_TWAI_RX_GPIO > 39
        || CONFIG_CIVIC_TWAI_TX_GPIO == CONFIG_CIVIC_TWAI_RX_GPIO
        || gpio_is_flash_reserved(CONFIG_CIVIC_TWAI_TX_GPIO)
        || gpio_is_flash_reserved(CONFIG_CIVIC_TWAI_RX_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_TWAI_TX_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_TWAI_RX_GPIO)
        || gpio_is_console_reserved(CONFIG_CIVIC_TWAI_TX_GPIO)
        || gpio_is_console_reserved(CONFIG_CIVIC_TWAI_RX_GPIO)) {
        ESP_LOGE(TAG, "TWAI GPIO mapping is unset, reused, flash/console-reserved, or strapping; refusing TWAI startup");
        return ESP_ERR_INVALID_ARG;
    }

#if !CIVIC_RECEIVE_ONLY
    if (CONFIG_CIVIC_INTERLOCK_SENSE_GPIO < 0 || CONFIG_CIVIC_INTERLOCK_SENSE_GPIO > 39
        || CONFIG_CIVIC_TWAI_TX_GPIO == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO
        || CONFIG_CIVIC_TWAI_RX_GPIO == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO < 0 || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO > 33
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO == CONFIG_CIVIC_TWAI_TX_GPIO
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO == CONFIG_CIVIC_TWAI_RX_GPIO
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO
        || gpio_is_flash_reserved(CONFIG_CIVIC_INTERLOCK_SENSE_GPIO)
        || gpio_is_flash_reserved(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_INTERLOCK_SENSE_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO)
        || gpio_is_console_reserved(CONFIG_CIVIC_INTERLOCK_SENSE_GPIO)
        || gpio_is_console_reserved(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO)) {
        ESP_LOGE(TAG, "TX gate/interlock GPIO mapping is unset, reused, flash/console-reserved, or strapping; refusing TWAI startup");
        return ESP_ERR_INVALID_ARG;
    }

    const int interlock_gpio = CONFIG_CIVIC_INTERLOCK_SENSE_GPIO;
    const gpio_config_t interlock_input = {
        .pin_bit_mask = gpio_pin_mask(interlock_gpio),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    /* Board-level external bias must make an open/disconnected interlock inactive. */
    err = gpio_config(&interlock_input);
    if (err != ESP_OK) {
        return err;
    }
#endif

    s_hardware_configuration_accepted = true;
    s_frame_queue = xQueueCreate(
        (UBaseType_t)CONFIG_CIVIC_APP_RX_QUEUE_DEPTH,
        sizeof(civic_can_frame_t)
    );
    if (s_frame_queue == NULL) {
        s_hardware_configuration_accepted = false;
        return ESP_ERR_NO_MEM;
    }

    twai_general_config_t general_config = TWAI_GENERAL_CONFIG_DEFAULT(
        CONFIG_CIVIC_TWAI_TX_GPIO,
        CONFIG_CIVIC_TWAI_RX_GPIO,
        TWAI_MODE_LISTEN_ONLY
    );
    general_config.rx_queue_len = (uint32_t)CONFIG_CIVIC_TWAI_RX_QUEUE_LEN;
    /* No TX queue: a disarmed request must never be queued for later surprise transmission. */
    general_config.tx_queue_len = 0U;

#if !CIVIC_RECEIVE_ONLY && defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX) && CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX \
    && defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT) && CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT \
    && defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED) && CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED
    general_config.mode = TWAI_MODE_NORMAL;
    s_tx_capable = true;
#else
    general_config.mode = TWAI_MODE_LISTEN_ONLY;
    s_tx_capable = false;
#endif

    twai_timing_config_t timing_config;
    if (CONFIG_CIVIC_CAN_BITRATE == 125000) {
        timing_config = (twai_timing_config_t)TWAI_TIMING_CONFIG_125KBITS();
    } else if (CONFIG_CIVIC_CAN_BITRATE == 250000) {
        timing_config = (twai_timing_config_t)TWAI_TIMING_CONFIG_250KBITS();
    } else if (CONFIG_CIVIC_CAN_BITRATE == 500000) {
        timing_config = (twai_timing_config_t)TWAI_TIMING_CONFIG_500KBITS();
    } else if (CONFIG_CIVIC_CAN_BITRATE == 1000000) {
        timing_config = (twai_timing_config_t)TWAI_TIMING_CONFIG_1MBITS();
    } else {
        vQueueDelete(s_frame_queue);
        s_frame_queue = NULL;
        s_hardware_configuration_accepted = false;
        return ESP_ERR_NOT_SUPPORTED;
    }

    const twai_filter_config_t filter_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    err = twai_driver_install(&general_config, &timing_config, &filter_config);
    if (err != ESP_OK) {
        vQueueDelete(s_frame_queue);
        s_frame_queue = NULL;
        s_hardware_configuration_accepted = false;
        ESP_LOGE(TAG, "TWAI install failed: %s", esp_err_to_name(err));
        return err;
    }
    s_driver_installed = true;

    err = twai_start();
    if (err != ESP_OK) {
        (void)twai_driver_uninstall();
        s_driver_installed = false;
        vQueueDelete(s_frame_queue);
        s_frame_queue = NULL;
        s_hardware_configuration_accepted = false;
        ESP_LOGE(TAG, "TWAI start failed: %s", esp_err_to_name(err));
        return err;
    }

    if (xTaskCreate(
            civic_can_rx_pump,
            "civic_can_rx",
            (uint32_t)CONFIG_CIVIC_RX_TASK_STACK_BYTES,
            NULL,
            (UBaseType_t)CONFIG_CIVIC_RX_TASK_PRIORITY,
            &s_rx_task
        ) != pdPASS) {
        (void)twai_stop();
        (void)twai_driver_uninstall();
        s_driver_installed = false;
        s_rx_task = NULL;
        vQueueDelete(s_frame_queue);
        s_frame_queue = NULL;
        s_hardware_configuration_accepted = false;
        return ESP_ERR_NO_MEM;
    }

    s_hardware_ready = true;
    ESP_LOGI(
        TAG,
        "TWAI started; mode=%s rx_driver_queue=%u app_queue=%u tx_queue=0",
        s_tx_capable ? "normal-but-gated" : "listen-only",
        (unsigned)CONFIG_CIVIC_TWAI_RX_QUEUE_LEN,
        (unsigned)CONFIG_CIVIC_APP_RX_QUEUE_DEPTH
    );
    return ESP_OK;
}

esp_err_t civic_can_receive(civic_can_frame_t *out_frame, uint32_t timeout_ms)
{
    if (out_frame == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_driver_installed || s_frame_queue == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    const TickType_t wait_ticks = pdMS_TO_TICKS(timeout_ms);
    if (xQueueReceive(s_frame_queue, out_frame, wait_ticks) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    uint64_t rx_frames = 0U;
    uint64_t software_drops = 0U;
    uint64_t malformed_frames = 0U;
    read_software_counters(&rx_frames, &software_drops, &malformed_frames);
    (void)rx_frames;
    (void)malformed_frames;
    out_frame->dropped_frames_after = software_drops;
    return ESP_OK;
}

esp_err_t civic_can_get_diagnostics(civic_can_diagnostics_t *out_diagnostics)
{
    if (out_diagnostics == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    memset(out_diagnostics, 0, sizeof(*out_diagnostics));

    out_diagnostics->driver_installed = s_driver_installed;
    out_diagnostics->transmit_capable = s_tx_capable;
    out_diagnostics->software_armed = software_armed_state();
    out_diagnostics->controller_state = s_driver_installed
        ? CIVIC_CAN_CONTROLLER_UNKNOWN : CIVIC_CAN_CONTROLLER_STOPPED;
    out_diagnostics->bitrate_bps = s_driver_installed
        ? (uint32_t)CONFIG_CIVIC_CAN_BITRATE : 0U;

    read_software_counters(
        &out_diagnostics->rx_frames_dequeued,
        &out_diagnostics->software_dropped_frames,
        &out_diagnostics->malformed_frames
    );
    if (s_frame_queue != NULL) {
        out_diagnostics->app_rx_queue_depth = (uint32_t)uxQueueMessagesWaiting(s_frame_queue);
    }

    if (!s_driver_installed) {
        return ESP_OK;
    }

    twai_status_info_t status;
    const esp_err_t err = twai_get_status_info(&status);
    if (err != ESP_OK) {
        out_diagnostics->controller_state = CIVIC_CAN_CONTROLLER_ERROR;
        return err;
    }

    out_diagnostics->controller_state = map_controller_state(status.state);
    out_diagnostics->driver_rx_queue_depth = status.msgs_to_rx;
    out_diagnostics->tx_error_counter = status.tx_error_counter;
    out_diagnostics->rx_error_counter = status.rx_error_counter;
    out_diagnostics->tx_failed_count = status.tx_failed_count;
    out_diagnostics->rx_missed_count = status.rx_missed_count;
    out_diagnostics->rx_overrun_count = status.rx_overrun_count;
    out_diagnostics->arbitration_lost_count = status.arb_lost_count;
    out_diagnostics->bus_error_count = status.bus_error_count;
    return ESP_OK;
}

esp_err_t civic_can_get_status(twai_status_info_t *out_status)
{
    if (out_status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_driver_installed) {
        return ESP_ERR_INVALID_STATE;
    }
    return twai_get_status_info(out_status);
}

esp_err_t civic_can_set_software_armed(bool armed)
{
    if (!armed) {
        set_software_armed_state(false);
#if CIVIC_RECEIVE_ONLY
        /* Receive-only bench build has no TX gate GPIO; disarm is already the only state. */
        return ESP_OK;
#else
        return civic_safety_drive_tx_request(false);
#endif
    }

#if !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX) || !CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX
    ESP_LOGW(TAG, "Hardware TX capability is disabled in this build");
    return ESP_ERR_NOT_SUPPORTED;
#elif !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT) || !CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT
    return ESP_ERR_INVALID_STATE;
#elif !defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED) || !CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED
    return ESP_ERR_INVALID_STATE;
#else
    if (!s_driver_installed || !s_hardware_configuration_accepted || !s_tx_capable) {
        return ESP_ERR_INVALID_STATE;
    }
    if (!interlock_is_active()) {
        set_software_armed_state(false);
        (void)civic_safety_drive_tx_request(false);
        return ESP_ERR_INVALID_STATE;
    }

    twai_status_info_t status;
    esp_err_t err = twai_get_status_info(&status);
    if (err != ESP_OK || status.state != TWAI_STATE_RUNNING
        || status.tx_error_counter >= CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD
        || status.rx_error_counter >= CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD) {
        set_software_armed_state(false);
        (void)civic_safety_drive_tx_request(false);
        return err == ESP_OK ? ESP_ERR_INVALID_STATE : err;
    }

    const civic_safety_inputs_t inputs = {
        .software_armed = true,
        .physical_interlock_active = true,
        .controller_running = true,
        .controller_faulted = false,
        .hardware_configuration_verified = s_hardware_configuration_accepted,
    };
    if (!civic_safety_tx_permitted(&inputs)) {
        return ESP_ERR_INVALID_STATE;
    }

    err = civic_safety_drive_tx_request(true);
    if (err != ESP_OK || !interlock_is_active()) {
        set_software_armed_state(false);
        (void)civic_safety_drive_tx_request(false);
        return err == ESP_OK ? ESP_ERR_INVALID_STATE : err;
    }

    s_tx_frames_this_arm = 0U;
    s_tx_has_last = false;
    set_software_armed_state(true);
    ESP_LOGW(TAG, "TX software arm active; independent physical interlock remains required");
    return ESP_OK;
#endif
}

esp_err_t civic_can_transmit_guarded(
    const civic_can_tx_request_t *request,
    uint32_t timeout_ms
)
{
    if (request == NULL || timeout_ms == 0U || timeout_ms > 1000U
        || request->dlc > 8U
        || (!request->extended_id && request->arbitration_id > 0x7FFU)
        || (request->extended_id && request->arbitration_id > 0x1FFFFFFFU)) {
        return ESP_ERR_INVALID_ARG;
    }

#if !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX) || !CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX
    return ESP_ERR_NOT_SUPPORTED;
#elif !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT) || !CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT
    return ESP_ERR_NOT_SUPPORTED;
#elif !defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED) || !CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED
    return ESP_ERR_NOT_SUPPORTED;
#else
    if (!s_driver_installed || !s_hardware_configuration_accepted
        || !s_tx_capable || !software_armed_state()) {
        return ESP_ERR_INVALID_STATE;
    }
    if (!interlock_is_active()) {
        (void)civic_can_set_software_armed(false);
        return ESP_ERR_INVALID_STATE;
    }

    twai_status_info_t status;
    esp_err_t err = twai_get_status_info(&status);
    if (err != ESP_OK || status.state != TWAI_STATE_RUNNING
        || status.tx_error_counter >= CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD
        || status.rx_error_counter >= CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD) {
        (void)civic_can_set_software_armed(false);
        return err == ESP_OK ? ESP_ERR_INVALID_STATE : err;
    }

    twai_message_t message;
    memset(&message, 0, sizeof(message));
    message.identifier = request->arbitration_id;
    message.extd = request->extended_id;
    message.rtr = request->remote_frame;
    message.data_length_code = request->dlc;
    if (!request->remote_frame && request->dlc > 0U) {
        memcpy(message.data, request->data, request->dlc);
    }

    if (s_tx_frames_this_arm >= (uint32_t)CONFIG_CIVIC_TX_MAX_FRAMES_PER_ARM) {
        tx_audit(request, "REJECTED_ARM_BUDGET_EXHAUSTED_DISARMED");
        (void)civic_can_set_software_armed(false);
        return ESP_ERR_INVALID_STATE;
    }
    const int64_t now_us = esp_timer_get_time();
    if (s_tx_has_last && (now_us - s_tx_last_us) < (int64_t)CONFIG_CIVIC_TX_MIN_INTERVAL_MS * 1000) {
        tx_audit(request, "REJECTED_RATE_LIMIT");
        return ESP_ERR_TIMEOUT;
    }

    /* TX queue is configured as length zero, so no frame remains queued after timeout/disarm. */
    err = twai_transmit(&message, pdMS_TO_TICKS(timeout_ms));
    s_tx_has_last = true;
    s_tx_last_us = now_us;
    if (err != ESP_OK) {
        tx_audit(request, "FAILED_DISARMED");
        (void)civic_can_set_software_armed(false);
        ESP_LOGE(TAG, "Guarded TX failed: %s; TX request has been disarmed", esp_err_to_name(err));
        return err;
    }
    ++s_tx_frames_this_arm;
    tx_audit(request, "SENT");

    /* Re-check after the send; hardware interlock is still the immediate physical barrier. */
    if (!interlock_is_active()) {
        (void)civic_can_set_software_armed(false);
        return ESP_ERR_INVALID_STATE;
    }
    return ESP_OK;
#endif
}

esp_err_t civic_can_request_bus_recovery(void)
{
    (void)civic_can_set_software_armed(false);
    if (!s_driver_installed) {
        return ESP_ERR_INVALID_STATE;
    }

    twai_status_info_t status;
    esp_err_t err = twai_get_status_info(&status);
    if (err != ESP_OK) {
        return err;
    }
    if (status.state != TWAI_STATE_BUS_OFF) {
        return ESP_ERR_INVALID_STATE;
    }

    err = twai_initiate_recovery();
    if (err == ESP_OK) {
        ESP_LOGW(TAG, "TWAI bus-off recovery started; TX remains disarmed");
    }
    return err;
}

esp_err_t civic_can_restart_after_recovery(void)
{
    (void)civic_can_set_software_armed(false);
    if (!s_driver_installed) {
        return ESP_ERR_INVALID_STATE;
    }

    twai_status_info_t status;
    esp_err_t err = twai_get_status_info(&status);
    if (err != ESP_OK) {
        return err;
    }
    if (status.state != TWAI_STATE_STOPPED) {
        return ESP_ERR_INVALID_STATE;
    }

    err = twai_start();
    if (err == ESP_OK) {
        s_hardware_ready = true;
        ESP_LOGI(TAG, "TWAI restarted after recovery; TX remains disarmed");
    }
    return err;
}
