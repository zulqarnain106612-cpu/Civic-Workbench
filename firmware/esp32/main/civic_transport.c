#include "civic_transport.h"

#include <stdio.h>
#include <string.h>

#include "civic_transport_format.h"
#include "esp_random.h"
#include "esp_timer.h"

#define CIVIC_TRANSPORT_LINE_CAPACITY 512U
#define CIVIC_WORKBENCH_FIRMWARE_VERSION "0.3.0-dev"

static char s_session_id[CIVIC_TRANSPORT_UUID_LENGTH + 1U];
static bool s_initialized;

static void make_uuid(char output[CIVIC_TRANSPORT_UUID_LENGTH + 1U])
{
    uint8_t bytes[16];
    esp_fill_random(bytes, sizeof(bytes));
    bytes[6] = (uint8_t)((bytes[6] & 0x0FU) | 0x40U);
    bytes[8] = (uint8_t)((bytes[8] & 0x3FU) | 0x80U);

    (void)snprintf(
        output, CIVIC_TRANSPORT_UUID_LENGTH + 1U,
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        bytes[0], bytes[1], bytes[2], bytes[3],
        bytes[4], bytes[5], bytes[6], bytes[7],
        bytes[8], bytes[9], bytes[10], bytes[11],
        bytes[12], bytes[13], bytes[14], bytes[15]
    );
}

static const char *wire_controller_state(civic_can_controller_state_t state)
{
    switch (state) {
    case CIVIC_CAN_CONTROLLER_RUNNING:
        return "running";
    case CIVIC_CAN_CONTROLLER_STOPPED:
        return "stopped";
    case CIVIC_CAN_CONTROLLER_BUS_OFF:
        return "bus_off";
    case CIVIC_CAN_CONTROLLER_RECOVERING:
        return "recovering";
    case CIVIC_CAN_CONTROLLER_ERROR:
        return "error";
    case CIVIC_CAN_CONTROLLER_UNKNOWN:
    default:
        return "unknown";
    }
}

static civic_transport_controller_state_t transport_controller_state(
    civic_can_controller_state_t state
)
{
    switch (state) {
    case CIVIC_CAN_CONTROLLER_RUNNING:
        return CIVIC_TRANSPORT_STATE_RUNNING;
    case CIVIC_CAN_CONTROLLER_STOPPED:
        return CIVIC_TRANSPORT_STATE_STOPPED;
    case CIVIC_CAN_CONTROLLER_BUS_OFF:
        return CIVIC_TRANSPORT_STATE_BUS_OFF;
    case CIVIC_CAN_CONTROLLER_RECOVERING:
        return CIVIC_TRANSPORT_STATE_RECOVERING;
    case CIVIC_CAN_CONTROLLER_ERROR:
        return CIVIC_TRANSPORT_STATE_ERROR;
    case CIVIC_CAN_CONTROLLER_UNKNOWN:
    default:
        return CIVIC_TRANSPORT_STATE_UNKNOWN;
    }
}

static void append_fault(char *faults, size_t capacity, bool *first, const char *code)
{
    const size_t used = strlen(faults);
    if (used >= capacity) {
        return;
    }
    const int written = snprintf(
        faults + used, capacity - used,
        "%s\"%s\"", *first ? "" : ",", code
    );
    if (written > 0 && (size_t)written < capacity - used) {
        *first = false;
    }
}

static void emit_line(const char *json_line)
{
    /* Host serial readers ignore non-CW1 diagnostic lines from ESP-IDF logging. */
    (void)printf("CW1 %s\n", json_line);
    (void)fflush(stdout);
}

esp_err_t civic_transport_init(void)
{
    make_uuid(s_session_id);
    s_initialized = true;
    return ESP_OK;
}

void civic_transport_emit_handshake(void)
{
    if (!s_initialized) {
        return;
    }

    char line[384];
    const int length = snprintf(
        line, sizeof(line),
        "{\"schema_version\":1,\"record_type\":\"handshake\","
        "\"agent_role\":\"firmware\",\"agent_id\":\"civic-workbench-esp32\","
        "\"software_version\":\"%s\","
        "\"supported_schema_versions\":{\"handshake\":[1],\"can_frame\":[1],\"device_status\":[1]},"
        "\"supported_message_types\":[\"can_frame\",\"device_status\"]}",
        CIVIC_WORKBENCH_FIRMWARE_VERSION
    );
    if (length > 0 && (size_t)length < sizeof(line)) {
        emit_line(line);
    }
}

