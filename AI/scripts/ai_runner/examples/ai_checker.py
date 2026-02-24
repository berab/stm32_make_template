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
import os
import argparse
import logging
import re
import multiprocessing
import pathlib

from time import perf_counter

import numpy as np

try:
    from stm_ai_runner import AiRunner, __version__
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    try:
        from stm_ai_runner import AiRunner, __version__
    except ImportError as e:
        print('ModuleNotFoundError:', e,  # noqa: T201
              '- Update the \'PYTHONPATH\' to find the stm_ai_runner Python module.')
        sys.exit(1)


_DEFAULT = 'serial'
__VERSION__ = "1.3.1"


# History
#
#  1.3.0 - disable the dump of the intermediate tfl tensors
#          by default, "--with-data" should be used. User should be aware that
#          for some TFlite models, when "experimental_preserve_all_tensors" option is used,
#          outputs of the model can be different.
#  1.3.1 - add check/detection to import stm_ai_runner module w/o PYTHONPATH
#


def _shape_desc(values):
    values = list(values)
    return '(' + ','.join([str(v) for v in values]) + ')'


def topk_by_sort(values, k, axis=None, ascending=True):
    """Return topK values - (index[], values[])"""  # noqa: DAR101,DAR201,DAR40
    if not ascending:
        values *= -1
    ind = np.argsort(values, axis=axis)
    ind = np.take(ind, np.arange(k), axis=axis)
    if not ascending:
        values *= -1
    val = np.take_along_axis(values, ind, axis=axis)
    return ind, val


def print_table(table, print_fn=None, with_header=True, indent=0):
    """Simple utility function to print a formatted table"""  # noqa: DAR101,DAR201,DAR401

    print_drv = print if print_fn is None else print_fn  # noqa: T202

    def p_fn(str_):
        """."""  # noqa: DAR101,DAR201,DAR401
        print_drv('{}{}'.format(' ' * indent, str_))

    if 'rows' not in table:
        return

    if 'fmt' not in table:
        fmt = [''] * len(table['rows'][0])
    else:
        fmt = table['fmt']

    row_size = [0] * len(table['rows'][0])
    for row in table['rows']:
        c_size = []
        if not row:
            continue
        for item in row:
            c_size.append(len(str(item)) + 2)
        row_size = [max(r, cur) for r, cur in zip(row_size, c_size)]

    line_size = sum(row_size) + len(row_size) - 1

    if 'title' in table:
        p_fn('{}'.format(table['title']))
        line_size = max(line_size, len(table['title']))

    p_fn('-' * line_size)

    for idx, row in enumerate(table['rows']):
        if not row:
            p_fn('-' * line_size)
            continue
        str_ = ''
        for size_, fmt_, item in zip(row_size, fmt, row):
            item = str(item)
            if '>' in fmt_:
                str_ += ' ' * (size_ - len(item)) + item
            else:
                str_ += item + ' ' * (size_ - len(item))
            str_ += ' '
        p_fn(str_)
        if idx == 0 and with_header:
            p_fn('-' * line_size)
    if with_header:
        p_fn('-' * line_size)


