python nanopb/generator/nanopb_generator.py -D c/Weights_encryption/nanopb_outputs/ message.proto
python nanopb_tests_venv/Lib/site-packages/grpc_tools/protoc.py --python_out=python/pb_outputs/ --proto_path=. message.proto