esp_err_t civic_transport_emit_can_frame(
    const civic_can_frame_t *frame,
    const civic_can_diagnostics_t *diagnostics
)
{
    if (!s_initialized || frame == NULL || diagnostics == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    char frame_id[CIVIC_TRANSPORT_UUID_LENGTH + 1U];
    char line[CIVIC_TRANSPORT_LINE_CAPACITY];
    make_uuid(frame_id);

    civic_transport_record_t record = {
        .frame_id = frame_id,
        .session_id = s_session_id,
        .observed_monotonic_us = frame->observed_monotonic_us,
        .arbitration_id = frame->arbitration_id,
        .dlc = frame->dlc,
        .extended_id = frame->extended_id,
        .remote_frame = frame->remote_frame,
        .dropped_frames_before = frame->dropped_frames_before,
        .dropped_frames_after = frame->dropped_frames_after,
        .controller_state = transport_controller_state(diagnostics->controller_state),
    };
    memcpy(record.data, frame->data, sizeof(record.data));

    const civic_transport_format_result_t result = civic_transport_format_frame(
        &record, line, sizeof(line)
    );
    if (result != CIVIC_TRANSPORT_FORMAT_OK) {
        return result == CIVIC_TRANSPORT_FORMAT_BUFFER_TOO_SMALL
            ? ESP_ERR_NO_MEM : ESP_ERR_INVALID_ARG;
    }

    emit_line(line);
    return ESP_OK;
}

void civic_transport_emit_device_status(const civic_can_diagnostics_t *diagnostics)
{
    if (!s_initialized || diagnostics == NULL) {
        return;
    }

    const uint64_t observed_ns = (uint64_t)esp_timer_get_time() * 1000ULL;
    const uint64_t dropped_total = (uint64_t)diagnostics->software_dropped_frames
        + diagnostics->rx_missed_count + diagnostics->rx_overrun_count;
    char faults[256] = "";
    bool first = true;

    if (!diagnostics->driver_installed) {
        append_fault(faults, sizeof(faults), &first, "hardware_capture_unavailable");
    } else {
        if (diagnostics->controller_state == CIVIC_CAN_CONTROLLER_BUS_OFF) {
            append_fault(faults, sizeof(faults), &first, "twai_bus_off");
        }
        if (diagnostics->controller_state == CIVIC_CAN_CONTROLLER_RECOVERING) {
            append_fault(faults, sizeof(faults), &first, "twai_recovery_in_progress");
        }
        if (diagnostics->controller_state == CIVIC_CAN_CONTROLLER_STOPPED) {
            append_fault(faults, sizeof(faults), &first, "twai_controller_stopped");
        }
        if (diagnostics->controller_state == CIVIC_CAN_CONTROLLER_ERROR) {
            append_fault(faults, sizeof(faults), &first, "twai_controller_error");
        }
        if (diagnostics->tx_error_counter >= CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD
            || diagnostics->rx_error_counter >= CIVIC_CAN_TX_ERROR_COUNTER_INHIBIT_THRESHOLD) {
            append_fault(faults, sizeof(faults), &first, "twai_error_counter_inhibit");
        }
        if (diagnostics->software_dropped_frames > 0U) {
            append_fault(faults, sizeof(faults), &first, "software_rx_queue_drop");
        }
        if (diagnostics->rx_missed_count > 0U) {
            append_fault(faults, sizeof(faults), &first, "twai_rx_queue_missed");
        }
        if (diagnostics->rx_overrun_count > 0U) {
            append_fault(faults, sizeof(faults), &first, "twai_rx_fifo_overrun");
        }
        if (diagnostics->tx_failed_count > 0U) {
            append_fault(faults, sizeof(faults), &first, "twai_tx_failed");
        }
    }

    char line[768];
    char bitrate_json[16];
    if (diagnostics->driver_installed) {
        (void)snprintf(bitrate_json, sizeof(bitrate_json), "%lu",
            (unsigned long)diagnostics->bitrate_bps);
    } else {
        (void)snprintf(bitrate_json, sizeof(bitrate_json), "null");
    }
    const int length = snprintf(
        line, sizeof(line),
        "{\"schema_version\":1,\"record_type\":\"device_status\","
        "\"observed_monotonic_ns\":%llu,\"clock_source\":\"monotonic_only\","
        "\"connected\":true,\"controller_state\":\"%s\","
        "\"firmware_version\":\"%s\",\"bitrate_bps\":%s,"
        "\"transmit_capable\":%s,\"software_armed\":%s,"
        "\"software_dropped_frames\":%llu,\"malformed_frames\":%llu,"
        "\"driver_rx_queue_depth\":%lu,\"app_rx_queue_depth\":%lu,"
        "\"tx_error_counter\":%lu,\"rx_error_counter\":%lu,"
        "\"tx_failed_count\":%lu,\"rx_missed_count\":%lu,\"rx_overrun_count\":%lu,"
        "\"arbitration_lost_count\":%lu,\"bus_error_count\":%lu,"
        "\"dropped_frames_total\":%llu,\"faults\":[%s]}",
        (unsigned long long)observed_ns,
        wire_controller_state(diagnostics->controller_state),
        CIVIC_WORKBENCH_FIRMWARE_VERSION,
        bitrate_json,
        diagnostics->transmit_capable ? "true" : "false",
        diagnostics->software_armed ? "true" : "false",
        (unsigned long long)diagnostics->software_dropped_frames,
        (unsigned long long)diagnostics->malformed_frames,
        (unsigned long)diagnostics->driver_rx_queue_depth,
        (unsigned long)diagnostics->app_rx_queue_depth,
        (unsigned long)diagnostics->tx_error_counter,
        (unsigned long)diagnostics->rx_error_counter,
        (unsigned long)diagnostics->tx_failed_count,
        (unsigned long)diagnostics->rx_missed_count,
        (unsigned long)diagnostics->rx_overrun_count,
        (unsigned long)diagnostics->arbitration_lost_count,
        (unsigned long)diagnostics->bus_error_count,
        (unsigned long long)dropped_total,
        faults
    );
    if (length > 0 && (size_t)length < sizeof(line)) {
        emit_line(line);
    }
}
