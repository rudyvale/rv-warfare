import argparse
import ctypes
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tkinter as tk


parser = argparse.ArgumentParser()
parser.add_argument('--server', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
server = args.server.resolve()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(server))
spec = importlib.util.spec_from_file_location('rv_live_launcher', server / 'warfare-launcher.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except (AttributeError, OSError):
    pass
state = module.server_status(server)
if state.get('state') != 'stopped' or state.get('ready'):
    raise RuntimeError('The planned GUI start requires a gracefully stopped server')
window = tk.Tk()
app = module.Launcher(window, folder=server)
window.state('zoomed')
started = None
previous = time.perf_counter()
intervals = []
finished = False
report = {}


def begin():
    global started, previous
    if app.server.get('state') != 'stopped':
        window.after(100, begin)
        return
    started = time.perf_counter()
    previous = started
    app.start_button.invoke()
    window.after(50, heartbeat)
    print('Actual GUI Start invoked; heartbeat50ms active', flush=True)


def heartbeat():
    global previous, finished, report
    now = time.perf_counter()
    intervals.append((now - previous) * 1000)
    previous = now
    server_ready = app.server.get('ready') is True
    tunnel_ready = app.connection.get('ready') is True
    worker_complete = app.server_job is None and app.status_key == 'online'
    if server_ready and tunnel_ready and worker_complete:
        finished = True
        state = module.server_status(server)
        report = {'passed': max(intervals) < 250 and state.get('ready') and not app.client_job and not app.client_running, 'actualGuiStart': True, 'workerComplete': worker_complete, 'serverReady': server_ready, 'portholeReady': tunnel_ready, 'heartbeatMs': 50, 'samples': len(intervals), 'maxIntervalMs': round(max(intervals), 2), 'meanIntervalMs': round(statistics.mean(intervals), 2), 'elapsedSeconds': round(now - started, 2), 'serverStartupSeconds': state.get('startup_seconds'), 'port': state.get('port'), 'maxMemoryGb': state.get('max_memory_gb'), 'clientStarted': app.client_job or app.client_running}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report), flush=True)
        window.after(200, app.close)
        return
    if now - started > 270 or (app.server_job is None and app.status_key in ('error', 'tunnel_error')):
        report = {'passed': False, 'actualGuiStart': True, 'status': app.status_key, 'serverReady': server_ready, 'portholeReady': tunnel_ready, 'elapsedSeconds': round(now - started, 2)}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report), flush=True)
        app.close()
        return
    window.after(50, heartbeat)


window.after(1500, begin)
window.mainloop()
if not finished or not report.get('passed'):
    raise SystemExit('Actual GUI start acceptance failed')
final = module.server_status(server)
if not final.get('ready'):
    raise SystemExit('Closing GUI unexpectedly stopped server')
print('PASS closing the actual GUI leaves server running', flush=True)