def load_tflite_model(tflite_file, batch_size, logger, preserve_internal=False, use_built_op='AUTO',
                      no_multi_threads=False, verbosity=0):
    """Create the TFLite interpreter"""  # noqa:DAR101,DAR201
    import tensorflow as tf  # ignore_missing_imports: ignore

    if not tflite_file:
        return None, []

    indent = 1
    print_drv = print if logger is None else logger.info  # noqa: T202

    def p_fn(str_):
        """."""  # noqa:DAR101
        print_drv('{}{}'.format(' ' * indent, str_))

    def build_row_tensor_table(first, tens):
        row = [first]
        name = tens['name'].split('/')
        name = '{}/{}/{}'.format(len(name) - 2, name[-2], name[-1]) if len(name) > 1 else name[0]
        row.append(name)
        row.append(tens['index'])
        row.append(_shape_desc(tens['shape']))
        row.append(np.dtype(tens['dtype']))
        if tens['quantization'][0]:
            row.append('S:{:.4f} O:{}'.format(tens['quantization'][0], tens['quantization'][1]))
        else:
            row.append('')
        return row

    def build_row_op_table(first, operator):
        row = [first]
        row.append(operator['op_name'])
        row.append(operator['inputs'])
        row.append(operator['outputs'])
        return row

    p_fn('')
    p_fn('Loading \'{}\' file...'.format(tflite_file))
    if no_multi_threads:
        nb_threads = None
    else:
        nb_threads = int(multiprocessing.cpu_count() / 2)
    if use_built_op == 'DEFAULT':
        resolver_type = tf.lite.experimental.OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES
    elif use_built_op == 'BUILTIN_REF':
        resolver_type = tf.lite.experimental.OpResolverType.BUILTIN_REF
    elif use_built_op == 'BUILTIN':
        resolver_type = tf.lite.experimental.OpResolverType.BUILTIN
    else:
        resolver_type = tf.lite.experimental.OpResolverType.AUTO

    interpreter = tf.lite.Interpreter(model_path=str(tflite_file), num_threads=nb_threads,
                                      experimental_op_resolver_type=resolver_type,
                                      experimental_preserve_all_tensors=preserve_internal)

    p_fn(f' OpResolver={resolver_type}, _preserve_all_tensors={preserve_internal},'
         f' num_threads={nb_threads}')
    p_fn(f' Tensorflow v{tf.__version__} is used')

    input_details = interpreter.get_input_details()
    if batch_size > 1:
        for in_d in input_details:
            n_shape = list(in_d['shape'])
            n_shape[0] = batch_size
            interpreter.resize_tensor_input(in_d["index"], n_shape)

    interpreter.allocate_tensors()

    output_details = interpreter.get_output_details()
    input_details = interpreter.get_input_details()

    interpreter.invoke()

    p_fn('')
    table = {'title': 'TFL tensors', 'rows': [], 'fmt': ['', '', '', '', '', '', '', '']}
    table['rows'].append(['tensor', 'name', 'index', 'shape', 'dtype', 'quant', 'data'])

    for idx, tens in enumerate(input_details):
        row = build_row_tensor_table('I.{}'.format(idx), tens)
        row.append('')
        table['rows'].append(row)

    for idx, tens in enumerate(output_details):
        row = build_row_tensor_table('O.{}'.format(idx), tens)
        row.append('')
        table['rows'].append(row)

    if verbosity > 0 and not preserve_internal:
        print_table(table, p_fn)
        p_fn('')

    if not preserve_internal:
        logger.info('')
        return interpreter, []

    table_op = {'title': 'TFL operators', 'rows': [], 'fmt': ['', '', '>', '>', '>']}
    table_op['rows'].append(['op', 'name', 'in', 'out', 'type'])

    tensor_details = interpreter.get_tensor_details()
    ops_details = interpreter._get_ops_details()  # pylint: disable=protected-access
    tfl_internals = []
    for op_d in ops_details:
        tfl_internals.append({'name': '{}'.format(op_d['op_name']), 'idx': op_d['index'], 'outputs': []})
        table_op['rows'].append(build_row_op_table('N.{}'.format(op_d['index']), op_d))
        for port, o_idx in enumerate(op_d['outputs']):
            tens = tensor_details[o_idx]
            data = interpreter.get_tensor(o_idx)
            tag = 'N.{}.{}'.format(op_d['index'], port)
            tfl_internals[-1]['outputs'].append({'port': port, 'idx': o_idx, 'tag': tag, 'data': None})
            row = build_row_tensor_table(tag, tens)
            row.append('{}/{}'.format(_shape_desc(data.shape), data.dtype))
            table['rows'].append(row)

    if verbosity > 0:
        print_table(table, p_fn)
        p_fn('')
        print_table(table_op, p_fn)
        p_fn('')
    else:
        p_fn(f' nb operators  {len(ops_details)}')
        p_fn(f' nb tensor     {len(tensor_details)}')

    return interpreter, tfl_internals


def invoke_tflite_model(interpreter, inputs, tfl_internals, logger):
    """Invoke the TFLite interpreter"""  # noqa:DAR101,DAR201

    if interpreter is None:
        return []

    inputs = inputs if isinstance(inputs, list) else list(inputs)

    logger.info('Invoking TFLite model...')

    outputs = []
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    for in_d, in_v in zip(input_details, inputs):
        interpreter.set_tensor(in_d["index"], in_v.reshape(in_d["shape"]))

    interpreter.invoke()

    for out_d in output_details:
        outputs.append(interpreter.get_tensor(out_d["index"]))

    for internal in tfl_internals:
        for port in internal['outputs']:
            port['data'] = interpreter.get_tensor(port["idx"])

    return outputs


