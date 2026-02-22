###################################################################################
#   Copyright (c) 2021,2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################

import os
import logging

import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger("tensorflow").setLevel(logging.ERROR)

import tensorflow as tf

# from tensorflow import keras

H, W, C = 28, 28, 1
IN_SHAPE = (H, W, C)
NB_CLASSES = 10

# Create and train a digit classification model

def load_data():
    """Load MNIST data set """
    mnist = tf.keras.datasets.mnist
    (x_train, y_train), (x_test, y_test) = mnist.load_data()

    # Normalize the input image so that each pixel value is between 0 to 1.
    x_train = x_train / 255.0
    x_test = x_test / 255.0

    x_train = x_train.reshape(x_train.shape[0], H, W, C)
    x_test = x_test.reshape(x_test.shape[0], H, W, C)

    # convert class vectors to binary class matrices
    y_train = tf.keras.utils.to_categorical(y_train, NB_CLASSES)
    y_test = tf.keras.utils.to_categorical(y_test, NB_CLASSES)

    return x_train, y_train, x_test, y_test


def build_model():
    """Define the model architecture."""
    model = tf.keras.Sequential([
      tf.keras.layers.InputLayer(input_shape=IN_SHAPE),
      tf.keras.layers.Conv2D(filters=12, kernel_size=(3, 3), activation=tf.nn.relu),
      tf.keras.layers.MaxPooling2D(pool_size=(2, 2)),
      tf.keras.layers.Dropout(0.5),
      tf.keras.layers.Flatten(),
      tf.keras.layers.Dense(10, activation='softmax')
    ])

    model.compile(optimizer='adam',
                  loss=tf.keras.losses.categorical_crossentropy,
                  metrics=['accuracy'])

    model.summary()

    return model


def _get_shape_inputs(k_model):
    """Return list of input shape"""

    if k_model.__class__.__name__ == 'Sequential':
        layer = k_model.layers[0]
        return [(1,) + layer.input_shape[1:]]
    else:
        s_in = []
        for layer in k_model.layers:
            if layer.__class__.__name__ == 'InputLayer':
                s = layer.input_shape
                s_in.append((1,) + s[0][1:])
        return s_in


def tflite_convert_to_int8(k_model, data, type_io=None):
    """Quantize a Keras model"""

    print("Quantize the model (post-quantization) io_type={}".format(type_io), flush=True)

    converter = tf.lite.TFLiteConverter.from_keras_model(k_model)

    shape_inputs = _get_shape_inputs(k_model)

    assert len(shape_inputs) == 1

    def rep_data_gen():
        # note: should be updated for multiple inputs
        for i in data[0:100]:
            f_ = np.reshape(i, shape_inputs[0])
            tensor = tf.convert_to_tensor(f_, tf.float32)
            yield [tensor]

    converter.representative_dataset = rep_data_gen
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]

    if type_io:
        converter.inference_input_type = type_io[0]
        converter.inference_output_type = type_io[1]

    return converter.convert()


# Load data set
x, y, tx, ty = load_data()

# Build and train a model
model = build_model()
model.fit(x, y, epochs=2,validation_split=0.1)

print("Saving the model : ", 'mnist_fp32.h5')
model.save('mnist_fp32.h5')

# test the model
_, acc = model.evaluate(tx, ty, verbose=0)

print('acc = {:.2f}'.format(acc))

# post-quantize the model
tf_q = tflite_convert_to_int8(model, x)  # (tf.int8, tf.int8))

print("Saving the model : ", 'mnist_q_with_fp32_io.tflite')  
with open('mnist_q_with_fp32_io.tflite', 'wb') as f:
    f.write(tf_q)
    f.close()