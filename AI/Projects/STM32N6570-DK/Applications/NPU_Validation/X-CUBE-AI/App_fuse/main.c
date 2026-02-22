/**
  ******************************************************************************
  * @file    Src/main.c
  * @author  MCD Application Team
  * @brief   This example describes how to configure an OTP value
  *          using BSEC API.
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
#include "main.h"

/** @addtogroup STM32N6xx_Examples
  * @{
  */

/** @addtogroup HAL
  * @{
  */

/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/
//#define CLOCK_800_MHZ

/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/

/* Private function prototypes -----------------------------------------------*/
static void SystemClock_Config(void);

/* Private functions ---------------------------------------------------------*/


/**
  * @brief  Main program
  * @param  None
  * @retval None
  */
int main(void)
{
  /* Reset of all peripherals, initializes the systick. */
  HAL_Init();

  /* Set System clock configuration */
  SystemClock_Config();

  /* Check and program fuses if needed */
  fuse_vddio();

  while (1)
  {
  }
}

/**
  * @brief  System Clock Configuration
  *         The system Clock is configured as follow if CLOCK_800_MHZ is defined :
  *            CPU Clock source               = IC1  (PLL1 source, divider 1)
  *            System bus Clock source        = IC2  (PLL1 source, divider 4)
  *            CPUCLK(Hz)                     = 800000000
  *            SYSCLK(Hz)                     = 200000000
  *            HCLK(Hz)                       = 100000000
  *            AHB Prescaler                  = 2
  *            APB1 Prescaler                 = 1
  *            APB2 Prescaler                 = 1
  *            APB4 Prescaler                 = 1
  *            APB5 Prescaler                 = 1
  *            HSI Frequency(Hz)              = 48000000
  *            PLL1 State                     = ON
  *            PLL1 reference clock           = 48000000
  *            PLL1 DIVM                      = 6
  *            PLL1 DIVN                      = 100
  *            PLL1 DIVP1                     = 1
  *            PLL1 DIVP2                     = 1
  *            PLL2 State                     = OFF
  *            PLL3 State                     = OFF
  *            PLL4 State                     = OFF
  *         Otherwise :
  *            CPU Clock source               = HSI
  *            System bus Clock source        = HSI
  *            SYSCLK(Hz)                     = 48000000
  *            HCLK(Hz)                       = 48000000
  *            AHB Prescaler                  = 1
  *            APB1 Prescaler                 = 1
  *            APB2 Prescaler                 = 1
  *            APB4 Prescaler                 = 1
  *            APB5 Prescaler                 = 1
  *            HSI Frequency(Hz)              = 48000000
  *            PLL1 State                     = OFF
  *            PLL2 State                     = OFF
  *            PLL3 State                     = OFF
  *            PLL4 State                     = OFF
  * @retval None
  */
static void SystemClock_Config(void)
{
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};

#if defined (CLOCK_800_MHZ)
  __HAL_RCC_HSE_CONFIG(RCC_HSE_ON);
  HAL_Delay(500);

  /* PLL1 800MHz based on HSE setup for CPU and System bus clocks */
  /* PLL1 = ((((48/6)*100)/1)/1) = 800 MHz */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_NONE;
  RCC_OscInitStruct.PLL1.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL1.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL1.PLLM = 6;
  RCC_OscInitStruct.PLL1.PLLN = 100;
  RCC_OscInitStruct.PLL1.PLLP1 = 1;
  RCC_OscInitStruct.PLL1.PLLP2 = 1;
  RCC_OscInitStruct.PLL1.PLLFractional = 0;
  RCC_OscInitStruct.PLL2.PLLState = RCC_PLL_NONE;
  RCC_OscInitStruct.PLL3.PLLState = RCC_PLL_NONE;
  RCC_OscInitStruct.PLL4.PLLState = RCC_PLL_NONE;
#else
  /* HSI selected as source (redundant since HSI is ON at reset) */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSIDiv = RCC_HSI_DIV1;
  RCC_OscInitStruct.HSICalibrationValue = 0;;
  RCC_OscInitStruct.PLL1.PLLState = RCC_PLL_OFF;
  RCC_OscInitStruct.PLL2.PLLState = RCC_PLL_OFF;
  RCC_OscInitStruct.PLL3.PLLState = RCC_PLL_OFF;
  RCC_OscInitStruct.PLL4.PLLState = RCC_PLL_OFF;
#endif

  if(HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    /* Initialization Error */
    while(1){};
  }

  /* Configure the HCLK, PCLK1, PCLK2, PCLK4 and PCLK5 clocks dividers */
  RCC_ClkInitStruct.ClockType = (RCC_CLOCKTYPE_CPUCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2 | RCC_CLOCKTYPE_PCLK4 | RCC_CLOCKTYPE_PCLK5);
#if defined (CLOCK_800_MHZ)
  /* Select PLL1 output as System CPU clock source and System bus clock source */
  RCC_ClkInitStruct.CPUCLKSource = RCC_CPUCLKSOURCE_IC1;
  RCC_ClkInitStruct.IC1Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
  RCC_ClkInitStruct.IC1Selection.ClockDivider = 1;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_IC2;
  RCC_ClkInitStruct.IC2Selection.ClockSelection = RCC_ICCLKSOURCE_PLL1;
  RCC_ClkInitStruct.IC2Selection.ClockDivider = 4;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_HCLK_DIV2;    // RCC_HCLK_DIV1 to check
#else
  /* Select HSI as CPU and System bus clock source */
  RCC_ClkInitStruct.CPUCLKSource = RCC_CPUCLKSOURCE_HSI;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_HCLK_DIV1;
#endif
  RCC_ClkInitStruct.APB1CLKDivider = RCC_APB1_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_APB2_DIV1;
  RCC_ClkInitStruct.APB4CLKDivider = RCC_APB4_DIV1;
  RCC_ClkInitStruct.APB5CLKDivider = RCC_APB5_DIV1;

  if(HAL_RCC_ClockConfig(&RCC_ClkInitStruct) != HAL_OK)
  {
    /* Initialization Error */
    while(1){};
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

