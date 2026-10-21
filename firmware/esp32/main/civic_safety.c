#include "civic_safety.h"

#include <stdint.h>
#include "driver/gpio.h"
#include "esp_log.h"
#include "sdkconfig.h"

static const char *TAG = "civic_safety";

static uint64_t gpio_pin_mask(int gpio_num)
{
    /* Caller validates the pin before use; avoid a compile-time -1 shift warning. */
    return UINT64_C(1) << (unsigned int)gpio_num;
}

esp_err_t civic_safety_init_inhibited(void)
{
    const int gate_gpio = CONFIG_CIVIC_TX_GATE_REQUEST_GPIO;
    if (gate_gpio < 0 || gate_gpio > 33
        || (gate_gpio >= 6 && gate_gpio <= 11)
        || gate_gpio == 0 || gate_gpio == 2 || gate_gpio == 5
        || gate_gpio == 12 || gate_gpio == 15
        || gate_gpio == CONFIG_CIVIC_TWAI_TX_GPIO
        || gate_gpio == CONFIG_CIVIC_TWAI_RX_GPIO
        || gate_gpio == CONFIG_CIVIC_INTERLOCK_SENSE_GPIO) {
        /* Reject flash-connected and boot-strapping pins before configuring any output. */
        ESP_LOGW(TAG, "TX gate GPIO is unconfigured, flash-reserved, or a strapping pin; remaining inhibited");
        return ESP_ERR_INVALID_STATE;
    }

    const gpio_config_t output_config = {
        .pin_bit_mask = gpio_pin_mask(gate_gpio),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    esp_err_t err = gpio_config(&output_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure TX gate request: %s", esp_err_to_name(err));
        return err;
    }

    /* Set OFF immediately. External pull-down must keep the request inactive at reset. */
    err = gpio_set_level(CONFIG_CIVIC_TX_GATE_REQUEST_GPIO, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to force TX gate inactive: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "TX gate request initialized INACTIVE; physical gate remains authoritative");
    return ESP_OK;
}
