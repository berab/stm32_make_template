/**
  ******************************************************************************
  * @file    network.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-02-23T23:27:35+0100
  * @brief   AI Tool Automatic Code Generator for Embedded NN computing
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


#include "network.h"
#include "network_data.h"

#include "ai_platform.h"
#include "ai_platform_interface.h"
#include "ai_math_helpers.h"

#include "core_common.h"
#include "core_convert.h"

#include "layers.h"



#undef AI_NET_OBJ_INSTANCE
#define AI_NET_OBJ_INSTANCE g_network
 
#undef AI_NETWORK_MODEL_SIGNATURE
#define AI_NETWORK_MODEL_SIGNATURE     "0xc6dcec9d7e85dcb0e884c7b534488e1f"

#ifndef AI_TOOLS_REVISION_ID
#define AI_TOOLS_REVISION_ID     ""
#endif

#undef AI_TOOLS_DATE_TIME
#define AI_TOOLS_DATE_TIME   "2026-02-23T23:27:35+0100"

#undef AI_TOOLS_COMPILE_TIME
#define AI_TOOLS_COMPILE_TIME    __DATE__ " " __TIME__

#undef AI_NETWORK_N_BATCHES
#define AI_NETWORK_N_BATCHES         (1)

static ai_ptr g_network_activations_map[1] = AI_C_ARRAY_INIT;
static ai_ptr g_network_weights_map[1] = AI_C_ARRAY_INIT;



/**  Array declarations section  **********************************************/
/* Array#0 */
AI_ARRAY_OBJ_DECLARE(
  input_output_array, AI_ARRAY_FORMAT_S8|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 784, AI_STATIC)

/* Array#1 */
AI_ARRAY_OBJ_DECLARE(
  _fc1_Gemm_output_0_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 515, AI_STATIC)

/* Array#2 */
AI_ARRAY_OBJ_DECLARE(
  _Slice_1_output_0_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 512, AI_STATIC)

/* Array#3 */
AI_ARRAY_OBJ_DECLARE(
  output_QuantizeLinear_Input_output_array, AI_ARRAY_FORMAT_S8|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 40, AI_STATIC)

/* Array#4 */
AI_ARRAY_OBJ_DECLARE(
  node_19_QuantizeLinear_Input_output_array, AI_ARRAY_FORMAT_S8|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 3, AI_STATIC)

/* Array#5 */
AI_ARRAY_OBJ_DECLARE(
  _fc1_Gemm_output_0_weights_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 403760, AI_STATIC)

/* Array#6 */
AI_ARRAY_OBJ_DECLARE(
  _fc1_Gemm_output_0_bias_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 515, AI_STATIC)

/* Array#7 */
AI_ARRAY_OBJ_DECLARE(
  output_QuantizeLinear_Input_weights_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 20480, AI_STATIC)

/* Array#8 */
AI_ARRAY_OBJ_DECLARE(
  output_QuantizeLinear_Input_bias_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 40, AI_STATIC)

/* Array#9 */
AI_ARRAY_OBJ_DECLARE(
  _fc1_Gemm_output_0_scratch0_array, AI_ARRAY_FORMAT_S16,
  NULL, NULL, 1030, AI_STATIC)

/* Array#10 */
AI_ARRAY_OBJ_DECLARE(
  output_QuantizeLinear_Input_scratch0_array, AI_ARRAY_FORMAT_S16,
  NULL, NULL, 80, AI_STATIC)

/**  Array metadata declarations section  *************************************/
/* Int quant #0 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(_Slice_1_output_0_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.013232775032520294f),
    AI_PACK_INTQ_ZP(-7)))

/* Int quant #1 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(_fc1_Gemm_output_0_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.013232775032520294f),
    AI_PACK_INTQ_ZP(-7)))

/* Int quant #2 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(_fc1_Gemm_output_0_weights_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0002812141610775143f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #3 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(input_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.024220522493124008f),
    AI_PACK_INTQ_ZP(6)))

/* Int quant #4 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(node_19_QuantizeLinear_Input_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.013232775032520294f),
    AI_PACK_INTQ_ZP(-7)))

/* Int quant #5 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(output_QuantizeLinear_Input_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.006029282230883837f),
    AI_PACK_INTQ_ZP(-32)))

/* Int quant #6 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(output_QuantizeLinear_Input_weights_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0003479790175333619f),
    AI_PACK_INTQ_ZP(0)))

/**  Tensor declarations section  *********************************************/
/* Tensor #0 */
AI_TENSOR_OBJ_DECLARE(
  _Slice_1_output_0_output, AI_STATIC,
  0, 0x1,
  AI_SHAPE_INIT(4, 1, 512, 1, 1), AI_STRIDE_INIT(4, 1, 1, 512, 512),
  1, &_Slice_1_output_0_output_array, &_Slice_1_output_0_output_array_intq)

