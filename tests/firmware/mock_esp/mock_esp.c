#define _POSIX_C_SOURCE 200809L

#include "mock_esp.h"
#include "sdkconfig.h"

#include <errno.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "driver/gpio.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#define MOCK_TWAI_RX_CAPACITY 256U
#define MOCK_GPIO_COUNT 40U

struct civic_mock_queue {
    pthread_mutex_t mutex;
    pthread_cond_t has_items;
    size_t capacity;
    size_t item_size;
    size_t head;
    size_t count;
    unsigned char *items;
};

static pthread_mutex_t g_driver_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_driver_has_items = PTHREAD_COND_INITIALIZER;
static bool g_driver_installed;
static twai_general_config_t g_general_config;
static twai_timing_config_t g_timing_config;
static twai_status_info_t g_status;
static twai_message_t g_driver_rx[MOCK_TWAI_RX_CAPACITY];
static size_t g_driver_rx_head;
static size_t g_driver_rx_count;
static twai_message_t g_last_tx;
static uint32_t g_tx_count;
static int g_gpio_levels[MOCK_GPIO_COUNT];
static int64_t g_clock_us = 1000;

static void realtime_deadline(struct timespec *deadline, uint32_t timeout_ms)
{
    (void)clock_gettime(CLOCK_REALTIME, deadline);
    deadline->tv_sec += (time_t)(timeout_ms / 1000U);
    deadline->tv_nsec += (long)(timeout_ms % 1000U) * 1000000L;
    if (deadline->tv_nsec >= 1000000000L) {
        ++deadline->tv_sec;
        deadline->tv_nsec -= 1000000000L;
    }
}

void mock_twai_reset(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    g_driver_installed = false;
    memset(&g_general_config, 0, sizeof(g_general_config));
    memset(&g_timing_config, 0, sizeof(g_timing_config));
    memset(&g_status, 0, sizeof(g_status));
    g_status.state = TWAI_STATE_STOPPED;
    memset(g_driver_rx, 0, sizeof(g_driver_rx));
    g_driver_rx_head = 0U;
    g_driver_rx_count = 0U;
    memset(&g_last_tx, 0, sizeof(g_last_tx));
    g_tx_count = 0U;
    g_clock_us = 1000;
    pthread_cond_broadcast(&g_driver_has_items);
    pthread_mutex_unlock(&g_driver_mutex);

    memset(g_gpio_levels, 0, sizeof(g_gpio_levels));
    g_gpio_levels[CONFIG_CIVIC_INTERLOCK_SENSE_GPIO] = CONFIG_CIVIC_INTERLOCK_ACTIVE_LEVEL;
    g_gpio_levels[CONFIG_CIVIC_TX_GATE_REQUEST_GPIO] = 0;
}

void mock_twai_inject(const twai_message_t *message)
{
    if (message == NULL) {
        return;
    }
    pthread_mutex_lock(&g_driver_mutex);
    if (g_driver_rx_count < MOCK_TWAI_RX_CAPACITY) {
        const size_t tail = (g_driver_rx_head + g_driver_rx_count) % MOCK_TWAI_RX_CAPACITY;
        g_driver_rx[tail] = *message;
        ++g_driver_rx_count;
        pthread_cond_broadcast(&g_driver_has_items);
    } else {
        ++g_status.rx_missed_count;
    }
    pthread_mutex_unlock(&g_driver_mutex);
}

void mock_twai_set_state(twai_state_t state)
{
    pthread_mutex_lock(&g_driver_mutex);
    g_status.state = state;
    pthread_cond_broadcast(&g_driver_has_items);
    pthread_mutex_unlock(&g_driver_mutex);
}

void mock_twai_set_error_stats(
    uint32_t tx_error,
    uint32_t rx_error,
    uint32_t rx_missed,
    uint32_t rx_overrun
)
{
    pthread_mutex_lock(&g_driver_mutex);
    g_status.tx_error_counter = tx_error;
    g_status.rx_error_counter = rx_error;
    g_status.rx_missed_count = rx_missed;
    g_status.rx_overrun_count = rx_overrun;
    pthread_mutex_unlock(&g_driver_mutex);
}

