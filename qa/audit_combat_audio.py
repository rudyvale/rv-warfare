import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/qa-1.1.0/audio-libs'))
import numpy as np
import soundfile as sf

parser = argparse.ArgumentParser()
parser.add_argument('--mcheli', type=Path, required=True)
parser.add_argument('--audio', type=Path, required=True)
parser.add_argument('--game', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Warfare-1.12.2')
args = parser.parse_args()
work = ROOT / '.local/qa-1.1.0' / ('audio-audit-' + uuid.uuid4().hex)
work.mkdir(parents=True)
index_path = args.game / 'assets/indexes/1.12.json'
index = json.loads(index_path.read_text(encoding='utf-8'))['objects']
resources = {}
events = {}
manifests = []
archives = {}


def key(name):
    return name if ':' in name else 'minecraft:' + name


def resource_key(name):
    pieces = name.split('/')
    if len(pieces) >= 4 and pieces[0] == 'assets' and pieces[2] == 'sounds' and name.endswith('.ogg'):
        return pieces[1] + ':' + '/'.join(pieces[3:])[:-4]


def merge(namespace, manifest, source):
    for name, definition in manifest.items():
        event = namespace + ':' + name
        if event not in events or definition.get('replace', False):
            events[event] = []
        events[event].extend(definition.get('sounds', []))
    manifests.append({'source': source, 'namespace': namespace, 'eventCount': len(manifest), 'replaceEvents': sum(value.get('replace', False) for value in manifest.values())})


for name, entry in index.items():
    digest = entry['hash']
    path = args.game / 'assets/objects' / digest[:2] / digest
    if name.startswith('minecraft/sounds/') and name.endswith('.ogg'):
        resources['minecraft:' + name[len('minecraft/sounds/'):-4]] = ('asset', path, digest)
    elif name == 'minecraft/sounds.json':
        assert path.is_file() and hashlib.sha1(path.read_bytes()).hexdigest() == digest, 'Vanilla manifest missing/corrupt'
        merge('minecraft', json.loads(path.read_bytes()), str(path))

vendors_root = ROOT / '.local/rv-1.1.0/comfort-mods'
vendors = json.loads((vendors_root / 'verified-mods.json').read_text())['mods']
paths = [args.mcheli, ROOT / '.local/controls/final/techguns-1.12.2-rv.jar']
for vendor in vendors:
    path = vendors_root / vendor['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == vendor['sha256'], 'Vendor archive changed'
    paths.append(path)
paths.append(args.audio)
sources = []
for path in paths:
    archive = zipfile.ZipFile(path)
    archives[str(path)] = archive
    sources.append({'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for name in archive.namelist():
        sound = resource_key(name)
        if sound:
            resources[sound] = ('zip', str(path), name)
        if name.startswith('assets/') and name.endswith('/sounds.json'):
            merge(name.split('/')[1], json.loads(archive.read(name)), str(path))

resolved = set()
event_links = 0
file_references = 0


def resolve(event, trail):
    global event_links, file_references
    assert event in events, 'Missing sound event: ' + event
    assert event not in trail, 'Sound event cycle: ' + event
    for value in events[event]:
        entry = {'name': value} if isinstance(value, str) else value
        sound = key(entry['name'])
        if entry.get('type', 'file') == 'event':
            event_links += 1
            resolve(sound, trail + [event])
        else:
            assert sound in resources, 'Missing OGG: ' + sound + ' from ' + event
            file_references += 1
            resolved.add(sound)


for event in events:
    resolve(event, [])

referenced = set(resolved)
pack_files = [name for name in archives[str(args.audio)].namelist() if resource_key(name)]
resolved.update(resource_key(name) for name in pack_files)
decoded = []
for sound in sorted(resolved):
    item = resources[sound]
    if item[0] == 'asset':
        raw = item[1].read_bytes()
        assert hashlib.sha1(raw).hexdigest() == item[2], 'Corrupt vanilla OGG: ' + sound
        origin = str(item[1])
    else:
        raw = archives[item[1]].read(item[2])
        origin = item[1]
    with sf.SoundFile(io.BytesIO(raw)) as audio:
        assert audio.frames > 0 and audio.samplerate > 0 and audio.channels in (1, 2), 'Empty/invalid OGG: ' + sound
        peak = 0.0
        frames = 0
        for block in audio.blocks(blocksize=65536, dtype='float32', always_2d=True):
            assert np.isfinite(block).all(), 'Nonfinite OGG sample: ' + sound
            peak = max(peak, float(np.abs(block).max()))
            frames += len(block)
        assert frames == audio.frames, 'Incomplete decode: ' + sound
        decoded.append({'sound': sound, 'source': origin, 'sha256': hashlib.sha256(raw).hexdigest(), 'frames': frames, 'sampleRate': audio.samplerate, 'channels': audio.channels, 'seconds': frames / audio.samplerate, 'peak': peak})

for name in pack_files:
    sound = resource_key(name)
    value = next((value for value in decoded if value['sound'] == sound and value['source'] == str(args.audio)), None)
    assert value and value['channels'] == 1, 'RV positional sound unused or not mono: ' + sound
result = {'passed': True, 'sources': sources, 'assetIndexSha256': hashlib.sha256(index_path.read_bytes()).hexdigest(), 'manifests': manifests, 'mergedEventsByNamespace': {namespace: sum(event.startswith(namespace + ':') for event in events) for namespace in sorted({event.split(':')[0] for event in events})}, 'resolvedFileReferences': file_references, 'resolvedEventReferences': event_links, 'uniqueDecodedSounds': len(decoded), 'rvPackMonoFiles': len(pack_files), 'unreferencedRVFiles': sorted(resource_key(name) for name in pack_files if resource_key(name) not in referenced), 'peaksAboveUnity': [value for value in decoded if value['peak'] > 1.0], 'sounds': decoded, 'nativePlaybackTested': False, 'audibleListeningTested': False}
for archive in archives.values():
    archive.close()
(work / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({name: result[name] for name in ['passed', 'mergedEventsByNamespace', 'resolvedFileReferences', 'resolvedEventReferences', 'uniqueDecodedSounds', 'rvPackMonoFiles']}, indent=2))
print('Decoded peaks above unity: ' + str(len(result['peaksAboveUnity'])))
print(str(work / 'report.json'))
