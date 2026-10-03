import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk
import webbrowser

from host_runtime import SERVER_PROFILES, memory_limit, porthole, read_json, server_status, write_json
from invitations import export_invite

ROOT = Path(__file__).resolve().parent
RELEASE_URL = 'https://github.com/rudyvale/rv-warfare/releases/latest'
TEXTS = {
    'ru': {
        'play': 'ИГРАТЬ', 'start': 'ЗАПУСТИТЬ СЕРВЕР', 'stop': 'ОТКЛЮЧИТЬ СЕРВЕР',
        'settings': 'Настройки', 'copy': 'Копировать код', 'copied': 'Код скопирован.',
        'off': 'Сервер выключен', 'loading': 'Сервер загружается', 'ready': 'Сервер готов',
        'saving': 'Сохраняем мир', 'failed': 'Ошибка запуска сервера',
        'intro': 'Сначала запусти сервер. Затем заходи в игру.',
        'online': 'Можно играть. Для друзей скопируй код подключения.',
        'wait': 'Загрузка модов и мира. Окно можно использовать.',
        'launching': 'Запускаем Minecraft…', 'launched': 'Minecraft запущен.',
        'stopped': 'Мир сохранён. Сервер отключён.',
        'error': 'Не удалось выполнить действие. Открой журнал для подробностей.',
        'tunnel_error': 'Сервер готов локально. Porthole не подключился — проверь Steam и нажми «Повторить Porthole».',
        'retry': 'ПОВТОРИТЬ PORTHOLE', 'network': 'Подключение для друзей',
        'network_off': 'Porthole выключен', 'network_loading': 'Подключаем Porthole…',
        'logs': 'Открыть журнал', 'update': 'Доступно обновление', 'github': 'Версии на GitHub',
        'auto': 'Проверять обновления на GitHub при запуске',
        'memory': 'Память сервера, ГБ', 'memory_note': 'Применится при следующем запуске сервера. Остальная память нужна игре и Windows.',
        'save': 'Сохранить', 'cancel': 'Отмена', 'close_note': 'Закрытие окна оставляет сервер включённым.',
        'fps': 'Мало FPS? Отключи шейдеры и поставь дальность 6–8 чанков.',
        'keys': 'F11 — полный экран   ·   Esc — выйти из полного экрана',
        'language': 'Язык', 'saved': 'Настройки сохранены.', 'version': 'Версия',
        'controller': 'Настроить контроллер', 'controller_open': 'Калибровка открыта. В игре её можно вызвать клавишей F8.',
        'invite': 'Пригласить друзей', 'invite_saved': 'Приглашение сохранено. Отправь этот файл друзьям для подключения.', 'invite_error': 'Приглашение не сохранено. Проверь готовность сервера и Porthole.',
    },
    'en': {
        'play': 'PLAY', 'start': 'START SERVER', 'stop': 'STOP SERVER',
        'settings': 'Settings', 'copy': 'Copy code', 'copied': 'Code copied.',
        'off': 'Server is offline', 'loading': 'Server is loading', 'ready': 'Server is ready',
        'saving': 'Saving the world', 'failed': 'Server could not start',
        'intro': 'Start the server, then join the game.',
        'online': 'Ready to play. Copy the connection code for friends.',
        'wait': 'Loading mods and the world. You can keep using this window.',
        'launching': 'Starting Minecraft…', 'launched': 'Minecraft started.',
        'stopped': 'World saved. Server stopped.',
        'error': 'The action failed. Open the log for details.',
        'tunnel_error': 'Local server is ready. Porthole could not connect. Check Steam and click Retry Porthole.',
        'retry': 'RETRY PORTHOLE', 'network': 'Connection for friends',
        'network_off': 'Porthole is offline', 'network_loading': 'Connecting Porthole…',
        'logs': 'Open log', 'update': 'Update available', 'github': 'GitHub releases',
        'auto': 'Check GitHub for updates on launch',
        'memory': 'Server memory, GB', 'memory_note': 'Applies on the next server start. Keep memory available for the game and Windows.',
        'save': 'Save', 'cancel': 'Cancel', 'close_note': 'Closing this window leaves the server running.',
        'fps': 'Low FPS? Disable shaders and use a render distance of 6–8 chunks.',
        'keys': 'F11 — full screen   ·   Esc — leave full screen',
        'language': 'Language', 'saved': 'Settings saved.', 'version': 'Version',
        'controller': 'Configure controller', 'controller_open': 'Calibration opened. You can also press F8 in the game.',
        'invite': 'Invite friends', 'invite_saved': 'Invitation saved. Send the file to your friends to connect.', 'invite_error': 'Invitation was not saved. Check that the server and Porthole are ready.',
    },
}