uint32_t mock_twai_tx_count(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    const uint32_t result = g_tx_count;
    pthread_mutex_unlock(&g_driver_mutex);
    return result;
}

bool mock_twai_last_tx(twai_message_t *out_message)
{
    if (out_message == NULL) {
        return false;
    }
    pthread_mutex_lock(&g_driver_mutex);
    const bool has_tx = g_tx_count > 0U;
    if (has_tx) {
        *out_message = g_last_tx;
    }
    pthread_mutex_unlock(&g_driver_mutex);
    return has_tx;
}

twai_mode_t mock_twai_installed_mode(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    const twai_mode_t result = g_general_config.mode;
    pthread_mutex_unlock(&g_driver_mutex);
    return result;
}

int mock_gpio_level(int gpio_num)
{
    if (gpio_num < 0 || gpio_num >= (int)MOCK_GPIO_COUNT) {
        return -1;
    }
    return __atomic_load_n(&g_gpio_levels[gpio_num], __ATOMIC_SEQ_CST);
}

void mock_set_interlock_level(int level)
{
    __atomic_store_n(
        &g_gpio_levels[CONFIG_CIVIC_INTERLOCK_SENSE_GPIO],
        level,
        __ATOMIC_SEQ_CST
    );
}

void mock_esp_log(const char *level, const char *tag, const char *format, ...)
{
    (void)level;
    (void)tag;
    (void)format;
}

void esp_fill_random(void *buffer, size_t length)
{
    static uint32_t state = UINT32_C(0xC1A1C0DE);
    uint8_t *bytes = buffer;
    for (size_t i = 0U; i < length; ++i) {
        state = state * UINT32_C(1664525) + UINT32_C(1013904223);
        bytes[i] = (uint8_t)(state >> 24);
    }
}

const char *esp_err_to_name(esp_err_t error)
{
    switch (error) {
    case ESP_OK:
        return "ESP_OK";
    case ESP_FAIL:
        return "ESP_FAIL";
    case ESP_ERR_NO_MEM:
        return "ESP_ERR_NO_MEM";
    case ESP_ERR_INVALID_ARG:
        return "ESP_ERR_INVALID_ARG";
    case ESP_ERR_INVALID_STATE:
        return "ESP_ERR_INVALID_STATE";
    case ESP_ERR_NOT_FOUND:
        return "ESP_ERR_NOT_FOUND";
    case ESP_ERR_NOT_SUPPORTED:
        return "ESP_ERR_NOT_SUPPORTED";
    case ESP_ERR_TIMEOUT:
        return "ESP_ERR_TIMEOUT";
    default:
        return "ESP_ERR_UNKNOWN";
    }
}

esp_err_t gpio_config(const gpio_config_t *config)
{
    return config == NULL || config->pin_bit_mask == 0U
        ? ESP_ERR_INVALID_ARG : ESP_OK;
}

int gpio_get_level(gpio_num_t gpio_num)
{
    return mock_gpio_level(gpio_num);
}

esp_err_t gpio_set_level(gpio_num_t gpio_num, int level)
{
    if (gpio_num < 0 || gpio_num >= (gpio_num_t)MOCK_GPIO_COUNT) {
        return ESP_ERR_INVALID_ARG;
    }
    __atomic_store_n(&g_gpio_levels[gpio_num], level != 0, __ATOMIC_SEQ_CST);
    return ESP_OK;
}

int64_t esp_timer_get_time(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    g_clock_us += 1000;
    const int64_t result = g_clock_us;
    pthread_mutex_unlock(&g_driver_mutex);
    return result;
}

