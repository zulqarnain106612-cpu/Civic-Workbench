#pragma once

#include "FreeRTOS.h"

typedef void (*TaskFunction_t)(void *);

BaseType_t xTaskCreate(
    TaskFunction_t task_function,
    const char *name,
    uint32_t stack_depth,
    void *parameter,
    UBaseType_t priority,
    TaskHandle_t *task_handle
);
void vTaskDelay(TickType_t ticks);
