# ==============================================================================
# 后端 API 服务：读取缓存结果、流式运行遗传算法
# 运行: cd 源码/code && python api_server.py
# ==============================================================================

import json
import os
import queue
import sys
import threading

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_for_frontend import (
    DATASET_CONFIGS,
    OUTPUT_PATH,
    export_all_datasets,
    load_cached_results,
)

app = Flask(__name__)
CORS(app)

_run_lock = threading.Lock()
_run_state = {'running': False, 'dataset_ids': None}


class StreamCapture:
    """将 stdout 重定向到回调，同时保留终端输出"""

    def __init__(self, callback, original):
        self.callback = callback
        self.original = original
        self._buffer = ''

    def write(self, text):
        if not text:
            return
        self.original.write(text)
        self.original.flush()
        self._buffer += text
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            self.callback(line + '\n')

    def flush(self):
        self.original.flush()
        if self._buffer:
            self.callback(self._buffer)
            self._buffer = ''


def _sse_event(event_type, **data):
    payload = {'type': event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'cached': os.path.isfile(OUTPUT_PATH),
        'running': _run_state['running'],
        'datasets': [c['id'] for c in DATASET_CONFIGS],
    })


@app.route('/api/results')
def get_results():
    payload = load_cached_results()
    if payload is None:
        return jsonify({'error': '暂无缓存数据，请先运行算法'}), 404
    return jsonify(payload)


@app.route('/api/run', methods=['POST'])
def run_optimization():
    if _run_state['running']:
        return jsonify({'error': '算法正在运行中，请稍候'}), 409

    body = request.get_json(silent=True) or {}
    dataset_ids = body.get('datasetIds')
    if dataset_ids is not None and not isinstance(dataset_ids, list):
        return jsonify({'error': 'datasetIds 必须为数组'}), 400

    def generate():
        log_queue = queue.Queue()

        def push_log(text):
            log_queue.put(('log', text))

        def worker():
            global _run_state
            old_stdout = sys.stdout
            try:
                with _run_lock:
                    _run_state = {'running': True, 'dataset_ids': dataset_ids}
                sys.stdout = StreamCapture(push_log, old_stdout)

                print('=' * 60)
                if dataset_ids:
                    names = [c['name'] for c in DATASET_CONFIGS if c['id'] in dataset_ids]
                    print(f'开始运行遗传算法（{", ".join(names)}）...')
                else:
                    print('开始运行遗传算法（全部数据集）...')
                print('=' * 60)

                payload = export_all_datasets(dataset_ids=dataset_ids)
                log_queue.put(('done', payload))
            except Exception as exc:
                log_queue.put(('error', str(exc)))
            finally:
                sys.stdout = old_stdout
                sys.stdout.flush()
                _run_state = {'running': False, 'dataset_ids': None}

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            kind, data = log_queue.get()
            if kind == 'log':
                yield _sse_event('log', message=data)
            elif kind == 'done':
                yield _sse_event('done', generatedAt=data.get('generatedAt'))
                break
            elif kind == 'error':
                yield _sse_event('error', message=data)
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


if __name__ == '__main__':
    port = int(os.environ.get('API_PORT', '5181'))
    print(f'API 服务启动: http://127.0.0.1:{port}')
    print(f'缓存路径: {OUTPUT_PATH}')
    app.run(host='127.0.0.1', port=port, threaded=True)
