###################################################################################
#   Copyright (c) 2021,2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################

import os
import sys
import argparse
from statistics import mean
import logging
import numpy as np

from sklearn.metrics import classification_report

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger("tensorflow").setLevel(logging.ERROR)

from tensorflow.keras.utils import to_categorical
from tensorflow.keras.datasets import mnist

from stm_ai_runner import AiRunner

_DEFAULT = 'st_ai_ws/'
# _DEFAULT = 'serial'
_DEBUG = False


H, W, C = 28, 28, 1
IN_SHAPE = (H, W, C)
NB_CLASSES = 10

def load_data_test():
    """Load MNIST data set """
    (_, _), (x_test, y_test) = mnist.load_data()

    # Normalize the input image so that each pixel value is between 0 to 1.
    x_test = x_test / 255.0
    x_test = x_test.reshape(x_test.shape[0], H, W, C).astype(np.float32)

    # convert class vectors to binary class matrices
    y_test = to_categorical(y_test, NB_CLASSES)

    return x_test, y_test


parser = argparse.ArgumentParser(description='Test model')
parser.add_argument('--desc', '-d', metavar='STR', type=str, default=_DEFAULT)
parser.add_argument('--batch', '-b', metavar='INT', type=int, default=None)
args = parser.parse_args()

print('using "{}"'.format(args.desc))
runner = AiRunner(debug=_DEBUG)

if not runner.connect(args.desc):
    print(f'runtime "{args.desc}" is not connected (error={runner.get_error()})')
    sys.exit(1)

print(runner, flush=True)
runner.summary()

# Load the data
inputs, refs = load_data_test()

if args.batch or not 'machine' in runner.get_info()['device']:
    nb = 100 if not args.batch else args.batch
    print('INFO: use only the first {} samples (instead {})'.format(nb, inputs.shape[0]), flush=True)
    inputs = inputs[:nb]
    refs = refs[:nb]

# Perform the inference
predictions, profiler = runner.invoke(inputs)

# Display profiling info
print('')
print('execution time           : {:.3f}s'.format(profiler['debug']['host_duration'] / 1000))
print('number of samples        : {}'.format(len(profiler['c_durations'])))
print('inference time by sample : {:.3f}ms (average)'.format(mean(profiler['c_durations'])))

# classification report
print('\nClassification report (sklearn.metrics)\n')

# align the shape of the outputs (c-model is always - (b, h, w, c))
predictions[0] = predictions[0].reshape(refs.shape)

target_names = ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9']
print(classification_report(np.argmax(refs, axis=1), np.argmax(predictions[0], axis=1),
                            target_names=target_names))

runner.disconnect()
