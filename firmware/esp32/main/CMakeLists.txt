idf_component_register(
    SRCS "app_main.c" "civic_can.c" "civic_safety.c" "civic_safety_policy.c"
    INCLUDE_DIRS "."
    REQUIRES driver
)