QueueHandle_t xQueueCreate(UBaseType_t length, UBaseType_t item_size)
{
    if (length == 0U || item_size == 0U) {
        return NULL;
    }
    struct civic_mock_queue *queue = calloc(1U, sizeof(*queue));
    if (queue == NULL) {
        return NULL;
    }
    queue->items = calloc((size_t)length, (size_t)item_size);
    if (queue->items == NULL) {
        free(queue);
        return NULL;
    }
    queue->capacity = length;
    queue->item_size = item_size;
    (void)pthread_mutex_init(&queue->mutex, NULL);
    (void)pthread_cond_init(&queue->has_items, NULL);
    return queue;
}

BaseType_t xQueueSend(QueueHandle_t queue, const void *item, TickType_t wait_ticks)
{
    (void)wait_ticks;
    if (queue == NULL || item == NULL) {
        return pdFALSE;
    }
    pthread_mutex_lock(&queue->mutex);
    if (queue->count == queue->capacity) {
        pthread_mutex_unlock(&queue->mutex);
        return pdFALSE;
    }
    const size_t tail = (queue->head + queue->count) % queue->capacity;
    memcpy(queue->items + tail * queue->item_size, item, queue->item_size);
    ++queue->count;
    pthread_cond_signal(&queue->has_items);
    pthread_mutex_unlock(&queue->mutex);
    return pdTRUE;
}

BaseType_t xQueueReceive(QueueHandle_t queue, void *item, TickType_t wait_ticks)
{
    if (queue == NULL || item == NULL) {
        return pdFALSE;
    }
    pthread_mutex_lock(&queue->mutex);
    struct timespec deadline;
    if (wait_ticks > 0U && wait_ticks != portMAX_DELAY) {
        realtime_deadline(&deadline, wait_ticks);
    }
    while (queue->count == 0U) {
        if (wait_ticks == 0U) {
            pthread_mutex_unlock(&queue->mutex);
            return pdFALSE;
        }
        int err;
        if (wait_ticks == portMAX_DELAY) {
            err = pthread_cond_wait(&queue->has_items, &queue->mutex);
        } else {
            err = pthread_cond_timedwait(&queue->has_items, &queue->mutex, &deadline);
        }
        if (err == ETIMEDOUT) {
            pthread_mutex_unlock(&queue->mutex);
            return pdFALSE;
        }
    }

    memcpy(item, queue->items + queue->head * queue->item_size, queue->item_size);
    queue->head = (queue->head + 1U) % queue->capacity;
    --queue->count;
    pthread_mutex_unlock(&queue->mutex);
    return pdTRUE;
}

UBaseType_t uxQueueMessagesWaiting(QueueHandle_t queue)
{
    if (queue == NULL) {
        return 0U;
    }
    pthread_mutex_lock(&queue->mutex);
    const UBaseType_t count = (UBaseType_t)queue->count;
    pthread_mutex_unlock(&queue->mutex);
    return count;
}

void vQueueDelete(QueueHandle_t queue)
{
    if (queue != NULL) {
        pthread_mutex_destroy(&queue->mutex);
        pthread_cond_destroy(&queue->has_items);
        free(queue->items);
        free(queue);
    }
}

struct task_context {
    TaskFunction_t function;
    void *parameter;
};

static void *task_trampoline(void *context)
{
    struct task_context *task = context;
    const TaskFunction_t function = task->function;
    void *parameter = task->parameter;
    free(task);
    function(parameter);
    return NULL;
}

BaseType_t xTaskCreate(
    TaskFunction_t task_function,
    const char *name,
    uint32_t stack_depth,
    void *parameter,
    UBaseType_t priority,
    TaskHandle_t *task_handle
)
{
    (void)name;
    (void)stack_depth;
    (void)priority;
    if (task_function == NULL) {
        return pdFALSE;
    }
    struct task_context *context = malloc(sizeof(*context));
    if (context == NULL) {
        return pdFALSE;
    }
    context->function = task_function;
    context->parameter = parameter;
    pthread_t thread;
    if (pthread_create(&thread, NULL, task_trampoline, context) != 0) {
        free(context);
        return pdFALSE;
    }
    (void)pthread_detach(thread);
    if (task_handle != NULL) {
        *task_handle = NULL;
    }
    return pdPASS;
}