def print_tflite_profiling(interpreter, inputs, tfl_internals, outputs, logger):
    """."""  # noqa:DAR101,DAR201
    if interpreter is None:
        return

    indent = 1
    print_drv = print if logger is None else logger.info  # noqa: T202

    def p_fn(str_):
        """."""  # noqa:DAR101
        print_drv('{}{}'.format(' ' * indent, str_))

    def build_row_stat_table(first, arr):
        row = [first]

        if arr.dtype in [float, np.float32, np.float64]:
            min_ = '{:.03f}'.format(arr.min())
            max_ = '{:.03f}'.format(arr.max())
        else:
            min_ = '{}'.format(arr.min())
            max_ = '{}'.format(arr.max())

        row.append('{}/{}'.format(_shape_desc(arr.shape), arr.dtype))
        row.extend([min_, max_, '{:6.03f}'.format(arr.mean()), '{:6.03f}'.format(arr.std())])
        return row

    p_fn('')
    table = {'title': 'TFL Profiling', 'rows': [], 'fmt': ['', '', '>', '>', '>', '>']}
    table['rows'].append(['tensor', 'shape/type', 'min', 'max', 'mean', 'std'])

    for idx, in_ in enumerate(inputs):  # interpreter.get_input_details()):
        table['rows'].append(build_row_stat_table('I.{}'.format(idx), in_))

    for internal in tfl_internals:
        for idx, port in enumerate(internal['outputs']):
            table['rows'].append(build_row_stat_table('{}'.format(port['tag']), port['data']))

    for idx, out_ in enumerate(outputs):  # , interpreter.get_output_details()):
        table['rows'].append(build_row_stat_table('O.{}'.format(idx), out_))

    print_table(table, p_fn)
    p_fn('')


def check_io(runner, tfl_interpreter, logger):
    """."""  # noqa:DAR101,DAR201,DAR401

    if tfl_interpreter is None or runner is None:
        return

    logger.info('Checking IO tensors...')

    tfl_is = tfl_interpreter.get_input_details()
    tfl_os = tfl_interpreter.get_output_details()
    ai_is = runner.get_input_infos()
    ai_os = runner.get_output_infos()

    if len(tfl_is) != len(ai_is) or len(tfl_os) != len(ai_os):
        raise ValueError('IO size are not consistent')

    for tf_i, ai_i in zip(tfl_is, ai_is):
        if tf_i['dtype'] != ai_i['type']:
            raise ValueError(f"Invalid I dtype, {ai_i['type']}, expected {tf_i['dtype']}")
        if np.prod(tf_i['shape'][1:]) != np.prod(ai_i['shape'][1:]):
            raise ValueError(f"Invalid I shape, {ai_i['shape']}, expected {tf_i['shape']}")

    for tf_o, ai_o in zip(tfl_os, ai_os):
        if tf_o['dtype'] != ai_o['type']:
            raise ValueError(f"Invalid O dtype, {ai_o['type']}, expected {tf_o['dtype']}")
        if np.prod(tf_o['shape'][1:]) != np.prod(ai_o['shape'][1:]):
            raise ValueError('Invalid O shape')

    logger.info(' OK')


def gen_datas(runner, name, batch, range_value, logger, rnd_gen):
    """."""  # noqa:DAR101,DAR201

    logger.info('')
    logger.info('Generating input data... (b={}, range={})'.format(batch, range_value))

    val = range_value
    if range_value and len(range_value) == 1:
        val = [range_value[0]]
        logger.info(' same value is used for all items: {}'.format(val))

    inputs = runner.generate_rnd_inputs(name, batch_size=batch, rng=rnd_gen, val=val)

    logger.info('')

    return inputs


def remove_nans(lhs, rhs):
    """Remove NaNs and infinities from a pair of arrays."""  # noqa: DAR101,DAR201
    mask = (np.isnan(lhs) & np.isnan(rhs)) | ((lhs == np.inf) & (rhs == np.inf)) | ((lhs == -np.inf) & (rhs == -np.inf))
    lhs[mask] = rhs[mask] = 0.0

    return lhs, rhs


def fix_and_check_valid_tag(tag, p_fn):
    """Fix the expected tag definition"""  # noqa:DAR101,DAR201
    tag = tag.upper()
    stag = tag.split('.')
    if len(stag) < 3:
        tag += '.0'

    if bool(re.match(r'E.[0-9]+.[0-9]+', tag)):
        return tag

    if not bool(re.match(r'N.[0-9]+.[0-9]+', tag)):
        p_fn('WARN: \'{}\' invalid tag format'.format(tag))
        return None

    return tag


def get_from_tflm(tag, tfl_internals):
    """Extract a given tensor"""  # noqa:DAR101,DAR201

    if not tfl_internals:
        return None

    if len(tag.split('.')) == 2:
        tag += '.0'

    for internal in tfl_internals:
        for _, port in enumerate(internal['outputs']):
            if tag == port['tag']:
                return port['data']

    return None


