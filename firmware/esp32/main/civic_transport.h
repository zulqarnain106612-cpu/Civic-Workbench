#pragma once

#include "civic_can.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Serial protocol: "CW1 " followed by one schema-v1 JSON record and newline. */
esp_err_t civic_transport_init(void);
void civic_transport_emit_handshake(void);
esp_err_t civic_transport_emit_can_frame(
    const civic_can_frame_t *frame,
    const civic_can_diagnostics_t *diagnostics
);
void civic_transport_emit_device_status(const civic_can_diagnostics_t *diagnostics);

#ifdef __cplusplus
}
#endif
