#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CIVIC_TRANSPORT_UUID_LENGTH 36U

typedef enum {
    CIVIC_TRANSPORT_STATE_UNKNOWN = 0,
    CIVIC_TRANSPORT_STATE_RUNNING,
    CIVIC_TRANSPORT_STATE_STOPPED,
    CIVIC_TRANSPORT_STATE_BUS_OFF,
    CIVIC_TRANSPORT_STATE_RECOVERING,
    CIVIC_TRANSPORT_STATE_ERROR
} civic_transport_controller_state_t;

typedef struct {
    const char *frame_id;
    const char *session_id;
    uint64_t observed_monotonic_us;
    uint32_t arbitration_id;
    uint8_t dlc;
    uint8_t data[8];
    bool extended_id;
    bool remote_frame;
    uint64_t dropped_frames_before;
    uint64_t dropped_frames_after;
    civic_transport_controller_state_t controller_state;
} civic_transport_record_t;

typedef enum {
    CIVIC_TRANSPORT_FORMAT_OK = 0,
    CIVIC_TRANSPORT_FORMAT_INVALID_ARGUMENT,
    CIVIC_TRANSPORT_FORMAT_INVALID_FRAME,
    CIVIC_TRANSPORT_FORMAT_BUFFER_TOO_SMALL
} civic_transport_format_result_t;

/* Formats one schema-v1 can_frame JSON record. No ESP-IDF dependency. */
civic_transport_format_result_t civic_transport_format_frame(
    const civic_transport_record_t *record,
    char *buffer,
    size_t buffer_size
);
