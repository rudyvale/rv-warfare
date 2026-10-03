import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

from host_runtime import check_local_compatibility, porthole, read_json, server_port, server_status

ROOT = Path(__file__).resolve().parent
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def validate_owner(game):
    game = Path(game).resolve()
    policy = read_json(ROOT / 'vm-owner.json')
    settings = read_json(game / 'warfare-settings.json')
    nickname = policy.get('nickname', '')
    if not nickname or settings.get('nickname') != nickname:
        raise ValueError('Ник RV должен совпадать с ником владельца сервера.')
    trusted = {os.path.normcase(str(Path(path).resolve())) for path in policy.get('allowedGameDirs', [])}
    if os.path.normcase(str(game)) not in trusted:
        raise ValueError('Эта папка игры не настроена для входа владельца.')
    properties = {}
    for line in (ROOT / 'vm-owner.properties').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            properties[key.strip()] = value.strip()
    if properties.get('nickname') != nickname or policy.get('serverPort') != server_port(ROOT):
        raise ValueError('Настройки владельца и сервера не совпадают.')
    for path in (game / 'Play-Warfare.ps1', game / 'runtime/bin/java.exe', ROOT / 'Check-OwnerConnection.ps1', ROOT / 'forge-1.12.2-14.23.5.2860.jar'):
        if not path.is_file():
            raise FileNotFoundError('Не найден файл: ' + str(path))
    return nickname


def run_hidden(arguments, timeout=30):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        result = subprocess.run(arguments, cwd=ROOT, stdout=output, stderr=errors, timeout=timeout, creationflags=HIDDEN)
        output.seek(0)
        errors.seek(0)
        stdout = output.read().decode('utf-8', errors='replace').strip()
        stderr = errors.read().decode('utf-8', errors='replace').strip()
    if result.returncode:
        raise RuntimeError(stderr or stdout or 'Не удалось выполнить запуск.')
    return stdout


def wait_for_server(cancel, update, timeout=180):
    state = server_status(ROOT)
    if state.get('state') == 'stopping':
        raise RuntimeError('Сервер сохраняет мир. Дождись остановки и нажми RV снова.')
    if state.get('state') == 'running' and state.get('ready'):
        return int(state['port'])
    update('Запускаю сервер…')
    run_hidden([sys.executable.replace('pythonw.exe', 'python.exe'), '-X', 'utf8', str(ROOT / 'host_runtime.py'), 'start'])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cancel.is_set():
            return None
        state = server_status(ROOT)
        if state.get('state') == 'running' and state.get('ready'):
            return int(state['port'])
        if state.get('state') in ('failed', 'stopped', 'stopping'):
            raise RuntimeError('Сервер не запустился. Подробности: ' + str(ROOT / 'console.log'))
        update('Загружаю мир…' if state.get('phase') == 'world' else 'Запускаю сервер…')
        cancel.wait(0.5)
    raise TimeoutError('Сервер ещё загружается. Дождись готовности и нажми RV снова.')


def start_friends(cancel, update):
    shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    expected = read_json(ROOT / 'owner-play-settings.json').get('peerTarget')
    current = porthole.read_status(ROOT)
    if current.get('ready') and (not expected or current.get('peerTarget') == expected):
        return current
    for attempt in range(3):
        if cancel.is_set():
            return None
        update('Подключаю друзей через Steam…')
        try:
            run_hidden([str(shell), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'Start-Porthole.ps1')], timeout=50)
            connection = porthole.read_status(ROOT)
            if not connection.get('ready'):
                raise RuntimeError('Porthole ещё не готов.')
            if expected and connection.get('peerTarget') != expected:
                raise ValueError('Steam открыт под другим аккаунтом. Войди в аккаунт, для которого собрана игра друзей.')
            return connection
        except ValueError:
            raise
        except (RuntimeError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise RuntimeError('Не удалось открыть подключение для друзей. Проверь вход в Steam и интернет, затем нажми RV снова. Подробности: ' + str(ROOT / 'porthole-errors.log'))
            if cancel.wait(3):
                return None


def play(game, cancel, update):
    nickname = validate_owner(game)
    port = wait_for_server(cancel, update)
    if port is None or cancel.is_set():
        return {'state': 'cancelled'}
    update('Проверяю игру…')
    check_local_compatibility(ROOT, game, port)
    connection = start_friends(cancel, update)
    if connection is None:
        return {'state': 'cancelled'}
    if cancel.is_set():
        return {'state': 'cancelled'}
    update('Запускаю Minecraft — ' + nickname)
    shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    run_hidden([str(shell), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(game / 'Play-Warfare.ps1'), '-Server', '127.0.0.1', '-Port', str(port), '-SkipTunnel'], timeout=60)
    return {'state': 'running', 'nickname': nickname, 'server': '127.0.0.1', 'port': port, 'friendsReady': True, 'code': connection.get('code')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '')) / 'Warfare-1.12.2')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()
    game = args.game_root.resolve()
    if args.check:
        print(json.dumps({'state': 'ready', 'nickname': validate_owner(game), 'gameRoot': str(game)}, ensure_ascii=False))
        return
    import msvcrt
    with (ROOT / '.owner-play.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        cancel = threading.Event()
        if args.headless:
            print(json.dumps(play(game, cancel, lambda message: None), ensure_ascii=False))
            return
        import tkinter as tk
        from tkinter import ttk
        window = tk.Tk()
        window.title('RV Warfare')
        window.geometry('520x260')
        window.resizable(False, False)
        try:
            window.iconbitmap(str(ROOT / 'code.ico'))
        except tk.TclError:
            pass
        status = tk.StringVar(value='Готовлю запуск…')
        ttk.Label(window, text='RV Warfare', font=('Segoe UI', 19, 'bold')).pack(pady=(18, 8))
        ttk.Label(window, textvariable=status, wraplength=460, justify='center', font=('Segoe UI', 11)).pack()
        progress = ttk.Progressbar(window, mode='indeterminate', length=380)
        progress.pack(pady=14)
        progress.start(12)
        events = queue.Queue()
        active_job = {'running': True}
        controls = ttk.Frame(window)
        controls.pack(pady=6)

        def close():
            cancel.set()
            window.withdraw() if active_job['running'] else window.destroy()

        def work():
            try:
                result = play(game, cancel, lambda message: events.put(('progress', message)))
                events.put(('done', result))
            except Exception as error:
                events.put(('error', str(error)))

        def poll():
            try:
                while True:
                    kind, value = events.get_nowait()
                    if kind == 'progress':
                        status.set(value)
                    else:
                        active_job['running'] = False
                        if kind == 'error':
                            (ROOT / 'owner-play-error.log').write_text(value, encoding='utf-8')
                            if not cancel.is_set():
                                status.set(value)
                                progress.stop()
                                retry.pack(side='left', padx=5)
                                journal.pack(side='left', padx=5)
                                continue
                        window.destroy()
                        return
            except queue.Empty:
                window.after(100, poll)

        def retry_work():
            active_job['running'] = True
            retry.pack_forget()
            journal.pack_forget()
            status.set('Повторяю запуск…')
            progress.start(12)
            threading.Thread(target=work, daemon=True).start()

        retry = ttk.Button(controls, text='Повторить', command=retry_work)
        journal = ttk.Button(controls, text='Открыть журнал', command=lambda: os.startfile(str(ROOT / 'owner-play-error.log')))

        window.protocol('WM_DELETE_WINDOW', close)
        threading.Thread(target=work, daemon=True).start()
        window.after(100, poll)
        window.mainloop()


if __name__ == '__main__':
    main()
