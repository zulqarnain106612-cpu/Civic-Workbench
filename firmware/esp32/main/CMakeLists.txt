idf_component_register(
    SRCS "app_main.c" "civic_can.c" "civic_safety.c" "civic_safety_policy.c"
         "civic_transport.c" "civic_transport_format.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_timer esp_hw_support
)
