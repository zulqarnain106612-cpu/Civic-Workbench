#pragma once

#include "esp_err.h"
#include "civic_safety_policy.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Force the firmware TX-gate request inactive before configuring CAN. */
esp_err_t civic_safety_init_inhibited(void);

#ifdef __cplusplus
}
#endif
