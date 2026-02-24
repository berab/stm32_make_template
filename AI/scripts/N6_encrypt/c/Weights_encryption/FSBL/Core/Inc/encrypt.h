#ifndef __ENCRYPT_H__
#define __ENCRYPT_H__
#include <stdint.h>

void encrypt_init(void);
void encrypt_set_keys_and_round(uint32_t* keys, uint32_t round_nb);
void encrypt_encrypt(void* dst, void* src, uint32_t len, void* real_life_address);


#endif
