###################################################################################
#   Copyright (c) 2021,2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Minimal example - Invoke a model with the random data

Model should be previously deployed on a pysical board with the aiValidation stack
or on the host.


Deployment on the host:

    $ stedgeai generate -d <model_path> --target stm32 --c-api st-ai --dll

    Generated host shared dll is located by default in the ./st_ai_ws folder.


Deployment on a pysical board:
    $ stedgeai generate -d <model_path> --target stm32 --c-api st-ai

    Generated specialized files are included in the built-in aiValidation test application.
"""

import sys
import argparse
from statistics import mean
from stm_ai_runner import AiRunner

_DEFAULT = 'st_ai_ws/'


def example(args):
    """Entry point"""  # noqa: DAR101,DAR201,DAR401

    print('Creating AiRunner session with `{}`'.format(args), flush=True)  # noqa: T201

    runner = AiRunner(debug=args.debug)
    runner.connect(args.desc)

    if not runner.is_connected:
        print('No c-model available, use the --desc/-d option to specifiy a valid path/descriptor')  # noqa: T201
        print(f' {runner.get_error()}')  # noqa: T201
        return 1

    print('')  # noqa: T201
    print(runner, flush=True)  # noqa: T201

    runner.summary()

    inputs = runner.generate_rnd_inputs(batch_size=args.batch)

    print('')  # noqa: T201
    print('Invoking the model with random data (b={})..'.format(inputs[0].shape[0]), flush=True)  # noqa: T201

    mode = AiRunner.Mode.IO_ONLY
    if args.debug or args.target_log:
        mode |= AiRunner.Mode.DEBUG

    _, profile = runner.invoke(inputs, mode=mode)

    print('')  # noqa: T201
    print('host execution time      : {:.3f}ms'.format(profile['debug']['host_duration']))  # noqa: T201
    print('protocole                : {}'.format(profile['info']['runtime']['protocol']))  # noqa: T201
    print('runtime                  : {}'.format(profile['info']['runtime']['name']))  # noqa: T201
    print('number of sample(s)      : {}'.format(len(profile['c_durations'])))  # noqa: T201
    print('inference time by sample : {:.3f}ms (average)'.format(mean(profile['c_durations'])))  # noqa: T201

    runner.disconnect()

    return 0


def main():
    """ Script entry point """  # noqa: DAR101,DAR201,DAR401

    parser = argparse.ArgumentParser(description='Minimal example')

    parser.add_argument('--desc', '-d', metavar='STR', type=str, help='description for the connection',
                        default=_DEFAULT)
    parser.add_argument('--batch', '-b', metavar='INT', type=int, help='number of sample', default=1)
    parser.add_argument('--debug', action='store_true',
                        help="debug option")
    parser.add_argument('--target-log', action='store_true',
                        help="enable additional log from the target")

    args = parser.parse_args()

    return example(args)


if __name__ == '__main__':
    sys.exit(main())
