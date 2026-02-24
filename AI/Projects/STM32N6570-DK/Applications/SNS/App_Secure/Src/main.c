/**
  ******************************************************************************
  * @file    PWR/PWR_STANDBY_TrustZone/App_Secure/Src/main.c
  * @author  GPM Application Team
  * @brief   Secure main program.
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; COPYRIGHT 2023 STMicroelectronics</center></h2>
  *
  * This software component is licensed by ST under BSD 3-Clause license,
  * the "License"; You may not use this file except in compliance with the
  * License. You may obtain a copy of the License at:
  *                        opensource.org/licenses/BSD-3-Clause
  *
  ******************************************************************************
  */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "stm32n6xx_it.h"
#include "stm32n6570_discovery_xspi.h"

/** @addtogroup STM32N6xx_HAL_Template
  * @{
  */
/** @addtogroup HAL
  * @{
  */
/* Private typedef -----------------------------------------------------------*/

/* Private define ------------------------------------------------------------*/
/* Non-secure Vector table to jump to                                         */
/* Caution: address must correspond to non-secure address as it is mapped in  */
/*          the non-secure vector table                                       */

/* Memory partitioning on STM32N6xx uses */
/* Secure code is stored from 0x7010'0000 to 0x7017ffff */
/* Non-Secure code is stored from 0x7018'0000 to 0x701fffff */

#define VECT_TAB_NS_OFFSET  0x00180400
#define VTOR_TABLE_NS_START_ADDR (XSPI2_BASE|VECT_TAB_NS_OFFSET)

/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/
/* Private function prototypes -----------------------------------------------*/
static void SystemIsolation_Config(void);
static void set_clk_sleep_mode(void);
/* Global variables ----------------------------------------------------------*/
RTC_HandleTypeDef hrtc;
/* Private functions ---------------------------------------------------------*/
static void system_init_post(void)
{  
  __HAL_RCC_SYSCFG_CLK_ENABLE();
  __HAL_RCC_CRC_CLK_ENABLE();
   
  /* Enable NPU RAMs (4x448KB) + CACHEAXI */
  RCC->MEMENR |= RCC_MEMENR_AXISRAM3EN | RCC_MEMENR_AXISRAM4EN | RCC_MEMENR_AXISRAM5EN | RCC_MEMENR_AXISRAM6EN;
  RCC->MEMENR |= RCC_MEMENR_CACHEAXIRAMEN; // RCC_MEMENR_NPUCACHERAMEN;
  
  RAMCFG_SRAM2_AXI->CR &= ~RAMCFG_CR_SRAMSD;
  RAMCFG_SRAM3_AXI->CR &= ~RAMCFG_CR_SRAMSD;
  RAMCFG_SRAM4_AXI->CR &= ~RAMCFG_CR_SRAMSD;
  RAMCFG_SRAM5_AXI->CR &= ~RAMCFG_CR_SRAMSD;
  RAMCFG_SRAM6_AXI->CR &= ~RAMCFG_CR_SRAMSD;
  
  /* Allow caches to be activated. Default value is 1, but the current boot sets it to 0 */
  MEMSYSCTL->MSCR |= MEMSYSCTL_MSCR_DCACTIVE_Msk | MEMSYSCTL_MSCR_ICACTIVE_Msk;
}
void init_external_memories(void)
{ 
  BSP_XSPI_RAM_Init(0);
  BSP_XSPI_RAM_EnableMemoryMappedMode(0);
}

static void NPU_Config(void)
{
  CACHEAXI_HandleTypeDef hcacheaxi_s;
  __HAL_RCC_NPU_CLK_ENABLE();
  __HAL_RCC_NPU_FORCE_RESET();
  __HAL_RCC_NPU_RELEASE_RESET();
  // __HAL_RCC_NPU_CLK_SLEEP_DISABLE();
  
  // __HAL_RCC_RAMCFG_CLK_SLEEP_DISABLE();
  
  __HAL_RCC_CACHEAXI_CLK_ENABLE();
  __HAL_RCC_CACHEAXI_FORCE_RESET();
  __HAL_RCC_CACHEAXI_RELEASE_RESET();
  __HAL_RCC_CACHEAXI_CLK_SLEEP_DISABLE();
  hcacheaxi_s.Instance = CACHEAXI;
  HAL_CACHEAXI_Init(&hcacheaxi_s);
   
  RIMC_MasterConfig_t master_conf;
  /* Enable Non-Secure access for NPU */
  master_conf.MasterCID = 2;    // Master CID = 1
  master_conf.SecPriv = RIF_ATTRIBUTE_NSEC | RIF_ATTRIBUTE_PRIV; // Priviledged Nonsecure
  HAL_RIF_RIMC_ConfigMasterAttributes(RIF_MASTER_INDEX_NPU, &master_conf);  // Configure accesses of the NPU to the AXI bus
  
  HAL_RIF_RISC_SetSlaveSecureAttributes(RIF_RISC_PERIPH_INDEX_NPU, RIF_ATTRIBUTE_PRIV | RIF_ATTRIBUTE_NSEC); // Configure who can configure the NPU (RISUP) -- if Non-secure, then the RIMU config above is ignored.
}


