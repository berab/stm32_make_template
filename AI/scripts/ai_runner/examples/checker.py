###################################################################################
#   Copyright (c) 2021, 2024 STMicroelectronics.
#   All rights reserved.
#   This software is licensed under terms that can be found in the LICENSE file in
#   the root directory of this software component.
#   If no LICENSE file comes with this software, it is provided AS-IS.
###################################################################################
"""
Typical ai_runner example
"""
import sys
import argparse

from stm_ai_runner import AiRunner

_DEFAULT = 'st_ai_ws/'


def run(args):
    """Main function"""  # noqa: DAR101,DAR201,DAR401

    mode = AiRunner.Mode.PER_LAYER
    if args.io_only and not args.show_tensors:
        mode = AiRunner.Mode.IO_ONLY
    elif args.with_data:
        mode = AiRunner.Mode.PER_LAYER_WITH_DATA
    if args.perf_only:
        mode |= AiRunner.Mode.PERF_ONLY
    if args.debug:
        mode |= AiRunner.Mode.DEBUG

    print(f'Creating AiRunner session with `{args}`', flush=True)  # noqa: T201

    runner = AiRunner(debug=args.debug)
    runner.connect(args.desc)

    if not runner.is_connected:
        print('ERR: No c-model available, use the --desc/-d option to specifiy a valid path/descriptor')  # noqa: T201
        print(f' {runner.get_error()}')  # noqa: T201
        return 1

    print('')  # noqa: T201
    print(runner, flush=True)  # noqa: T201

    c_name = runner.names[0] if not args.name else args.name

    if c_name not in runner.names:
        print(f'ERR: c-model "{c_name}" is not available')  # noqa: T201
        return 1

    session = runner.session(c_name)
    if args.verbosity:
        print(session.get_inputs())  # noqa: T201
        print(session.get_outputs())  # noqa: T201
        print('session = ', session, flush=True)  # noqa: T201

    session.summary(indent=1)

    print('')  # noqa: T201
    print(f'Running c-model "{c_name}" with random data (b={args.batch})..', flush=True)  # noqa: T201

    inputs = runner.generate_rnd_inputs(session.name, batch_size=args.batch)

    outputs, profiler = session.invoke(inputs, mode=mode)

    runner.print_profiling(inputs, profiler, outputs, indent=1, tensor_info=args.show_tensors)

    runner.disconnect()

    return 0


def main():
    """Main function to parse the arguments"""  # noqa: DAR101,DAR201,DAR401
    parser = argparse.ArgumentParser(description='AI runner')
    parser.add_argument('--desc', '-d', metavar='STR', type=str, help='description', default=_DEFAULT)
    parser.add_argument('--batch', '-b', metavar='INT', type=int, help='batch_size', default=2)
    parser.add_argument('--name', '-n', metavar='STR', type=str, help='c-model name', default=None)

    parser.add_argument('--perf-only', action='store_true', help="debug option")
    parser.add_argument('--io-only', action='store_true', help="without intermediate values")
    parser.add_argument('--with-data', action='store_true', help="dump intermediate values")

    parser.add_argument('--show-tensors', action='store_true', help="display tensor info")

    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1,
                        type=int, choices=range(0, 3),
                        help="set verbosity level",
                        default=0)
    parser.add_argument('--debug', action='store_true', help="debug option")
    args = parser.parse_args()

    return run(args)


if __name__ == '__main__':
    sys.exit(main())
