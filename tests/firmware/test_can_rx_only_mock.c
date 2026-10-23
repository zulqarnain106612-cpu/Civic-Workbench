/* Receive-only bench build (hardware Rev B) executes the production CAN core with mocks. */
#define _POSIX_C_SOURCE 200809L

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

#include "sdkconfig.h"
#include "civic_can.h"
#include "mock_esp.h"

#if !defined(CONFIG_CIVIC_RECEIVE_ONLY_BENCH)
#error "This test must be compiled against the receive-only mock sdkconfig"
#endif

static unsigned int s_assertions;

#define CHECK(expression) \
    do { \
        ++s_assertions; \
        if (!(expression)) { \
            fprintf(stderr, "ASSERTION FAILED at %s:%d: %s\n", __FILE__, __LINE__, #expression); \
            return 1; \
        } \
    } while (0)

int main(void)
{
    mock_twai_reset();
    /* No TX gate or interlock GPIO is configured (-1), yet receive-only startup succeeds. */
    CHECK(civic_can_init() == ESP_OK);
    CHECK(civic_can_controller_ready());
    CHECK(mock_twai_installed_mode() == TWAI_MODE_LISTEN_ONLY);

    civic_can_diagnostics_t diagnostics;
    CHECK(civic_can_get_diagnostics(&diagnostics) == ESP_OK);
    CHECK(!diagnostics.transmit_capable);
    CHECK(!diagnostics.software_armed);

    /* Arming and transmission are unavailable in this build. */
    CHECK(civic_can_set_software_armed(true) != ESP_OK);
    civic_can_tx_request_t request = {.arbitration_id = 0x123U, .dlc = 1U, .data = {0xAAU}};
    CHECK(civic_can_transmit_guarded(&request, 10U) == ESP_ERR_NOT_SUPPORTED);
    CHECK(mock_twai_tx_count() == 0U);

    /* Frames are still received. */
    twai_message_t message = {.identifier = 0x321U, .data_length_code = 2U, .data = {1U, 2U}};
    mock_twai_inject(&message);
    civic_can_frame_t frame;
    esp_err_t received = ESP_ERR_TIMEOUT;
    for (unsigned int attempt = 0U; attempt < 50U && received != ESP_OK; ++attempt) {
        received = civic_can_receive(&frame, 20U);
    }
    CHECK(received == ESP_OK);
    CHECK(frame.arbitration_id == 0x321U);
    CHECK(frame.dlc == 2U);

    printf("CAN_RX_ONLY_ASSERTIONS=%u\n", s_assertions);
    return 0;
}
