---
title:  MNIST example
---


# Overview

This is a typical example to use the ST AI runner Python module with the user data against
the generated c-model to perform a advanced validation flow.

`'train.py'` allows to generate and train a Keras model with the MNIST data set. The model
is also quantized using TFLite converter with a part of the data-set.

`'test.py'` demonstrates how to test the generate c-model (X86 or target implementation)
with the MNIST test data set. Classification report is based on sklearn.metrics function.


# Setting up work environment

Following Python packages should be installed in your Python 3.x environment to launch the scripts
(see `requirements.txt`file). It is recommended to use a virtual environment.

```
# to use ai_runner
protobuf<3.21
tqdm
colorama
pyserial

# for train/test scripts
tensorflow==2.15.1
scikit-learn
```

To use the `'test.py'` script, and be able to import the `'stm_ai_runner'` package,
the `'PYTHONPATH'` environment variable should updated:

```bash
export STEDGEAI_INSTALL_DIR=...  # root location where the stedgeai package has been installed
export PYTHONPATH=$STEDGEAI_INSTALL_DIR/scripts/ai_runner:$PYTHONPATH
```


## Note about the version of the 'protobuf' package

The `stm_ai_runner` package communicates with the board using a protocol based on the `'Nanopb'` module version 0.3.x. `'Nanopb'` is a plain-C implementation of Google's Protocol Buffers data format. The `stm_ai_runner` package is fully compatible with protobuf versions below 3.21. For more information, you can visit the [Nanopb website][NANO_PB]. If a more recent version of `'protobuf'` is installed in your environment and the protobuf package cannot be downgraded, the following environment variable can be used:

```bash
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
```

[NANO_PB]: https://jpa.kapsi.fi/nanopb/

# How-to

- Create and train the Keras model

```bash
python train.py
```

Generated model files: `mnist_fp32.h5`, `mnist_q_with_fp32_io.tflite`


- Generate and validate the c-model with ST AI CLI

Standard approach with random data based on the numerical comparaison between the execution of the
original model and the generated c-model. 

```bash
stedgeai validate -m mnist_q_with_fp32_io.tflite --target stm32
```

- Generate the shared lib (also called DLL) with the c-model

Following command allows to generate a shared library (including the 
generated network.c files and requested c-kernels) which should be
loaded in a Python process throught the ai_runner interface. 

```bash
stedgeai generate -m mnist_q_with_fp32_io.tflite --target stm32 --dll
```

```bash
 Generated files (6)
 -------------------------------------------------------------------
 ...
 ..\st_ai_ws\inspector_network\workspace\lib\libai_network.dll

```

To perform also a validation on the board, a STM32 board should be also flashed with
the aiValidation test application including the model.


- Report the accuracy of the generated c-model and the MNIST test set

With the host shared library

```bash
python test.py -d st_ai_ws
```

```bash
...
Classification report (sklearn.metrics)

              precision    recall  f1-score   support

          c0       0.97      0.99      0.98       980
          c1       0.98      0.99      0.99      1135
          c2       0.96      0.96      0.96      1032
          c3       0.94      0.98      0.96      1010
          c4       0.98      0.98      0.98       982
          c5       0.98      0.97      0.98       892
          c6       0.97      0.98      0.97       958
          c7       0.96      0.94      0.95      1028
          c8       0.98      0.94      0.96       974
          c9       0.96      0.95      0.95      1009

    accuracy                           0.97     10000
   macro avg       0.97      0.97      0.97     10000
weighted avg       0.97      0.97      0.97     10000
```


With a STM32 board (first valid serial COM port is used)

```bash
python test.py -d serial
```

To indicate a specific serial COM port, following command can be used:

```bash
python test.py -d serial:COMx             # Windows world
python test.py -d serial:/dev/ttyACMx     # Linux/MacOS world
```



