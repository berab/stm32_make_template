#ifndef _CLIENT_H_
#define _CLIENT_H_

// Init I/O streams
void init_pb();
void client_clear_output_stream();
void client_clear_input_stream();

//static bool bytes_callback(pb_ostream_t *stream, const pb_field_t *field, void * const *arg);

// Functions related to the user protocol messages
void client_send_raw_data(uint32_t status, uint32_t chunk_no, void* ptr, uint32_t bufsize);
void client_parse_msg(uint32_t size_bytes);
// This processes the encryption packets "pipeline", ensuring do data is overriden and timing uart operations
void process_encryption();

#endif
