import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('vm_porthole', ROOT / 'porthole-status.py')
porthole = importlib.util.module_from_spec(spec)
spec.loader.exec_module(porthole)


def read_json(path, default=None):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else dict(default or {})
    except (OSError, ValueError):
        return dict(default or {})


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    for attempt in range(21):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 20:
                raise
            time.sleep(0.025)


def memory_gb():
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ('total', 'available', 'page', 'free_page', 'virtual', 'free_virtual', 'extended')]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if os.name == 'nt' and ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return status.total / 2 ** 30
    return 8


def memory_limit(settings, total=None):
    total = memory_gb() if total is None else total
    automatic = 2 if total < 12 else 3 if total < 20 else 4
    try:
        value = int(settings.get('serverMemoryGB', automatic))
    except (ValueError, TypeError):
        value = automatic
    return max(2, min(8, int(total / 2), value))


def server_port(folder):
    path = Path(folder) / 'server.properties'
    port = 25565
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('server-port='):
                port = int(line.split('=', 1)[1].strip())
    if not 1 <= port <= 65535:
        raise ValueError('Invalid server port')
    return port


def server_status(folder=ROOT, probe=None):
    probe = probe or porthole.process_identity
    state = read_json(Path(folder) / 'server-state.json')
    if state.get('state') not in ('starting', 'running', 'stopping'):
        return state or {'state': 'stopped', 'ready': False}
    try:
        identity = probe(int(state.get('pid', 0))) if state.get('pid') else None
        if identity and Path(identity['executable']).name.lower() in ('java.exe', 'javaw.exe'):
            started = state.get('processStartedAt')
            valid_legacy = started is None and identity['startedAt'] <= float(state.get('updated', 0)) + 2
            if valid_legacy or (started is not None and abs(float(started) - identity['startedAt']) < 2):
                return state
        if state.get('state') == 'starting' and time.time() - float(state.get('updated', 0)) < 20:
            return state
    except (TypeError, ValueError, KeyError, OverflowError):
        pass
    return dict(state, state='stopped', ready=False)


def acquire_lock(folder=ROOT):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    key = hashlib.sha256(str(Path(folder).resolve()).casefold().encode()).hexdigest()[:24]
    handle = kernel.CreateMutexW(None, False, 'Local\\VMServer-' + key)
    if not handle:
        raise OSError(ctypes.get_last_error(), 'Server lock could not be created')
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)
        return None
    return handle


def java_arguments(folder, settings, total=None):
    folder = Path(folder)
    java = Path(os.environ.get('VM_JAVA', str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Warfare-1.12.2/runtime/bin/java.exe')))
    if not java.is_file():
        fallback = Path(os.environ.get('APPDATA', '')) / '.minecraft/runtime/temurin8/jdk8u504-b01-jre/bin/java.exe'
        if fallback.is_file():
            java = fallback
    if not java.is_file():
        raise FileNotFoundError('Java 8 is missing. Install RV first or set VM_JAVA.')
    jar = folder / 'forge-1.12.2-14.23.5.2860.jar'
    if not jar.is_file():
        raise FileNotFoundError('Forge server is missing in ' + str(folder))
    ram = memory_limit(settings, total)
    threads = max(1, min(4, (os.cpu_count() or 2) // 2))
    return [str(java), '-Dfile.encoding=UTF-8', '-Xms512M', '-Xmx' + str(ram) + 'G', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=100', '-XX:ParallelGCThreads=' + str(threads), '-XX:ConcGCThreads=' + str(max(1, threads // 2)), '-jar', jar.name, 'nogui'], ram


def request_stop(folder=ROOT, timeout=120, probe=None):
    folder = Path(folder)
    state = server_status(folder, probe)
    if state.get('state') not in ('starting', 'running', 'stopping'):
        return
    with (folder / 'commands.txt').open('a', encoding='utf-8') as stream:
        stream.write('stop\n')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = server_status(folder, probe)
        if current.get('state') not in ('starting', 'running', 'stopping'):
            return
        time.sleep(0.25)
    raise TimeoutError('Server is still saving or stopping. See console.log; it was not killed.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps(server_status()))
    elif args.action == 'stop':
        request_stop()
    else:
        if server_status().get('state') in ('starting', 'running', 'stopping'):
            return
        process = subprocess.Popen([sys.executable.replace('python.exe', 'pythonw.exe'), str(ROOT / 'run-server.py')], cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = read_json(ROOT / 'server-state.json')
            if state.get('runnerPid') == process.pid:
                if state.get('state') == 'failed':
                    raise RuntimeError(state.get('error', 'Server failed to start'))
                return
            if process.poll() is not None:
                if server_status().get('state') in ('starting', 'running', 'stopping'):
                    return
                raise RuntimeError('Server runner exited before starting. See server-state.json.')
            time.sleep(0.05)
        raise TimeoutError('Server runner did not report startup within 10 seconds.')


if __name__ == '__main__':
    main()
