#pragma once

#include <stdbool.h>
#include "esp_err.h"

/* Internal gate driver. Only civic_can.c may request the gate to be asserted. */
esp_err_t civic_safety_drive_tx_request(bool asserted);
