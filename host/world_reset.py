from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import uuid

from host_runtime import acquire_lock, server_port, server_status

PLAYER_DIRS = ('playerdata', 'advancements', 'stats')


def world_path(server):
    server = Path(server).resolve(strict=True)
    match = re.search(r'^level-name=(.+)$', (server / 'server.properties').read_text(encoding='utf-8-sig'), re.MULTILINE)
    name = match.group(1).strip() if match else 'world'
    if not re.fullmatch(r'[\w -]+', name) or name in ('.', '..'):
        raise ValueError('Имя мира должно быть папкой внутри сервера.')
    world = (server / name).resolve(strict=True)
    if world.parent != server or not (world / 'level.dat').is_file():
        raise ValueError('Не найдена папка мира сервера.')
    return world


@contextmanager
def maintenance(server):
    server = Path(server).resolve(strict=True)
    lock = acquire_lock(server)
    if lock is None:
        raise RuntimeError('Сначала останови сервер и дождись сохранения мира.')
    try:
        if server_status(server).get('state') in ('starting', 'running', 'stopping'):
            raise RuntimeError('Сервер ещё работает; мир не изменён.')
        with socket.socket() as reservation:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                reservation.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            reservation.bind(('127.0.0.1', server_port(server)))
            yield
    finally:
        close = ctypes.windll.kernel32.CloseHandle
        close.argtypes = [ctypes.c_void_p]
        close(lock)


def ignore_progress(directory, names):
    return {name for name in names if name in PLAYER_DIRS or name in ('session.lock', 'level.dat_old', 'scoreboard.dat')}


def capture_baseline(server):
    server = Path(server).resolve(strict=True)
    with maintenance(server):
        world = world_path(server)
        target = server / '.world-reset' / 'baseline'
        if target.exists():
            raise FileExistsError('Исходная карта уже сохранена.')
        target.parent.mkdir(exist_ok=True)
        stage = target.parent / ('baseline-new-' + uuid.uuid4().hex)
        shutil.copytree(world, stage, ignore=ignore_progress)
        if not (stage / 'region').is_dir() or not (stage / 'level.dat').is_file():
            raise ValueError('Неполная копия карты; исходное состояние не заменено.')
        stage.replace(target)
        files = {path.relative_to(target).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in target.rglob('*') if path.is_file()}
        (target.parent / 'baseline.json').write_text(json.dumps({'world': world.name, 'created': datetime.now(timezone.utc).isoformat(), 'regionFiles': len(list((target / 'region').glob('*.mca'))), 'files': files}, indent=2), encoding='utf-8')
        return target


def restore_stopped(server, mode='map'):
    if mode not in ('map', 'all'):
        raise ValueError('Неизвестный режим сброса.')
    server = Path(server).resolve(strict=True)
    with maintenance(server):
        world = world_path(server)
        baseline = (server / '.world-reset' / 'baseline').resolve(strict=True)
        if baseline.parent != server / '.world-reset' or not (baseline / 'level.dat').is_file():
            raise ValueError('Сначала сохрани исходную карту.')
        metadata = json.loads((baseline.parent / 'baseline.json').read_text(encoding='utf-8'))
        files = metadata.get('files', {})
        if metadata.get('world') != world.name or not files:
            raise ValueError('Не удалось проверить исходную карту.')
        for name, digest in files.items():
            path = (baseline / name).resolve(strict=True)
            if baseline not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('Исходная карта повреждена; текущий мир не изменён.')
        stage = server / ('.world-reset-stage-' + uuid.uuid4().hex)
        shutil.copytree(baseline, stage)
        if mode == 'map':
            for name in PLAYER_DIRS + ('data',):
                if (world / name).is_dir():
                    shutil.copytree(world / name, stage / name, dirs_exist_ok=True)
        backup = server / 'backups' / ('world-reset-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
        backup.mkdir(parents=True, exist_ok=False)
        archived = backup / world.name
        if world.parent != server or stage.resolve().parent != server or archived.resolve().parent.parent != server / 'backups':
            raise ValueError('Пути восстановления вышли за папку сервера.')
        world.replace(archived)
        try:
            stage.replace(world)
        except OSError:
            archived.replace(world)
            raise
        (backup / 'restore.json').write_text(json.dumps({'mode': mode, 'world': world.name, 'playersPreserved': mode == 'map'}, indent=2), encoding='utf-8')
        return {'state': 'restored', 'mode': mode, 'backup': str(backup), 'playersPreserved': mode == 'map'}
