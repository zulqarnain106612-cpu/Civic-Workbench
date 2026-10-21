#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "driver/twai.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    /* Time the application dequeued this RX frame; not hardware SOF time. */
    uint64_t observed_monotonic_us;
    uint32_t arbitration_id;
    uint8_t dlc;
    uint8_t data[8];
    bool extended_id;
    bool remote_frame;
} civic_can_frame_t;

/* Installs the controller only when explicit hardware configuration is allowed. */
esp_err_t civic_can_init_listen_only(void);

/* Non-blocking dequeue; ESP_ERR_NOT_FOUND means no queued frame. */
esp_err_t civic_can_receive(civic_can_frame_t *out_frame, uint32_t timeout_ms);

/* Report controller status; caller must treat error/bus-off as TX inhibit. */
esp_err_t civic_can_get_status(twai_status_info_t *out_status);

/* S02 intentionally provides no hardware TX send path; S03 will add gated TX. */
bool civic_can_hardware_ready(void);

#ifdef __cplusplus
}
#endif
