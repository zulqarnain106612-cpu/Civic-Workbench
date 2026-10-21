#include "civic_can.h"
#include "civic_safety.h"

#include <stdint.h>
#include <string.h>
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "civic_can";
static bool s_driver_installed;
static bool s_hardware_ready;

static uint64_t gpio_pin_mask(int gpio_num)
{
    /* Caller validates the pin before use; avoid a compile-time -1 shift warning. */
    return UINT64_C(1) << (unsigned int)gpio_num;
}

static bool gpio_is_flash_reserved(int gpio)
{
    return gpio >= 6 && gpio <= 11;
}

static bool gpio_is_strapping(int gpio)
{
    return gpio == 0 || gpio == 2 || gpio == 5 || gpio == 12 || gpio == 15;
}

bool civic_can_hardware_ready(void)
{
    return s_hardware_ready;
}

esp_err_t civic_can_init_listen_only(void)
{
    s_hardware_ready = false;
    s_driver_installed = false;

    /* Safety output is forced inactive before any controller initialization. */
    esp_err_t safety_err = civic_safety_init_inhibited();
    if (safety_err != ESP_OK) {
        ESP_LOGW(TAG, "Hardware TX request not configured; TWAI startup denied");
        return safety_err;
    }

#if !defined(CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT) || !CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT
    ESP_LOGW(TAG, "CAN startup disabled by build configuration; compile-only safe default");
    return ESP_ERR_INVALID_STATE;
#endif
#if !defined(CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED) || !CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED
    ESP_LOGE(TAG, "Bitrate is not evidence-confirmed; refusing TWAI startup");
    return ESP_ERR_INVALID_STATE;
#endif
    if (CONFIG_CIVIC_TWAI_TX_GPIO < 0 || CONFIG_CIVIC_TWAI_TX_GPIO > 33
        || CONFIG_CIVIC_TWAI_RX_GPIO < 0 || CONFIG_CIVIC_TWAI_RX_GPIO > 39
        || CONFIG_CIVIC_INTERLOCK_SENSE_GPIO < 0 || CONFIG_CIVIC_INTERLOCK_SENSE_GPIO > 39
        || CONFIG_CIVIC_TWAI_TX_GPIO == CONFIG_CIVIC_TWAI_RX_GPIO
        || CONFIG_CIVIC_TWAI_TX_GPIO == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO
        || CONFIG_CIVIC_TWAI_RX_GPIO == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO < 0 || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO > 33
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO == CONFIG_CIVIC_TWAI_TX_GPIO
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO == CONFIG_CIVIC_TWAI_RX_GPIO
        || CONFIG_CIVIC_TX_GATE_REQUEST_GPIO == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO
        || gpio_is_flash_reserved(CONFIG_CIVIC_TWAI_TX_GPIO)
        || gpio_is_flash_reserved(CONFIG_CIVIC_TWAI_RX_GPIO)
        || gpio_is_flash_reserved(CONFIG_CIVIC_INTERLOCK_SENSE_GPIO)
        || gpio_is_flash_reserved(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_TWAI_TX_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_TWAI_RX_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_INTERLOCK_SENSE_GPIO)
        || gpio_is_strapping(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO)) {
        ESP_LOGE(TAG, "GPIO mapping is unset, invalid for original ESP32, or reused; refusing TWAI startup");
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
    /* Hardware must bias the interlock feedback to inactive when open/disconnected. */
    esp_err_t err = gpio_config(&interlock_input);
    if (err != ESP_OK) {
        return err;
    }

    const twai_general_config_t general_config = TWAI_GENERAL_CONFIG_DEFAULT(
        CONFIG_CIVIC_TWAI_TX_GPIO,
        CONFIG_CIVIC_TWAI_RX_GPIO,
        TWAI_MODE_LISTEN_ONLY
    );
    twai_timing_config_t selected_timing;
    if (CONFIG_CIVIC_CAN_BITRATE == 125000) {
        selected_timing = (twai_timing_config_t)TWAI_TIMING_CONFIG_125KBITS();
    } else if (CONFIG_CIVIC_CAN_BITRATE == 250000) {
        selected_timing = (twai_timing_config_t)TWAI_TIMING_CONFIG_250KBITS();
    } else if (CONFIG_CIVIC_CAN_BITRATE == 500000) {
        selected_timing = (twai_timing_config_t)TWAI_TIMING_CONFIG_500KBITS();
    } else if (CONFIG_CIVIC_CAN_BITRATE == 1000000) {
        selected_timing = (twai_timing_config_t)TWAI_TIMING_CONFIG_1MBITS();
    } else {
        ESP_LOGE(TAG, "Requested bitrate has no reviewed timing macro; refusing TWAI startup");
        return ESP_ERR_NOT_SUPPORTED;
    }

    const twai_filter_config_t filter_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    err = twai_driver_install(&general_config, &selected_timing, &filter_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "TWAI install failed: %s", esp_err_to_name(err));
        return err;
    }
    s_driver_installed = true;

    /* This stage starts listen-only. TX is not implemented in S02. */
    err = twai_start();
    if (err != ESP_OK) {
        (void)twai_driver_uninstall();
        s_driver_installed = false;
        ESP_LOGE(TAG, "TWAI start failed: %s", esp_err_to_name(err));
        return err;
    }
    s_hardware_ready = true;
    ESP_LOGI(TAG, "TWAI started in LISTEN_ONLY mode; hardware TX request remains inactive");
    return ESP_OK;
}

esp_err_t civic_can_receive(civic_can_frame_t *out_frame, uint32_t timeout_ms)
{
    if (out_frame == NULL || !s_driver_installed) {
        return ESP_ERR_INVALID_STATE;
    }

    twai_message_t message;
    const TickType_t wait_ticks = pdMS_TO_TICKS(timeout_ms);
    esp_err_t err = twai_receive(&message, wait_ticks);
    if (err != ESP_OK) {
        return err;
    }

    memset(out_frame, 0, sizeof(*out_frame));
    out_frame->observed_monotonic_us = (uint64_t)esp_timer_get_time();
    out_frame->arbitration_id = message.identifier;
    out_frame->dlc = message.data_length_code;
    out_frame->extended_id = message.extd;
    out_frame->remote_frame = message.rtr;
    /* ESP-IDF 5.3 twai_message_t has no per-frame overrun flag.
       RX queue/missed-frame counters are exposed through civic_can_get_status(). */
    if (!message.rtr && message.data_length_code <= sizeof(out_frame->data)) {
        memcpy(out_frame->data, message.data, message.data_length_code);
    }
    return ESP_OK;
}

esp_err_t civic_can_get_status(twai_status_info_t *out_status)
{
    if (out_status == NULL || !s_driver_installed) {
        return ESP_ERR_INVALID_STATE;
    }
    return twai_get_status_info(out_status);
}
