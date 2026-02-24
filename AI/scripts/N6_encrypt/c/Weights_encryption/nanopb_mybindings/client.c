#include "pb.h"
#include "pb_encode.h"
#include "pb_decode.h"
#include "client.h"
#include "message.pb.h"
#include "pb_to_uart.h"
#include "encrypt.h"
#include "stm32n6xx_hal.h"
#include "stm32n6570_discovery.h"

pb_ostream_t o_stream ;
pb_istream_t i_stream ;

extern uart_cf_t uart_status;

typedef struct buffered_data
{
	uint32_t size;
	uint8_t buffer[I_STREAM_SIZE_BYTES] __ALIGNED(8); // Buffers should be 8 bytes aligned to ease work with stream engines.
} buffered_data_t;

buffered_data_t rx_buffered_raw_data;
buffered_data_t tx_buffered_raw_data;

typedef struct _enc_params
{
	uint32_t encryption_keys[4];
	uint32_t encryption_rounds;
} encryption_params_t;

typedef struct _enc_chunk
{
	uint32_t chunk_no;
	uint32_t base_addr;
	uint32_t chunk_size;
	bool     is_last;
	void*    data_ptr;
} encryption_chunk_t;

encryption_params_t enc_p;
encryption_chunk_t buffered_chunk, current_chunk;


MyMessage rx_msg;
MyMessage tx_msg;

static struct _epd
{
	bool rx_ready; // If set, the data has been received from host
	bool processing_done; // If true: processing is finished, memcpy and set shadow rx ready
	bool rx_shadow_buffer_ready; // If set, it is possible to do a memcpy from Rx buffer to the shadow buffer (tbd when data processing is over - data is in the Tx shadow buffer)
	bool tx_shadow_buffer_ready; // If set, it is possible to start a new encryption (tbd when data has been copied to the Tx buffer)
}encryption_pipeline_desc;


static enum _current_cmd
{
	NONE = 0,
	ENCRYPT,
	SET_KEYS,

}current_cmd;





/******** STREAM HANDLING ********/
void client_clear_output_stream()
{
	o_stream = pb_ostream_from_buffer(output_stream_buffer, O_STREAM_SIZE_BYTES);
}

void client_clear_input_stream()
{
	i_stream = pb_istream_from_buffer(input_stream_buffer, I_STREAM_SIZE_BYTES);
}

void init_pb()
{
	client_clear_output_stream();
	client_clear_input_stream();
	encryption_pipeline_desc.rx_ready = false;
	encryption_pipeline_desc.processing_done = false;
	encryption_pipeline_desc.rx_shadow_buffer_ready = true;
	encryption_pipeline_desc.tx_shadow_buffer_ready = true;

	// Initialize commands-related variables:
	memset(&enc_p, 0, sizeof(enc_p));
	memset(&buffered_chunk, 0, sizeof(buffered_chunk));
	memset(&current_chunk, 0, sizeof(current_chunk));
}




/******** PROTOCOL MESSAGES HANDLING ********/
void client_send_raw_data(uint32_t status, uint32_t chunk_no, void* ptr, uint32_t bufsize)
{
  // Status - VARINT because enums
  pb_encode_tag(&o_stream, PB_WT_VARINT, RawData_stat_tag);
  pb_encode_varint(&o_stream, RawData_Status_STATUS_FIRST_CHUNK);
  // Chunk number:
  pb_encode_tag(&o_stream, PB_WT_32BIT, RawData_chunk_no_tag);
  pb_encode_fixed32(&o_stream, chunk_no);
  // payload : string because it's BYTES
  pb_encode_tag(&o_stream, PB_WT_STRING, RawData_data_tag);
  pb_encode_string(&o_stream, ptr, bufsize);
  assert(o_stream.errmsg == 0);
  uart_write_packet(&o_stream);
}


/***********************************************
 * Callbacks for the payload of the message (Tx)
 ***********************************************/
bool send_ack()
{
	BSP_LED_Toggle(LED_RED);
	//memcpy(&MyMessage_init_zero, &msg, sizeof(msg));
	o_stream = pb_ostream_from_buffer(output_stream_buffer, O_STREAM_SIZE_BYTES);

	tx_msg.which_payload = MyMessage_ack_tag;
	pb_encode(&o_stream, MyMessage_fields, &tx_msg);
	assert(o_stream.errmsg == 0);
	uart_write_packet(&o_stream);
	return true;
}

bool send_raw_data(uint32_t size)
{
	BSP_LED_Toggle(LED_RED);
	o_stream = pb_ostream_from_buffer(output_stream_buffer, O_STREAM_SIZE_BYTES);

	tx_msg.which_payload = MyMessage_raw_data_tag;
	tx_msg.payload.raw_data.data.size = current_chunk.chunk_size;
	tx_msg.payload.raw_data.chunk_no = current_chunk.chunk_no;
	tx_msg.payload.raw_data.base_address = current_chunk.base_addr;
	pb_encode(&o_stream, MyMessage_fields, &tx_msg);
	assert(o_stream.errmsg == 0);
	uart_write_packet(&o_stream);
	return true;
}


/***********************************************
 * Callbacks for the payload of the message (Rx)
 ***********************************************/
bool EncryptionParams_callback(pb_istream_t *stream, const pb_field_t *field, void **arg)
{
	//uint32_t* ptr = *arg;
	uint32_t k;
	// get the two 64-bit-keys
	for(k=0; k<4; ++k)
	{
		pb_decode_varint32(stream, *arg + k*sizeof(uint32_t));
	}
	return true;
}




