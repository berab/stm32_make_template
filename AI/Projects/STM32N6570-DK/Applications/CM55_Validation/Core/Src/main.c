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


void MX_X_CUBE_AI_Init(void);
void MX_X_CUBE_AI_Process(void);

/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/
/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/
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

#if defined(USE_EXTERNAL_MEMORY_DEVICES) && USE_EXTERNAL_MEMORY_DEVICES == 1
  BSP_XSPI_NOR_Init_t Flash;
  
#if (NUCLEO_N6_CONFIG == 0)
  BSP_XSPI_RAM_Init(0);
  BSP_XSPI_RAM_EnableMemoryMappedMode(0);
  MODIFY_REG(XSPI1->CR, XSPI_CR_NOPREF, HAL_XSPI_AUTOMATIC_PREFETCH_DISABLE); // Hotfix for xspi: no prefetch
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
  
  set_clk_sleep_mode();
 
  MX_X_CUBE_AI_Init();
  MX_X_CUBE_AI_Process();
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
