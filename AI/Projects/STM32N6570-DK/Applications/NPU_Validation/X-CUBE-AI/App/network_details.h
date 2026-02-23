/**
  ******************************************************************************
  * @file    network.h
  * @date    2026-02-22T21:13:24+0100
  * @brief   ST.AI Tool Automatic Code Generator for Embedded NN computing
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  ******************************************************************************
  */
#ifndef STAI_NETWORK_DETAILS_H
#define STAI_NETWORK_DETAILS_H

#include "stai.h"
#include "layers.h"

const stai_network_details g_network_details = {
  .tensors = (const stai_tensor[5]) {
   { .size_bytes = 784, .flags = (STAI_FLAG_HAS_BATCH|STAI_FLAG_CHANNEL_LAST), .format = STAI_FORMAT_S8, .shape = {4, (const int32_t[4]){1, 1, 28, 28}}, .scale = {1, (const float[1]){0.023948537185788155}}, .zeropoint = {1, (const int16_t[1]){-1}}, .name = "input_output" },
   { .size_bytes = 19, .flags = (STAI_FLAG_HAS_BATCH|STAI_FLAG_CHANNEL_LAST), .format = STAI_FORMAT_S8, .shape = {2, (const int32_t[2]){1, 19}}, .scale = {1, (const float[1]){0.012382245622575283}}, .zeropoint = {1, (const int16_t[1]){23}}, .name = "_fc1_Gemm_output_0_output" },
   { .size_bytes = 16, .flags = (STAI_FLAG_HAS_BATCH|STAI_FLAG_CHANNEL_LAST), .format = STAI_FORMAT_S8, .shape = {2, (const int32_t[2]){1, 16}}, .scale = {1, (const float[1]){0.012382245622575283}}, .zeropoint = {1, (const int16_t[1]){23}}, .name = "_Slice_1_output_0_output" },
   { .size_bytes = 40, .flags = (STAI_FLAG_HAS_BATCH|STAI_FLAG_CHANNEL_LAST), .format = STAI_FORMAT_S8, .shape = {2, (const int32_t[2]){1, 40}}, .scale = {1, (const float[1]){0.008222827687859535}}, .zeropoint = {1, (const int16_t[1]){24}}, .name = "output_QuantizeLinear_Input_output" },
   { .size_bytes = 3, .flags = (STAI_FLAG_HAS_BATCH|STAI_FLAG_CHANNEL_LAST), .format = STAI_FORMAT_S8, .shape = {2, (const int32_t[2]){1, 3}}, .scale = {1, (const float[1]){0.012382245622575283}}, .zeropoint = {1, (const int16_t[1]){23}}, .name = "node_19_QuantizeLinear_Input_output" }
  },
  .nodes = (const stai_node_details[4]){
    {.id = 16, .type = AI_LAYER_DENSE_TYPE, .input_tensors = {1, (const int32_t[1]){0}}, .output_tensors = {1, (const int32_t[1]){1}} }, /* _fc1_Gemm_output_0 */
    {.id = 20, .type = AI_LAYER_SLICE_TYPE, .input_tensors = {1, (const int32_t[1]){1}}, .output_tensors = {1, (const int32_t[1]){2}} }, /* _Slice_1_output_0 */
    {.id = 25, .type = AI_LAYER_DENSE_TYPE, .input_tensors = {1, (const int32_t[1]){2}}, .output_tensors = {1, (const int32_t[1]){3}} }, /* output_QuantizeLinear_Input */
    {.id = 19, .type = AI_LAYER_SLICE_TYPE, .input_tensors = {1, (const int32_t[1]){1}}, .output_tensors = {1, (const int32_t[1]){4}} } /* node_19_QuantizeLinear_Input */
  },
  .n_nodes = 4
};
#endif

