#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "driver/twai.h"

void mock_twai_reset(void);
void mock_twai_inject(const twai_message_t *message);
void mock_twai_set_state(twai_state_t state);
void mock_twai_set_error_stats(uint32_t tx_error, uint32_t rx_error, uint32_t rx_missed, uint32_t rx_overrun);
uint32_t mock_twai_tx_count(void);
bool mock_twai_last_tx(twai_message_t *out_message);
twai_mode_t mock_twai_installed_mode(void);
int mock_gpio_level(int gpio_num);
void mock_set_interlock_level(int level);