TEXTS['ru'].update(profile='Профиль сервера', custom='Свои настройки', low='Слабый ПК: 4 чанка / 2 ГБ', balanced='Сбалансированный: 6 чанков / 3 ГБ', quality='Качество: 8 чанков / 4 ГБ', profile_note='Выбранный профиль изменит дальность сервера при следующем запуске. Текущий мир и игровые правила сохраняются. Объём памяти ограничен доступной ОЗУ.', network_same_account='Хост и гость используют один Steam-аккаунт. Для соединения нужны разные Steam-аккаунты.', network_steam_offline='Соединение со Steam потеряно. Войди в Steam, затем нажми «Повторить Porthole».', network_steam_changed='Steam перезапущен. Нажми «Повторить Porthole».', network_timeout='Соединение не успело установиться. Проверь Steam и интернет, затем повтори Porthole.', network_failed='Porthole сообщил об ошибке. Повтори подключение; локальный сервер доступен.', network_connecting='Подключаем Porthole…')
TEXTS['en'].update(profile='Server profile', custom='Custom settings', low='Low: 4 chunks / 2 GB', balanced='Balanced: 6 chunks / 3 GB', quality='Quality: 8 chunks / 4 GB', profile_note='The selected profile changes server view distance on its next start. Your world and gameplay rules are preserved. Memory is capped by physical RAM.', network_same_account='Host and guest use the same Steam account. Connect using separate Steam accounts.', network_steam_offline='Steam connection was lost. Sign in to Steam, then click Retry Porthole.', network_steam_changed='Steam restarted. Click Retry Porthole.', network_timeout='Connection timed out. Check Steam and internet, then retry Porthole.', network_failed='Porthole reported an error. Retry the connection; the local server is available.', network_connecting='Connecting Porthole…')
TEXTS['ru']['incompatible_mod_version'] = 'Версии игры и сервера не совпадают. Обнови оба до одной версии RV, затем повтори запуск игры.'
TEXTS['en']['incompatible_mod_version'] = 'Game and server versions differ. Update both to the same RV release, then try playing again.'
TEXTS['ru']['server_unavailable'] = 'Сервер сейчас недоступен. Дождись готовности сервера, затем повтори запуск игры.'
TEXTS['en']['server_unavailable'] = 'The server is unavailable. Wait until it is ready, then try playing again.'
TEXTS['ru']['memory_budget'] = 'Не хватает памяти для игры и сервера. Закрой другие игры Java или выбери слабый профиль сервера и перезапусти его с сохранением мира.'
TEXTS['en']['memory_budget'] = 'Not enough memory for the game and server. Close other Java games or select the Low server profile and restart it with a world save.'
TEXTS['ru']['cancelled'] = 'Запуск отменён.'
TEXTS['en']['cancelled'] = 'Launch cancelled.'


class PlayCancelled(Exception):
    pass