/* Tensor #1 */
AI_TENSOR_OBJ_DECLARE(
  _fc1_Gemm_output_0_bias, AI_STATIC,
  1, 0x0,
  AI_SHAPE_INIT(4, 1, 515, 1, 1), AI_STRIDE_INIT(4, 4, 4, 2060, 2060),
  1, &_fc1_Gemm_output_0_bias_array, NULL)

/* Tensor #2 */
AI_TENSOR_OBJ_DECLARE(
  _fc1_Gemm_output_0_output, AI_STATIC,
  2, 0x1,
  AI_SHAPE_INIT(4, 1, 515, 1, 1), AI_STRIDE_INIT(4, 1, 1, 515, 515),
  1, &_fc1_Gemm_output_0_output_array, &_fc1_Gemm_output_0_output_array_intq)

/* Tensor #3 */
AI_TENSOR_OBJ_DECLARE(
  _fc1_Gemm_output_0_scratch0, AI_STATIC,
  3, 0x0,
  AI_SHAPE_INIT(4, 1, 1030, 1, 1), AI_STRIDE_INIT(4, 2, 2, 2060, 2060),
  1, &_fc1_Gemm_output_0_scratch0_array, NULL)

/* Tensor #4 */
AI_TENSOR_OBJ_DECLARE(
  _fc1_Gemm_output_0_weights, AI_STATIC,
  4, 0x1,
  AI_SHAPE_INIT(4, 784, 515, 1, 1), AI_STRIDE_INIT(4, 1, 784, 403760, 403760),
  1, &_fc1_Gemm_output_0_weights_array, &_fc1_Gemm_output_0_weights_array_intq)

/* Tensor #5 */
AI_TENSOR_OBJ_DECLARE(
  input_output, AI_STATIC,
  5, 0x1,
  AI_SHAPE_INIT(4, 1, 28, 28, 1), AI_STRIDE_INIT(4, 1, 1, 28, 784),
  1, &input_output_array, &input_output_array_intq)

/* Tensor #6 */
AI_TENSOR_OBJ_DECLARE(
  input_output0, AI_STATIC,
  6, 0x1,
  AI_SHAPE_INIT(4, 1, 784, 1, 1), AI_STRIDE_INIT(4, 1, 1, 784, 784),
  1, &input_output_array, &input_output_array_intq)

/* Tensor #7 */
AI_TENSOR_OBJ_DECLARE(
  node_19_QuantizeLinear_Input_output, AI_STATIC,
  7, 0x1,
  AI_SHAPE_INIT(4, 1, 3, 1, 1), AI_STRIDE_INIT(4, 1, 1, 3, 3),
  1, &node_19_QuantizeLinear_Input_output_array, &node_19_QuantizeLinear_Input_output_array_intq)

/* Tensor #8 */
AI_TENSOR_OBJ_DECLARE(
  output_QuantizeLinear_Input_bias, AI_STATIC,
  8, 0x0,
  AI_SHAPE_INIT(4, 1, 40, 1, 1), AI_STRIDE_INIT(4, 4, 4, 160, 160),
  1, &output_QuantizeLinear_Input_bias_array, NULL)

/* Tensor #9 */
AI_TENSOR_OBJ_DECLARE(
  output_QuantizeLinear_Input_output, AI_STATIC,
  9, 0x1,
  AI_SHAPE_INIT(4, 1, 40, 1, 1), AI_STRIDE_INIT(4, 1, 1, 40, 40),
  1, &output_QuantizeLinear_Input_output_array, &output_QuantizeLinear_Input_output_array_intq)

/* Tensor #10 */
AI_TENSOR_OBJ_DECLARE(
  output_QuantizeLinear_Input_scratch0, AI_STATIC,
  10, 0x0,
  AI_SHAPE_INIT(4, 1, 80, 1, 1), AI_STRIDE_INIT(4, 2, 2, 160, 160),
  1, &output_QuantizeLinear_Input_scratch0_array, NULL)

/* Tensor #11 */
AI_TENSOR_OBJ_DECLARE(
  output_QuantizeLinear_Input_weights, AI_STATIC,
  11, 0x1,
  AI_SHAPE_INIT(4, 512, 40, 1, 1), AI_STRIDE_INIT(4, 1, 512, 20480, 20480),
  1, &output_QuantizeLinear_Input_weights_array, &output_QuantizeLinear_Input_weights_array_intq)



/**  Layer declarations section  **********************************************/