/**
  * @brief  Main program
  * @param  None
  * @retval None
  */
int main(void)
{
  funcptr_NS NonSecure_ResetHandler;
  /* Configure I/D-Caches in Secure mode -------------------------------------*/
  SCB_EnableICache();
  SCB_DisableDCache();

  /* Enable BusFault and SecureFault handlers (HardFault is default) */
  SCB->SHCSR |= (SCB_SHCSR_BUSFAULTENA_Msk | SCB_SHCSR_SECUREFAULTENA_Msk);

  /* Reset of all peripherals, Initializes the Flash interface and the systick. */
  HAL_Init();

  system_init_post();
  init_external_memories();
  NPU_Config();
  /* Secure/Non-secure Memory and Peripheral isolation configuration */
  SystemIsolation_Config();
  set_clk_sleep_mode();
  HAL_NVIC_EnableIRQ(IAC_IRQn);
  /*************** Setup and jump to non-secure *******************************/

  /* Set non-secure vector table location */
  SCB_NS->VTOR = VTOR_TABLE_NS_START_ADDR;

  /* Set non-secure main stack (MSP_NS) */
  __TZ_set_MSP_NS((*(uint32_t *)VTOR_TABLE_NS_START_ADDR));

  /* Get non-secure reset handler */
  NonSecure_ResetHandler = (funcptr_NS)(*((uint32_t *)((VTOR_TABLE_NS_START_ADDR) + 4U)));

  /* Start non-secure state software application */
  NonSecure_ResetHandler();

  /* Non-secure software does not return, this code is not executed */
  while (1) {
    __NOP();
  }
}


static uint32_t get_risaf_max_addr(RISAF_TypeDef *risaf)
{
  uint32_t max_addr = 0U;
  if      ((risaf == RISAF1_S)  || (risaf == RISAF1_NS))  {max_addr = RISAF1_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF2_S)  || (risaf == RISAF2_NS))  {max_addr = RISAF2_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF3_S)  || (risaf == RISAF3_NS))  {max_addr = RISAF3_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF4_S)  || (risaf == RISAF4_NS))  {max_addr = RISAF4_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF5_S)  || (risaf == RISAF5_NS))  {max_addr = RISAF5_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF6_S)  || (risaf == RISAF6_NS))  {max_addr = RISAF6_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF7_S)  || (risaf == RISAF7_NS))  {max_addr = RISAF7_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF8_S)  || (risaf == RISAF8_NS))  {max_addr = RISAF8_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF9_S)  || (risaf == RISAF9_NS))  {max_addr = RISAF9_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF11_S) || (risaf == RISAF11_NS)) {max_addr = RISAF11_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF12_S) || (risaf == RISAF12_NS)) {max_addr = RISAF12_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF13_S) || (risaf == RISAF13_NS)) {max_addr = RISAF13_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF14_S) || (risaf == RISAF14_NS)) {max_addr = RISAF14_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF15_S) || (risaf == RISAF15_NS)) {max_addr = RISAF15_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF21_S) || (risaf == RISAF21_NS)) {max_addr = RISAF21_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF22_S) || (risaf == RISAF22_NS)) {max_addr = RISAF22_LIMIT_ADDRESS_SPACE_SIZE;}
  else if ((risaf == RISAF23_S) || (risaf == RISAF23_NS)) {max_addr = RISAF23_LIMIT_ADDRESS_SPACE_SIZE;}
  return max_addr;
}
/**
  * @brief  System Isolation Configuration
  *         This function is responsible for Memory and Peripheral isolation
  *         for secure and non-secure application parts
  * @retval None
  */
