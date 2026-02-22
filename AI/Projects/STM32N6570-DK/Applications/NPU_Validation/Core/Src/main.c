  /**
  ******************************************************************************
  * @file    main.c
  * @author  GPM/AIS Application Team
  * @brief   Entry point for AI Validation application
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2023 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */

/* Includes ------------------------------------------------------------------*/

#include <stdio.h>
#include <string.h>

#include "app_config.h"

#include "mcu_cache.h"

#include "main.h"
#include "misc_toolbox.h"

#include "aiValidation.h"
#if defined(USE_USB_CDC_CLASS)
#include "app_usbx_device.h"
#include "ux_api.h"
#endif

/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/
/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/
#if defined(USE_USB_CDC_CLASS)
PCD_HandleTypeDef hpcd_USB1_OTG_HS;
extern UX_SLAVE_CLASS_CDC_ACM  *cdc_acm;
#endif
/* Private function prototypes -----------------------------------------------*/
/* Private functions ---------------------------------------------------------*/
/* Main function -------------------------------------------------------------*/
int main(void)
{
  // Set VTOR to proper address and ack possible pending IRQs
  set_vector_table_addr();
  
  HAL_Init();
  
  // Ensure proper clocking after a reset / after exiting the bootloader
  SystemClock_Config_ResetClocks();
  
  system_init_post();

#if USE_MCU_ICACHE
  SCB_EnableICache();
#else
  SCB_DisableICache();
#endif

#if !USE_MCU_DCACHE_ONLY_FOR_INFERENCE
#if USE_MCU_DCACHE
  SCB_EnableDCache();
#else
  SCB_DisableDCache();
#endif
#endif
     
  /* Configure the system clock */
#if USE_OVERDRIVE
  upscale_vddcore_level();
  SystemClock_Config_HSI_overdrive();
#else
#ifdef NO_OVD_CLK400
  SystemClock_Config_HSI_400();
#else
  SystemClock_Config_HSI_no_overdrive();
#endif
#endif

  // Force fusing of the OTP when using a Nucleo/DK board only
#if (defined(USE_STM32N6xx_NUCLEO) || defined(USE_STM32N6570_DK))
  fuse_vddio();
#endif
  
  /* Clear SLEEPDEEP bit of Cortex System Control Register */
  CLEAR_BIT(SCB->SCR, SCB_SCR_SLEEPDEEP_Msk);

  UART_Config();
#if defined(USE_USB_CDC_CLASS)
  MX_USBX_Device_Init();
  USB_RIF_Config();
#endif
  NPU_Config();
  
#if defined(USE_EXTERNAL_MEMORY_DEVICES) && USE_EXTERNAL_MEMORY_DEVICES == 1
  BSP_XSPI_NOR_Init_t Flash;
  
#if (NUCLEO_N6_CONFIG == 0)
  BSP_XSPI_RAM_Init(0);
  BSP_XSPI_RAM_EnableMemoryMappedMode(0);
  /* Configure the memory in octal DTR */
  Flash.InterfaceMode = MX66UW1G45G_OPI_MODE;
  Flash.TransferRate = MX66UW1G45G_DTR_TRANSFER;
#else
  Flash.InterfaceMode = MX25UM51245G_OPI_MODE;
  Flash.TransferRate = MX25UM51245G_DTR_TRANSFER;
#endif
  
  if(BSP_XSPI_NOR_Init(0, &Flash) != BSP_ERROR_NONE)
  {
        __BKPT(0);
  }
  BSP_XSPI_NOR_EnableMemoryMappedMode(0);

#endif 
  
  RISAF_Config();

/* USED FOR TESTING ACCESS TO EXTERNAL MEMORIES */  
#if defined(USE_EXTERNAL_MEMORY_DEVICES) && USE_EXTERNAL_MEMORY_DEVICES == 1
  uint32_t x[20];
  memcpy((uint32_t*)x, (uint32_t*)0x70000000, 20*4);
#if (NUCLEO_N6_CONFIG == 0)
  memset((uint8_t *)0x90000000, 0xAA, 16 * 1024 *1024);
  memcpy((uint32_t*)x, (uint32_t*)0x90000000, 20*4);
#endif
#endif
  
  set_clk_sleep_mode();
  
  aiValidationInit();
  aiValidationProcess();

}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#if defined(USE_USB_CDC_CLASS)
/**
  * @brief USB_OTG_HS Initialization Function
  * @param None
  * @retval None
  */