def get_from_stm_ai(tag, ai_profiler, ref, p_fn):
    """Extract a given tensor"""  # noqa:DAR101,DAR201

    if not ai_profiler:
        return None

    if len(tag.split('.')) == 2:
        tag += '.0'

    if ai_profiler['c_nodes']:
        for _, c_node in enumerate(ai_profiler['c_nodes']):
            for _, (data, io_tensor) in enumerate(zip(c_node['data'], c_node['io_tensors'])):
                if data.size:
                    if io_tensor.tag == tag:
                        if ref is not None:
                            if ref.dtype == data.dtype and ref.size == data.size:
                                return data
                            else:
                                msg_ = '{} tag, type: {} -> {}, size: {} -> {}'.format(tag, data.dtype,
                                                                                       ref.dtype,
                                                                                       data.size, ref.size)
                                p_fn('ERR: Incompatible tensor fmt for STM.AI.' + msg_)

    if not ai_profiler['c_nodes']:
        p_fn('WARN: STAM.AI model should be executed not only with IO_ONLY option')

    return None


def get_histogram(ref, desc, density=False):
    """Return histogram of the error"""  # noqa:DAR101,DAR201

    import termplotlib as tpl

    res = '\n'

    counts, bin_edges = np.histogram(ref, bins=64, range=(-128, 127), density=density)
    bin_ = ['  {:-4f}'.format(v) for v in bin_edges]
    fig = tpl.figure()
    fig.barh(counts, bin_, force_ascii=True)
    res += f' {desc} distribution\n'
    res += ' ' + '-' * 50 + '\n'
    res += fig.get_string()
    res += '\n' + ' ' + '-' * 50 + '\n'
    return res


