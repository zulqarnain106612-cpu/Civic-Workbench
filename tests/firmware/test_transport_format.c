#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../../firmware/esp32/main/civic_transport_format.h"

static civic_transport_record_t sample_record(void)
{
    civic_transport_record_t record = {
        .frame_id = "1c1a0f51-3ca6-4db0-9a9a-2fb0914d7e15",
        .session_id = "7a4e6c3b-9ec9-4d07-8a4e-2de691b104cc",
        .observed_monotonic_us = 1234567U,
        .arbitration_id = 0x123U,
        .dlc = 3U,
        .data = {0U, 16U, 255U},
        .extended_id = false,
        .remote_frame = false,
        .dropped_frames_before = 0U,
        .dropped_frames_after = 2U,
        .controller_state = CIVIC_TRANSPORT_STATE_RUNNING,
    };
    return record;
}

int main(void)
{
    char line[512];
    civic_transport_record_t record = sample_record();

    assert(civic_transport_format_frame(&record, line, sizeof(line)) == CIVIC_TRANSPORT_FORMAT_OK);
    puts(line);

    record.arbitration_id = 0x1ABCDEFFU;
    record.extended_id = true;
    record.dlc = 8U;
    record.data[3] = 4U;
    record.data[4] = 5U;
    record.data[5] = 6U;
    record.data[6] = 7U;
    record.data[7] = 8U;
    assert(civic_transport_format_frame(&record, line, sizeof(line)) == CIVIC_TRANSPORT_FORMAT_OK);
    puts(line);

    record.remote_frame = true;
    assert(civic_transport_format_frame(&record, line, sizeof(line)) == CIVIC_TRANSPORT_FORMAT_OK);
    puts(line);

    record.remote_frame = false;
    record.extended_id = false;
    record.arbitration_id = 0x800U;
    assert(civic_transport_format_frame(&record, line, sizeof(line)) == CIVIC_TRANSPORT_FORMAT_INVALID_FRAME);

    record = sample_record();
    assert(civic_transport_format_frame(&record, line, 8U) == CIVIC_TRANSPORT_FORMAT_BUFFER_TOO_SMALL);
    assert(line[0] == '\0');

    record = sample_record();
    record.frame_id = "bad-uuid";
    assert(civic_transport_format_frame(&record, line, sizeof(line)) == CIVIC_TRANSPORT_FORMAT_INVALID_FRAME);

    record = sample_record();
    record.controller_state = CIVIC_TRANSPORT_STATE_RECOVERING;
    assert(civic_transport_format_frame(&record, line, sizeof(line)) == CIVIC_TRANSPORT_FORMAT_OK);
    puts(line);

    puts("TRANSPORT_ASSERTIONS=7");
    return 0;
}
