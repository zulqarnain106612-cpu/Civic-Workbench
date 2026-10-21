#include "civic_transport.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    assert(civic_transport_init() == ESP_OK);
    civic_transport_emit_handshake();

    civic_can_diagnostics_t diagnostics;
    memset(&diagnostics, 0, sizeof(diagnostics));
    diagnostics.driver_installed = false;
    diagnostics.controller_state = CIVIC_CAN_CONTROLLER_STOPPED;
    civic_transport_emit_device_status(&diagnostics);

    memset(&diagnostics, 0, sizeof(diagnostics));
    diagnostics.driver_installed = true;
    diagnostics.controller_state = CIVIC_CAN_CONTROLLER_RUNNING;
    diagnostics.bitrate_bps = 500000U;
    diagnostics.transmit_capable = true;
    diagnostics.software_armed = true;
    diagnostics.software_dropped_frames = 2U;
    diagnostics.malformed_frames = 1U;
    diagnostics.driver_rx_queue_depth = 12U;
    diagnostics.app_rx_queue_depth = 6U;
    diagnostics.tx_error_counter = 7U;
    diagnostics.rx_error_counter = 8U;
    diagnostics.tx_failed_count = 1U;
    diagnostics.rx_missed_count = 3U;
    diagnostics.rx_overrun_count = 4U;
    diagnostics.arbitration_lost_count = 5U;
    diagnostics.bus_error_count = 6U;
    civic_transport_emit_device_status(&diagnostics);

    diagnostics.controller_state = CIVIC_CAN_CONTROLLER_RECOVERING;
    diagnostics.software_armed = false;
    diagnostics.tx_error_counter = 96U;
    civic_transport_emit_device_status(&diagnostics);

    civic_can_frame_t frame;
    memset(&frame, 0, sizeof(frame));
    frame.observed_monotonic_us = 1234567U;
    frame.arbitration_id = 0x123U;
    frame.dlc = 3U;
    frame.data[0] = 0U;
    frame.data[1] = 16U;
    frame.data[2] = 255U;
    frame.extended_id = false;
    frame.remote_frame = false;
    frame.dropped_frames_before = 1U;
    frame.dropped_frames_after = 2U;
    diagnostics.software_dropped_frames = 9U;
    assert(civic_transport_emit_can_frame(&frame, &diagnostics) == ESP_OK);

    diagnostics.controller_state = CIVIC_CAN_CONTROLLER_RUNNING;
    diagnostics.software_armed = true;
    diagnostics.tx_error_counter = 7U;
    assert(civic_transport_emit_can_frame(&frame, &diagnostics) == ESP_OK);

    return 0;
}
