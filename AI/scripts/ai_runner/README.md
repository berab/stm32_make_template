# AiRunner

## Overview

`stm_ai_runner` is a Python module providing an unified inference interface
for the different X-CUBE-AI runtime: X86 or STM32. It allows to use the
generated c-model from an user Python script like a `tf.lite.Interpreter` to
perform an inference. According the capabilities of the associated run-time,
profiling data are also reported (execution time per layer,...).
For advanced usage, the user has the possibility to register a callback allowing
to have the intermediate tensor/feature
values before and/or after the execution of a node.

## Requirements

see `requirements.txt` file.

    pip install -r requirements.txt


Set the environment variable `PYTHONPATH` to tell python where to find the
module.

    $ export PYTHONPATH=<path/to/ai_runner>:$PYTHONPATH


## Getting started

### With a X86 shared library

With the stm.ai 6.0 CLI, `validate` command is used to generate the X86 shared library
(or DLL in Windows world), default location: `stm32ai_ws/inspector_network/workspace/lib/libai_network.dll`

    $ stm32ai validate <my_model> --split-weights

**Note:** `--split-weights` is currently a workaround to generate the shared library with
the weights.
      
With X-CUBE-AI v7+, `--dll` must be used with the `generate` command:
      
    $ stm32ai generate <my_model> --dll


The `example\minimal.py` script is a minimal example to open the shared library
and to perform an inference with the random data. Full file path of the shared
library can be passed to the `connect()` method or only a root directory.

```Python
from stm_ai_runner import AiRunner
runner = AiRunner()
runner.connect('file:stm32ai_ws')  # 'file' prefix can be omitted
...
outputs, _ = runner.invoke(inputs)  # invoke the model
...
```

    $ python examples\minimal.py -d file:stm32ai_ws


### With a STM32 aiValidation firmware

Same interface can be used also to inject the data and to retrieve the predictions from a
model running on a STM32 board. Firmware should be generated with the aiValidation test
application to have the COM stack with the HOST.

```Python
from stm_ai_runner import AiRunner
runner = AiRunner()
runner.connect('serial')  # default, auto-detection
...
outputs, _ = runner.invoke(inputs)  # invoke the model
...
```

    $ python examples\minimal.py -d serial


### Evaluating a generated TFLite model

The `examples/tflite_test.py` script is a typical example to compare the outputs of the
generated C-model against the predictions from the `tf.lite.Interpreter`.

```Python
outputs, _ = ai_runner.invoke(inputs)
tf_outputs = tf_run(tf_interpreter, inputs)
```

1. Generate the X86 shared library or/and the STM32 aiValidation firmware with the TFLite model  
2. Compare the outputs with a STM32 run-time

```bash
$ python examples/tflite_test.py -m <tflite_file_path> -d serial
```


### Per-layer or per-layer-with-data capabilities

The `examples/ai_runner_test.py` script provides an example to exploite the contents
of the returned `profiler` dictionary.  

```python
outputs, profiler = session.invoke(inputs, mode=mode)
```


## Profiler

The `ìnvoke()` method returns a list of numpy (`outputs`) with the predictions and
a dictionary (`profiler`) with the profiling/stat information. 

### `profiler` definition

| key             | description       |
|:----------------|:------------------| 
|`info`           | c-model info (`get_info()`)    | 
|`c_durations`    | inference times by sample in ms (list)  |
|`c_nodes`        | c-node description (list) / `Caps.PER_LAYER` cap. is requested |
|`debug`          | specific dictionary with debug info  |

**sub-dictionary:** `'info'`
  
| key               | description    |
|:------------------|:-------------------------| 
|`name`             | c-name of the model |
|`model_datetime`   | `str` with the date when the model has been generated  |
|`compile_datetime` | `str` with the date when the generated c-files have been compiled |
|`hash`             | hash of the original model file (if available) | 
|`n_nodes`          | number of the c-nodes  |
|`inputs`           | inputs description - list (`get_input_infos()`) | 
|`outputs`          | outputs description - list (`get_output_infos()`) |
|`weights`          | size of the parameters in bytes (c-level)   |
|`activations`      | size of the activations buffer in byte (c-level) |   
|`macc`             | complexity of the model  |
|`runtime`          | run-time description (dictionary)   |
|`c_durations`      | inference times by sample in ms (list)  |
|`debug`            | specific dictionary with debug info  |


**`inputs/outputs`: description of the inputs/outputs of the model**

| key               | description    |
|:------------------|:-------------------------|
|`name`   | tensor name when available else index is used with `input_` prefix | 
|`shape`   | shape definition, BHWC format | 
|`type`   | data type (numpy type is used) | 
|`scale`   | scale factor if available| 
|`zero_point`   | zero-point definition if available | 


**`runtime`: run-time description**

| key               | description    |
|:------------------|:-------------------------|
|`name`   | name - implementation dependent: `X-CUBE-AI`, `TFLM`, ...| 
|`version`   | version of the embedded run-time | 
|`capabilities`   |  list of the supported capabilities | 
|`tools_version`   | version of the tools |  
|`device`   | device description - implementation dependent (dictionary) |  


**`c_nodes`: c-node description**

| key               | description    |
|:------------------|:-------------------------|
|`c_durations`   | inference times in ms (list, one by sample)  | 
|`m_id`   | id/position in the original model  | 
|`layer_type`   | type of layer (implementation specific)  | 
|`type`   | list with the type of the output tensors (numpy type)  | 
|`shape`   | list with the shape of the output tensors, (1,..) format  | 
|`scale`   | list with the scale value if available  | 
|`zero_point`  | list with the zero-point value if available  | 
|`data`   | list of numpy array with the dump of the outputs (`Caps.PER_LAYER_WITH_DATA` cap.)  | 


**`debug` dictionary**

| key               | description    |
|:------------------|:-------------------------|
|`exec_times`       | list with the execution times in ms, one item by sample, HOST point of view  | 
|`host_duration`    | total execution time of the batch, HOST point of view   |   



### connect parameter

`AiRunner()` class is the main object to manage the connection with a given run-time. The `connect(desc)` method is used to bind it. The `desc` parameter (`'str'` type) is used to describe the expected run-time.

Supported run-times  
+ X86 shared library generated by stm.ai tools (v6 version is requested to have the user-callback support). 

| desc                   | description    | 
|:----------------------|:-------------------------| 
| `'file:<dll_path>'`   | indicate the full path of the shared library (extension is optional) | 
| `'<dll_path>'`        | *idem*  | 
| `'<root_dir>'`        | indicate the root location to search a shared library (first shared library found will be used) | 
| `'file:<root_dir>'`   | *idem*  | 

+ STM32 aiValidation firmware with one or multiple models. Note that there is also a support for the STM32 AI run-times based on TensorFlow Light for Micro-controller.

| desc                     | description    | 
|:------------------------|:-------------------------| 
| `' ' `                  | STM32 aiValidation - auto-detection, the first valid COM port is used (default baud-rate: 115200) | 
| `'serial'`              | *idem* | 
| `':'`                   | *idem* | 
| `'serial:COMxx'`        | COMxx should be used (default baud-rate: 115200) | 
| `'serial:921600'`       | auto-detection with a baud-rate of 921600 | 
| `'serial:COMxx:921600'` | COMxx is used with a baud-rate of 921600 | 


# License

AiRunner is licensed under the BSD 3-Clause license.

