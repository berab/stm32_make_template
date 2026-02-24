#include "encrypt.h"
#include "stm32n6xx_hal.h"
#include "ll_aton_cipher.h"
#include "ll_aton.h"
#include "npu_cache.h"

void * dma_memcpy_with_streng(void *dst, void *src, size_t n, int is_dst_cached, int is_src_cached);


#define LS32_MASK32_MSB(x) (((uint64_t)x<<32) & 0xFFFFFFFF00000000)
#define MASK32_LSB(x)	   ((uint64_t)x & 0x00000000FFFFFFFF)
#define CONCAT_KEYS(x,y)   (LS32_MASK32_MSB(x) | MASK32_LSB(y))

static uint64_t s_keys[2];
static uint32_t s_nbrounds;

void encrypt_init(void)
{
	  __HAL_RCC_NPU_CLK_ENABLE();
	  __HAL_RCC_NPU_FORCE_RESET();
	  __HAL_RCC_NPU_RELEASE_RESET();
	  __HAL_RCC_CACHEAXI_CLK_ENABLE();
	  __HAL_RCC_CACHEAXI_FORCE_RESET();
	  __HAL_RCC_CACHEAXI_RELEASE_RESET();
}


void encrypt_set_keys_and_round(uint32_t* keys, uint32_t round_nb)
{
	s_keys[0] = CONCAT_KEYS(keys[1],keys[0]);
	s_keys[1] = CONCAT_KEYS(keys[3],keys[2]);
	s_nbrounds = round_nb;
}

void encrypt_encrypt(void* dst, void* src, uint32_t len, void* real_life_address)
{
	LL_Cypher_InitTypeDef cypherConfig;
	uint32_t len_aligned;
	// Sanity check to prevent errors when doing a STRENG transfer -- all buffers should be 8-bytes aligned
	assert((uint32_t)src % 8 == 0);
	assert((uint32_t)dst % 8 == 0);
	assert((uint32_t)real_life_address % 8 == 0);
	// And the transfer length should be multiple of 8 bytes
	len_aligned = ((len / 8) + 1) * 8;
	cypherConfig.srcAdd = (uint32_t) src;
	cypherConfig.dstAdd = (uint32_t) real_life_address;
	cypherConfig.len = len_aligned;
	//global configs
	cypherConfig.cypherCacheMask  = CYPHER_CACHE_DST ; // Use cache for destination addresses
	cypherConfig.cypherEnableMask = CYPHER_DST_MASK ; // Cypher using destination address
	cypherConfig.busIfKeyLsb = s_keys[0];
	cypherConfig.busIfKeyMsb = s_keys[1];
	npu_cache_enable();
	LL_DmaCypherInit ( &cypherConfig ) ;
	dma_memcpy_with_streng(dst, real_life_address, len, 0, 1); // Dest is NOT cached (0) ||  Src IS cached (1) as it should be read from the AXICACHE.
	// Cache is disabled to force invalidate when powering it back on.
	npu_cache_disable();
}


/**
 * memcpy using STRENG from Neural-Art.
 * 	The transfers are forced in 8-bits mode
 * dst destination memory address
 * src source memory address
 * n   Transfer length (in bytes)
 * is_dst_cached Destination under cache flag
 * is_src_cached Source under cache flag
 *
 *	This function uses STRENG 0 and 1
 */

void * dma_memcpy_with_streng(void *dst, void *src, size_t n, int is_dst_cached, int is_src_cached)
{
  if (n > 0)
  {
    // Read from src one frame of length n using 8-bit accesses. Access is done in RAW mode.
	LL_Streng_TensorInitTypeDef dma_in = {
        .dir = 0,
        .addr_base = {(uint8_t *)src},
        .offset_start = 0,
        .offset_end = n,
        .offset_limit = n + 64, // Ensure limit is higher than offset_end
        .raw = 1,
        .frame_count = 0,
        .fwidth = 0,
        .fheight = 0,
        .batch_depth = 0,
        .batch_offset = 0,
        .frame_offset = n,
        .line_offset = 0,
        .loop_offset = 0,
        .frame_loop_cnt = 0,
        .frame_tot_cnt = 1,
        .nbits_in = 8,				// 8 bits in
        .nbits_out = 8,				// 8 bits out
        .nbits_unsigned = 0,
        .align_right = 0,
        .noblk = 0,
    };
	// Write to dest one frame of length n using 8-bit accesses.  Access is done in RAW mode.
    LL_Streng_TensorInitTypeDef dma_out = {
        .dir = 1,
        .addr_base = {(uint8_t *)dst},
        .offset_start = 0,
        .offset_end = n,
        .raw = 1,
        .frame_count = 0,
        .fwidth = 0,
        .fheight = 0,
        .batch_depth = 0,
        .batch_offset = 0,
        .frame_offset = n,
        .line_offset = 0,
        .loop_offset = 0,
        .frame_loop_cnt = 0,
        .frame_tot_cnt = 1,
        .nbits_in = 8,				// 8 bits in
        .nbits_out = 8,				// 8 bits out
        .nbits_unsigned = 0,
        .align_right = 0,
        .noblk = 0,
    };

    if (is_src_cached != 0)
    {
      dma_in.cacheable = 1;
      dma_in.cache_allocate = 1;
    }

    if (is_dst_cached != 0)
    {
      dma_out.cacheable = 1;
      dma_out.cache_allocate = 1;
    }
	
	// Connect stream-engines together.
    const LL_Switch_InitTypeDef switch_init = {LL_Switch_Init_Dest() = ATONN_DSTPORT(STRSWITCH, 0, STRENG, 1, 0),
                                               LL_Switch_Init_Source(0) = ATONN_SRCPORT(STRSWITCH, 0, STRENG, 0, 0),
                                               LL_Switch_Init_Context(0) = 1, LL_Switch_Init_Frames(0) = 0};
    const LL_ATON_EnableUnits_InitTypeDef dma_units[] = {{{STRENG, 1}}, {{STRENG, 0}}};
    const uint32_t dma_wait_mask = 0x2;

    LL_Streng_TensorInit(0, &dma_in, 1);
    LL_Streng_TensorInit(1, &dma_out, 1);
    LL_Switch_Init(&switch_init, 1);
    LL_ATON_EnableUnits_Init(dma_units, 2);
    LL_Streng_Wait(dma_wait_mask);
    LL_ATON_DisableUnits_Init(dma_units, 1);
    LL_Switch_Deinit(&switch_init, 1);
  }

  return dst;
}


