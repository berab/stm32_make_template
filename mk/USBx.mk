### USB-specific
USBX_DIR=$(MIDDLEWARES_PATH)/usbx
USBX_CORE_DIR=$(USBX_DIR)/common/core/src
USBX_DCD_DIR=$(USBX_DIR)/common/usbx_stm32_device_controllers
USBX_DEVICE_CLASSES_DIR=$(USBX_DIR)/common/usbx_device_classes/src/

DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_pcd.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_hal_pcd_ex.c
DRIVER_SOURCES += $(N6_DRIVER_PATH)/Src/stm32n6xx_ll_usb.c

C_DEFS += -DUX_INCLUDE_USER_DEFINE_FILE
C_DEFS += -DUX_STANDALONE
C_DEFS += -DUSE_USB_CDC_CLASS=1

C_INCLUDES += -I$(USBX_DIR)/common/core/inc
C_INCLUDES += -I$(USBX_DIR)/target
C_INCLUDES += -I$(USBX_DIR)/common/usbx_device_classes/inc
C_INCLUDES += -I$(USBX_DIR)/common/usbx_stm32_device_controllers
C_INCLUDES += -I$(USBX_DIR)/ports/generic/inc
C_INCLUDES += -I$(PROJECT_PATH)/User/USBX

# User / USBX
USB_SOURCES += $(PROJECT_PATH)/User/USBX/app_usbx_device.c
USB_SOURCES += $(PROJECT_PATH)/User/USBX/ux_device_cdc_acm.c
USB_SOURCES += $(PROJECT_PATH)/User/USBX/ux_device_descriptors.c

# USBX-Core
C_USBX_CORE += $(USBX_CORE_DIR)/ux_system_error_handler.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_system_initialize.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_system_tasks_run.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_system_uninitialize.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_trace_event_insert.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_trace_event_update.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_trace_object_register.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_trace_object_unregister.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_debug_callback_register.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_debug_log.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_delay_ms.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_descriptor_pack.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_descriptor_parse.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_error_callback_register.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_event_flags_create.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_event_flags_delete.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_event_flags_get.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_event_flags_set.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_long_get.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_long_get_big_endian.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_long_put.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_long_put_big_endian.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_allocate.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_allocate_add_safe.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_allocate_mulc_safe.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_allocate_mulv_safe.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_byte_pool_create.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_byte_pool_search.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_compare.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_copy.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_free.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_free_block_best_get.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_memory_set.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_mutex_create.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_mutex_delete.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_mutex_off.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_mutex_on.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_pci_class_scan.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_pci_read.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_pci_write.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_physical_address.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_semaphore_create.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_semaphore_delete.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_semaphore_get.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_semaphore_put.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_set_interrupt_handler.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_short_get.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_short_get_big_endian.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_short_put.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_short_put_big_endian.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_string_length_check.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_string_length_get.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_string_to_unicode.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_create.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_delete.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_identify.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_relinquish.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_resume.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_schedule_other.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_sleep.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_thread_suspend.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_timer_create.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_timer_delete.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_unicode_to_string.c
C_USBX_CORE += $(USBX_CORE_DIR)/ux_utility_virtual_address.c

# USBX-Device Core stack
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_alternate_setting_get.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_alternate_setting_set.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_class_register.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_class_unregister.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_clear_feature.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_configuration_get.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_configuration_set.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_control_request_process.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_descriptor_send.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_disconnect.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_endpoint_stall.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_get_status.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_initialize.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_interface_delete.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_interface_get.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_interface_set.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_interface_start.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_microsoft_extension_register.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_set_feature.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_tasks_run.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_transfer_abort.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_transfer_all_request_abort.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_transfer_request.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_transfer_run.c
C_USBX_DCORE_STACK += $(USBX_CORE_DIR)/ux_device_stack_uninitialize.c

# C_USBX_CDC-ACM
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_activate.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_bulkin_thread.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_bulkout_thread.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_control_request.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_deactivate.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_entry.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_initialize.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_ioctl.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_read.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_read_run.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_tasks_run.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_unitialize.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_write.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_write_run.c
C_USBX_ACM += $(USBX_DEVICE_CLASSES_DIR)/ux_device_class_cdc_acm_write_with_callback.c

# USBX-Device-controllers
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_callback.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_endpoint_create.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_endpoint_destroy.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_endpoint_reset.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_endpoint_stall.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_endpoint_status.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_frame_number_get.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_function.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_initialize.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_initialize_complete.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_interrupt_handler.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_transfer_abort.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_transfer_request.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_transfer_run.c
C_USBX_DCD += $(USBX_DCD_DIR)/ux_dcd_stm32_uninitialize.c


USB_SOURCES += $(C_USBX_CORE) $(C_USBX_DCORE_STACK) $(C_USBX_ACM) $(C_USBX_DCD)