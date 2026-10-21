#include "civic_can.h"
#include "civic_transport.h"

#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "civic_workbench";

void app_main(void)
{
    ESP_LOGI(TAG, "Civic-Workbench firmware boot");
    ESP_LOGI(TAG, "Default behavior: TX inhibited; no vehicle identifiers or bitrate are assumed");

    esp_err_t transport_err = civic_transport_init();
    if (transport_err == ESP_OK) {
        civic_transport_emit_handshake();
    } else {
        ESP_LOGE(TAG, "Transport initialization failed: %s", esp_err_to_name(transport_err));
    }

    const esp_err_t init_result = civic_can_init();
    if (init_result != ESP_OK) {
        ESP_LOGW(TAG, "Hardware capture unavailable (%s); staying safe and alive", esp_err_to_name(init_result));
    }

    TickType_t last_status_tick = 0;
    for (;;) {
        const TickType_t now = xTaskGetTickCount();
        if (now - last_status_tick >= pdMS_TO_TICKS(1000U)) {
            last_status_tick = now;
            civic_can_diagnostics_t diagnostics;
            if (civic_can_get_diagnostics(&diagnostics) == ESP_OK) {
                civic_transport_emit_device_status(&diagnostics);
                if (diagnostics.driver_installed) {
                    ESP_LOGI(
                        TAG,
                        "CAN state=%d rx=%llu app_q=%u driver_q=%u sw_drop=%llu malformed=%llu "
                        "hw_missed=%lu hw_overrun=%lu tx_capable=%u armed=%u",
                        (int)diagnostics.controller_state,
                        (unsigned long long)diagnostics.rx_frames_dequeued,
                        (unsigned)diagnostics.app_rx_queue_depth,
                        (unsigned)diagnostics.driver_rx_queue_depth,
                        (unsigned long long)diagnostics.software_dropped_frames,
                        (unsigned long long)diagnostics.malformed_frames,
                        (unsigned long)diagnostics.rx_missed_count,
                        (unsigned long)diagnostics.rx_overrun_count,
                        diagnostics.transmit_capable ? 1U : 0U,
                        diagnostics.software_armed ? 1U : 0U
                    );
                }
            }
        }

        if (civic_can_controller_ready()) {
            civic_can_frame_t frame;
            const esp_err_t receive_err = civic_can_receive(&frame, 100U);
            if (receive_err == ESP_OK) {
                civic_can_diagnostics_t diagnostics;
                if (civic_can_get_diagnostics(&diagnostics) == ESP_OK) {
                    const esp_err_t transport_result = civic_transport_emit_can_frame(&frame, &diagnostics);
                    if (transport_result != ESP_OK) {
                        ESP_LOGW(TAG, "Could not serialize CAN frame: %s", esp_err_to_name(transport_result));
                    }
                }
            } else if (receive_err != ESP_ERR_TIMEOUT) {
                ESP_LOGW(TAG, "Frame ingress receive returned: %s", esp_err_to_name(receive_err));
                vTaskDelay(pdMS_TO_TICKS(20U));
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(100U));
        }
    }
}
