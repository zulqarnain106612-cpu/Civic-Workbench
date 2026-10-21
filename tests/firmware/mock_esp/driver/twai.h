#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"

typedef enum {
    TWAI_STATE_STOPPED = 0,
    TWAI_STATE_RUNNING,
    TWAI_STATE_BUS_OFF,
    TWAI_STATE_RECOVERING
} twai_state_t;

typedef enum {
    TWAI_MODE_NORMAL = 0,
    TWAI_MODE_NO_ACK,
    TWAI_MODE_LISTEN_ONLY
} twai_mode_t;

typedef struct {
    uint32_t identifier;
    uint8_t data_length_code;
    uint8_t data[8];
    bool extd;
    bool rtr;
} twai_message_t;

typedef struct {
    int controller_id;
    twai_mode_t mode;
    int tx_io;
    int rx_io;
    int clkout_io;
    int bus_off_io;
    uint32_t tx_queue_len;
    uint32_t rx_queue_len;
    uint32_t alerts_enabled;
    uint32_t clkout_divider;
} twai_general_config_t;

typedef struct {
    uint32_t bitrate;
} twai_timing_config_t;

typedef struct {
    uint32_t acceptance_code;
} twai_filter_config_t;

typedef struct {
    twai_state_t state;
    uint32_t msgs_to_tx;
    uint32_t msgs_to_rx;
    uint32_t tx_error_counter;
    uint32_t rx_error_counter;
    uint32_t tx_failed_count;
    uint32_t rx_missed_count;
    uint32_t rx_overrun_count;
    uint32_t arb_lost_count;
    uint32_t bus_error_count;
} twai_status_info_t;

#define TWAI_GENERAL_CONFIG_DEFAULT(tx, rx, selected_mode) \
    ((twai_general_config_t){ .controller_id = 0, .mode = (selected_mode), .tx_io = (tx), .rx_io = (rx), .clkout_io = -1, .bus_off_io = -1, .tx_queue_len = 5, .rx_queue_len = 64, .alerts_enabled = 0, .clkout_divider = 0 })
#define TWAI_TIMING_CONFIG_125KBITS() { .bitrate = 125000 }
#define TWAI_TIMING_CONFIG_250KBITS() { .bitrate = 250000 }
#define TWAI_TIMING_CONFIG_500KBITS() { .bitrate = 500000 }
#define TWAI_TIMING_CONFIG_1MBITS() { .bitrate = 1000000 }
#define TWAI_FILTER_CONFIG_ACCEPT_ALL() ((twai_filter_config_t){ .acceptance_code = 0xFFFFFFFFU })

esp_err_t twai_driver_install(
    const twai_general_config_t *general,
    const twai_timing_config_t *timing,
    const twai_filter_config_t *filter
);
esp_err_t twai_driver_uninstall(void);
esp_err_t twai_start(void);
esp_err_t twai_stop(void);
esp_err_t twai_receive(twai_message_t *message, TickType_t timeout_ticks);
esp_err_t twai_transmit(const twai_message_t *message, TickType_t timeout_ticks);
esp_err_t twai_get_status_info(twai_status_info_t *status);
esp_err_t twai_initiate_recovery(void);
