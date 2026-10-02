import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def stage_medical(folder, profile='balanced'):
    source = ROOT / '.local/rv-1.1.0/comfort-mods'
    vendors = json.loads((source / 'verified-mods.json').read_text(encoding='utf-8'))['mods']
    mods = folder / 'mods'
    mods.mkdir(exist_ok=True)
    for vendor in vendors:
        archive = source / vendor['file']
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == vendor['sha256'], 'Medical vendor changed: ' + vendor['file']
        shutil.copy2(archive, mods / vendor['file'])
    config = folder / 'config'
    config.mkdir(exist_ok=True)
    files = {'firstaid.cfg': 'firstaid.cfg', 'enhancedvisuals.json': 'enhancedvisuals.json', 'enhancedvisuals-client.json': 'enhancedvisuals-low.json' if profile == 'low' else 'enhancedvisuals-client.json'}
    hashes = {}
    for target, original in files.items():
        path = ROOT / 'patches/controls/config' / original
        shutil.copy2(path, config / target)
        hashes[target] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'vendors': [{key: value[key] for key in ['file', 'version', 'sha256']} for value in vendors], 'configSha256': hashes, 'profile': profile}
