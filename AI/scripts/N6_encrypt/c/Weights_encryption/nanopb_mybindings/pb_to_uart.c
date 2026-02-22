#include "stm32n6xx_hal.h" // huart
#include <pb_encode.h>
#include <pb_decode.h>
#include "pb_to_uart.h"

extern UART_HandleTypeDef huart1;

__attribute__((aligned(32))) uint8_t output_stream_buffer[O_STREAM_SIZE_BYTES]; // output_stream_buffer
__attribute__((aligned(32))) uint8_t input_stream_buffer[I_STREAM_SIZE_BYTES]; // input_stream_buffer

struct xfer_status
{
	bool receiving_len;
	bool receiving_pb;
	bool dma_complete;
	bool command_ready;
	uint32_t xfer_len;
};

static volatile struct xfer_status rx_status;

uart_cf_t uart_status;


uint32_t uart_write_packet(pb_ostream_t* s)
{
	uint8_t* output_stream_buffer_start;
	uint32_t len;
	// Add header to the packet
	len = s->bytes_written;
	HAL_UART_Transmit(&huart1, &len, 4, 0xFFFFFFFF); // Transmit (block)
	output_stream_buffer_start = (uint8_t*)(s->state - s->bytes_written);
	//SCB_CleanDCache_by_Addr(output_stream_buffer_start, s->bytes_written);
	HAL_UART_Transmit_DMA(&huart1, output_stream_buffer_start, s->bytes_written);
	uart_status.rts = false;
	//HAL_UART_Transmit(&huart1, output_stream_buffer_start, s->bytes_written, HAL_MAX_DELAY);
}



/******** PB WRAPPING PROTOCOL **********/

void init_uart_pb()
{
	  rx_status.receiving_len =false;
	  rx_status.receiving_pb=false;
	  rx_status.dma_complete = false;
	  rx_status.command_ready = false;
	  rx_status.xfer_len=0;
	  uart_status.rtr = true;
	  uart_status.rts = true;
}

void client_rx_command_len()
{
	  rx_status.receiving_len = true;
	  HAL_UART_Receive_DMA(&huart1, input_stream_buffer, 4);
}




/* USER CODE BEGIN CLK 1 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{

  if (huart == &huart1)
  {
	  /* Reception is completed (the DMA transfer is over) */
	  rx_status.dma_complete = true;
//	  SCB_InvalidateDCache_by_Addr(input_stream_buffer, I_STREAM_SIZE_BYTES);
	  uart_status.rtr = false;
  }
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{

  if (huart == &huart1)
  {
	  /* Tx is completed (the DMA transfer is over) */
	  uart_status.rts = true;
  }
}

void handle_uart()
{

	/****** RX ******/
	// Check if DMA transfer is over, and do something with it
	if (rx_status.dma_complete == true)
	{
		if (rx_status.receiving_len == true)
		{
			// Received length of the full command, reconfigure uart/dma to receive enough bytes
			rx_status.xfer_len = *(uint32_t*)input_stream_buffer;
			HAL_UART_Receive_DMA(&huart1, input_stream_buffer, rx_status.xfer_len);
			uart_status.rtr = false;
			rx_status.receiving_len = false;
			rx_status.receiving_pb = true;
		}
		else if (rx_status.receiving_pb == true)
		{
			// Command is ready to parse // Get ready for the next one
			rx_status.command_ready = true;
			rx_status.receiving_pb = false;
			rx_status.receiving_len = true;
			// wait for next packet size
			HAL_UART_Receive_DMA(&huart1, input_stream_buffer, 4);
			uart_status.rtr = false;
		}
		rx_status.dma_complete = false;
	}
	/****** TX ******/
}





void handle_commands()
{
	if (rx_status.command_ready == true)
	{
		client_parse_msg(rx_status.xfer_len);
		rx_status.command_ready = false;
	}

	// Encryption is a full scenario with multiple packets, the handler below shall be executed as often as possible when the current command == encrypt
	process_encryption();
};