class Launcher:
    def __init__(self, window, folder=ROOT, monitor=True):
        self.window = window
        self.folder = Path(folder)
        self.settings = read_json(self.folder / 'launcher-settings.json')
        self.language = self.settings.get('language', 'ru')
        if self.language not in TEXTS:
            self.language = 'ru'
        self.events = queue.Queue()
        self.closed = threading.Event()
        self.cancel_start = threading.Event()
        self.server_operation_lock = threading.Lock()
        self.server_generation = 0
        self.server = {'state': 'stopped', 'ready': False}
        self.connection = {}
        self.server_job = None
        self.client_job = False
        self.controller_job = False
        self.invite_job = False
        self.client_running = False
        self.update_available = False
        self.status_key = 'intro'
        self.preferences = read_json(self.folder / '.updates/preferences.json')
        self.auto_check = self.preferences.get('autoCheck') is not False
        self.update_lock = threading.Lock()
        self.window.title('RV')
        self.window.configure(bg='#0d1319')
        scale = max(1, float(self.window.tk.call('tk', 'scaling')) / (96 / 72))
        self.window.geometry(f'{int(1180 * scale)}x{int(760 * scale)}')
        self.window.minsize(int(800 * scale), int(620 * scale))
        icon = self.folder / 'code.ico'
        if not icon.is_file():
            icon = self.folder.parent / 'assets/code.ico'
        if icon.is_file():
            self.window.iconbitmap(str(icon))
        self.window.bind('<F11>', lambda event: self.fullscreen())
        self.window.bind('<Escape>', lambda event: self.window.attributes('-fullscreen', False))
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.build()
        self.translate()
        if monitor:
            threading.Thread(target=self.monitor, daemon=True).start()
            self.check_updates()
        self.poll_id = self.window.after(80, self.poll)

    def t(self, key):
        return TEXTS[self.language][key]

    def button(self, parent, command, primary=False):
        return tk.Button(parent, command=command, bg='#96f1cd' if primary else '#1c2b35', fg='#10251d' if primary else '#e4eee9', activebackground='#b7ffdf' if primary else '#2a404d', activeforeground='#10251d' if primary else '#ffffff', disabledforeground='#5d756c' if primary else '#77878d', relief='flat', bd=0, highlightthickness=1, highlightbackground='#2d424a', highlightcolor='#96f1cd', font=('Segoe UI', 13, 'bold'), cursor='hand2', padx=22, pady=17, takefocus=True)

    def build(self):
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        self.header = tk.Frame(self.window, bg='#0d1319', padx=36, pady=14)
        self.header.grid(row=0, column=0, sticky='ew')
        tk.Label(self.header, text='</>  RV', bg='#0d1319', fg='#96f1cd', font=('Segoe UI', 20, 'bold')).pack(side='left')
        self.settings_button = self.button(self.header, self.show_settings)
        self.settings_button.configure(pady=10, font=('Segoe UI', 11))
        self.settings_button.pack(side='right')
        self.github_button = self.button(self.header, lambda: webbrowser.open(RELEASE_URL))
        self.github_button.configure(pady=10, font=('Segoe UI', 11))
        self.github_button.pack(side='right', padx=12)
        self.main = tk.Frame(self.window, bg='#0d1319', padx=52)
        self.main.grid(row=1, column=0, sticky='nsew')
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(0, weight=1)
        self.main.rowconfigure(9, weight=1)
        self.title = tk.Label(self.main, text='RV', bg='#0d1319', fg='#f0f5f2', font=('Segoe UI', 36, 'bold'), anchor='w')
        self.title.grid(row=1, column=0, sticky='w', pady=(0, 8))
        self.server_label = tk.Label(self.main, bg='#0d1319', fg='#a6b7bc', font=('Segoe UI', 16), anchor='w')
        self.server_label.grid(row=2, column=0, sticky='ew', pady=(0, 14))
        self.play_button = self.button(self.main, lambda: self.run_action('play'), primary=True)
        self.play_button.configure(font=('Segoe UI', 25, 'bold'), pady=14)
        self.play_button.grid(row=3, column=0, sticky='ew')
        self.actions = tk.Frame(self.main, bg='#0d1319')
        self.actions.grid(row=4, column=0, sticky='ew', pady=(10, 10))
        self.actions.columnconfigure((0, 1), weight=1, uniform='actions')
        self.start_button = self.button(self.actions, lambda: self.run_action('start'))
        self.start_button.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.stop_button = self.button(self.actions, lambda: self.run_action('stop'))
        self.stop_button.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        self.progress = ttk.Progressbar(self.main, mode='indeterminate')
        self.progress.grid(row=5, column=0, sticky='ew')
        self.progress.grid_remove()
        self.progress_active = False
        self.status = tk.Label(self.main, bg='#0d1319', fg='#a6b7bc', font=('Segoe UI', 11), justify='left', anchor='w', wraplength=1050)
        self.status.grid(row=6, column=0, sticky='ew', pady=(8, 12))
        self.network_row = tk.Frame(self.main, bg='#0d1319')
        self.network_row.grid(row=7, column=0, sticky='ew', pady=(2, 0))
        self.network_label = tk.Label(self.network_row, bg='#0d1319', fg='#a6b7bc', font=('Segoe UI', 12), anchor='w')
        self.network_label.pack(side='left')
        self.copy_button = self.button(self.network_row, self.copy_code)
        self.copy_button.configure(pady=8, font=('Segoe UI', 10))
        self.copy_button.pack(side='right')
        self.invite_button = self.button(self.network_row, self.save_invite)
        self.invite_button.configure(pady=8, font=('Segoe UI', 10))
        self.invite_button.pack(side='right', padx=8)
        self.retry_button = self.button(self.network_row, lambda: self.run_action('tunnel'))
        self.retry_button.configure(pady=8, font=('Segoe UI', 10))
        self.footer = tk.Frame(self.window, bg='#0d1319', padx=36, pady=18)
        self.footer.grid(row=2, column=0, sticky='ew')
        self.footer.columnconfigure(0, weight=1)
        self.hint = tk.Label(self.footer, bg='#0d1319', fg='#73868d', font=('Segoe UI', 10), anchor='w', justify='left')
        self.hint.grid(row=0, column=0, sticky='w')
        self.log_button = self.button(self.footer, self.open_log)
        self.log_button.configure(pady=8, font=('Segoe UI', 10))
        self.log_button.grid(row=0, column=1, sticky='e')
        self.main.bind('<Configure>', lambda event: self.status.configure(wraplength=max(500, event.width - 104)))

    def translate(self):
        for button, key in [(self.play_button, 'play'), (self.settings_button, 'settings'), (self.copy_button, 'copy'), (self.invite_button, 'invite'), (self.stop_button, 'stop'), (self.log_button, 'logs'), (self.retry_button, 'retry')]:
            button.configure(text=self.t(key))
        self.hint.configure(text=self.t('close_note') + '\n' + self.t('keys'))
        self.render()

    def render(self):
        state = self.server.get('state', 'stopped')
        ready = state == 'running' and self.server.get('ready')
        busy = state in ('starting', 'stopping') or self.server_job is not None or self.client_job
        label = 'ready' if ready else {'starting': 'loading', 'stopping': 'saving', 'failed': 'failed'}.get(state, 'off')
        self.server_label.configure(text='●  ' + self.t(label), fg='#96f1cd' if ready else '#a6b7bc')
        self.play_button.configure(state='normal' if ready and not self.client_job and not self.client_running and self.server_job != 'stop' else 'disabled')
        can_start = not self.server_job and state not in ('starting', 'stopping') and not ready
        self.start_button.configure(text=self.t('start'), state='normal' if can_start else 'disabled')
        can_stop = self.server_job != 'stop' and (state in ('starting', 'running') or self.connection.get('ready'))
        self.stop_button.configure(state='normal' if can_stop else 'disabled')
        code = self.connection.get('code') if self.connection.get('ready') else ''
        network_key = 'network_loading' if self.server_job == 'tunnel' else 'network_' + str(self.connection.get('reason', 'off'))
        if network_key not in TEXTS[self.language]:
            network_key = 'network_off'
        self.network_label.configure(text=self.t('network') + ': ' + (code or self.t(network_key)), wraplength=780, justify='left')
        self.copy_button.configure(state='normal' if code else 'disabled')
        self.invite_button.configure(state='normal' if ready and self.connection.get('ready') and not self.invite_job and not self.server_job else 'disabled')
        if ready and not code:
            self.copy_button.pack_forget()
            self.retry_button.pack(side='right')
            self.retry_button.configure(state='normal' if not self.server_job else 'disabled')
        else:
            self.retry_button.pack_forget()
            self.copy_button.pack(side='right')
        self.github_button.configure(text=self.t('update' if self.update_available else 'github'))
        status_key = self.status_key
        if status_key == 'intro':
            status_key = 'online' if ready else 'wait' if state == 'starting' else 'intro'
        if ready and not code and status_key in ('online', 'tunnel_error'):
            candidate = 'network_' + str(self.connection.get('reason', ''))
            status_key = candidate if candidate in TEXTS[self.language] else 'tunnel_error'
        self.status.configure(text=self.t(status_key))
        if busy and not self.progress_active:
            self.progress.grid()
            self.progress.start(20)
            self.progress_active = True
        elif not busy and self.progress_active:
            self.progress.stop()
            self.progress.grid_remove()
            self.progress_active = False

    def fullscreen(self):
        self.window.attributes('-fullscreen', not self.window.attributes('-fullscreen'))

    def show_settings(self):
        if getattr(self, 'dialog', None) and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        dialog = self.dialog = tk.Toplevel(self.window)
        dialog.title(self.t('settings'))
        dialog.configure(bg='#0d1319', padx=26, pady=24)
        dialog.transient(self.window)
        dialog.resizable(False, False)
        dialog.grab_set()
        for row, key in [(0, 'language'), (2, 'memory')]:
            tk.Label(dialog, text=self.t(key), bg='#0d1319', fg='#e4eee9', font=('Segoe UI', 12)).grid(row=row, column=0, sticky='w', pady=(0, 8))
        lang = tk.StringVar(value='Русский' if self.language == 'ru' else 'English')
        ttk.Combobox(dialog, textvariable=lang, values=['Русский', 'English'], state='readonly').grid(row=1, column=0, sticky='ew', pady=(0, 20))
        ram = tk.StringVar(value=str(memory_limit(self.settings)))
        ram_input = ttk.Spinbox(dialog, from_=2, to=8, textvariable=ram, state='readonly' if self.settings.get('serverProfile', 'custom') == 'custom' else 'disabled')
        ram_input.grid(row=3, column=0, sticky='ew')
        tk.Label(dialog, text=self.t('memory_note'), bg='#0d1319', fg='#a6b7bc', wraplength=420, justify='left').grid(row=4, column=0, sticky='w', pady=(8, 20))
        auto = tk.BooleanVar(value=self.auto_check)
        tk.Checkbutton(dialog, text=self.t('auto'), variable=auto, bg='#0d1319', fg='#e4eee9', activebackground='#0d1319', activeforeground='#e4eee9', selectcolor='#263942', font=('Segoe UI', 11)).grid(row=5, column=0, sticky='w')
        tk.Label(dialog, text=self.t('profile'), bg='#0d1319', fg='#e4eee9', font=('Segoe UI', 12)).grid(row=6, column=0, sticky='w', pady=(16, 8))
        profile_keys = ['custom', 'low', 'balanced', 'quality']
        profile_labels = [self.t(key) for key in profile_keys]
        selected = self.settings.get('serverProfile', 'custom')
        profile = tk.StringVar(value=self.t(selected) if selected in profile_keys else self.t('custom'))
        chooser = ttk.Combobox(dialog, textvariable=profile, values=profile_labels, state='readonly')
        chooser.grid(row=7, column=0, sticky='ew')
        tk.Label(dialog, text=self.t('profile_note'), bg='#0d1319', fg='#a6b7bc', wraplength=420, justify='left').grid(row=8, column=0, sticky='w', pady=(8, 8))
        profile_touched = [False]
        def profile_changed(event):
            profile_touched[0] = True
            key = profile_keys[profile_labels.index(profile.get())]
            if key in SERVER_PROFILES:
                ram.set(str(memory_limit({'serverMemoryGB': SERVER_PROFILES[key]['memory']})))
            ram_input.configure(state='disabled' if key in SERVER_PROFILES else 'readonly')
        chooser.bind('<<ComboboxSelected>>', profile_changed)
        def save():
            try:
                self.settings = read_json(self.folder / 'launcher-settings.json', self.settings)
                self.language = 'ru' if lang.get() == 'Русский' else 'en'
                self.settings.update(language=self.language, serverMemoryGB=memory_limit({'serverMemoryGB': ram.get()}))
                key = profile_keys[profile_labels.index(profile.get())]
                pending = self.settings.get('pendingServerProfile')
                self.settings['serverProfile'] = key
                self.settings.pop('pendingServerProfile', None)
                if key in SERVER_PROFILES and (profile_touched[0] or key != selected or pending == key):
                    self.settings['pendingServerProfile'] = key
                    if profile_touched[0] or key != selected or 'serverProfileRequest' not in self.settings:
                        self.settings['serverProfileRequest'] = str(time.time_ns())
                else:
                    self.settings.pop('serverProfileRequest', None)
                write_json(self.folder / 'launcher-settings.json', self.settings)
                self.auto_check = auto.get()
                preferences = read_json(self.folder / '.updates/preferences.json')
                preferences['autoCheck'] = self.auto_check
                write_json(self.folder / '.updates/preferences.json', preferences)
                self.status_key = 'saved'
                self.translate()
                dialog.destroy()
            except OSError:
                self.status_key = 'error'
                self.render()
        def controller():
            dialog.destroy()
            self.configure_controller()
        controller_button = self.button(dialog, controller)
        controller_button.configure(text=self.t('controller'), state='disabled' if self.controller_job else 'normal')
        controller_button.grid(row=9, column=0, sticky='ew', pady=(16, 0))
        self.button(dialog, save, primary=True).grid(row=10, column=0, sticky='ew', pady=(12, 0))
        dialog.grid_slaves(row=10)[0].configure(text=self.t('save'))

    def configure_controller(self):
        if self.controller_job:
            return
        self.controller_job = True
        def work():
            try:
                game = Path(os.environ['APPDATA']) / '.minecraft/versions/Warfare-1.12.2'
                self.script('Configure-Controller.ps1', timeout=30, arguments=['-InstallRoot', str(game)])
                self.events.put(('controller', 'controller_open'))
            except Exception:
                self.events.put(('controller', 'error'))
        threading.Thread(target=work, daemon=True).start()

    def copy_code(self):
        if self.connection.get('ready') and self.connection.get('code'):
            self.window.clipboard_clear()
            self.window.clipboard_append(self.connection['code'])
            self.status_key = 'copied'
            self.render()

    def save_invite(self):
        if self.invite_job:
            return
        path = filedialog.asksaveasfilename(parent=self.window, title=self.t('invite'), initialfile='RV.rvinvite', defaultextension='.rvinvite', filetypes=[('RV', '*.rvinvite')])
        if not path:
            return
        self.invite_job = True
        self.render()
        def work():
            try:
                export_invite(self.folder, path)
                self.events.put(('invite', 'invite_saved'))
            except (OSError, ValueError):
                self.events.put(('invite', 'invite_error'))
        threading.Thread(target=work, daemon=True).start()

    def open_log(self):
        path = self.folder / 'launcher.log'
        if not path.exists():
            path = self.folder / 'console.log'
        if path.exists():
            os.startfile(path)

    def check_updates(self):
        if not self.auto_check or os.environ.get('VM_SKIP_UPDATE_CHECK') == '1':
            return
        def work():
            if not self.update_lock.acquire(blocking=False):
                return
            try:
                worker = self.folder / 'Check-WarfareUpdate.ps1'
                version = read_json(self.folder / 'release.json').get('version')
                if worker.is_file() and version:
                    subprocess.run([self.shell(), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', str(worker), '-Root', str(self.folder), '-CurrentVersion', version], creationflags=subprocess.CREATE_NO_WINDOW, timeout=25)
            except (OSError, subprocess.TimeoutExpired):
                pass
            finally:
                self.update_lock.release()
        threading.Thread(target=work, daemon=True).start()

    def shell(self):
        return str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')

    def script(self, name, timeout=180, arguments=()):
        with (self.folder / 'launcher.log').open('a', encoding='utf-8') as log:
            log.write(time.strftime('\n%Y-%m-%d %H:%M:%S ') + name + '\n')
            log.flush()
            result = subprocess.run([self.shell(), '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-File', str(self.folder / name)] + list(arguments), cwd=self.folder, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout)
        if result.returncode == 2 and name == 'Join-Server.ps1':
            raise PlayCancelled()
        if result.returncode:
            raise RuntimeError(name)

    def run_action(self, action):
        if action == 'play':
            if self.client_job or self.client_running or not self.server.get('ready') or self.server_job == 'stop':
                return
            self.client_job = True
            self.status_key = 'launching'
        elif action == 'stop':
            if self.server_job == 'stop':
                return
            self.cancel_start.set()
            self.server_generation += 1
            self.server_job = 'stop'
            self.status_key = 'saving'
        else:
            if self.server_job or self.server.get('state') in ('starting', 'stopping'):
                return
            if action == 'tunnel' and not self.server.get('ready'):
                return
            self.cancel_start = threading.Event()
            self.server_generation += 1
            self.server_job = action
            self.status_key = 'wait'
        if action in ('play', 'start'):
            self.check_updates()
        self.render()
        cancel = self.cancel_start
        generation = self.server_generation
        action_started = time.time()
        def work():
            try:
                if action == 'play':
                    self.script('Join-Server.ps1', timeout=600)
                elif action == 'stop':
                    with self.server_operation_lock:
                        self.script('Stop-All.ps1')
                else:
                    if action == 'start' and not server_status(self.folder).get('ready'):
                        with self.server_operation_lock:
                            if cancel.is_set():
                                return
                            self.script('Start-Server.ps1', timeout=25)
                        beginning = time.monotonic()
                        while time.monotonic() - beginning < 240:
                            if cancel.wait(0.25):
                                return
                            state = server_status(self.folder)
                            if state.get('ready'):
                                break
                            if state.get('state') in ('failed', 'stopped') and time.monotonic() - beginning > 5:
                                raise RuntimeError('Server did not start')
                        else:
                            raise TimeoutError('Server startup exceeded 240 seconds')
                    if cancel.is_set():
                        return
                    try:
                        with self.server_operation_lock:
                            if cancel.is_set():
                                return
                            self.events.put(('phase', (generation, 'tunnel')))
                            self.script('Start-Porthole.ps1', timeout=45)
                    except Exception:
                        self.events.put(('done', (action, 'tunnel_error', generation)))
                        return
                self.events.put(('done', (action, {'play': 'launched', 'stop': 'stopped', 'start': 'online', 'tunnel': 'online'}[action], generation)))
            except PlayCancelled:
                self.events.put(('done', (action, 'cancelled', generation)))
            except Exception as error:
                try:
                    with (self.folder / 'launcher.log').open('a', encoding='utf-8') as log:
                        log.write(str(error) + '\n')
                except OSError:
                    pass
                client = read_json(self.folder / 'client-state.json') if action == 'play' else {}
                try:
                    reason = client.get('reason') if float(client.get('started', 0)) >= action_started else None
                except (TypeError, ValueError, OverflowError):
                    reason = None
                if action == 'play' and not server_status(self.folder).get('ready'):
                    reason = 'server_unavailable'
                self.events.put(('done', (action, reason if reason in ('incompatible_mod_version', 'server_unavailable', 'memory_budget') else 'error', generation)))
        threading.Thread(target=work, daemon=True).start()

    def monitor(self):
        while not self.closed.is_set():
            server = server_status(self.folder)
            connection = porthole.read_status(self.folder)
            client = read_json(self.folder / 'client-state.json')
            try:
                identity = porthole.process_identity(int(client.get('pid', 0)))
                stamp = client.get('processStartedAt')
                running = bool(identity and Path(identity['executable']).name.lower() in ('java.exe','javaw.exe') and abs(identity['startedAt'] - float(stamp if stamp is not None else client.get('started',0))) < (0.05 if stamp is not None else 3))
            except (TypeError, ValueError, OverflowError):
                running = False
            update = read_json(self.folder / '.updates/status.json')
            current = read_json(self.folder / 'release.json')
            try:
                newer = tuple(map(int, update['version'].split('.'))) > tuple(map(int, current['version'].split('.')))
                available = update.get('state') in ('available', 'downloaded') and newer
            except (KeyError, ValueError, AttributeError):
                available = False
            self.events.put(('snapshot', (server, connection, running, available)))
            self.closed.wait(1)

    def poll(self):
        if self.closed.is_set():
            return
        try:
            for _ in range(50):
                event, value = self.events.get_nowait()
                if event == 'snapshot':
                    self.server, self.connection, self.client_running, self.update_available = value
                elif event == 'controller':
                    self.controller_job = False
                    self.status_key = value
                elif event == 'invite':
                    self.invite_job = False
                    self.status_key = value
                elif event == 'phase' and value[0] == self.server_generation and self.server_job == 'start':
                    self.server_job = value[1]
                elif event == 'done':
                    action, status, generation = value
                    if action == 'play':
                        self.client_job = False
                    elif generation != self.server_generation:
                        continue
                    else:
                        self.server_job = None
                    self.status_key = status
        except queue.Empty:
            pass
        self.render()
        self.poll_id = self.window.after(80, self.poll)

    def close(self):
        if self.closed.is_set():
            return
        self.closed.set()
        self.window.after_cancel(self.poll_id)
        if self.progress_active:
            self.progress.stop()
        self.window.destroy()
        for name, value in list(vars(self).items()):
            if isinstance(value, (tk.Misc, tk.Variable)):
                setattr(self, name, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        key = hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
        lock = kernel.CreateMutexW(None, False, 'Local\\VMLauncher-' + key)
        if ctypes.get_last_error() == 183:
            return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    window = tk.Tk()
    if args.check:
        window.withdraw()
    app = Launcher(window, monitor=not args.check)
    if args.check:
        for language in TEXTS:
            app.language = language
            app.translate()
            window.update_idletasks()
            assert app.play_button.cget('text') == TEXTS[language]['play']
            assert str(app.play_button.cget('state')) == 'disabled'
            assert str(app.start_button.cget('state')) == 'normal'
        app.close()
        print(json.dumps({'launcher': 'valid', 'languages': list(TEXTS), 'tabs': 0, 'primary_actions': 3}))
    else:
        window.state('zoomed')
        window.mainloop()


if __name__ == '__main__':
    main()