def compute_metrics(ai_profiler, quant_params, ai_outputs, tfl_internals, tfl_outputs, mapper, histo, logger):
    """."""  # noqa:DAR101,DAR201
    if not tfl_outputs:
        logger.warning(" WARN: Skipped, no TFL data...")
        return

    indent = 1
    print_drv = print if logger is None else logger.info  # noqa: T202

    def p_fn(str_):
        """."""  # noqa:DAR101
        print_drv('{}{}'.format(' ' * indent, str_))

    def dequant(idx, vals, quant_params):
        """Dequant the quantized values"""  # noqa: DAR201,DAR101
        if not quant_params:
            return vals
        param = quant_params[idx]
        if len(param['scales']):
            return (vals.astype(np.float32) - param['zero_points'][0]) * param['scales'][0]
        return vals

    def _bias(ref, pred):
        """Return bias"""  # noqa: DAR201,DAR101
        return np.mean(ref - pred)

    def _min(ref, pred):
        """Return min diff"""  # noqa: DAR201,DAR101
        return (ref - pred).min()

    def _max(ref, pred):
        """Return max diff"""  # noqa: DAR201,DAR101
        return (ref - pred).max()

    def _std(ref, pred):
        """Return bias"""  # noqa: DAR201,DAR101
        return np.std(ref - pred, ddof=1)

    def _mse(ref, pred):
        """Return Mean Squared Error (MSE)"""  # noqa: DAR201,DAR101
        return np.mean((ref - pred) ** 2)

    def _rmse(ref, pred):
        """Return Root Mean Squared Error (RMSE)."""  # noqa: DAR201,DAR101
        return np.sqrt(_mse(ref, pred))

    def _cosine(ref, pred):
        """Return Cosine Similarity (COS)"""  # noqa: DAR201,DAR101
        ref_ = ref
        pred_ = pred
        numerator = np.dot(ref_.flatten(), pred_.flatten())
        denominator = np.linalg.norm(ref_.flatten()) * np.linalg.norm(pred_.flatten() + np.finfo(np.float32).eps)
        if np.isclose(numerator, denominator, rtol=np.finfo(np.float32).eps):
            err = np.float32(1.0)
        else:
            err = np.float32(numerator / denominator)
        return err

    def _nse(ref, pred):
        """Return Nash-Sutcliffe efficiency criteria"""  # noqa: DAR201,DAR101
        # Normalized statistic that determines the relative magnitude of
        # the residual variance ("noise") compared to the measured data
        # variance ("information").
        # Regressor model - range = (-inf, 1], bigger is best
        #   numerator = np.sum((ref.flatten() - pred.flatten()) ** 2)
        #   denominator = np.sum((ref.flatten() - np.mean(ref.flatten())) ** 2)
        #   return 1 - numerator / denominator
        nse_ = 1 - _mse(ref, pred) / ((np.std(ref, ddof=1) ** 2) + np.finfo(np.float32).eps)
        return nse_

    def _histogram(ref, pred, histo=None):
        """Return histogram of the error"""  # noqa:DAR101,DAR201

        import termplotlib as tpl

        diff_all = np.subtract(ref, pred).flatten()
        diff = diff_all[diff_all != 0]

        perc = 1 - ((diff_all.size - diff.size) / diff_all.size)

        no_diff = False
        if diff.size == 0:
            no_diff = True
            diff = diff_all

        if ref.dtype != np.float32:
            min_, max_ = int(np.min(diff)), int(np.max(diff))
        else:
            min_, max_ = np.min(diff), np.max(diff)
        n_bins = 20
        if ((max_ - min_) / n_bins) < 1:
            n_bins = max_ - min_

        if n_bins < 3:
            n_bins = 4
            h_min_, h_max_ = -1, 3
        else:
            h_min_, h_max_ = min_, max_

        counts, bin_edges = np.histogram(diff, bins=int(n_bins), range=(h_min_, h_max_))
        bin_ = [f'  {v:-4.1f}' for v in bin_edges]
        fig = tpl.figure()
        fig.barh(counts, bin_, force_ascii=True)
        desc = f' REF[{np.min(ref)}, {np.max(ref)}], PRED[{np.min(pred)}, {np.max(pred)}],'
        if no_diff:
            desc += f' NO DIFF[{min_:.04f}, {max_:.04f}]'
        else:
            desc += f' {diff.size:,d}/{ref.size:,d} != 0 ({perc * 100:.2f}%), DIFF[{min_:.03f}, {max_:.03f}]'

        # fig.show()
        len_ = len(desc)

        res = '-' * len_ + '\n'
        res += desc
        res += '\n ' + '-' * len_ + '\n'

        if histo and histo == 'full':
            res += get_histogram(ref, 'TFL.REF')
            res += '\n'
            res += ' Error distribution\n'
            res += ' ' + '-' * len_ + '\n'

        res += fig.get_string()

        res += '\n\n'
        res += ' COS  : {:.3f}\n'.format(_cosine(ref, pred))
        res += ' NSE  : {:.3f}\n'.format(_nse(ref, pred))
        res += ' RMSE : {:.8f}\n'.format(_rmse(ref, pred))

        return res

    def build_row_metric_table(first, shape_type, ref, pred):
        row = [first]
        row.append(shape_type)
        row.append('{:.3f}'.format(_cosine(ref, pred)))
        row.append('{:.3f}'.format(_nse(ref, pred)))
        row.append('{:.8f}'.format(_min(ref, pred)))
        row.append('{:.8f}'.format(_max(ref, pred)))
        row.append('{:.8f}'.format(_mse(ref, pred)))
        row.append('{:.8f}'.format(_rmse(ref, pred)))
        row.append('{:.8f}'.format(_bias(ref, pred)))
        row.append('{:.8f}'.format(_std(ref, pred)))
        return row

    table = {'title': 'Computed metrics (tfl/stm.ai)', 'rows': [],
             'fmt': ['', '', '>', '>', '>', '>', '>', '>', '>', '>']}
    table['rows'].append(['tensor', 'item', 'cos', 'nse', 'min', 'max', 'mse', 'rmse', 'bias', 'std'])

    for idx, (tf_o, ai_o) in enumerate(zip(tfl_outputs, ai_outputs)):
        shape_type = '{:,}/{}/{}'.format(tf_o.size, tf_o.dtype, '(' + ','.join([str(v_) for v_ in tf_o.shape]) + ')')
        histo_ = histo if (histo and np.issubdtype(tf_o.dtype, np.integer)) else None
        dtf_o = dequant(idx, tf_o.flatten().astype(np.float32), quant_params)
        dai_o = dequant(idx, ai_o.flatten().astype(np.float32), quant_params)
        table['rows'].append(build_row_metric_table(f'O.{idx}/O.{idx}', shape_type, dtf_o, dai_o))

        if histo_:
            p_fn(f'\n O.{idx}/O.{idx} {shape_type} Histogram of the error "{tf_o.dtype}"')
            p_fn(_histogram(dtf_o, dai_o, histo_))

    if mapper:
        for req_map in mapper:
            req_map = req_map.split(":")
            if len(req_map) == 1:
                req_map.append(req_map[0])
            if len(req_map) != 2:
                p_fn('\nwarning: \'{}\' is an invalid map request - \'N.n.p:N.n.p\''.format(
                    ':'.join(req_map)))
                continue
            req_map[0] = fix_and_check_valid_tag(req_map[0], p_fn)
            req_map[1] = fix_and_check_valid_tag(req_map[1], p_fn)
            if not req_map[0] or not req_map[1]:
                continue
            ref = get_from_tflm(req_map[0], tfl_internals)
            pred = get_from_stm_ai(req_map[1], ai_profiler, ref, p_fn)
            if ref is not None and pred is not None:
                shape_type = '{:,}/{}/{}'.format(ref.size, ref.dtype,
                                                 '(' + ','.join([str(v_) for v_ in ref.shape]) + ')')
                histo_ = histo if (histo and np.issubdtype(ref.dtype, np.integer)) else None
                ref, pred = ref.flatten().astype(np.float32), pred.flatten().astype(np.float32)
                table['rows'].append(build_row_metric_table('{}/{}'.format(req_map[0], req_map[1]),
                                                            shape_type, ref, pred))
                if histo_:
                    p_fn('\n {}/{} {} Histogram of the error'.format(req_map[0], req_map[1], shape_type))
                    p_fn(_histogram(ref, pred, histo_))
            else:
                p_fn('WARN: unable to compare the \'TFM.{}\' tensor with the \'STM.AI.{}\' tensor'.format(
                    req_map[0], req_map[1]))

    p_fn('')
    print_table(table, p_fn)
    if quant_params and len(quant_params[0]['scales']) and quant_params[0]['scales'][0]:
        p_fn('Note: dequantized values are used to compute the metrics')

    p_fn('')
    p_fn(' cos  : Cosine Similarity')
    p_fn(' nse  : Nash-Sutcliffe efficiency')
    p_fn(' mse  : Mean Squared Error')
    p_fn(' rmse : Root Mean Squared Error')
    p_fn(' bias : Bias/Mean')
    p_fn(' std  : Standard Deviation')
    p_fn('')


