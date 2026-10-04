import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from host_runtime import read_json, server_status
from world_reset import restore_stopped
from invitations import export_invite

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('owner_play', ROOT / 'play-owner.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def stop_server(update):
    update('Сохраняю мир и выключаю сервер…')
    shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    owner.run_hidden([str(shell), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'Stop-All.ps1')], timeout=150)
    if server_status(ROOT).get('state') in ('starting', 'running', 'stopping'):
        raise RuntimeError('Сервер ещё сохраняет мир. Дождись завершения.')
    return 'Мир сохранён. Сервер выключен.'


def reset_world(mode, cancel, update):
    stop_server(update)
    update('Восстанавливаю исходную карту…')
    result = restore_stopped(ROOT, mode)
    owner.wait_for_server(cancel, update)
    owner.start_friends(cancel, update)
    return 'Карта восстановлена. Сервер готов — можно переподключиться.'


class Panel:
    def __init__(self, window, game, monitor=True):
        self.window, self.game = window, game
        self.events = queue.Queue()
        self.busy = False
        self.cancel = threading.Event()
        self.closed = False
        self.server = {}
        self.connection = {}
        window.title('RV — сервер')
        window.geometry('620x530')
        window.minsize(620, 530)
        window.configure(bg='#101822')
        try:
            window.iconbitmap(str(ROOT / 'code.ico'))
        except tk.TclError:
            pass
        self.main = tk.Frame(window, bg='#101822', padx=28, pady=24)
        self.main.pack(fill='both', expand=True)
        tk.Label(self.main, text='RV Warfare', bg='#101822', fg='#e9f1f5', font=('Segoe UI', 23, 'bold')).pack(anchor='w')
        nickname = read_json(ROOT / 'vm-owner.json').get('nickname', '')
        tk.Label(self.main, text='Твой сервер · ' + nickname, bg='#101822', fg='#9db1be', font=('Segoe UI', 11)).pack(anchor='w', pady=(0, 18))
        self.server_label = self.label('Проверяю сервер…')
        self.friends_label = self.label('Проверяю подключение друзей…')
        self.actions = tk.Frame(self.main, bg='#101822')
        self.actions.pack(fill='x', pady=(20, 8))
        self.actions.columnconfigure((0, 1), weight=1)
        self.play_button = self.button('ИГРАТЬ', lambda: self.run('play'), primary=True)
        self.play_button.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        self.copy_button = self.button('Копировать код', self.copy_code)
        self.copy_button.grid(row=1, column=0, sticky='ew', padx=(0, 5), pady=4)
        self.retry_button = self.button('Подключить друзей', lambda: self.run('friends'))
        self.retry_button.grid(row=1, column=1, sticky='ew', padx=(5, 0), pady=4)
        self.reset_button = self.button('Сбросить мир…', self.confirm_reset)
        self.reset_button.grid(row=2, column=0, sticky='ew', padx=(0, 5), pady=4)
        self.stop_button = self.button('Остановить сервер', lambda: self.run('stop'))
        self.stop_button.grid(row=2, column=1, sticky='ew', padx=(5, 0), pady=4)
        self.invite_button = self.button('Сохранить приглашение для друзей', self.save_invite)
        self.invite_button.grid(row=3, column=0, columnspan=2, sticky='ew', pady=4)
        self.status = tk.Label(self.main, text='RV сам запускает сервер и подключение для друзей.', bg='#101822', fg='#a9bcc7', wraplength=560, justify='left', font=('Segoe UI', 10))
        self.status.pack(anchor='w', pady=(10, 4))
        tk.Button(self.main, text='Открыть журнал', command=self.open_log, bg='#101822', fg='#90dec4', activebackground='#101822', activeforeground='white', borderwidth=0, cursor='hand2').pack(anchor='w')
        tk.Label(self.main, text='Закрытие панели оставляет сервер включённым.', bg='#101822', fg='#70899b', font=('Segoe UI', 9)).pack(anchor='w', side='bottom', pady=(6, 0))
        window.protocol('WM_DELETE_WINDOW', self.close)
        self.render()
        if monitor:
            self.scan()
            window.after(2000, self.monitor)
            window.after(100, self.poll)

    def label(self, text):
        label = tk.Label(self.main, text=text, bg='#101822', fg='#a9bcc7', font=('Segoe UI', 12), anchor='w')
        label.pack(fill='x', pady=3)
        return label

    def button(self, text, command, primary=False):
        return tk.Button(self.actions, text=text, command=command, font=('Segoe UI', 12, 'bold' if primary else 'normal'), bg='#8de7c6' if primary else '#253645', fg='#102322' if primary else '#e9f1f5', activebackground='#a6f2d8' if primary else '#344b5d', borderwidth=0, padx=14, pady=10, cursor='hand2')

    def render(self):
        state = self.server.get('state', 'stopped')
        ready = state == 'running' and self.server.get('ready')
        labels = {'stopped': 'Сервер выключен', 'starting': 'Сервер загружается', 'stopping': 'Сохраняется мир', 'failed': 'Ошибка запуска сервера'}
        self.server_label.configure(text='●  ' + ('Сервер готов' if ready else labels.get(state, 'Проверяю сервер')), fg='#8de7c6' if ready else '#a9bcc7')
        friends = self.connection.get('ready') and ready
        reason = self.connection.get('reason', '')
        offline = {'connecting': 'подключаю Steam…', 'steam_offline': 'нужно войти в Steam', 'steam_changed': 'Steam перезапущен — подключи друзей снова', 'timeout': 'сбой связи — нажми «Подключить друзей»'}.get(reason, 'подключение выключено')
        self.friends_label.configure(text='●  Друзья: ' + ('можно заходить · ' + str(self.connection.get('code', '')) if friends else offline), fg='#8de7c6' if friends else '#a9bcc7')
        for button in (self.play_button, self.retry_button, self.reset_button, self.stop_button):
            button.configure(state='disabled' if self.busy else 'normal')
        self.copy_button.configure(state='normal' if friends else 'disabled')
        self.invite_button.configure(state='normal' if friends and not self.busy else 'disabled')
        self.retry_button.configure(state='normal' if ready and not self.busy else 'disabled')
        self.reset_button.configure(state='normal' if (ROOT / '.world-reset/baseline/level.dat').is_file() and not self.busy else 'disabled')
        self.stop_button.configure(state='normal' if state in ('running', 'starting', 'stopping') and not self.busy else 'disabled')

    def scan(self):
        def work():
            try:
                self.events.put(('snapshot', (server_status(ROOT), owner.porthole.read_status(ROOT))))
            except Exception:
                self.events.put(('snapshot', ({}, {})))
        threading.Thread(target=work, daemon=True).start()

    def monitor(self):
        self.scan()
        self.window.after(2000, self.monitor)

    def run(self, action, mode='map'):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.render()
        def update(message):
            self.events.put(('progress', message))
        def work():
            try:
                if action == 'play':
                    owner.play(self.game, self.cancel, update)
                    result = 'Minecraft запущен. Подключение для друзей готово.'
                elif action == 'friends':
                    owner.start_friends(self.cancel, update)
                    result = 'Друзья могут заходить по прежнему коду.'
                elif action == 'reset':
                    result = reset_world(mode, self.cancel, update)
                elif action == 'invite':
                    export_invite(ROOT, mode)
                    result = 'Приглашение сохранено. Отправь его друзьям для подключения.'
                else:
                    result = stop_server(update)
                self.events.put(('done', result))
            except Exception as error:
                (ROOT / 'owner-panel-error.log').write_text(str(error), encoding='utf-8')
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def confirm_reset(self):
        dialog = tk.Toplevel(self.window)
        dialog.title('Сброс мира')
        dialog.geometry('500x260')
        dialog.transient(self.window)
        dialog.grab_set()
        tk.Label(dialog, text='Вернуть расширенную карту к исходному состоянию?', wraplength=450, font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=22, pady=(22, 12))
        mode = tk.StringVar(value=read_json(ROOT / 'owner-play-settings.json').get('resetMode', 'map'))
        tk.Radiobutton(dialog, text='Только карту — инвентари и счёт сохранить', variable=mode, value='map').pack(anchor='w', padx=18)
        tk.Radiobutton(dialog, text='Всё заново — инвентари и счёт сбросить', variable=mode, value='all').pack(anchor='w', padx=18)
        tk.Label(dialog, text='Сервер остановится, сохранит копию текущего мира и перезапустится. Игрокам потребуется переподключиться.', wraplength=450, justify='left').pack(anchor='w', padx=22, pady=14)
        buttons = tk.Frame(dialog)
        buttons.pack(anchor='e', padx=22)
        tk.Button(buttons, text='Отмена', command=dialog.destroy, padx=14).pack(side='left', padx=8)
        def apply():
            chosen = mode.get()
            dialog.destroy()
            self.run('reset', chosen)
        tk.Button(buttons, text='Сбросить мир', command=apply, padx=14).pack(side='left')

    def copy_code(self):
        if self.connection.get('ready'):
            self.window.clipboard_clear()
            self.window.clipboard_append(self.connection.get('code', ''))
            self.status.configure(text='Код подключения скопирован.')

    def save_invite(self):
        path = filedialog.asksaveasfilename(parent=self.window, title='Сохранить приглашение', initialfile='RV.rvinvite', defaultextension='.rvinvite', filetypes=[('Приглашение RV', '*.rvinvite')])
        if path:
            self.run('invite', path)

    def open_log(self):
        path = ROOT / 'owner-panel-error.log'
        os.startfile(str(path if path.exists() else ROOT / 'console.log'))

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'snapshot':
                    self.server, self.connection = value
                    self.render()
                elif kind == 'progress':
                    self.status.configure(text=value, fg='#a9bcc7')
                else:
                    if self.closed:
                        self.window.destroy()
                        return
                    self.busy = False
                    self.status.configure(text=value, fg='#e59d96' if kind == 'error' else '#8de7c6')
                    self.scan()
                    self.render()
        except queue.Empty:
            self.window.after(100, self.poll)

    def close(self):
        self.closed = True
        self.window.withdraw() if self.busy else self.window.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    window = tk.Tk()
    if args.check:
        window.withdraw()
    panel = Panel(window, args.game_root.resolve(), monitor=not args.check)
    if args.check:
        window.update_idletasks()
        print(json.dumps({'state': 'ready', 'buttons': 6, 'resetRequiresConfirmation': True}))
        window.destroy()
    else:
        window.mainloop()
