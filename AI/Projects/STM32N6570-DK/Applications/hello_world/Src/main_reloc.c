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
#include "ll_aton_reloc_network.h"
static NN_Instance_TypeDef NN_Instance_network;

/*

 PSRAM (32MB)

  0x9000 0000  -----------------
                 reserv.          max. 1MB
  0x9010 0000  -----------------
                 ext RAM          max. 27MB
  0x91C0 0000  -----------------
                 ext EXE RAM      max. 4MB
  0x9200 0000  -----------------


 FLASH (128MB)

  0x7000 0000  -----------------
                  reserv.         16MB
  0x7100 0000  -----------------
                  IMG0            8MB
  0x7180 0000  -----------------
                 (PARAM0)         104MB
  0x7800 0000  -----------------

*/
#define _RELOC_EXT_RAM_ADDR           (0x90100000)        // +1MB
#define _RELOC_MAX_EXT_RAM_SZ         (27 * 1024 * 1024)  // 27MB

#define _RELOC_BASE_ADDR_0            (0x71000000)        // +16MB
#define _RELOC_BASE_PARAMS_ADDR_0     (0x71800000)        // +24MB

#define _RELOC_BASE_ADDR_1            (0x90000000)

#define _RELOC_MAX_EXEC_RAM_SZ  ((512 + 128) * 1024)  /* 512 + 128 KB */

// uint64_t exec_ram[_RELOC_MAX_EXE_RAM_SZ / 8];

// #define _RELOC_EXEC_RAM_ADDR  (&exec_ram[0])
// #define _RELOC_EXEC_RAM_ADDR  (0x24350000)  /* npuRAM6 */
// #define _RELOC_EXEC_RAM_ADDR  (0x34100000)  /* AXIRAM2 */

/* AXIRAM1 + 256+128 KB (512+128 KB is reserved for the exec RAM */
#define _RELOC_EXEC_RAM_ADDR   (0x34060000)

#define _USED_RELOC_MODE   AI_RELOC_RT_LOAD_MODE_COPY

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
  
  int res;
  
  uint32_t *rom_addr = (uint32_t *)_RELOC_BASE_ADDR_1;
  uintptr_t ext_param_addr = NULL;

  if (AI_RELOC_MAGIC != *rom_addr) {
      rom_addr = (uint32_t *)_RELOC_BASE_ADDR_0;
  }

  if (AI_RELOC_MAGIC != *rom_addr)
    return NULL;
  
  ll_aton_reloc_info rt;

  ll_aton_reloc_log_info((uintptr_t)rom_addr);

  // Retrieve the info from the binary objects. Requested RAM size,...
  res = ll_aton_reloc_get_info((uintptr_t)rom_addr, &rt);

  if (rt.params_off == 0)
    ext_param_addr = _RELOC_BASE_PARAMS_ADDR_0;

  if (res || rt.ext_ram_sz > _RELOC_MAX_EXT_RAM_SZ)
    return NULL;

    
  // Create and install an instance of the relocatable model
  ll_aton_reloc_config config;

  config.exec_ram_addr = (uintptr_t)_RELOC_EXEC_RAM_ADDR;
  config.exec_ram_size = _RELOC_MAX_EXEC_RAM_SZ;
  config.ext_ram_addr = (uintptr_t)_RELOC_EXT_RAM_ADDR;
  config.ext_ram_size = rt.ext_ram_sz;
  config.ext_param_addr = ext_param_addr;
  config.mode = _USED_RELOC_MODE; // AI_RELOC_RT_LOAD_MODE_CLEAR
  
  res = ll_aton_reloc_install((uintptr_t)rom_addr, &config, &NN_Instance_network);
  
  if (res)
    return NULL;
  
  LL_ATON_RT_RetValues_t ll_aton_rt_ret = LL_ATON_RT_DONE;
  
  /* Retreive the start address of the input and output buffer
  (reserved in the activation buffer) */
  const LL_Buffer_InfoTypeDef *ibuffersInfos = &ll_aton_reloc_get_input_buffers_info(&NN_Instance_network, -1)[0];
  const LL_Buffer_InfoTypeDef *obuffersInfos = &ll_aton_reloc_get_output_buffers_info(&NN_Instance_network, -1)[0];
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
