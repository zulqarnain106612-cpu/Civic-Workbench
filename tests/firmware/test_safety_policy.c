#include <assert.h>
#include <stdio.h>

#include "../../firmware/esp32/main/civic_safety_policy.h"

static civic_safety_inputs_t all_permissive(void)
{
    civic_safety_inputs_t state = {
        .software_armed = true,
        .physical_interlock_active = true,
        .controller_running = true,
        .controller_faulted = false,
        .hardware_configuration_verified = true,
    };
    return state;
}

int main(void)
{
    assert(!civic_safety_tx_permitted(0));

    civic_safety_inputs_t state = all_permissive();
    assert(civic_safety_tx_permitted(&state));

    state.software_armed = false;
    assert(!civic_safety_tx_permitted(&state));
    state = all_permissive();

    state.physical_interlock_active = false;
    assert(!civic_safety_tx_permitted(&state));
    state = all_permissive();

    state.controller_running = false;
    assert(!civic_safety_tx_permitted(&state));
    state = all_permissive();

    state.controller_faulted = true;
    assert(!civic_safety_tx_permitted(&state));
    state = all_permissive();

    state.hardware_configuration_verified = false;
    assert(!civic_safety_tx_permitted(&state));

    puts("Firmware safety policy: 7 assertions passed");
    return 0;
}
