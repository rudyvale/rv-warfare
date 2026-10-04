import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile


BASELINE_SHA256 = '5fddd87a99455edbd85005dd24851591862ab7d065e405597d2def4bc66d1937'
PROTOTYPE_SHA256 = '13d6d8c6daa40aec05ff1e093308628e698f220452bbf30d6bf59d786d26137f'
ANIMATED_SHA256 = 'beb4a37f45e25b3aeee688d04244698aec20d9f6f3c3cb54eb682cc17a0a31fc'
NONE_SILENCE_SHA256 = '8809826354a276d08da626b01a029dbd445b08bb4a8da325f2b39c4eca05e2f4'
ALIASES = {
    'prototype.l115a3.sup': 'prototype.l115a3.shoot.sup',
    'prototype.mosin_nagant.sup': 'prototype.mosin_nagant.shoot.sup',
    'prototype.sks.sup': 'prototype.sks.shoot.sup',
    'prototype.p88.distant': 'prototype.p88.shoot.distant',
    'prototype.m14s.distant': 'prototype.m14.distant',
}


def load_pinned(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'Unexpected source checksum: {path}')
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError(f'Invalid source archive: {path}')
        return {name: archive.read(name) for name in archive.namelist()}


def file_reference(entry):
    name = entry if isinstance(entry, str) else entry['name']
    namespace, resource = name.split(':', 1)
    return f'assets/{namespace}/sounds/{resource}.ogg'


def build(source, prototype, output, animated=None):
    if output.resolve() in (source.resolve(), prototype.resolve(), animated.resolve() if animated else None):
        raise ValueError('Output must differ from both source archives')
    content = load_pinned(source, BASELINE_SHA256)
    native = load_pinned(prototype, PROTOTYPE_SHA256)
    native_events = json.loads(native['assets/modularwarfare/sounds.json'])
    events = {}
    for alias, target in ALIASES.items():
        samples = native_events[target]['sounds']
        if not samples or any(file_reference(entry) not in native for entry in samples):
            raise ValueError(f'Unresolved original event: {target}')
        events[alias] = {'replace': True, 'sounds': [{'name': f'modularwarfare:{target}', 'type': 'event'}]}
    m14 = deepcopy(native_events['prototype.m14.shoot'])
    m14['sounds'] = [entry for entry in m14['sounds'] if file_reference(entry) in native]
    if m14['sounds'] != [f'modularwarfare:m14/shoot{number}' for number in (2, 3, 4)]:
        raise ValueError('Unexpected original M14 samples')
    m14['replace'] = True
    events['prototype.m14.shoot'] = m14
    variations = {
        'prototype.hk416.shoot': ('ar1', 1.0, 32),
        'prototype.hk416.shoot.distant': ('ar1', 0.28, 96),
        'prototype.hk416.shoot.sup': ('silencedm4', 0.7, 32),
    }
    for event, (family, volume, distance) in variations.items():
        samples = []
        for variant in ('a', 'b'):
            resource = f'techguns:guns/{family}_shot_{variant}'
            sample = {'name': resource, 'volume': volume, 'attenuation_distance': distance}
            if file_reference(sample) not in content:
                raise ValueError(f'Missing RV rifle sample: {resource}')
            samples.append(sample)
        events[event] = {'replace': True, 'sounds': samples}
    if animated:
        animated_content = load_pinned(animated, ANIMATED_SHA256)
        animated_events = json.loads(animated_content['assets/modularwarfare/sounds.json'])
        event = 'cloud.siz_bg_nope_tcp'
        missing = file_reference(animated_events[event]['sounds'][0])
        intended = 'assets/modularwarfare/sounds/siz_bg_nope_tcp.ogg'
        silence = file_reference('mcheli:none_snd')
        if missing in animated_content or intended not in animated_content or silence not in content or hashlib.sha256(content[silence]).hexdigest() != NONE_SILENCE_SHA256:
            raise ValueError('Unexpected ModularWarfare silent-event resource layout')
        for config, sound_event in (('guns/tcp.ak74.json', 'weaponReloadSecond'), ('guns/tcp.s1897.json', 'weaponBulletLoad')):
            weapon = json.loads(animated_content[config])
            references = [item['soundName'] for item in weapon['weaponSoundMap'][sound_event]]
            if event not in references:
                raise ValueError(f'Unexpected silent-event use: {config}/{sound_event}')
        events[event] = {'category': 'player', 'replace': True, 'sounds': [{'name': 'mcheli:none_snd'}]}
    member = 'assets/modularwarfare/sounds.json'
    if member in content:
        raise ValueError('Baseline unexpectedly contains ModularWarfare overrides')
    content[member] = json.dumps(events, separators=(',', ':')).encode('utf-8')
    content['pack.mcmeta'] = json.dumps({'pack': {'pack_format': 3, 'description': 'RV Combat Audio 1.6 | FPV, weapons and directional rifle audio'}}, separators=(',', ':')).encode('utf-8')
    content['CREDITS.txt'] += (
        '\nRV 1.2: ModularWarfare event aliases reference original, locally installed samples.\n'
        'The M14 event uses its three existing samples; no vendor audio is distributed here.\n'
        'M4A4/HK416 fire uses the existing RV assault-rifle and silenced-rifle remixes\n'
        'for positional mono playback. These are a game sound design, not field recordings.\n'
        'ModularWarfare authors: https://www.curseforge.com/minecraft/mc-mods/modularwarfare\n'
        'Generated by tools/build_vendor_audio.py from pinned RV Combat Audio 1.5.\n'
    ).encode('utf-8')
    if animated:
        content['CREDITS.txt'] += b'An empty TCP reload cue is mapped to existing RV silence.\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    report = {
        'status': 'STAGED_NATIVE_PLAYBACK_PENDING',
        'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'sourceSha256': BASELINE_SHA256,
        'prototypeSha256': PROTOTYPE_SHA256,
        'sameWeaponAliases': ALIASES,
        'm14Samples': m14['sounds'],
        'directionalRifleEvents': list(variations),
        'animatedSha256': ANIMATED_SHA256 if animated else None,
        'silentEventAlias': {'cloud.siz_bg_nope_tcp': 'mcheli:none_snd'} if animated else None,
        'newAudioFiles': 0,
        'newVendorAudioFiles': 0,
        'existingAudioBytesPreserved': True,
        'nativePlaybackVerified': False,
    }
    output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build RV audio compatibility overrides from pinned sources.')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--prototype', type=Path, required=True)
    parser.add_argument('--animated', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.prototype, args.output, args.animated)))
