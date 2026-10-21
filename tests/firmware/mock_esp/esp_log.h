#pragma once

void mock_esp_log(const char *level, const char *tag, const char *format, ...);

#define ESP_LOGE(tag, ...) mock_esp_log("E", tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) mock_esp_log("W", tag, __VA_ARGS__)
#define ESP_LOGI(tag, ...) mock_esp_log("I", tag, __VA_ARGS__)