def save_ai_tensors(inputs, ai_profiler, ai_outputs, logger):
    """Save the tensors in a npz file"""  # noqa:DAR101,DAR201

    # tag is used as key
    dir_ = pathlib.Path("./")

    _arr_dict = {}
    f_name = dir_ / 'tensors_stm_ai.npz'

    logger.info(' Saving STM AI data... {}'.format(f_name))

    for idx, in_ in enumerate(inputs):
        _arr_dict['I.{}'.format(idx)] = in_

    for idx, out_ in enumerate(ai_outputs):
        _arr_dict['O.{}'.format(idx)] = out_

    if ai_profiler and ai_profiler['c_nodes']:
        for _, c_node in enumerate(ai_profiler['c_nodes']):
            for idx, (data, io_tensor) in enumerate(zip(c_node['data'], c_node['io_tensors'])):
                if data.size:
                    key = io_tensor.tag
                    _arr_dict[key] = data

    np.savez(f_name, **_arr_dict)


def save_tfm_tensors(inputs, tfl_internals, tfl_outputs, logger):
    """Save the tensors in a npz file"""  # noqa:DAR101,DAR201

    if not tfl_outputs:
        logger.warning(" WARN: No TFL data...")
        return

    # tag is used as key
    dir_ = pathlib.Path("./")

    _arr_dict = {}
    f_name = dir_ / 'tensors_tfl.npz'

    logger.info(' Saving TFL data... {}'.format(f_name))

    for idx, in_ in enumerate(inputs):
        _arr_dict['I.{}'.format(idx)] = in_

    for idx, out_ in enumerate(tfl_outputs):
        _arr_dict['O.{}'.format(idx)] = out_

    for c_idx, internal in enumerate(tfl_internals):
        for idx, port in enumerate(internal['outputs']):
            key = 'N.{}.{}'.format(c_idx, idx)
            _arr_dict[key] = port['data']

    np.savez(f_name, **_arr_dict)