AI_STATIC_CONST ai_u8 node_19_QuantizeLinear_Input_axes_data[] = { 2 };
AI_ARRAY_OBJ_DECLARE(
    node_19_QuantizeLinear_Input_axes, AI_ARRAY_FORMAT_U8,
    node_19_QuantizeLinear_Input_axes_data, node_19_QuantizeLinear_Input_axes_data, 1, AI_STATIC_CONST)

AI_STATIC_CONST ai_i16 node_19_QuantizeLinear_Input_starts_data[] = { 0 };
AI_ARRAY_OBJ_DECLARE(
    node_19_QuantizeLinear_Input_starts, AI_ARRAY_FORMAT_S16,
    node_19_QuantizeLinear_Input_starts_data, node_19_QuantizeLinear_Input_starts_data, 1, AI_STATIC_CONST)

AI_STATIC_CONST ai_i16 node_19_QuantizeLinear_Input_ends_data[] = { 3 };
AI_ARRAY_OBJ_DECLARE(
    node_19_QuantizeLinear_Input_ends, AI_ARRAY_FORMAT_S16,
    node_19_QuantizeLinear_Input_ends_data, node_19_QuantizeLinear_Input_ends_data, 1, AI_STATIC_CONST)
AI_TENSOR_CHAIN_OBJ_DECLARE(
  node_19_QuantizeLinear_Input_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &_fc1_Gemm_output_0_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &node_19_QuantizeLinear_Input_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  node_19_QuantizeLinear_Input_layer, 19,
  SLICE_TYPE, 0x0, NULL,
  slice, forward_slice,
  &node_19_QuantizeLinear_Input_chain,
  NULL, &node_19_QuantizeLinear_Input_layer, AI_STATIC, 
  .axes = &node_19_QuantizeLinear_Input_axes, 
  .starts = &node_19_QuantizeLinear_Input_starts, 
  .ends = &node_19_QuantizeLinear_Input_ends, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  output_QuantizeLinear_Input_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &_Slice_1_output_0_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &output_QuantizeLinear_Input_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &output_QuantizeLinear_Input_weights, &output_QuantizeLinear_Input_bias),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &output_QuantizeLinear_Input_scratch0)
)

AI_LAYER_OBJ_DECLARE(
  output_QuantizeLinear_Input_layer, 25,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense_integer_SSSA,
  &output_QuantizeLinear_Input_chain,
  NULL, &node_19_QuantizeLinear_Input_layer, AI_STATIC, 
)


AI_STATIC_CONST ai_u8 _Slice_1_output_0_axes_data[] = { 2 };
AI_ARRAY_OBJ_DECLARE(
    _Slice_1_output_0_axes, AI_ARRAY_FORMAT_U8,
    _Slice_1_output_0_axes_data, _Slice_1_output_0_axes_data, 1, AI_STATIC_CONST)

AI_STATIC_CONST ai_i16 _Slice_1_output_0_starts_data[] = { 3 };
AI_ARRAY_OBJ_DECLARE(
    _Slice_1_output_0_starts, AI_ARRAY_FORMAT_S16,
    _Slice_1_output_0_starts_data, _Slice_1_output_0_starts_data, 1, AI_STATIC_CONST)

AI_STATIC_CONST ai_i16 _Slice_1_output_0_ends_data[] = { 515 };
AI_ARRAY_OBJ_DECLARE(
    _Slice_1_output_0_ends, AI_ARRAY_FORMAT_S16,
    _Slice_1_output_0_ends_data, _Slice_1_output_0_ends_data, 1, AI_STATIC_CONST)
AI_TENSOR_CHAIN_OBJ_DECLARE(
  _Slice_1_output_0_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &_fc1_Gemm_output_0_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &_Slice_1_output_0_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  _Slice_1_output_0_layer, 20,
  SLICE_TYPE, 0x0, NULL,
  slice, forward_slice,
  &_Slice_1_output_0_chain,
  NULL, &output_QuantizeLinear_Input_layer, AI_STATIC, 
  .axes = &_Slice_1_output_0_axes, 
  .starts = &_Slice_1_output_0_starts, 
  .ends = &_Slice_1_output_0_ends, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  _fc1_Gemm_output_0_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &input_output0),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &_fc1_Gemm_output_0_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &_fc1_Gemm_output_0_weights, &_fc1_Gemm_output_0_bias),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &_fc1_Gemm_output_0_scratch0)
)

AI_LAYER_OBJ_DECLARE(
  _fc1_Gemm_output_0_layer, 16,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense_integer_SSSA,
  &_fc1_Gemm_output_0_chain,
  NULL, &_Slice_1_output_0_layer, AI_STATIC, 
)


