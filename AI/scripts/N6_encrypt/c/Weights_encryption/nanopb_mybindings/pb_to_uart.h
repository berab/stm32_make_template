#ifndef _PB_TO_UART_H_
#define _PB_TO_UART_H_

#include <pb.h>


// MAKE THE SIZE SOMETHING THAT IS a MULTIPLE OF 32 to ease cache stuff
#define MULTIPLE_TT(a) (((a/32)+1)*32)
#define O_STREAM_SIZE_BYTES (MULTIPLE_TT(4111)) // (4096) Add some extra bytes for headers
#define I_STREAM_SIZE_BYTES (MULTIPLE_TT(4111)) // (4096)

extern uint8_t output_stream_buffer[O_STREAM_SIZE_BYTES]; // output_stream_buffer
extern uint8_t input_stream_buffer[I_STREAM_SIZE_BYTES]; // input_stream_buffer

typedef struct uart_buffers_status
{
	bool rtr;	// If set, send an ack to the host (tbd when the Rx buffer is clear)
	bool rts; // If set, one can use the
} uart_cf_t;

extern uart_cf_t uart_status;


pb_ostream_t pb_ostream_from_uart(int fd);
pb_istream_t pb_istream_from_uart(int fd);

uint32_t uart_write_packet(pb_ostream_t* s);

void init_uart_pb();
void client_rx_command_len();

void handle_uart();
void handle_commands();



#endif //_PB_TO_UART_H_
