/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    app_usbx_device.c
  * @author  MCD Application Team
  * @brief   USBX Device applicative file
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2024 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "app_usbx_device.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "main.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

static ULONG cdc_acm_interface_number;
static ULONG cdc_acm_configuration_number;
static UX_SLAVE_CLASS_CDC_ACM_PARAMETER cdc_acm_parameter;

/* USER CODE BEGIN PV */
extern PCD_HandleTypeDef hpcd_USB1_OTG_HS;

#if defined ( __ICCARM__ ) /* IAR Compiler */
  #pragma data_alignment=4
#endif /* defined ( __ICCARM__ ) */
__ALIGN_BEGIN static UCHAR ux_device_byte_pool_buffer[USBX_DEVICE_MEMORY_STACK_SIZE]
__ALIGN_END = {0};

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN PFP */
static int usb_init(PCD_HandleTypeDef *pcd_handle, PCD_TypeDef *pcd_instance);
/* USER CODE END PFP */

/**
  * @brief  Application USBX Device Initialization.
  * @param  memory_ptr: memory pointer
  * @retval status
  */
UINT MX_USBX_Device_Init(VOID)
{
  UINT ret = UX_SUCCESS;
  UCHAR *device_framework_high_speed;
  UCHAR *device_framework_full_speed;
  ULONG device_framework_hs_length;
  ULONG device_framework_fs_length;
  ULONG string_framework_length;
  ULONG language_id_framework_length;
  UCHAR *string_framework;
  UCHAR *language_id_framework;
  UCHAR *pointer;

  /* USER CODE BEGIN MX_USBX_Device_Init0 */
  
  /* USER CODE END MX_USBX_Device_Init0 */

  pointer = ux_device_byte_pool_buffer;
 
  /* Initialize USBX Memory */
  if (ux_system_initialize(pointer, USBX_DEVICE_MEMORY_STACK_SIZE, UX_NULL, 0) != UX_SUCCESS)
  {
    /* USER CODE BEGIN USBX_SYSTEM_INITIALIZE_ERROR */
    return UX_ERROR;
    /* USER CODE END USBX_SYSTEM_INITIALIZE_ERROR */
  }

  /* Get Device Framework High Speed and get the length */
  device_framework_high_speed = USBD_Get_Device_Framework_Speed(USBD_HIGH_SPEED,
                                                                &device_framework_hs_length);

  /* Get Device Framework Full Speed and get the length */
  device_framework_full_speed = USBD_Get_Device_Framework_Speed(USBD_FULL_SPEED,
                                                                &device_framework_fs_length);

  /* Get String Framework and get the length */
  string_framework = USBD_Get_String_Framework(&string_framework_length);

  /* Get Language Id Framework and get the length */
  language_id_framework = USBD_Get_Language_Id_Framework(&language_id_framework_length);

  /* Install the device portion of USBX */
  if (ux_device_stack_initialize(device_framework_high_speed,
                                 device_framework_hs_length,
                                 device_framework_full_speed,
                                 device_framework_fs_length,
                                 string_framework,
                                 string_framework_length,
                                 language_id_framework,
                                 language_id_framework_length,
                                 UX_NULL) != UX_SUCCESS)
  {
    /* USER CODE BEGIN USBX_DEVICE_INITIALIZE_ERROR */
    return UX_ERROR;
    /* USER CODE END USBX_DEVICE_INITIALIZE_ERROR */
  }

  /* Initialize the cdc acm class parameters for the device */
  cdc_acm_parameter.ux_slave_class_cdc_acm_instance_activate   = USBD_CDC_ACM_Activate;
  cdc_acm_parameter.ux_slave_class_cdc_acm_instance_deactivate = USBD_CDC_ACM_Deactivate;
  cdc_acm_parameter.ux_slave_class_cdc_acm_parameter_change    = USBD_CDC_ACM_ParameterChange;

  /* USER CODE BEGIN CDC_ACM_PARAMETER */

  /* USER CODE END CDC_ACM_PARAMETER */

  /* Get cdc acm configuration number */
  cdc_acm_configuration_number = USBD_Get_Configuration_Number(CLASS_TYPE_CDC_ACM, 0);

  /* Find cdc acm interface number */
  cdc_acm_interface_number = USBD_Get_Interface_Number(CLASS_TYPE_CDC_ACM, 0);

  /* Initialize the device cdc acm class */
  if (ux_device_stack_class_register(_ux_system_slave_class_cdc_acm_name,
                                     ux_device_class_cdc_acm_entry,
                                     cdc_acm_configuration_number,
                                     cdc_acm_interface_number,
                                     &cdc_acm_parameter) != UX_SUCCESS)
  {
    /* USER CODE BEGIN USBX_DEVICE_CDC_ACM_REGISTER_ERROR */
    return UX_ERROR;
    /* USER CODE END USBX_DEVICE_CDC_ACM_REGISTER_ERROR */
  }

  /* USER CODE BEGIN MX_USBX_Device_Init1 */
  // USBX_APP_Device_Init();
  usb_init(&hpcd_USB1_OTG_HS, USB1_OTG_HS);
  /* USER CODE END MX_USBX_Device_Init1 */

  return HAL_PCD_Start(&hpcd_USB1_OTG_HS);
}

