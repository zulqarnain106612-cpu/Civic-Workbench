#pragma once

#include <stdbool.h>

typedef struct {
    bool software_armed;
    bool physical_interlock_active;
    bool controller_running;
    bool controller_faulted;
    bool hardware_configuration_verified;
} civic_safety_inputs_t;

/* Pure fail-closed policy; it does not itself drive a transceiver or send CAN. */
bool civic_safety_tx_permitted(const civic_safety_inputs_t *inputs);
