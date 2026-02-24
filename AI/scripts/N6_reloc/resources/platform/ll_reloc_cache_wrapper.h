/**
 ******************************************************************************
 * @file    ll_reloc_cache_wrapper.h
 * @author  MCD/AIS Team
 * @brief   Macros to wrap the call of the NPU/MCU cache maintenance op
 *          to have an indirection for CLANG env.
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2025 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */

#ifndef __LL_CACHE_WRAPPER_H__
#define __LL_CACHE_WRAPPER_H__

#include <stdint.h> 

#include "ll_aton_caches_interface.h"

#ifdef __cplusplus
extern "C" {
#endif

struct _cache_op {
  uintptr_t virtual_addr;
  uint32_t size;
};
  
void reloc_npu_clean_invalidate_range(struct _cache_op *op);
void reloc_npu_clean_range(struct _cache_op *cache_op);

/* NPU cache */

#define RELOC_LL_ATON_Cache_NPU_Clean_Invalidate_Range(addr_, size_)\
  { static struct _cache_op cache_op = {addr_, size_}; \
    reloc_npu_clean_invalidate_range(&cache_op); }
  
[[clang::optnone]]
void reloc_npu_clean_invalidate_range(struct _cache_op *cache_op) {
    LL_ATON_Cache_NPU_Clean_Invalidate_Range(cache_op->virtual_addr, cache_op->size);
}
  
#define RELOC_LL_ATON_Cache_NPU_Clean_Range(addr_, size_)\
  { static struct _cache_op cache_op = {addr_, size_}; \
    reloc_npu_clean_range(&cache_op); }
  
[[clang::optnone]]
void reloc_npu_clean_range(struct _cache_op *cache_op) {
    LL_ATON_Cache_NPU_Clean_Range(cache_op->virtual_addr, cache_op->size);
}

/* MCU $D cache */

void reloc_mcu_invalidate_range(struct _cache_op *op);
void reloc_mcu_clean_range(struct _cache_op *cache_op);

#define RELOC_LL_ATON_Cache_MCU_Invalidate_Range(addr_, size_)\
  { static struct _cache_op cache_op = {addr_, size_}; \
    reloc_mcu_invalidate_range(&cache_op); }
  
[[clang::optnone]]
void reloc_mcu_invalidate_range(struct _cache_op *cache_op) {
    LL_ATON_Cache_MCU_Invalidate_Range(cache_op->virtual_addr, cache_op->size);
}
  
#define RELOC_LL_ATON_Cache_MCU_Clean_Range(addr_, size_)\
  { static struct _cache_op cache_op = {addr_, size_}; \
    reloc_mcu_clean_range(&cache_op); }
  
[[clang::optnone]]
void reloc_mcu_clean_range(struct _cache_op *cache_op) {
  LL_ATON_Cache_MCU_Clean_Range(cache_op->virtual_addr, cache_op->size);
}

#ifdef __cplusplus
}
#endif
  
#endif  /* __LL_CACHE_WRAPPER_H__ */