bool msg_callback(pb_istream_t *stream, const pb_field_t *field, void **arg)
{
    // Set the correct callback(s) for the current message before decoding sub-messages
	//MyMessage *topmsg = field->message;
    //printf("prefix: %d\n", (int)topmsg->status);

    switch(field->tag)
    {
    case MyMessage_encryption_params_tag:
    	// Save encryption keys to encryption_keys global variable
    	EncryptionParams *msg_ep = field->pData;
    	msg_ep->keys.funcs.decode = EncryptionParams_callback;
    	msg_ep->keys.arg = enc_p.encryption_keys;
    	break;
    case MyMessage_raw_data_tag:
    	// Copy raw message somewhere for processing
    	RawData *msg_rd = field->pData;
    	// tbd after decoding: No callbacks for the bytes
    	break;
    }
    return true;
}


// The message should be in the Rx buffer
void client_parse_msg(uint32_t size_bytes)
{
	bool status;
	rx_msg.cb_payload.funcs.decode = msg_callback;
	i_stream = pb_istream_from_buffer(input_stream_buffer, size_bytes);
	status = pb_decode(&i_stream, MyMessage_fields, &rx_msg);
	BSP_LED_Toggle(LED_GREEN);
	if (!status)
    {
        printf("Decoding of the message failed: %s\n", PB_GET_ERROR(&i_stream));
        return;
    }

    // Check payload status, and gather data that has not been handled before ...
    switch (rx_msg.which_payload)
    {
    case MyMessage_encryption_params_tag:
       	// Encryption keys are handled in the Encryption Param callback already
    	enc_p.encryption_rounds = ((EncryptionParams*)&rx_msg.payload)->nb_rounds;
    	encrypt_set_keys_and_round(enc_p.encryption_keys, enc_p.encryption_rounds);
    	send_ack();
    	current_cmd  = NONE;
    	break;
    case MyMessage_raw_data_tag:

    	encryption_pipeline_desc.rx_ready = true;
    	// Defer the processing to the function executing the encryption pipeline.
    	current_cmd  = ENCRYPT;
    	break;
    default:
    	current_cmd = NONE;
    }
}


// This processes the encryption packets "pipeline", ensuring do data is overriden and timing uart operations
void process_encryption()
{
	uint32_t size;
	if (current_cmd != ENCRYPT)
	{
		return;
	}
	if ((encryption_pipeline_desc.rx_ready == true) && (encryption_pipeline_desc.rx_shadow_buffer_ready == true))
	{
		// Copy Rx to shadow buffer for processing
		size = ((RawData*)&rx_msg.payload)->data.size;

		rx_buffered_raw_data.size = size;
		memcpy(rx_buffered_raw_data.buffer,  (void*)((RawData*)&rx_msg.payload)->data.bytes, size);
		// Create the buffered chunk object from message data (will be used to transfer info through the pipeline)
		buffered_chunk.chunk_no = ((RawData*)&rx_msg.payload)->chunk_no;
		buffered_chunk.chunk_size = size;
		buffered_chunk.data_ptr = rx_buffered_raw_data.buffer;
		buffered_chunk.base_addr = (uint32_t)((RawData*)&rx_msg.payload)->base_address;
		if (((RawData*)&rx_msg.payload)->stat == RawData_Status_STATUS_LAST_CHUNK)
		{
			buffered_chunk.is_last = true;
		}
		else
		{
			buffered_chunk.is_last = false;
		}
		// End buffered chunk creation, the buffer points to rx_buffered_raw_data (== "rx_shadow_buffer")
		encryption_pipeline_desc.rx_ready = false;
		encryption_pipeline_desc.rx_shadow_buffer_ready = false;
		uart_status.rtr = true;
	}
	if ((encryption_pipeline_desc.rx_shadow_buffer_ready == false) && // data incoming
			(encryption_pipeline_desc.tx_shadow_buffer_ready == true) &&  // output buffer after processing of the data is ready
			(uart_status.rts == true))	// it is possible to send an ack
	{
		// Rx buffer has been copied to Shadow buffer, allow the host to send new data
		// Copy is done on the shadow buffer, allow the host to send new data
		send_ack();
		memcpy(&current_chunk, &buffered_chunk, sizeof(buffered_chunk));	// move buffered chunk to current chunk
		// Start processing on rx_buffered_raw_data.buffer data .. the output should be in  tx_buffered_raw_data.buffer
		// The processing should set processing_done = true
		encryption_pipeline_desc.tx_shadow_buffer_ready = false;
		encryption_pipeline_desc.processing_done = false;
		tx_buffered_raw_data.size = current_chunk.chunk_size;
		//memcpy( (void*)tx_buffered_raw_data.buffer, rx_buffered_raw_data.buffer, size);
		// Encryption procedure is blocking (i.e. "processing_done" flag is not useful in this case, and will be set after the following line...)
		encrypt_encrypt((void*)tx_buffered_raw_data.buffer, current_chunk.data_ptr,  current_chunk.chunk_size, current_chunk.base_addr);
		encryption_pipeline_desc.processing_done = true;
	}

	if ((encryption_pipeline_desc.processing_done == true) && (uart_status.rts == true))
	{
		// Processing is over: copy shadow buffer to Tx buffer if ok, set Rx shadow buffer empty
		encryption_pipeline_desc.rx_shadow_buffer_ready = true;
		encryption_pipeline_desc.processing_done = false;
		memcpy((void*)((RawData*)&tx_msg.payload)->data.bytes,  tx_buffered_raw_data.buffer, current_chunk.chunk_size);
		encryption_pipeline_desc.tx_shadow_buffer_ready = true;
		send_raw_data(current_chunk.chunk_size);

		// Check if last packet
		if (current_chunk.is_last == true)
		{
			BSP_LED_Off(LED_RED);
			BSP_LED_Off(LED_GREEN);
		}
	}
}




