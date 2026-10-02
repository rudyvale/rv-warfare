import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import socket
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
SERVER_PROFILES = {'low': {'memory': 2, 'distance': 4}, 'balanced': {'memory': 3, 'distance': 6}, 'quality': {'memory': 4, 'distance': 8}}


class CompatibilityError(ValueError):
    pass
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


def apply_pending_profile(folder, settings):
    folder = Path(folder)
    profile = settings.get('pendingServerProfile')
    if profile is None:
        return settings
    if profile not in SERVER_PROFILES:
        raise ValueError('Invalid pending server profile')
    request = str(settings.get('serverProfileRequest') or profile)
    marker = folder / '.server-profile-applied.json'
    if read_json(marker).get('request') == request:
        return settings
    if server_status(folder).get('state') in ('starting', 'running', 'stopping'):
        raise RuntimeError('Stop the server before applying a profile')
    path = folder / 'server.properties'
    original = path.read_bytes()
    lines = original.decode('utf-8-sig').splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith('view-distance=')]
    if len(matches) > 1:
        raise ValueError('Duplicate view-distance settings; no profile applied')
    value = 'view-distance=' + str(SERVER_PROFILES[profile]['distance'])
    if matches:
        index = matches[0]
        ending = '\r\n' if lines[index].endswith('\r\n') else '\n' if lines[index].endswith('\n') else ''
        lines[index] = value + ending
    else:
        if lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] += '\n'
        lines.append(value + '\n')
    updated = ''.join(lines).encode('utf-8')
    if original.startswith(b'\xef\xbb\xbf'):
        updated = b'\xef\xbb\xbf' + updated
    if updated != original:
        backups = folder / 'backups'
        backups.mkdir(exist_ok=True)
        with (backups / ('server-profile-' + str(time.time_ns()) + '.properties')).open('xb') as backup:
            backup.write(original)
        temporary = path.with_suffix('.properties.' + str(os.getpid()) + '.tmp')
        temporary.write_bytes(updated)
        temporary.replace(path)
    write_json(marker, {'request': request, 'profile': profile})
    return settings


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
    return [str(java), '-Dfile.encoding=UTF-8', '-Xms512M', '-Xmx' + str(ram) + 'G', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=100', '-XX:ParallelGCThreads=' + str(threads), '-XX:ConcGCThreads=' + str(max(1, threads // 2)), '-jar', str(jar.resolve()), 'nogui'], ram


def local_mod_versions(port, timeout=3):
    def encode(value):
        result = bytearray()
        while True:
            byte = value & 127
            value >>= 7
            result.append(byte | (128 if value else 0))
            if not value:
                return bytes(result)
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as connection:
        deadline = time.monotonic() + timeout
        def receive(size):
            result = bytearray()
            while len(result) < size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Server status timed out')
                connection.settimeout(remaining)
                data = connection.recv(size - len(result))
                if not data:
                    raise ValueError('Incomplete server status')
                result.extend(data)
            return bytes(result)
        def integer():
            value = 0
            for index in range(5):
                byte = receive(1)[0]
                value |= (byte & 127) << (index * 7)
                if not byte & 128:
                    return value
            raise ValueError('Invalid server status length')
        host = b'127.0.0.1'
        handshake = b'\x00' + encode(340) + encode(len(host)) + host + port.to_bytes(2, 'big') + b'\x01'
        connection.sendall(encode(len(handshake)) + handshake + b'\x01\x00')
        frame = integer()
        if not 2 <= frame <= 1048576:
            raise ValueError('Invalid server status frame')
        body = receive(frame)
        position = 0
        def body_integer():
            nonlocal position
            value = 0
            for index in range(5):
                if position >= len(body):
                    raise ValueError('Incomplete server status frame')
                byte = body[position]
                position += 1
                if index == 4 and byte & 240:
                    raise ValueError('Invalid server status integer')
                value |= (byte & 127) << (index * 7)
                if not byte & 128:
                    return value
            raise ValueError('Invalid server status integer')
        if body_integer() != 0:
            raise ValueError('Invalid server status packet')
        size = body_integer()
        if not 1 <= size <= 1048576 or position + size != len(body):
            raise ValueError('Invalid server status payload')
        status = json.loads(body[position:].decode('utf-8'))
        if not isinstance(status, dict) or not isinstance(status.get('version'), dict) or not isinstance(status.get('modinfo', {}), dict):
            raise ValueError('Invalid Minecraft server status')
        if status['version'].get('protocol') != 340:
            raise CompatibilityError('Minecraft 1.12.2 is required')
        mods = status.get('modinfo', {}).get('modList', [])
        if not isinstance(mods, list):
            raise ValueError('Invalid Forge mod list')
        result = {}
        for mod in mods:
            if not isinstance(mod, dict):
                raise ValueError('Invalid Forge mod entry')
            name, version = mod.get('modid'), mod.get('version')
            if not isinstance(name, str) or not isinstance(version, str) or name in result:
                raise ValueError('Invalid Forge mod versions')
            result[name] = version
        return result


def check_local_compatibility(folder, game, port):
    folder, game = Path(folder), Path(game)
    required = read_json(folder / 'release.json').get('requiredMods')
    if not isinstance(required, dict) or not required or any(not isinstance(key, str) or not isinstance(value, str) or not value for key, value in required.items()):
        raise CompatibilityError('RV version requirements are missing. Update the host tools.')
    versions = local_mod_versions(port)
    if any(versions.get(name) != version for name, version in required.items()):
        raise CompatibilityError('Server and game versions differ. Update both to the same RV release.')
    def digest(path):
        with path.open('rb') as handle:
            return hashlib.file_digest(handle, 'sha256').digest()
    for filename in ('mcheli-ce-1.5.1-rv.jar', 'techguns-1.12.2-rv.jar'):
        files = [folder / 'mods' / filename, game / 'mods' / filename]
        if any(not path.is_file() for path in files) or digest(files[0]) != digest(files[1]):
            raise CompatibilityError('Server and game files differ. Update both to the same RV release.')


def update_stock_addons(folder):
    folder = Path(folder).resolve()
    native = folder / 'mcheli_addons/default'
    if not native.is_dir():
        return {'updated': 0, 'existingDefault': False}
    if not native.resolve().is_relative_to(folder):
        raise ValueError('The default addon directory is outside this installation')
    contract = folder / 'rv-addon-assets.json'
    if not contract.is_file():
        version = read_json(folder / 'release.json').get('version', '1.0.0')
        if tuple(map(int, version.split('.'))) >= (1,1,0):
            raise ValueError('The RV addon update map is missing. Update the host tools.')
        return {'updated': 0, 'existingDefault': True}
    manifest = read_json(contract)
    resources = manifest.get('resources')
    if manifest.get('schema') != 1 or not isinstance(resources, dict) or not 1 <= len(resources) <= 64:
        raise ValueError('Invalid RV addon update map')
    if server_status(folder).get('state') in ('starting','running','stopping'):
        raise RuntimeError('Stop the server before updating addon resources')
    jar = folder / 'mods/mcheli-ce-1.5.1-rv.jar'
    with jar.open('rb') as stream:
        installed = hashlib.file_digest(stream, 'sha256').hexdigest()
    if manifest.get('mcheliSha256') != installed:
        raise ValueError('The addon update map belongs to another installed mod')
    changes, names = [], set()
    with zipfile.ZipFile(jar) as archive:
        for resource, expected in resources.items():
            path = PurePosixPath(resource)
            if not isinstance(expected, str) or len(expected) != 64 or any(letter not in '0123456789abcdef' for letter in expected) or not resource.startswith('assets/mcheli/') or '\\' in resource or ':' in resource or '..' in path.parts or path.is_absolute() or resource != path.as_posix() or resource.casefold() in names:
                raise ValueError('Invalid bounded addon resource path or checksum')
            names.add(resource.casefold())
            entry = archive.getinfo(resource)
            if entry.file_size > 2 * 1024 * 1024:
                raise ValueError('Addon resource exceeds its size limit')
            data = archive.read(entry)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Addon resource does not match the installed mod')
            target = native / path
            if not target.resolve().is_relative_to(native.resolve()):
                raise ValueError('Addon resource path escapes the default directory')
            original = target.read_bytes() if target.exists() else None
            if original != data:
                changes.append((target, resource, original, data))
    if sum(len(data) for _,_,_,data in changes) > 8 * 1024 * 1024:
        raise ValueError('Addon update exceeds its total size limit')
    backup = folder / 'backups' / ('native-addon-' + str(time.time_ns()))
    for target, resource, original, _ in changes:
        if (target.read_bytes() if target.exists() else None) != original:
            raise RuntimeError('Addon resource changed during update preparation')
        if original is not None:
            destination = backup / 'mcheli_addons/default' / resource
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(original)
    for target, _, _, data in changes:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.' + str(os.getpid()) + '.rv-new')
        with temporary.open('xb') as stream:
            stream.write(data)
        temporary.replace(target)
    return {'updated': len(changes), 'existingDefault': True, 'backup': str(backup) if backup.exists() else None}


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
