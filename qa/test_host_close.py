import gc
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
import tkinter as tk
import warnings
import weakref


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
spec = importlib.util.spec_from_file_location('host_ui_close', ROOT / 'host/warfare-launcher.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    with tempfile.TemporaryDirectory(prefix='rv-host-close-') as temporary:
        window = tk.Tk()
        window.withdraw()
        app = ui.Launcher(window, temporary, monitor=False)
        gate = threading.Event()
        entered = threading.Event()
        finished = threading.Event()
        def work(name, timeout=180):
            entered.set()
            gate.wait(2)
            finished.set()
        app.script = work
        app.check_updates = lambda: None
        app.server = {'state': 'running', 'ready': True}
        app.run_action('play')
        assert entered.wait(1)
        app.close()
        app.close()
        assert not any(isinstance(value, (tk.Misc, tk.Variable)) for value in vars(app).values())
        reference = weakref.ref(app)
        del app
        del window
        gc.collect()
        gate.set()
        assert finished.wait(1)
        deadline = time.monotonic() + 2
        while reference() is not None and time.monotonic() < deadline:
            gc.collect()
            time.sleep(0.01)
        assert reference() is None
    assert not any('Tcl interpreter' in str(item.message) for item in caught), caught
print('PASS close during background operation; Tk resources released on main thread; double close safe')
