#define _POSIX_C_SOURCE 200809L

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

#include "sdkconfig.h"
#include "civic_can.h"
#include "civic_safety.h"
#include "esp_timer.h"
#include "mock_esp.h"

static unsigned int s_assertions;

#define CHECK(expression) \
    do { \
        ++s_assertions; \
        if (!(expression)) { \
            fprintf(stderr, "ASSERTION FAILED at %s:%d: %s\n", __FILE__, __LINE__, #expression); \
            return 1; \
        } \
    } while (0)

static void sleep_ms(unsigned int milliseconds)
{
    const struct timespec delay = {
        .tv_sec = (time_t)(milliseconds / 1000U),
        .tv_nsec = (long)(milliseconds % 1000U) * 1000000L,
    };
    (void)nanosleep(&delay, NULL);
}

static bool wait_for_counts(uint64_t expected_rx, uint64_t expected_drops, uint64_t expected_malformed)
{
    for (unsigned int attempt = 0U; attempt < 500U; ++attempt) {
        civic_can_diagnostics_t diagnostics;
        if (civic_can_get_diagnostics(&diagnostics) == ESP_OK
            && diagnostics.rx_frames_dequeued >= expected_rx
            && diagnostics.software_dropped_frames >= expected_drops
            && diagnostics.malformed_frames >= expected_malformed) {
            return true;
        }
        sleep_ms(1U);
    }
    return false;
}

static twai_message_t make_frame(
    uint32_t identifier,
    bool extended,
    uint8_t dlc,
    uint8_t seed
)
{
    twai_message_t message = {
        .identifier = identifier,
        .data_length_code = dlc,
        .data = {0U},
        .extd = extended,
        .rtr = false,
    };
    for (uint8_t i = 0U; i < 8U; ++i) {
        message.data[i] = (uint8_t)(seed + i);
    }
    return message;
}

int main(void)
{
    mock_twai_reset();

    CHECK(civic_can_init() == ESP_OK);
    CHECK(civic_can_controller_ready());
    CHECK(mock_twai_installed_mode() == TWAI_MODE_NORMAL);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);

    civic_can_diagnostics_t diagnostics;
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(diagnostics.driver_installed);
    CHECK(diagnostics.transmit_capable);
    CHECK(!diagnostics.software_armed);
    CHECK(diagnostics.bitrate_bps == 500000U);

    civic_can_tx_request_t tx = {
        .arbitration_id = 0x321U,
        .dlc = 2U,
        .data = {0xAAU, 0x55U},
        .extended_id = false,
        .remote_frame = false,
    };
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_ERR_INVALID_STATE);
    CHECK(mock_twai_tx_count() == 0U);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);

    const twai_message_t standard = make_frame(0x123U, false, 3U, 0x10U);
    const twai_message_t extended = make_frame(0x1ABCDEFFU, true, 8U, 0x20U);
    mock_twai_inject(&standard);
    mock_twai_inject(&extended);
    CHECK(wait_for_counts(2U, 0U, 0U));

    civic_can_frame_t received;
    CHECK(civic_can_receive(&received, 100U) == ESP_OK);
    CHECK(received.arbitration_id == 0x123U);
    CHECK(!received.extended_id);
    CHECK(received.dlc == 3U);
    CHECK(received.data[0] == 0x10U && received.data[2] == 0x12U);
    CHECK(received.observed_monotonic_us > 0U);

    CHECK(civic_can_receive(&received, 100U) == ESP_OK);
    CHECK(received.arbitration_id == 0x1ABCDEFFU);
    CHECK(received.extended_id);
    CHECK(received.dlc == 8U);
    CHECK(received.data[7] == 0x27U);

    twai_message_t malformed = make_frame(0x123U, false, 9U, 0U);
    mock_twai_inject(&malformed);
    malformed = make_frame(0x800U, false, 1U, 0U);
    mock_twai_inject(&malformed);
    CHECK(wait_for_counts(2U, 0U, 2U));
    CHECK(civic_can_receive(&received, 5U) == ESP_ERR_TIMEOUT);

    /* Two-slot ingress queue: inject eight frames without draining it. */
    for (uint8_t i = 0U; i < 8U; ++i) {
        const twai_message_t message = make_frame((uint32_t)(0x400U + i), false, 1U, i);
        mock_twai_inject(&message);
    }
    CHECK(wait_for_counts(10U, 6U, 2U));
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(diagnostics.app_rx_queue_depth == 2U);
    CHECK(diagnostics.software_dropped_frames >= 6U);
    CHECK(diagnostics.rx_frames_dequeued >= 10U);

    CHECK(civic_can_receive(&received, 100U) == ESP_OK);
    CHECK(civic_can_receive(&received, 100U) == ESP_OK);
    CHECK(received.dropped_frames_after >= 6U);

    mock_set_interlock_level(CONFIG_CIVIC_INTERLOCK_ACTIVE_LEVEL);
    CHECK(civic_can_set_software_armed(true) == ESP_OK);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 1);
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_OK);
    CHECK(mock_twai_tx_count() == 1U);

    twai_message_t sent;
    CHECK(mock_twai_last_tx(&sent));
    CHECK(sent.identifier == 0x321U);
    CHECK(sent.data_length_code == 2U);
    CHECK(sent.data[0] == 0xAAU && sent.data[1] == 0x55U);

    /* Firmware rate bound: an immediate second frame is rejected without disarming. */
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_ERR_TIMEOUT);
    CHECK(mock_twai_tx_count() == 1U);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(diagnostics.software_armed);
    for (unsigned int i = 0U; i < 2U * CONFIG_CIVIC_TX_MIN_INTERVAL_MS; ++i) {
        (void)esp_timer_get_time(); /* mock clock advances 1 ms per call */
    }
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_OK);
    CHECK(mock_twai_tx_count() == 2U);
    for (unsigned int i = 0U; i < 2U * CONFIG_CIVIC_TX_MIN_INTERVAL_MS; ++i) {
        (void)esp_timer_get_time();
    }
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_OK);
    CHECK(mock_twai_tx_count() == 3U);
    for (unsigned int i = 0U; i < 2U * CONFIG_CIVIC_TX_MIN_INTERVAL_MS; ++i) {
        (void)esp_timer_get_time();
    }
    /* Per-arm budget (3) exhausted: rejected and disarmed; gate request released. */
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_ERR_INVALID_STATE);
    CHECK(mock_twai_tx_count() == 3U);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(!diagnostics.software_armed);
    CHECK(civic_can_set_software_armed(true) == ESP_OK);

    tx.arbitration_id = 0x800U;
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_ERR_INVALID_ARG);
    CHECK(mock_twai_tx_count() == 3U);
    tx.arbitration_id = 0x321U;

    mock_set_interlock_level(0);
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_ERR_INVALID_STATE);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(!diagnostics.software_armed);
    CHECK(mock_twai_tx_count() == 3U);

    /* Queue saturation while armed is an explicit disarm condition. */
    mock_set_interlock_level(CONFIG_CIVIC_INTERLOCK_ACTIVE_LEVEL);
    CHECK(civic_can_set_software_armed(true) == ESP_OK);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 1);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    const uint64_t rx_before_overflow = diagnostics.rx_frames_dequeued;
    const uint64_t drops_before_overflow = diagnostics.software_dropped_frames;
    for (uint8_t i = 0U; i < 5U; ++i) {
        const twai_message_t message = make_frame((uint32_t)(0x500U + i), false, 1U, i);
        mock_twai_inject(&message);
    }
    CHECK(wait_for_counts(
        rx_before_overflow + 5U, drops_before_overflow + 3U, 2U
    ));
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(!diagnostics.software_armed);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);
    CHECK(civic_can_receive(&received, 100U) == ESP_OK);
    CHECK(civic_can_receive(&received, 100U) == ESP_OK);

    mock_twai_set_error_stats(0U, 0U, 3U, 4U);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(diagnostics.rx_missed_count == 3U);
    CHECK(diagnostics.rx_overrun_count == 4U);

    /* Bus-off while armed: twai_receive() keeps timing out, so the RX pump must notice the
     * controller state itself, disarm and release the gate request without any TX call. */
    mock_set_interlock_level(CONFIG_CIVIC_INTERLOCK_ACTIVE_LEVEL);
    CHECK(civic_can_set_software_armed(true) == ESP_OK);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 1);
    mock_twai_set_state(TWAI_STATE_BUS_OFF);
    bool disarmed_by_pump = false;
    for (unsigned int attempt = 0U; attempt < 100U && !disarmed_by_pump; ++attempt) {
        const struct timespec pause = {.tv_sec = 0, .tv_nsec = 10L * 1000L * 1000L};
        nanosleep(&pause, NULL);
        CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
        disarmed_by_pump = !diagnostics.software_armed;
    }
    CHECK(disarmed_by_pump);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);

    CHECK(civic_can_request_bus_recovery() == ESP_OK);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(diagnostics.controller_state == CIVIC_CAN_CONTROLLER_RECOVERING);
    mock_twai_set_state(TWAI_STATE_STOPPED);
    CHECK(civic_can_restart_after_recovery() == ESP_OK);
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(diagnostics.controller_state == CIVIC_CAN_CONTROLLER_RUNNING);
    CHECK(!diagnostics.software_armed);
    CHECK(mock_gpio_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO) == 0);
    CHECK(civic_can_transmit_guarded(&tx, 50U) == ESP_ERR_INVALID_STATE);
    CHECK(mock_twai_tx_count() == 3U);

    printf("CAN_CORE_ASSERTIONS=%u\n", s_assertions);
    return 0;
}
