import os
from pathlib import Path
import re
import socket
import subprocess
import time
import traceback

from server_vendors import install_for_runner

from host_runtime import acquire_lock, apply_pending_profile, java_arguments, porthole, read_json, server_port, server_status, update_stock_addons, write_json


def run(root):
    lock = acquire_lock(root)
    if lock is None:
        return
    if server_status(root).get('state') in ('starting', 'running', 'stopping'):
        return
    state_path = root / 'server-state.json'
    commands_path = root / 'commands.txt'
    state = {'state': 'starting', 'ready': False, 'updated': time.time(), 'runnerPid': os.getpid()}

    def save():
        state['updated'] = time.time()
        write_json(state_path, state)

    process = None
    try:
        commands_path.write_text('', encoding='utf-8')
        vendor_meta = read_json(root / 'release.json')
        settings = read_json(root / 'launcher-settings.json')
        arguments, memory = java_arguments(root, settings)
        port = server_port(root)
        with socket.socket() as port_check:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                port_check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            port_check.bind(('127.0.0.1', port))
            update_stock_addons(root)
            apply_pending_profile(root, settings)
            if vendor_meta.get('vendorCatalogSha256'):
                save()
            def vendor_wait():
                state['phase'] = 'vendors'
                save()
                return any(line.strip() == 'stop' for line in commands_path.read_text(encoding='utf-8').splitlines())
            install_for_runner(root, vendor_wait if vendor_meta.get('vendorCatalogSha256') else None)
            if any(line.strip() == 'stop' for line in commands_path.read_text(encoding='utf-8').splitlines()):
                state.update(state='stopped', ready=False, phase='stopped')
                save()
                return
        if any(line.strip() == 'stop' for line in commands_path.read_text(encoding='utf-8').splitlines()):
            state.update(state='stopped', ready=False, phase='stopped')
            save()
            return
        save()
        with (root / 'console.log').open('w', encoding='utf-8', buffering=1) as output:
            process = subprocess.Popen(arguments, cwd=root, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT, text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            identity = porthole.process_identity(process.pid) or {}
            state.update(pid=process.pid, processStartedAt=identity.get('startedAt'), port=port, max_memory_gb=memory, phase='loading')
            save()
            offset = 0
            log_offset = 0
            log_partial = ''
            command_partial = ''
            started = time.monotonic()
            heartbeat = started
            while process.poll() is None:
                with commands_path.open('r', encoding='utf-8') as commands:
                    if commands_path.stat().st_size < offset:
                        offset = 0
                    commands.seek(offset)
                    pending = commands.read(65536)
                    offset = commands.tell()
                if pending:
                    parts = (command_partial + pending).split('\n')
                    command_partial = parts.pop()
                    if parts:
                        if any(command.strip() == 'stop' for command in parts):
                            state.update(state='stopping', ready=False, phase='saving')
                            save()
                        process.stdin.write('\n'.join(parts) + '\n')
                        process.stdin.flush()
                with (root / 'console.log').open('r', encoding='utf-8', errors='replace') as log:
                    log.seek(log_offset)
                    fresh = log.read(131072)
                    log_offset = log.tell()
                if fresh:
                    lines = (log_partial + fresh).split('\n')
                    log_partial = lines.pop()[-8192:]
                    for line in lines:
                        if 'Preparing spawn area' in line:
                            state['phase'] = 'world'
                        if 'Done (' in line and state['state'] != 'stopping':
                            if not state.get('bootQueued'):
                                with commands_path.open('a', encoding='utf-8') as queue:
                                    queue.write('function warfare:boot\n')
                                state['bootQueued'] = True
                            state.update(state='running', ready=True, phase='ready', startup_seconds=round(time.monotonic() - started, 2))
                            save()
                        joined = re.search(r'\]: (\w{1,16})\[/.*logged in with entity id', line)
                        if joined and state['state'] == 'running':
                            with commands_path.open('a', encoding='utf-8') as queue:
                                queue.write('execute ' + joined.group(1) + ' ~ ~ ~ function warfare:welcome\n')
                if time.monotonic() - heartbeat >= 2:
                    save()
                    heartbeat = time.monotonic()
                time.sleep(0.25)
            state.update(state='stopped' if process.returncode == 0 else 'failed', ready=False, exit_code=process.returncode, phase='stopped')
            save()
    except Exception:
        if process is None and 'RV_VENDOR_CANCELLED' in traceback.format_exc():
            state.update(state='stopped', ready=False, phase='stopped')
            save()
            return
        state.update(state='failed', ready=False, error=traceback.format_exc())
        try:
            save()
        except OSError:
            pass
        if process is not None and process.poll() is None:
            try:
                process.stdin.write('stop\n')
                process.stdin.flush()
                process.wait(timeout=120)
                state.update(state='failed', ready=False, exit_code=process.returncode)
            except (OSError, subprocess.TimeoutExpired):
                state.update(state='stopping', error='Runner failed; server may still be saving. See console.log.')
            try:
                save()
            except OSError:
                pass


if __name__ == '__main__':
    run(Path(__file__).resolve().parent)
