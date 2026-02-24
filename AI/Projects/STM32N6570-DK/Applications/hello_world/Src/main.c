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
#include "npu_cache.h"
#include "mcu_cache.h"
#include "ll_aton_rt_user_api.h"
#include "uart.h"
#include "md5.h"
#include "main.h"
#include "misc_toolbox.h"
/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/
/* Private macro -------------------------------------------------------------*/
LL_ATON_DECLARE_NAMED_NN_INSTANCE_AND_INTERFACE(network) // Defines NN_Instance_network and NN_Interface_network with network.c info
/* Private variables ---------------------------------------------------------*/
static uint32_t t_init;
static uint32_t t_out;
/* Private function prototypes -----------------------------------------------*/
void time_in(void);
uint32_t time_out(void);
#ifdef  USE_FULL_ASSERT
  void assert_failed(uint8_t* file, uint32_t line);
#endif
/* Private functions ---------------------------------------------------------*/
void init_dwt()
{
    /* Enable Trace */
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

  /* Reset Cycle Counter and Event Counters */
  ARM_PMU_CYCCNT_Reset();

  /* Enable Cycle Counter */
  ARM_PMU_CNTR_Enable(PMU_CNTENSET_CCNTR_ENABLE_Msk);

  /* Enable the PMU */
  ARM_PMU_Enable();
}

void time_in(void)
{
  ARM_PMU_CYCCNT_Reset();
  t_init = ARM_PMU_Get_CCNTR();
}

uint32_t time_out(void)
{
  t_out = ARM_PMU_Get_CCNTR();
  return (t_out - t_init);
}

void init_external_memories(void)
{
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
  printf("FAIL on file %s on line %d\r\n", file, line);
  __BKPT(0);
  /* Infinite loop */
  while (1)
  {
  }
}

#endif  /* USE_FULL_ASSERT */
/* Main function -------------------------------------------------------------*/
uint32_t duration_us;
uint32_t duration_dwt;
/* Flag signaling Epoch Controller has finished */

int main(void)
{
  float_t clock_Hz;
  uint8_t *buffer_in;
  uint8_t *buffer_out;
  uint32_t cpuclk;

  set_vector_table_addr();
  
  HAL_Init();

  system_init_post();

  if (USE_MCU_ICACHE)
  {
    SCB_EnableICache();
  }
  else
  {
    SCB_DisableICache();
  }

  if (USE_MCU_DCACHE)
  {
    SCB_EnableDCache();
  }
  else
  {
    SCB_DisableDCache();
  }

  /* Configure the system clock */
#if VDDCORE_OVERDRIVE == 1
  upscale_vddcore_level();
  SystemClock_Config_HSI_overdrive();
#else
  SystemClock_Config_HSI_no_overdrive();
#endif
  
  /* Clear SLEEPDEEP bit of Cortex System Control Register */
  CLEAR_BIT(SCB->SCR, SCB_SCR_SLEEPDEEP_Msk);
  
  UART_Config();
  
  NPU_Config();

  init_external_memories();
  
  RISAF_Config();
  set_clk_sleep_mode();
  //uart_selftest_loop(); // Check printf redirection to UART forever
  
  // Get clock frequency to compute inference duration later on 
  // and init time measurement capabilities with PMU
  cpuclk =  HAL_RCC_GetCpuClockFreq();
  clock_Hz = (float_t) cpuclk;
  init_dwt();
  
  LL_ATON_RT_RetValues_t ll_aton_rt_ret = LL_ATON_RT_DONE;
  const EpochBlock_ItemTypeDef *eb_list = LL_ATON_EpochBlockItems_network();
  
  /* Retreive the start address of the input and output buffer
  (reserved in the activation buffer) */
  const LL_Buffer_InfoTypeDef * ibuffersInfos = LL_ATON_Input_Buffers_Info(&NN_Instance_network);
  const LL_Buffer_InfoTypeDef * obuffersInfos = LL_ATON_Output_Buffers_Info(&NN_Instance_network);
  buffer_in = (uint8_t *)LL_Buffer_addr_start(&ibuffersInfos[0]);
  buffer_out = (uint8_t *)LL_Buffer_addr_start(&obuffersInfos[0]);
  
  LL_ATON_RT_RuntimeInit();
  LL_ATON_RT_Init_Network(&NN_Instance_network);  // Initialize passed network instance object
  while(1){
    /* ------------- */
    /* - Inference - */
    /* ------------- */
    /* Pre-process and fill the input buffer */
    //_pre_process(buffer_in);
    /* Perform the inference */
    LL_ATON_RT_Reset_Network(&NN_Instance_network);
    printf("Starting inference");
    time_in();
    do {
      /* Execute first/next step */
      ll_aton_rt_ret = LL_ATON_RT_RunEpochBlock(&NN_Instance_network);
      /* Wait for next event */
      if (ll_aton_rt_ret == LL_ATON_RT_WFE)
      LL_ATON_OSAL_WFE();
    } while (ll_aton_rt_ret != LL_ATON_RT_DONE);
    /* Post-process the output buffer */
    /* Invalidate the associated CPU cache region if requested */
    //_post_process(buffer_out);
    /* -------------------- */
    /* - End of Inference - */
    /* -------------------- */
    duration_dwt = time_out();
    duration_us = (uint32_t)(((float_t)duration_dwt * 1000000.0)/clock_Hz);
    printf(" -> Inference took %d us (%d) cycles)\r\n",duration_us, duration_dwt);
    HAL_Delay(200);
  }
  LL_ATON_RT_DeInit_Network(&NN_Instance_network);
  LL_ATON_RT_RuntimeDeInit();
  
}


/**
  * @brief  Redirect console output to COM
  */
extern UART_HandleTypeDef UartHandle;
#if defined(__ICCARM__)
__ATTRIBUTES  size_t __write(int handle, const unsigned char *ch, size_t size){HAL_UART_Transmit(&UartHandle, (uint8_t *)ch, size, HAL_MAX_DELAY);return 0;}
#elif defined (__CC_ARM) || defined(__ARMCC_VERSION)
/* ARM Compiler 5/6 */
int fputc(int ch, FILE *f){HAL_UART_Transmit(&UartHandle, (uint8_t *)&ch, 1, HAL_MAX_DELAY);return 0;}
#else //if defined(__GNUC__)
int _write(int fd, const void *buff, int count){HAL_UART_Transmit(&UartHandle, (uint8_t *)buff, count, HAL_MAX_DELAY);return 0;}
#endif
