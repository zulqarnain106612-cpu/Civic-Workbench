#include "civic_can.h"

#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "civic_workbench";

void app_main(void)
{
    ESP_LOGI(TAG, "Civic-Workbench firmware boot");
    ESP_LOGI(TAG, "Default behavior: TX inhibited; no vehicle identifiers or bitrate are assumed");

    const esp_err_t init_result = civic_can_init_listen_only();
    if (init_result != ESP_OK) {
        ESP_LOGW(TAG, "Hardware capture unavailable (%s); staying safe and alive", esp_err_to_name(init_result));
    }

    for (;;) {
        if (civic_can_hardware_ready()) {
            civic_can_frame_t frame;
            const esp_err_t err = civic_can_receive(&frame, 250);
            if (err == ESP_OK) {
                ESP_LOGI(
                    TAG,
                    "RX dequeue_t_us=%llu id=0x%08lx format=%s type=%s dlc=%u",
                    (unsigned long long)frame.observed_monotonic_us,
                    (unsigned long)frame.arbitration_id,
                    frame.extended_id ? "extended" : "standard",
                    frame.remote_frame ? "remote" : "data",
                    (unsigned)frame.dlc
                );
                if (!frame.remote_frame && frame.dlc > 0U && frame.dlc <= sizeof(frame.data)) {
                    ESP_LOG_BUFFER_HEXDUMP(TAG, frame.data, frame.dlc, ESP_LOG_INFO);
                }
            } else if (err != ESP_ERR_TIMEOUT && err != ESP_ERR_NOT_FOUND) {
                ESP_LOGW(TAG, "TWAI receive error: %s", esp_err_to_name(err));
                vTaskDelay(pdMS_TO_TICKS(50));
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}