#if (AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 426460, 1, 1),
    426460, NULL, NULL),
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 3360, 1, 1),
    3360, NULL, NULL),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_IN_NUM, &input_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_OUT_NUM, &output_QuantizeLinear_Input_output, &node_19_QuantizeLinear_Input_output),
  &_fc1_Gemm_output_0_layer, 0xaaa580ec, NULL)

#else

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 426460, 1, 1),
      426460, NULL, NULL)
  ),
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 3360, 1, 1),
      3360, NULL, NULL)
  ),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_IN_NUM, &input_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_OUT_NUM, &output_QuantizeLinear_Input_output, &node_19_QuantizeLinear_Input_output),
  &_fc1_Gemm_output_0_layer, 0xaaa580ec, NULL)

#endif	/*(AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)*/



/******************************************************************************/
AI_DECLARE_STATIC
ai_bool network_configure_activations(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_activations_map(g_network_activations_map, 1, params)) {
    /* Updating activations (byte) offsets */
    
    _fc1_Gemm_output_0_scratch0_array.data = AI_PTR(g_network_activations_map[0] + 0);
    _fc1_Gemm_output_0_scratch0_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    output_QuantizeLinear_Input_scratch0_array.data = AI_PTR(g_network_activations_map[0] + 0);
    output_QuantizeLinear_Input_scratch0_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    input_output_array.data = AI_PTR(g_network_activations_map[0] + 2060);
    input_output_array.data_start = AI_PTR(g_network_activations_map[0] + 2060);
    _fc1_Gemm_output_0_output_array.data = AI_PTR(g_network_activations_map[0] + 2844);
    _fc1_Gemm_output_0_output_array.data_start = AI_PTR(g_network_activations_map[0] + 2844);
    _Slice_1_output_0_output_array.data = AI_PTR(g_network_activations_map[0] + 2060);
    _Slice_1_output_0_output_array.data_start = AI_PTR(g_network_activations_map[0] + 2060);
    output_QuantizeLinear_Input_output_array.data = AI_PTR(g_network_activations_map[0] + 2572);
    output_QuantizeLinear_Input_output_array.data_start = AI_PTR(g_network_activations_map[0] + 2572);
    node_19_QuantizeLinear_Input_output_array.data = AI_PTR(g_network_activations_map[0] + 2060);
    node_19_QuantizeLinear_Input_output_array.data_start = AI_PTR(g_network_activations_map[0] + 2060);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_ACTIVATIONS);
  return false;
}




/******************************************************************************/
AI_DECLARE_STATIC
ai_bool network_configure_weights(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_weights_map(g_network_weights_map, 1, params)) {
    /* Updating weights (byte) offsets */
    
    _fc1_Gemm_output_0_weights_array.format |= AI_FMT_FLAG_CONST;
    _fc1_Gemm_output_0_weights_array.data = AI_PTR(g_network_weights_map[0] + 0);
    _fc1_Gemm_output_0_weights_array.data_start = AI_PTR(g_network_weights_map[0] + 0);
    _fc1_Gemm_output_0_bias_array.format |= AI_FMT_FLAG_CONST;
    _fc1_Gemm_output_0_bias_array.data = AI_PTR(g_network_weights_map[0] + 403760);
    _fc1_Gemm_output_0_bias_array.data_start = AI_PTR(g_network_weights_map[0] + 403760);
    output_QuantizeLinear_Input_weights_array.format |= AI_FMT_FLAG_CONST;
    output_QuantizeLinear_Input_weights_array.data = AI_PTR(g_network_weights_map[0] + 405820);
    output_QuantizeLinear_Input_weights_array.data_start = AI_PTR(g_network_weights_map[0] + 405820);
    output_QuantizeLinear_Input_bias_array.format |= AI_FMT_FLAG_CONST;
    output_QuantizeLinear_Input_bias_array.data = AI_PTR(g_network_weights_map[0] + 426300);
    output_QuantizeLinear_Input_bias_array.data_start = AI_PTR(g_network_weights_map[0] + 426300);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_WEIGHTS);
  return false;
}


/**  PUBLIC APIs SECTION  *****************************************************/



