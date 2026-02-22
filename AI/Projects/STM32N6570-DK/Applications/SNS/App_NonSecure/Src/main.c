/**
  ******************************************************************************
  * @file    PWR/PWR_STANDBY_TrustZone/App_NonSecure/Src/main.c
  * @author  GPM Application Team
  * @brief   Non-secure main program.
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
#include "secure_nsc.h"
#include "ll_aton_runtime.h"

/** @addtogroup STM32N6xx_HAL_Template
  * @{
  */

/** @addtogroup HAL
  * @{
  */

/* Private typedef -----------------------------------------------------------*/
/* Private defines -----------------------------------------------------------*/
/* Private macros ------------------------------------------------------------*/
LL_ATON_DECLARE_NAMED_NN_INSTANCE_AND_INTERFACE(network) // Defines NN_Instance_network and NN_Interface_network with network.c info
/* Private variables ---------------------------------------------------------*/
/* Private function prototypes -----------------------------------------------*/
void SecureFault_Callback(void);
void SecureError_Callback(void);
/* Global variables ----------------------------------------------------------*/
RTC_HandleTypeDef hrtc;
/* Private functions ---------------------------------------------------------*/

#define ARR_LEN (18)
void blink_led()
{
  static uint32_t dc_len_a[ARR_LEN] = {0,1,1,2,2,3,3,4,4,5,6,7,6,5,4,3,2,2};
  static uint8_t dc_len_i=0;
  static uint8_t up = 1;
  static uint32_t cnt = 0; // !!! valid init
  for(int i = 0; i < 10; i++)
  {
    BSP_LED_Toggle(LED1);BSP_LED_Toggle(LED2);
    HAL_Delay(cnt);
    BSP_LED_Toggle(LED1);BSP_LED_Toggle(LED2);
    HAL_Delay(dc_len_a[dc_len_i]-cnt);
  }
  if (up == 1)
  {
    if (cnt >= dc_len_a[dc_len_i]) 
    {
      up = 0;
      cnt = dc_len_a[dc_len_i];
    }
    else
    {
      cnt ++;
    }
  }
  else
  {
    if (cnt <= 1)
    {
      cnt = 0;
      up = 1;
      dc_len_i = (dc_len_i+1) % ARR_LEN;
    }
    else
    {
      cnt --;
    }
  }
}

/**
  * @brief  Main program
  * @param  None
  * @retval None
  */
int main(void)
{
  uint8_t *buffer_in;
  uint8_t *buffer_out;
  /* Reset of all peripherals, Initializes the Flash interface and the systick. */
  HAL_Init();

  //HAL_NVIC_DisableIRQ(SysTick_IRQn);
  /* Register SecureFault callback defined in non-secure and to be called by secure handler */
  SECURE_RegisterCallback(SECURE_FAULT_CB_ID, (void *)SecureFault_Callback);

  /* Register SecureError callback defined in non-secure and to be called by secure handler */
  SECURE_RegisterCallback(IAC_ERROR_CB_ID, (void *)SecureError_Callback);

  /*******************************************************************************
  *                          Common Configuration Routines                       *
  *******************************************************************************/
  /* Enable I/D-Caches in Non-Secure mode ------------------------------------*/
  SCB_EnableICache();
  SCB_EnableDCache();
  /* Initialize non-secure LED1 IO PO1 */
  BSP_LED_Init(LED1);
  BSP_LED_Init(LED2);
  BSP_LED_Toggle(LED1);
  LL_ATON_RT_RuntimeInit();
  while(1)
  {
    blink_led();
    
    LL_ATON_RT_RetValues_t ll_aton_rt_ret = LL_ATON_RT_DONE;
    const EpochBlock_ItemTypeDef *eb_list = LL_ATON_EpochBlockItems_network();
    
    //while (f==1)
    //{
    // __NOP();
    //}
    /* Retreive the start address of the input and output buffer
    (reserved in the activation buffer) */
    const LL_Buffer_InfoTypeDef * ibuffersInfos = NN_Interface_network.input_buffers_info();
    const LL_Buffer_InfoTypeDef * obuffersInfos = NN_Interface_network.output_buffers_info();
    buffer_in = (uint8_t *)LL_Buffer_addr_start(&ibuffersInfos[0]);
    buffer_out = (uint8_t *)LL_Buffer_addr_start(&obuffersInfos[0]);
    /* ------------- */
    /* - Inference - */
    /* ------------- */
    /* Pre-process and fill the input buffer */
    //_pre_process(buffer_in);
    /* Perform the inference */
    LL_ATON_RT_Init_Network(&NN_Instance_network);  // Initialize passed network instance object
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
    LL_ATON_RT_DeInit_Network(&NN_Instance_network);
    /* -------------------- */
    /* - End of Inference - */
    /* -------------------- */
  }
  LL_ATON_RT_RuntimeDeInit();

}

/**
  * @brief  Callback called by secure code following a secure fault interrupt
  * @note   This callback is called by secure code thanks to the registration
  *         done by the non-secure application with non-secure callable API
  *         SECURE_RegisterCallback(SECURE_FAULT_CB_ID, (void *)SecureFault_Callback);
  * @retval None
  */

void SecureFault_Callback(void)
{
  /* Go to infinite loop when Secure fault generated by IDAU/SAU check */
  /* because of illegal access */
  while (1)
  {
  }
}

/**
  * @brief  Callback called by secure code following a IAC secure interrupt (IAC_IRQn)
  * @note   This callback is called by secure code thanks to the registration
  *         done by the non-secure application with non-secure callable API
  *         SECURE_RegisterCallback(IAC_ERROR_CB_ID, (void *)SecureError_Callback);
  * @retval None
  */
void SecureError_Callback(void)
{
  /* Go to infinite loop when Secure error generated by RIF IAC check */
  /* because of illegal access */
  while (1)
  {
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
