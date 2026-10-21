#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "driver/twai.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Conservative pre-error-passive TX inhibit threshold; this is software policy, not a hardware guarantee. */
#define CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD 96U

typedef enum {
    CIVIC_CAN_CONTROLLER_UNKNOWN = 0,
    CIVIC_CAN_CONTROLLER_STOPPED,
    CIVIC_CAN_CONTROLLER_RUNNING,
    CIVIC_CAN_CONTROLLER_BUS_OFF,
    CIVIC_CAN_CONTROLLER_RECOVERING,
    CIVIC_CAN_CONTROLLER_ERROR
} civic_can_controller_state_t;

typedef struct {
    /* Timestamp is taken when the TWAI driver dequeues the frame, not at wire SOF. */
    uint64_t observed_monotonic_us;
    uint32_t arbitration_id;
    uint8_t dlc;
    uint8_t data[8];
    bool extended_id;
    bool remote_frame;
    uint64_t dropped_frames_before;
    uint64_t dropped_frames_after;
} civic_can_frame_t;

typedef struct {
    uint32_t arbitration_id;
    uint8_t dlc;
    uint8_t data[8];
    bool extended_id;
    bool remote_frame;
} civic_can_tx_request_t;

typedef struct {
    bool driver_installed;
    bool transmit_capable;
    bool software_armed;
    civic_can_controller_state_t controller_state;
    uint32_t bitrate_bps;
    uint32_t driver_rx_queue_depth;
    uint32_t app_rx_queue_depth;
    uint64_t rx_frames_dequeued;
    uint64_t software_dropped_frames;
    uint64_t malformed_frames;
    uint32_t tx_error_counter;
    uint32_t rx_error_counter;
    uint32_t tx_failed_count;
    uint32_t rx_missed_count;
    uint32_t rx_overrun_count;
    uint32_t arbitration_lost_count;
    uint32_t bus_error_count;
} civic_can_diagnostics_t;

/* Requires explicit hardware-init, bitrate-evidence, and valid pin configuration. */
esp_err_t civic_can_init(void);
bool civic_can_controller_ready(void);

/* Dequeues one frame from the bounded application ingress queue. */
esp_err_t civic_can_receive(civic_can_frame_t *out_frame, uint32_t timeout_ms);

/* Controller state, bounded queue depth, and driver/software loss counters. */
esp_err_t civic_can_get_diagnostics(civic_can_diagnostics_t *out_diagnostics);

/* Raw driver status for diagnostics/tests; never implies TX permission. */
esp_err_t civic_can_get_status(twai_status_info_t *out_status);

/* Deliberate software-arm transition. Hardware remains inhibited by default. */
esp_err_t civic_can_set_software_armed(bool armed);

/* One bounded frame only; S03 does not implement repeat schedules or diagnostics. */
esp_err_t civic_can_transmit_guarded(
    const civic_can_tx_request_t *request,
    uint32_t timeout_ms
);

/* Disarms first; recovery/restart leave TX software-disarmed. */
esp_err_t civic_can_request_bus_recovery(void);
esp_err_t civic_can_restart_after_recovery(void);

#ifdef __cplusplus
}
#endif