def run(args, logger):
    """Main processing function"""  # noqa: DAR101,DAR201,DAR401

    logger.info(f'Running ai_checker v{__VERSION__}..')

    inputs = None
    if args.valinput and os.path.isfile(args.valinput):
        logger.info(f'\n Loading data file : {args.valinput}')

        if args.valinput.endswith('.npy'):
            file_ = np.load(args.valinput)
            inputs = [file_]
        elif args.valinput.endswith('.npz'):
            file_ = np.load(args.valinput)
            keys = ['m_inputs', 'x_test']
            inputs = []
            for entry in file_.files:
                if keys[0] in entry or keys[1] in entry:
                    logger.info(f'  select the "{entry}" entry')
                    inputs = [file_[entry]]
            if not inputs:
                inputs = None
                logger.info(f'{keys} is not available.')
        else:
            inputs = None

        if inputs:
            logger.info('  shape={} dtype={} min={} max={}'.format(inputs[0].shape, inputs[0].dtype,
                                                                   np.min(inputs[0]), np.max(inputs[0])))
        else:
            logger.info('File format is not supported.')

    if inputs:
        args.batch = inputs[0].shape[0]

    if args.tflite:
        tfl_interpreter, tfl_internals = load_tflite_model(args.tflite, args.batch,
                                                           logger, preserve_internal=not args.no_internals,
                                                           use_built_op=args.tflite_op.upper(),
                                                           no_multi_threads=args.tflite_no_multi_threads,
                                                           verbosity=args.verbosity)
    else:
        tfl_interpreter, tfl_internals = None, []

    logger.info(f'\nOpening st.ai runtime "{args.desc}" (AiRunner v{__version__})..')

    verbosity = args.verbosity
    runner = AiRunner(debug=args.debug, verbosity=verbosity)
    runner.connect(args.desc)

    if not runner.is_connected:
        logger.error('!!! connection to st.ai runtime has failed..')
        logger.error(' {}'.format(runner.get_error()))
        return 1

    logger.debug(runner)
    c_name = runner.names[0] if not args.name else args.name
    session = runner.session(c_name)

    if args.list:
        for c_name in runner.names:
            runner.summary(c_name, print_fn=logger.info, indent=1)
        runner.disconnect()
        return 0

    session.summary(print_fn=logger.info, indent=1)

    check_io(session, tfl_interpreter, logger)

    if args.ihex:
        logger.info('Loading data... ihex={}'.format(args.ihex))
        session.extension(name=c_name, cmd='write', ihex=args.ihex)

    input_infos = session.get_input_infos()
    if not inputs:
        if args.image and os.path.isfile(args.image) and len(input_infos) == 1 and len(input_infos[0]['shape']) == 4:
            import cv2
            # pylint: disable=no-member
            in0_shape = input_infos[0]['shape']
            image11 = cv2.imread(args.image)
            img = cv2.resize(image11, (in0_shape[1], in0_shape[2]), interpolation=cv2.INTER_NEAREST)
            logger.info(f'Loading the image : {args.image} {img.shape} {img.dtype}\n')
            if args.show:
                resized = cv2.resize(img, (in0_shape[1] * 2, in0_shape[2] * 2), interpolation=cv2.INTER_AREA)
                cv2.imshow('image', resized)
                cv2.waitKey(0)
            img = np.expand_dims(img, axis=0)
            if args.rescale_01:
                inputs = [img / 255]
            else:
                inputs = [img / 127.5 - 1]
            inputs[0] = input_infos[0]['io_tensor'].quantize(inputs[0])
        else:
            rnd_gen = np.random.RandomState(args.seed)
            inputs = gen_datas(runner, session.name, args.batch, args.range, logger, rnd_gen)
    else:
        for idx, info in enumerate(input_infos):
            inputs[idx] = info['io_tensor'].quantize(inputs[idx])

    if args.io_only:
        mode = AiRunner.Mode.IO_ONLY
    elif args.with_data:
        mode = AiRunner.Mode.PER_LAYER_WITH_DATA
    else:
        mode = AiRunner.Mode.PER_LAYER

    if args.perf_only:
        mode |= AiRunner.Mode.PERF_ONLY
    if args.target_log or args.debug:
        mode |= AiRunner.Mode.DEBUG

    if args.range and len(args.range) == 1:
        mode |= AiRunner.Mode.FIXED_INPUT

    logger.info('Invoking STM AI model... (requested mode: {})'.format(mode))

    start_time = perf_counter()
    ai_outputs, ai_profiler = session.invoke(inputs, mode=mode)
    logger.info(f'\n executing time : {perf_counter() - start_time:.03f}s')

    full_info = args.verbosity > 0
    runner.print_profiling(inputs, ai_profiler, ai_outputs, print_fn=logger.info,
                           indent=1, debug=full_info, tensor_info=full_info)

    runner.disconnect()

    if tfl_interpreter is not None:
        start_time = perf_counter()
        tfl_outputs = invoke_tflite_model(tfl_interpreter, inputs, tfl_internals, logger)
        logger.info(' executing time : {:.03f}s'.format(perf_counter() - start_time))

        quant_params = []
        if args.dequant:
            for tf_o in tfl_interpreter.get_output_details():
                quant_params.append(tf_o['quantization_parameters'])

        print_tflite_profiling(tfl_interpreter, inputs, tfl_internals, tfl_outputs, logger)

        logger.info('Computing metrics...')
        histo_ = 'full' if args.histo_all else args.histo
        compute_metrics(ai_profiler, quant_params, ai_outputs, tfl_internals, tfl_outputs, args.map, histo_, logger)

    if args.classifier and len(ai_outputs) == 1 and ai_outputs[0].shape[0] == 1:
        pred = ai_outputs[0].flatten().astype(np.float32)
        t5_ind, t5_val = topk_by_sort(pred, 5, ascending=False)
        t5_r = [f'{id}:{val:.02f}' for id, val in zip(t5_ind, t5_val)]
        logger.info(f'top5 pred - {t5_r}')

        if tfl_interpreter:
            ref = tfl_outputs[0].flatten().astype(np.float32)
            rt5_ind, rt5_val = topk_by_sort(ref, 5, ascending=False)
            rt5_r = [f'{id}:{val:.02f}' for id, val in zip(rt5_ind, rt5_val)]
            logger.info(f'top5 ref - {rt5_r}')

    logger.info('')
    logger.info('Saving the tensors...')
    save_ai_tensors(inputs, ai_profiler, ai_outputs, logger)
    if tfl_interpreter is not None:
        save_tfm_tensors(inputs, tfl_internals, tfl_outputs, logger)

    return 0


