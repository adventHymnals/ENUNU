#! /usr/bin/env python3
# coding: utf-8
# fmt: off
print('Starting enunu server...')
import json
import os
import subprocess
import sys
import traceback

sys.path.append(os.path.dirname(__file__))
import numpy as np
import enunu_steps
import enulib
try:
    import zmq
except ModuleNotFoundError:
    python_exe = "python"
    command = [python_exe, '-m', 'pip', 'install', 'pyzmq']
    print('command:', command)
    subprocess.run(command, check=True)
    import zmq
# fmt: on


def timing(path_ust: str):
    config, temp_dir = enunu_steps.setup(path_ust)
    path_full_timing, path_mono_timing = enunu_steps.run_timing(config, temp_dir)
    return {
        'path_full_timing': path_full_timing,
        'path_mono_timing': path_mono_timing,
    }


def acoustic(path_ust: str):
    config, temp_dir = enunu_steps.setup(path_ust)
    path_temp_ust, path_temp_table, \
        path_full_score, path_mono_score, \
        path_full_timing, path_mono_timing, \
        path_acoustic, path_f0, path_spectrogram, \
        path_aperiodicity = enunu_steps.get_paths(temp_dir)
    enulib.utauplugin2score.utauplugin2score(
        path_temp_ust,
        path_temp_table,
        path_full_timing,
        strict_sinsy_style=False
    )
    path_acoustic, path_f0, path_spectrogram, \
        path_aperiodicity = enunu_steps.run_acoustic(config, temp_dir)
    for path in (path_f0, path_spectrogram, path_aperiodicity):
        arr = np.loadtxt(path, delimiter=',', dtype=np.float64)
        np.save(path[:-4] + '.npy', arr)
        if os.path.isfile(path):
            os.remove(path)
    return {
        'path_acoustic': path_acoustic,
        'path_f0': path_f0,
        'path_spectrogram': path_spectrogram,
        'path_aperiodicity': path_aperiodicity,
    }


def poll_socket(socket, timetick = 100):
    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    # wait up to 100msec
    try:
        while True:
            obj = dict(poller.poll(timetick))
            if socket in obj and obj[socket] == zmq.POLLIN:
                yield socket.recv()
    except KeyboardInterrupt:
        pass
    # Escape while loop if there's a keyboard interrupt.


def main():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind('tcp://*:15555')
    print('Started enunu server')

    for message in poll_socket(socket):
        request = json.loads(message)
        print('Received request: %s' % request)

        response = {}
        try:
            if request[0] == 'timing':
                response['result'] = timing(request[1])
            elif request[0] == 'acoustic':
                response['result'] = acoustic(request[1])
            else:
                raise NotImplementedError('unexpected command %s' % request[0])
        except Exception as e:
            response['error'] = str(e)
            traceback.print_exc()
        config, temp_dir = enunu_steps.setup(request[1])
        args = ['chmod', '-R', '777', temp_dir]
        subprocess.run(args, check=True)
        args = ['chown', '-R', 'nobody:nogroup', temp_dir]
        subprocess.run(args, check=True)
        print('Sending response: %s' % response)
        socket.send_string(json.dumps(response))


if __name__ == '__main__':
    main()