static void SystemIsolation_Config(void)
{
  RISAF_BaseRegionConfig_t risaf_conf;
  RISAF_TypeDef *risaf;
  /* RISAF Config */
  __HAL_RCC_RISAF_CLK_ENABLE();
  __HAL_RCC_IAC_CLK_ENABLE();
  HAL_RIF_IAC_EnableIT(RIF_AWARE_PERIPH_INDEX_RISAF12);
  HAL_RIF_IAC_EnableIT(RIF_AWARE_PERIPH_INDEX_RISAF11);
  HAL_RIF_IAC_EnableIT(RIF_AWARE_PERIPH_INDEX_RISAF15);

  /* set up base region configuration for AXISRAM1 and 2 */
  risaf_conf.StartAddress = 0;

  risaf_conf.Filtering = RISAF_FILTER_ENABLE;
  risaf_conf.PrivWhitelist = RIF_CID_MASK;
  risaf_conf.ReadWhitelist = RIF_CID_MASK;
  risaf_conf.WriteWhitelist = RIF_CID_MASK;

  /* FLEXRAM is secure */
  risaf = RISAF7;
  risaf_conf.EndAddress = get_risaf_max_addr(risaf);
  risaf_conf.Secure = RIF_ATTRIBUTE_SEC;
  HAL_RIF_RISAF_ConfigBaseRegion(risaf, RISAF_REGION_1, &risaf_conf);
  // ADD FLEXRAM NON SECURE FOR NS firmware
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  HAL_RIF_RISAF_ConfigBaseRegion(risaf, RISAF_REGION_2, &risaf_conf);
  
  /* AXISRAM1 is secure  -- Contains Secure firmware*/
  risaf = RISAF2;
  risaf_conf.EndAddress = get_risaf_max_addr(risaf);
  risaf_conf.Secure = RIF_ATTRIBUTE_SEC;
  HAL_RIF_RISAF_ConfigBaseRegion(risaf, RISAF_REGION_1, &risaf_conf);
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF2, RISAF_REGION_2, &risaf_conf);
  
  /* AXISRAM2 is non-secure */
  risaf = RISAF3;
  risaf_conf.EndAddress = get_risaf_max_addr(risaf);
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  HAL_RIF_RISAF_ConfigBaseRegion(risaf, RISAF_REGION_1, &risaf_conf);
  risaf_conf.Secure = RIF_ATTRIBUTE_SEC;
  HAL_RIF_RISAF_ConfigBaseRegion(risaf, RISAF_REGION_2, &risaf_conf);
  //// NPU Rams - Non secure
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  risaf_conf.EndAddress = get_risaf_max_addr(RISAF6);
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF6, RISAF_REGION_1, &risaf_conf);
  //// NPU masters for axi - Non secure
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  risaf_conf.EndAddress = get_risaf_max_addr(RISAF4);
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF4, RISAF_REGION_1, &risaf_conf);
  risaf_conf.EndAddress = get_risaf_max_addr(RISAF5);
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF5, RISAF_REGION_1, &risaf_conf);
  
    /* set up RISAF ROM regions for XSPI2 */
  risaf_conf.StartAddress = 0x00100000;
  risaf_conf.EndAddress = 0x0017FFFF;
  risaf_conf.Secure = RIF_ATTRIBUTE_SEC;
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF12, RISAF_REGION_1, &risaf_conf);
  
  risaf_conf.StartAddress = 0x00180000;
  risaf_conf.EndAddress = get_risaf_max_addr(RISAF12);
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF12, RISAF_REGION_2, &risaf_conf);
  
  risaf_conf.StartAddress = 0x00000000;
  risaf_conf.EndAddress = get_risaf_max_addr(RISAF11);
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  HAL_RIF_RISAF_ConfigBaseRegion(RISAF11, RISAF_REGION_1, &risaf_conf);
  
  // Configure Cache-AXI (enable access + config from NS world)
  risaf = RISAF15;      // Cache AXI configuration port
  risaf_conf.StartAddress = 0x00000000;
  risaf_conf.EndAddress = get_risaf_max_addr(risaf);
  risaf_conf.Secure = RIF_ATTRIBUTE_NSEC;
  HAL_RIF_RISAF_ConfigBaseRegion(risaf, RISAF_REGION_1, &risaf_conf);
  
  __HAL_RCC_RIFSC_CLK_ENABLE();
  HAL_RIF_RISC_SetSlaveSecureAttributes(RIF_RCC_PERIPH_INDEX_CACHEAXIRAM, RIF_ATTRIBUTE_NSEC); // CACHE AXI -- NPU CACHE (allow clock of the cache manipulation by NSEC)
  /* Set GPIOO as configurable by non-secure */
  HAL_RIF_RISC_SetSlaveSecureAttributes(RIF_RCC_PERIPH_INDEX_GPIOO, RIF_ATTRIBUTE_NSEC); // LED1
  HAL_RIF_RISC_SetSlaveSecureAttributes(RIF_RCC_PERIPH_INDEX_GPIOG, RIF_ATTRIBUTE_NSEC); // LED2

  /* Enable GPIOO clock and ensure GPIOO bank is powered on */
  __HAL_RCC_GPIOO_CLK_ENABLE();
  __HAL_RCC_GPIOG_CLK_ENABLE();
  /* Configure PO1 as non-secure to be used for non-secure led toggling */
  HAL_GPIO_ConfigPinAttributes(GPIOO, GPIO_PIN_1, GPIO_PIN_NSEC);  // LED1
  HAL_GPIO_ConfigPinAttributes(GPIOG, GPIO_PIN_10, GPIO_PIN_NSEC); // LED2
  
  /* Configure PWR_CPUCR as non-secure to be R/W for NSEC application*/
  HAL_PWR_ConfigAttributes(PWR_ITEM_6, PWR_NSEC_PRIV);
  
  /* Set RTC in secure mode except Init and Wake-up timer*/
  __HAL_RCC_RTC_CLK_ENABLE();
  RTC_SecureStateTypeDef  secureState = {0};
  secureState.rtcSecureFull = RTC_SECURE_FULL_NO;
  secureState.tampSecureFull = TAMP_SECURE_FULL_YES;
  secureState.rtcNonSecureFeatures = RTC_NONSECURE_FEATURE_INIT | RTC_NONSECURE_FEATURE_WUT;
  HAL_RTCEx_SecureModeSet(&hrtc, &secureState);
}