def main():
    """Main function to parse the arguments"""  # noqa: DAR101,DAR201,DAR401

    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description='AI runner')
    parser.add_argument('--desc', '-d', metavar='STR', type=str, help='connection descriptor', default=_DEFAULT)
    parser.add_argument('--list', '-l', action='store_true', help="List the available c-models")
    parser.add_argument('--batch', '-b', metavar='INT', type=int, help='batch_size', default=1)
    parser.add_argument('--seed', metavar='INT', type=int, help='seed value', default=42)
    parser.add_argument('--range', type=float,
                        metavar='RANGE', nargs='+', default=None,
                        help="requested range to generate randomly the input data (default=[0,1])")
    parser.add_argument('--valinput', '-vi', metavar='STR', type=str,
                        help='npy/npz files used as input/output data', default=None)
    parser.add_argument('--image', metavar='FILE', type=str, help='Simple file image is used as input', default=None)
    parser.add_argument('--show', action='store_true', help="Display the loaded image")
    parser.add_argument('--rescale-01', action='store_true',
                        help="Rescale the loaded image between 0 and 1 else -1, 1 is used")
    parser.add_argument('--classifier', action='store_true', help="Indicate that the mode is a classifier")
    parser.add_argument('--io-only', action='store_true', help="The info per layer are not reported")
    parser.add_argument('--perf-only', action='store_true', help="Only the perf info, no data are exchanged")
    parser.add_argument('--with-data', action='store_true', help="dump the intermediate results")
    parser.add_argument('--name', '-n', metavar='STR', type=str, help='c-model name', default=None)
    parser.add_argument('--tflite', metavar='STR', type=str, help='TFlite file', default=None)
    parser.add_argument('--histo', action='store_true', help="Compute the histogram of the errors (integer data type)")
    parser.add_argument('--histo-all', action='store_true', help="Compute the histogram of the associated REF")
    parser.add_argument('--map', metavar='STR', nargs='+', type=str, help='Output Tensor mapping', default=None)
    parser.add_argument('--ihex', '-x', type=str, nargs='+', help="Intel HEX files")
    parser.add_argument('--verbosity', '-v',
                        nargs='?', const=1,
                        type=int, choices=range(0, 3),
                        help="set verbosity level",
                        default=0)
    parser.add_argument('--debug', action='store_true', help="debug option")
    parser.add_argument('--dequant', action='store_true', help="dequant the values before to compute the metrics")
    parser.add_argument('--no-internals', action='store_true',
                        help="disable the experimental feature to dump the internal tflite tensors")
    parser.add_argument('--tflite-op', type=str, choices=['default', 'auto', 'builtin_ref', 'builtin'],
                        default='auto',
                        help="tflite experimental - select the OpResolverType (default=\'default\')")
    parser.add_argument('--tflite-no-multi-threads', action='store_true',
                        help="Disable the multi-thread support to execute the TFLite model")
    parser.add_argument('--target-log', action='store_true', help="enable additional log from the target")
    args = parser.parse_args()
    logging.basicConfig(format='%(message)s', stream=sys.stdout,
                        level=os.environ.get("LOGLEVEL", "DEBUG" if args.debug else "INFO"))

    if args.histo_all or args.map:
        args.with_data = True

    if not args.with_data and not args.no_internals:
        args.no_internals = True

    return run(args, log)


if __name__ == '__main__':
    sys.exit(main())
