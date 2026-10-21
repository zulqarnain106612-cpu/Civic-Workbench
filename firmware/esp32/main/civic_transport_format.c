#include "civic_transport_format.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

static bool is_uuid(const char *text)
{
    if (text == NULL || strlen(text) != CIVIC_TRANSPORT_UUID_LENGTH) {
        return false;
    }

    for (size_t i = 0; i < CIVIC_TRANSPORT_UUID_LENGTH; ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (text[i] != '-') {
                return false;
            }
            continue;
        }

        const char c = text[i];
        const bool is_hex = (c >= '0' && c <= '9')
            || (c >= 'a' && c <= 'f')
            || (c >= 'A' && c <= 'F');
        if (!is_hex) {
            return false;
        }
    }
    return true;
}

static const char *state_name(civic_transport_controller_state_t state)
{
    switch (state) {
    case CIVIC_TRANSPORT_STATE_RUNNING:
        return "running";
    case CIVIC_TRANSPORT_STATE_STOPPED:
        return "stopped";
    case CIVIC_TRANSPORT_STATE_BUS_OFF:
        return "bus_off";
    case CIVIC_TRANSPORT_STATE_RECOVERING:
        return "recovering";
    case CIVIC_TRANSPORT_STATE_ERROR:
        return "error";
    case CIVIC_TRANSPORT_STATE_UNKNOWN:
    default:
        return "unknown";
    }
}

static civic_transport_format_result_t appendf(
    char *buffer,
    size_t capacity,
    size_t *used,
    const char *format,
    ...
)
{
    if (*used >= capacity) {
        return CIVIC_TRANSPORT_FORMAT_BUFFER_TOO_SMALL;
    }

    va_list args;
    va_start(args, format);
    const int written = vsnprintf(buffer + *used, capacity - *used, format, args);
    va_end(args);

    if (written < 0 || (size_t)written >= capacity - *used) {
        return CIVIC_TRANSPORT_FORMAT_BUFFER_TOO_SMALL;
    }

    *used += (size_t)written;
    return CIVIC_TRANSPORT_FORMAT_OK;
}

civic_transport_format_result_t civic_transport_format_frame(
    const civic_transport_record_t *record,
    char *buffer,
    size_t buffer_size
)
{
    if (record == NULL || buffer == NULL || buffer_size == 0U) {
        return CIVIC_TRANSPORT_FORMAT_INVALID_ARGUMENT;
    }
    buffer[0] = '\0';

    if (!is_uuid(record->frame_id) || !is_uuid(record->session_id)
        || record->dlc > 8U
        || (!record->extended_id && record->arbitration_id > 0x7FFU)
        || (record->extended_id && record->arbitration_id > 0x1FFFFFFFU)
        || record->observed_monotonic_us > UINT64_MAX / 1000ULL
        || record->controller_state > CIVIC_TRANSPORT_STATE_ERROR) {
        return CIVIC_TRANSPORT_FORMAT_INVALID_FRAME;
    }

    size_t used = 0U;
    civic_transport_format_result_t result = appendf(
        buffer, buffer_size, &used,
        "{\"schema_version\":1,\"record_type\":\"can_frame\","
        "\"frame_id\":\"%s\",\"session_id\":\"%s\","
        "\"captured_monotonic_ns\":%llu,\"clock_source\":\"monotonic_only\","
        "\"arbitration_id\":%lu,\"id_format\":\"%s\","
        "\"frame_type\":\"%s\",\"dlc\":%u,\"payload\":[",
        record->frame_id,
        record->session_id,
        (unsigned long long)(record->observed_monotonic_us * 1000ULL),
        (unsigned long)record->arbitration_id,
        record->extended_id ? "extended" : "standard",
        record->remote_frame ? "remote" : "data",
        (unsigned)record->dlc
    );
    if (result != CIVIC_TRANSPORT_FORMAT_OK) {
        buffer[0] = '\0';
        return result;
    }

    const uint8_t payload_length = record->remote_frame ? 0U : record->dlc;
    for (uint8_t i = 0U; i < payload_length; ++i) {
        result = appendf(
            buffer, buffer_size, &used,
            "%s%u", i == 0U ? "" : ",", (unsigned)record->data[i]
        );
        if (result != CIVIC_TRANSPORT_FORMAT_OK) {
            buffer[0] = '\0';
            return result;
        }
    }

    result = appendf(
        buffer, buffer_size, &used,
        "],\"direction\":\"rx\",\"capture_source\":\"hardware\","
        "\"controller_state\":\"%s\",\"dropped_frames_before\":%llu,"
        "\"dropped_frames_after\":%llu}",
        state_name(record->controller_state),
        (unsigned long long)record->dropped_frames_before,
        (unsigned long long)record->dropped_frames_after
    );
    if (result != CIVIC_TRANSPORT_FORMAT_OK) {
        buffer[0] = '\0';
        return result;
    }

    return CIVIC_TRANSPORT_FORMAT_OK;
}