AI_DEPRECATED
AI_API_ENTRY
ai_bool ai_network_get_info(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_NETWORK_MODEL_NAME,
      .model_signature   = AI_NETWORK_MODEL_SIGNATURE,
      .model_datetime    = AI_TOOLS_DATE_TIME,
      
      .compile_datetime  = AI_TOOLS_COMPILE_TIME,
      
      .runtime_revision  = ai_platform_runtime_get_revision(),
      .runtime_version   = ai_platform_runtime_get_version(),

      .tool_revision     = AI_TOOLS_REVISION_ID,
      .tool_version      = {AI_TOOLS_VERSION_MAJOR, AI_TOOLS_VERSION_MINOR,
                            AI_TOOLS_VERSION_MICRO, 0x0},
      .tool_api_version  = AI_STRUCT_INIT,

      .api_version            = ai_platform_api_get_version(),
      .interface_api_version  = ai_platform_interface_api_get_version(),
      
      .n_macc            = 424795,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .params            = AI_STRUCT_INIT,
      .activations       = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0xaaa580ec,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}



AI_API_ENTRY
ai_bool ai_network_get_report(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_NETWORK_MODEL_NAME,
      .model_signature   = AI_NETWORK_MODEL_SIGNATURE,
      .model_datetime    = AI_TOOLS_DATE_TIME,
      
      .compile_datetime  = AI_TOOLS_COMPILE_TIME,
      
      .runtime_revision  = ai_platform_runtime_get_revision(),
      .runtime_version   = ai_platform_runtime_get_version(),

      .tool_revision     = AI_TOOLS_REVISION_ID,
      .tool_version      = {AI_TOOLS_VERSION_MAJOR, AI_TOOLS_VERSION_MINOR,
                            AI_TOOLS_VERSION_MICRO, 0x0},
      .tool_api_version  = AI_STRUCT_INIT,

      .api_version            = ai_platform_api_get_version(),
      .interface_api_version  = ai_platform_interface_api_get_version(),
      
      .n_macc            = 424795,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .map_signature     = AI_MAGIC_SIGNATURE,
      .map_weights       = AI_STRUCT_INIT,
      .map_activations   = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0xaaa580ec,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}


AI_API_ENTRY
ai_error ai_network_get_error(ai_handle network)
{
  return ai_platform_network_get_error(network);
}


AI_API_ENTRY
ai_error ai_network_create(
  ai_handle* network, const ai_buffer* network_config)
{
  return ai_platform_network_create(
    network, network_config, 
    AI_CONTEXT_OBJ(&AI_NET_OBJ_INSTANCE),
    AI_TOOLS_API_VERSION_MAJOR, AI_TOOLS_API_VERSION_MINOR, AI_TOOLS_API_VERSION_MICRO);
}


AI_API_ENTRY
ai_error ai_network_create_and_init(
  ai_handle* network, const ai_handle activations[], const ai_handle weights[])
{
  ai_error err;
  ai_network_params params;

  err = ai_network_create(network, AI_NETWORK_DATA_CONFIG);
  if (err.type != AI_ERROR_NONE) {
    return err;
  }
  
  if (ai_network_data_params_get(&params) != true) {
    err = ai_network_get_error(*network);
    return err;
  }
#if defined(AI_NETWORK_DATA_ACTIVATIONS_COUNT)
  /* set the addresses of the activations buffers */
  for (ai_u16 idx=0; activations && idx<params.map_activations.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_activations, idx, activations[idx]);
  }
#endif
#if defined(AI_NETWORK_DATA_WEIGHTS_COUNT)
  /* set the addresses of the weight buffers */
  for (ai_u16 idx=0; weights && idx<params.map_weights.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_weights, idx, weights[idx]);
  }
#endif
  if (ai_network_init(*network, &params) != true) {
    err = ai_network_get_error(*network);
  }
  return err;
}


AI_API_ENTRY
ai_buffer* ai_network_inputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_inputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_buffer* ai_network_outputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_outputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_handle ai_network_destroy(ai_handle network)
{
  return ai_platform_network_destroy(network);
}


AI_API_ENTRY
ai_bool ai_network_init(
  ai_handle network, const ai_network_params* params)
{
  ai_network* net_ctx = AI_NETWORK_OBJ(ai_platform_network_init(network, params));
  ai_bool ok = true;

  if (!net_ctx) return false;
  ok &= network_configure_weights(net_ctx, params);
  ok &= network_configure_activations(net_ctx, params);

  ok &= ai_platform_network_post_init(network);

  return ok;
}


AI_API_ENTRY
ai_i32 ai_network_run(
  ai_handle network, const ai_buffer* input, ai_buffer* output)
{
  return ai_platform_network_process(network, input, output);
}


AI_API_ENTRY
ai_i32 ai_network_forward(ai_handle network, const ai_buffer* input)
{
  return ai_platform_network_process(network, input, NULL);
}



#undef AI_NETWORK_MODEL_SIGNATURE
#undef AI_NET_OBJ_INSTANCE
#undef AI_TOOLS_DATE_TIME
#undef AI_TOOLS_COMPILE_TIME

