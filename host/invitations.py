import json
import os
from pathlib import Path
import re
import uuid

from host_runtime import porthole, read_json, server_port, server_status

VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?')
TARGET = re.compile(r'(?:peer:[0-9]{17}|[A-Z0-9]{4,16})')


def make_invite(server, connection, port, version, label='RV Warfare'):
    if server.get('state') != 'running' or server.get('ready') is not True or connection.get('ready') is not True:
        raise ValueError('invite_not_ready')
    if type(port) is not int or not 1 <= port <= 65535 or server.get('port') != port or connection.get('port') != port:
        raise ValueError('invite_invalid')
    target = connection.get('peerTarget') or connection.get('code')
    if not isinstance(target, str) or not TARGET.fullmatch(target) or target.startswith('peer:') and int(target[5:]) == 0:
        raise ValueError('invite_invalid')
    if not isinstance(version, str) or len(version) > 128 or not VERSION.fullmatch(version):
        raise ValueError('invite_invalid')
    if not isinstance(label, str) or len(label) > 64 or re.search(r'[\x00-\x1f\x7f]|://|^[\\/]|[A-Za-z]:[\\/]', label):
        raise ValueError('invite_invalid')
    return {'schema': 1, 'product': 'RV', 'transport': 'porthole', 'target': target, 'port': port, 'version': version, 'label': label}


def export_invite(folder, destination):
    folder, destination = Path(folder).resolve(), Path(destination).absolute()
    if destination.suffix.lower() != '.rvinvite' or destination.is_symlink() or not destination.parent.is_dir():
        raise ValueError('invite_destination')
    payload = make_invite(server_status(folder), porthole.read_status(folder), server_port(folder), read_json(folder / 'release.json').get('version'))
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(encoded) > 4096:
        raise ValueError('invite_invalid')
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