/* USER CODE BEGIN 1 */

static int usb_init(PCD_HandleTypeDef *pcd_handle, PCD_TypeDef *pcd_instance)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = { 0 };
  int ret;

  /* First be sure HSE is turn on */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  ret = HAL_RCC_OscConfig(&RCC_OscInitStruct);
  if (ret)
    return ret;

  /* configure usb */
  pcd_handle->Instance = pcd_instance;
  pcd_handle->Init.dev_endpoints = 9;
  pcd_handle->Init.speed = PCD_SPEED_HIGH;
  pcd_handle->Init.dma_enable = DISABLE;
  pcd_handle->Init.phy_itface = USB_OTG_HS_EMBEDDED_PHY;
  pcd_handle->Init.Sof_enable = DISABLE;
  pcd_handle->Init.low_power_enable = DISABLE;
  pcd_handle->Init.lpm_enable = DISABLE;
  pcd_handle->Init.vbus_sensing_enable = DISABLE;
  pcd_handle->Init.use_dedicated_ep1 = DISABLE;
  pcd_handle->Init.use_external_vbus = DISABLE;
  ret = HAL_PCD_Init(pcd_handle);
  if (ret)
    return ret;
  
  /* Set Rx FIFO */
  HAL_PCDEx_SetRxFiFo(&hpcd_USB1_OTG_HS, 0x200);
  /* Set Tx FIFO 0 */
  HAL_PCDEx_SetTxFiFo(&hpcd_USB1_OTG_HS, 0, 0x10);
  /* Set Tx FIFO 1 */
  HAL_PCDEx_SetTxFiFo(&hpcd_USB1_OTG_HS, 1, 0x80);
  /* Set Tx FIFO 2 */
  HAL_PCDEx_SetTxFiFo(&hpcd_USB1_OTG_HS, 2, 0x20);
  
  ux_dcd_stm32_initialize((ULONG)USB1_OTG_HS, (ULONG)&hpcd_USB1_OTG_HS);

  return 0;
}
/**
  * @brief  USBX_APP_Device_Init
  *         Initialization of USB device.
  * @param  none
  * @retval none
  */
VOID USBX_APP_Device_Init(VOID)
{
  /* USER CODE BEGIN USB_Device_Init_PreTreatment_0 */

  /* USER CODE END USB_Device_Init_PreTreatment_0 */

  HAL_PWREx_EnableVddUSB();
  
  /* USB_OTG_HS init function */
  MX_USB1_OTG_HS_PCD_Init();

  /* USER CODE BEGIN USB_Device_Init_PreTreatment_1 */
  /* Set Rx FIFO */
  HAL_PCDEx_SetRxFiFo(&hpcd_USB1_OTG_HS, 0x200);
  /* Set Tx FIFO 0 */
  HAL_PCDEx_SetTxFiFo(&hpcd_USB1_OTG_HS, 0, USBD_MAX_EP0_SIZE/4);
  /* Initialize and link controller HAL driver */
  ux_dcd_stm32_initialize((ULONG)USB1_OTG_HS, (ULONG)&hpcd_USB1_OTG_HS);

  /* USER CODE BEGIN USB_Device_Init_PostTreatment */
  HAL_PCD_Start(&hpcd_USB1_OTG_HS);
  /* USER CODE END USB_Device_Init_PostTreatment */
}

/**
  * @brief  MX_USBX_Device_Process
  *         Run USBX state machine.
  * @retval none
  */
VOID USBX_Device_Process(VOID)
{
  ux_system_tasks_run();
}


/**
  * @brief  _ux_utility_interrupt_disable
  *         USB utility interrupt disable.
  * @param  none
  * @retval none
  */
ALIGN_TYPE _ux_utility_interrupt_disable(VOID)
{
  UINT interrupt_save;

  /* USER CODE BEGIN _ux_utility_interrupt_disable */
  interrupt_save = __get_PRIMASK();
  __disable_irq();
  /* USER CODE END _ux_utility_interrupt_disable */

  return interrupt_save;
}

/**
  * @brief  _ux_utility_interrupt_restore
  *         USB utility interrupt restore.
  * @param  flags
  * @retval none
  */
VOID _ux_utility_interrupt_restore(ALIGN_TYPE flags)
{
  /* USER CODE BEGIN _ux_utility_interrupt_restore */
  __set_PRIMASK(flags);
  /* USER CODE END _ux_utility_interrupt_restore */
}

/**
  * @brief  _ux_utility_time_get
  *         Get Time Tick for host timing.
  * @param  none
  * @retval time tick
  */
ULONG _ux_utility_time_get(VOID)
{
  ULONG time_tick = 0U;

  /* USER CODE BEGIN _ux_utility_time_get */
  time_tick = HAL_GetTick();
  /* USER CODE END _ux_utility_time_get */

  return time_tick;
}
/* USER CODE END 1 */