static void set_clk_sleep_mode(void)
{
    /* Leave clocks enabled in Low Power modes */

  volatile uint32_t tmp;

  RCC_S->BUSLPENR = 0xffffffff;
  RCC_S->BUSLPENSR = 0xffffffff;
  tmp = RCC_S->BUSLPENR;

  RCC_S->MISCLPENR = 0xffffffff;
  RCC_S->MEMLPENR = 0xffffffff;
    RCC_S->MEMLPENSR = 0xffffffff;
  tmp = RCC_S->MISCLPENR;
  tmp = RCC_S->MEMLPENR;

  RCC_S->AHB1LPENR = 0xffffffff;
  RCC_S->AHB2LPENR = 0xffffffff;
  RCC_S->AHB3LPENR = 0xffffffff;
  RCC_S->AHB4LPENR = 0xffffffff;
  RCC_S->AHB5LPENR = 0xffffffff;
  RCC_S->AHB5LPENSR = 0xffffffff;

  tmp = RCC_S->AHB1LPENR;
  tmp = RCC_S->AHB2LPENR;
  tmp = RCC_S->AHB3LPENR;
  tmp = RCC_S->AHB4LPENR;
  tmp = RCC_S->AHB5LPENR;

  RCC_S->APB1LPENR1 = 0xffffffff;
    RCC_S->APB1LPENSR1 = 0xffffffff;

  tmp = RCC_S->APB1LPENR1;

  RCC_S->APB1LPENR2 = 0xffffffff;
  
  tmp = RCC_S->APB1LPENR2;

  RCC_S->APB2LPENR = 0xffffffff;
  RCC_S->APB3LPENR = 0xffffffff;

  tmp = RCC_S->APB2LPENR;
  tmp = RCC_S->APB3LPENR;

  RCC_S->APB4LPENR1 = 0xffffffff;
  RCC_S->APB4LPENR2 = 0xffffffff;

  tmp = RCC_S->APB4LPENR1;
  tmp = RCC_S->APB4LPENR2;

  RCC_S->APB5LPENR = 0xffffffff;
  tmp = RCC_S->APB5LPENR;

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

  /* Infinite loop */
  while (1)
  {
  }
}
#endif

/**
  * @}
  */

/**
  * @}
  */
