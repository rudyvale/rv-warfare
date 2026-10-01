import ctypes
import json
import pathlib
import re
from ctypes import wintypes

_sessions = {}

def process_identity(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        name = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(name))
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            return None
        created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)):
            return None
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return {'executable': name.value, 'startedAt': ticks / 10000000 - 11644473600}
    finally:
        kernel.CloseHandle(handle)


def read_status(folder, probe=process_identity):
    folder = pathlib.Path(folder)
    try:
        state = json.loads((folder / 'porthole-state.json').read_text(encoding='utf-8-sig'))
        pid = int(state['pid'])
        identity = probe(pid)
        if state.get('state') != 'running' or not identity or pathlib.Path(identity['executable']).name.lower() != 'porthole-gnu.exe':
            return {}
        started = float(state['startedAt'])
        if abs(started - identity['startedAt']) > 2:
            return {}
        events = folder / 'porthole-events.jsonl'
        stat = events.stat()
        if stat.st_mtime < started - 2:
            return {}
        key = str(folder.resolve())
        identity_key = (pid, started, stat.st_ino, int(state.get('port', 25565)))
        cached = _sessions.get(key)
        if not cached or cached['identity'] != identity_key or stat.st_size < cached['offset']:
            cached = {'identity': identity_key, 'offset': 0, 'partial': b'', 'session_ready': False, 'port_ready': False, 'result': {'pid': pid, 'port': identity_key[3], 'code': '', 'peerTarget': '', 'ready': False}}
            _sessions[key] = cached
        result = cached['result']
        with events.open('rb') as stream:
            stream.seek(cached['offset'])
            fresh = stream.read(131072)
            cached['offset'] = stream.tell()
        lines = (cached['partial'] + fresh).split(b'\n')
        cached['partial'] = lines.pop()[-8192:]
        for raw in lines:
            line = raw.decode('utf-8-sig', errors='replace')
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get('event') == 'static_code' and re.fullmatch(r'[A-Za-z0-9]{4,16}', str(event.get('code', ''))):
                result['code'] = str(event['code']).upper()
            elif event.get('event') == 'steam_id' and re.fullmatch(r'[0-9]{17}', str(event.get('steam_id', ''))):
                result['peerTarget'] = 'peer:' + str(event['steam_id'])
            elif event.get('event') == 'ready':
                cached['session_ready'] = True
            elif event.get('event') == 'port_accepted' and event.get('port') == result['port'] and event.get('proto') == 'tcp':
                cached['port_ready'] = True
        result['ready'] = cached['session_ready'] and cached['port_ready']
        return dict(result)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return {}