void vTaskDelay(TickType_t ticks)
{
    struct timespec delay = {
        .tv_sec = (time_t)(ticks / 1000U),
        .tv_nsec = (long)(ticks % 1000U) * 1000000L,
    };
    (void)nanosleep(&delay, NULL);
}

esp_err_t twai_driver_install(
    const twai_general_config_t *general,
    const twai_timing_config_t *timing,
    const twai_filter_config_t *filter
)
{
    if (general == NULL || timing == NULL || filter == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    pthread_mutex_lock(&g_driver_mutex);
    if (g_driver_installed) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }
    g_general_config = *general;
    g_timing_config = *timing;
    g_driver_installed = true;
    g_status.state = TWAI_STATE_STOPPED;
    g_status.msgs_to_rx = 0U;
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_driver_uninstall(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    g_driver_installed = false;
    g_status.state = TWAI_STATE_STOPPED;
    pthread_cond_broadcast(&g_driver_has_items);
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_start(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    if (!g_driver_installed || g_status.state == TWAI_STATE_RUNNING) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }
    g_status.state = TWAI_STATE_RUNNING;
    pthread_cond_broadcast(&g_driver_has_items);
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_stop(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    if (!g_driver_installed || g_status.state != TWAI_STATE_RUNNING) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }
    g_status.state = TWAI_STATE_STOPPED;
    g_driver_rx_count = 0U;
    pthread_cond_broadcast(&g_driver_has_items);
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_receive(twai_message_t *message, TickType_t timeout_ticks)
{
    if (message == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    pthread_mutex_lock(&g_driver_mutex);
    /* ESP-IDF documents INVALID_STATE only for a driver that is not installed; a bus-off or
     * stopped controller simply delivers no new frames, so this mock times out instead. */
    if (!g_driver_installed) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }

    struct timespec deadline;
    realtime_deadline(&deadline, timeout_ticks);
    while (g_driver_rx_count == 0U) {
        if (timeout_ticks == 0U) {
            pthread_mutex_unlock(&g_driver_mutex);
            return ESP_ERR_TIMEOUT;
        }
        const int err = pthread_cond_timedwait(
            &g_driver_has_items, &g_driver_mutex, &deadline
        );
        if (err == ETIMEDOUT) {
            pthread_mutex_unlock(&g_driver_mutex);
            return ESP_ERR_TIMEOUT;
        }
    }
    *message = g_driver_rx[g_driver_rx_head];
    g_driver_rx_head = (g_driver_rx_head + 1U) % MOCK_TWAI_RX_CAPACITY;
    --g_driver_rx_count;
    g_status.msgs_to_rx = (uint32_t)g_driver_rx_count;
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_transmit(const twai_message_t *message, TickType_t timeout_ticks)
{
    (void)timeout_ticks;
    if (message == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    pthread_mutex_lock(&g_driver_mutex);
    if (!g_driver_installed || g_status.state != TWAI_STATE_RUNNING) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }
    if (g_general_config.mode == TWAI_MODE_LISTEN_ONLY) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_NOT_SUPPORTED;
    }
    g_last_tx = *message;
    ++g_tx_count;
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_get_status_info(twai_status_info_t *status)
{
    if (status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    pthread_mutex_lock(&g_driver_mutex);
    if (!g_driver_installed) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }
    *status = g_status;
    status->msgs_to_rx = (uint32_t)g_driver_rx_count;
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}

esp_err_t twai_initiate_recovery(void)
{
    pthread_mutex_lock(&g_driver_mutex);
    if (!g_driver_installed || g_status.state != TWAI_STATE_BUS_OFF) {
        pthread_mutex_unlock(&g_driver_mutex);
        return ESP_ERR_INVALID_STATE;
    }
    g_status.state = TWAI_STATE_RECOVERING;
    g_driver_rx_count = 0U;
    pthread_cond_broadcast(&g_driver_has_items);
    pthread_mutex_unlock(&g_driver_mutex);
    return ESP_OK;
}
