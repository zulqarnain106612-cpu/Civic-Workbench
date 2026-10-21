#include "civic_safety_policy.h"

bool civic_safety_tx_permitted(const civic_safety_inputs_t *inputs)
{
    if (inputs == 0) {
        return false;
    }

    return inputs->software_armed
        && inputs->physical_interlock_active
        && inputs->controller_running
        && !inputs->controller_faulted
        && inputs->hardware_configuration_verified;
}