void MX_USB1_OTG_HS_PCD_Init(void)
{

  /* USER CODE BEGIN USB1_OTG_HS_Init 0 */

  /* USER CODE END USB1_OTG_HS_Init 0 */

  /* USER CODE BEGIN USB1_OTG_HS_Init 1 */

  memset(&hpcd_USB1_OTG_HS, 0x0, sizeof(PCD_HandleTypeDef));

  /* USER CODE END USB1_OTG_HS_Init 1 */
  hpcd_USB1_OTG_HS.Instance = USB1_OTG_HS;
  hpcd_USB1_OTG_HS.Init.dev_endpoints = 9;
  hpcd_USB1_OTG_HS.Init.speed = PCD_SPEED_HIGH;
  hpcd_USB1_OTG_HS.Init.dma_enable = DISABLE;
  hpcd_USB1_OTG_HS.Init.phy_itface = USB_OTG_HS_EMBEDDED_PHY;
  hpcd_USB1_OTG_HS.Init.Sof_enable = DISABLE;
  hpcd_USB1_OTG_HS.Init.low_power_enable = DISABLE;
  hpcd_USB1_OTG_HS.Init.lpm_enable = DISABLE;
  hpcd_USB1_OTG_HS.Init.vbus_sensing_enable = DISABLE;
  hpcd_USB1_OTG_HS.Init.use_dedicated_ep1 = DISABLE;
  hpcd_USB1_OTG_HS.Init.use_external_vbus = DISABLE;
  if (HAL_PCD_Init(&hpcd_USB1_OTG_HS) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USB1_OTG_HS_Init 2 */

  /* USER CODE END USB1_OTG_HS_Init 2 */
}
#endif

/**
* @brief PCD MSP Initialization
* This function configures the hardware resources used in this example
* @param hhcd: PCD handle pointer
* @retval None
*/
void HAL_PCD_MspInit(PCD_HandleTypeDef* pcdHandle)
{
  if (pcdHandle->Instance==USB1_OTG_HS)
  {
    /* USER CODE BEGIN USB_OTG_HS_MspInit 0 */

    /* USER CODE END USB_OTG_HS_MspInit 0 */
    /* Enable VDDUSB */
    __HAL_RCC_PWR_CLK_ENABLE();
    HAL_PWREx_EnableVddUSBVMEN();
    while(__HAL_PWR_GET_FLAG(PWR_FLAG_USB33RDY));
    HAL_PWREx_EnableVddUSB();

    /** Initializes the peripherals clock
    */
    RCC_PeriphCLKInitTypeDef PeriphClkInitStruct = {0};
    PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_USBOTGHS1;
    PeriphClkInitStruct.UsbOtgHs1ClockSelection = RCC_USBOTGHS1CLKSOURCE_HSE_DIRECT;

    if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct) != HAL_OK)
    {
      /* Initialization Error */
      Error_Handler();
    }

    /** Set USB OTG HS PHY1 Reference Clock Source */
    PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_USBPHY1;
    PeriphClkInitStruct.UsbPhy1ClockSelection = RCC_USBPHY1REFCLKSOURCE_HSE_DIRECT;

    if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct) != HAL_OK)
    {
      /* Initialization Error */
      Error_Handler();
    }

    __HAL_RCC_GPIOA_CLK_ENABLE();

    LL_AHB5_GRP1_ForceReset(0x00800000);
    __HAL_RCC_USB1_OTG_HS_FORCE_RESET();
    __HAL_RCC_USB1_OTG_HS_PHY_FORCE_RESET();

    LL_RCC_HSE_SelectHSEDiv2AsDiv2Clock();
    LL_AHB5_GRP1_ReleaseReset(0x00800000);

    /* Peripheral clock enable */
    __HAL_RCC_USB1_OTG_HS_CLK_ENABLE();

    /* Required few clock cycles before accessing USB PHY Controller Registers */
    HAL_Delay(1);
    
    for (volatile uint32_t i = 0; i < 10; i++) {
        __NOP(); // No Operation instruction to create a delay
    }

    USB1_HS_PHYC->USBPHYC_CR &= ~(0x7 << 0x4);

    USB1_HS_PHYC->USBPHYC_CR |= (0x1 << 16) |
                                (0x2 << 4)  |
                                (0x1 << 2)  |
                                 0x1U;

    __HAL_RCC_USB1_OTG_HS_PHY_RELEASE_RESET();

    /* Required few clock cycles before Releasing Reset */
    HAL_Delay(1);

    for (volatile uint32_t i = 0; i < 10; i++) {
        __NOP(); // No Operation instruction to create a delay
    }
    
    __HAL_RCC_USB1_OTG_HS_RELEASE_RESET();

    /* Peripheral PHY clock enable */
    __HAL_RCC_USB1_OTG_HS_PHY_CLK_ENABLE();

    /* USB_OTG_HS interrupt Init */
    HAL_NVIC_SetPriority(USB1_OTG_HS_IRQn, 7, 0);
    HAL_NVIC_EnableIRQ(USB1_OTG_HS_IRQn);

    /* USER CODE BEGIN USB_OTG_HS_MspInit 1 */

    /* USER CODE END USB_OTG_HS_MspInit 1 */
  }
}

#ifdef  USE_FULL_ASSERT

/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t* file, uint32_t line)
{
  /* Prevent unused argument(s) compilation warning */
  UNUSED(file);
  UNUSED(line);

  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  printf("FAIL on file %s on line %d\r\n", file, (int)line);
  __BKPT(0);
  /* Infinite loop */
  while (1)
  {
  }
}

#endif  /* USE_FULL_ASSERT */
