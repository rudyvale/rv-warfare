import os
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import zipfile

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK / 'audio-libs'))
import numpy as np
import soundfile as sf
from scipy import signal

CLIENT = Path(os.environ['APPDATA']) / '.minecraft/versions/Warfare-1.12.2'
OUT = WORK / 'audio'
OUT.mkdir(exist_ok=True)
RATE = 44100
records = []
content = {}
events = {}


def filt(x, frequency, kind):
    return signal.sosfilt(signal.butter(2, frequency, kind, fs=RATE, output='sos'), x)


def process(data, kind, seed):
    x, sr = sf.read(io.BytesIO(data), always_2d=True)
    original_channels = x.shape[1]
    x = x.mean(axis=1)
    if sr != RATE:
        divisor = math.gcd(sr, RATE)
        x = signal.resample_poly(x, RATE // divisor, sr // divisor)
    x = filt(x - np.mean(x), 32 if kind == 'explosion' else 55, 'highpass')
    x = x / max(float(np.max(np.abs(x))), 1e-8)
    duration = min(len(x) / RATE, 7.5 if kind == 'explosion' else 2.8)
    x = x[:int(duration * RATE)]
    extra = int(RATE * (0.6 if kind == 'explosion' else 0.12))
    dry = np.pad(x, (0, extra))
    low = filt(dry, 190 if kind == 'explosion' else 270, 'lowpass')
    top = filt(dry, 5200, 'highpass')
    y = dry + low * (0.65 if kind == 'explosion' else 0.35) - top * 0.2
    t = np.arange(len(y)) / RATE
    peak = float(np.max(np.abs(y)))
    rng = np.random.default_rng(seed)
    if kind == 'explosion':
        body = filt(rng.normal(0, 1, len(y)), 155, 'lowpass')
        body /= max(float(np.max(np.abs(body))), 1e-8)
        body *= (1 - np.exp(-t * 100)) * np.exp(-t / 0.55)
        y += peak * 0.20 * body
        taps = [(0.079, 0.13), (0.143, 0.09), (0.239, 0.055), (0.401, 0.035)]
    elif kind == 'rocket':
        taps = [(0.039, 0.07), (0.077, 0.035)]
    else:
        body = np.sin(2 * np.pi * (105 * t - 45 * t * t)) * np.exp(-t / 0.032)
        body *= 1 - np.exp(-t * 1500)
        y += peak * (0.17 if kind == 'heavy' else 0.085) * body
        taps = [(0.031, 0.065), (0.067, 0.025)]
    reflection = filt(dry, 2300, 'lowpass')
    for delay, gain in taps:
        n = int(delay * RATE)
        y[n:] += reflection[:-n] * gain
    y = np.tanh(y * 1.12)
    y *= np.minimum(1, t / 0.0005)
    end = min(int(0.07 * RATE), len(y))
    y[-end:] *= np.linspace(1, 0, end) ** 1.4
    limit = {'explosion': 0.79, 'heavy': 0.71, 'shot': 0.63, 'quiet': 0.34, 'rocket': 0.67}[kind]
    y *= limit / max(float(np.max(np.abs(y))), 1e-8)
    encoded = io.BytesIO()
    sf.write(encoded, y, RATE, format='OGG', subtype='VORBIS')
    decoded, rate = sf.read(io.BytesIO(encoded.getvalue()))
    peak = float(np.max(np.abs(decoded)))
    if peak > 0.89:
        y *= 0.87 / peak
        encoded = io.BytesIO()
        sf.write(encoded, y, RATE, format='OGG', subtype='VORBIS')
        decoded, rate = sf.read(io.BytesIO(encoded.getvalue()))
    assert decoded.ndim == 1 and rate == RATE and np.isfinite(decoded).all()
    assert float(np.max(np.abs(decoded))) < 0.9
    return encoded.getvalue(), original_channels, decoded


ballistic = ('assaultrifle', 'handgun', 'pistol', 'sawedoff', 'boltaction', 'combatshotgun', 'thompson', 'revolver', 'ak47', 'as50', 'pdw', 'lmg', 'silencedm4', 'goldenrevolver', 'minigun', 'grenadelauncher', 'aug')
preview = []
for namespace in ('techguns', 'mcheli'):
    jar = next(p for p in (CLIENT / 'mods').glob('*.jar') if p.name.startswith(namespace))
    with zipfile.ZipFile(jar) as z:
        definitions = json.loads(z.read(f'assets/{namespace}/sounds.json'))
        chosen = {}
        for event, definition in definitions.items():
            kind = None
            if namespace == 'techguns':
                if event.startswith('guns.') and event.endswith('fire') and event[5:-4] in ballistic:
                    kind = 'quiet' if 'silenced' in event else 'heavy' if any(s in event for s in ('as50', 'shotgun', 'sawedoff')) else 'shot'
                elif event in ('effects.explosion1', 'effects.nukeexplosion', 'npcs.apacheexplode'):
                    kind = 'explosion'
                elif event == 'guns.rocketfire':
                    kind = 'rocket'
            elif re.match(r'(gun_[hl]\d|cannon_\d|mk19_[lr]|xm301|gau-8|a10gau8)_snd$', event):
                kind = 'heavy' if any(s in event for s in ('cannon', 'gun_h')) else 'shot'
            elif namespace == 'mcheli' and event in ('rocket_snd', 'fim92_snd', 'missile_1_snd', 'missile_2_snd', 'missile_3_snd', 'missile_4_snd', 'hawk_snd', 'sa-2_snd', 'lau-68_snd'):
                kind = 'rocket'
            elif namespace == 'mcheli' and event == 'railgun':
                kind = 'heavy'
            if kind is None:
                continue
            chosen[event] = dict(definition, replace=True)
            for sound in definition['sounds']:
                name = sound if isinstance(sound, str) else sound['name']
                space, path = name.split(':', 1) if ':' in name else (namespace, name)
                member = f'assets/{space}/sounds/{path}.ogg'
                if member in content:
                    continue
                data, channels, decoded = process(z.read(member), kind, int(hashlib.sha256(member.encode()).hexdigest()[:8], 16))
                content[member] = data
                records.append({'path': member, 'kind': kind, 'source_channels': channels, 'channels': 1, 'rate': RATE, 'seconds': round(len(decoded) / RATE, 3), 'peak_dbfs': round(20 * np.log10(max(float(np.max(np.abs(decoded))), 1e-8)), 2)})
                if path in ('guns/ak47_shot_a', 'guns/as50_shot_a', 'effects/explosion1_a', 'cannon_1_snd'):
                    preview.append((member, decoded))
        events[namespace] = chosen

with zipfile.ZipFile(next(p for p in (CLIENT / 'mods').glob('*.jar') if p.name.startswith('mcheli'))) as z:
    aliases = {'hit_metal_snd': 'hit', 'railgun_snd': 'cannon_4_snd', 'lau-68_snd': 'rocket_snd'}
    aliases.update({f'smoke_{color}_snd': 'smoke_snd' for color in ('green', 'none', 'yellow', 'red', 'white', 'blue')})
    for alias, original in aliases.items():
        source = f'assets/mcheli/sounds/{original}.ogg'
        destination = f'assets/mcheli/sounds/{alias}.ogg'
        if source in content:
            content[destination] = content[source]
        else:
            x, sr = sf.read(io.BytesIO(z.read(source)), always_2d=True)
            x = x.mean(axis=1)
            divisor = math.gcd(sr, RATE)
            x = signal.resample_poly(x, RATE // divisor, sr // divisor)
            x *= min(1, 0.5 / max(float(np.max(np.abs(x))), 1e-8))
            stream = io.BytesIO()
            sf.write(stream, x, RATE, format='OGG', subtype='VORBIS')
            content[destination] = stream.getvalue()
    for alias in ('dummy_bay_closed_snd', 'none_snd'):
        stream = io.BytesIO()
        sf.write(stream, np.zeros(1323), RATE, format='OGG', subtype='VORBIS')
        content[f'assets/mcheli/sounds/{alias}.ogg'] = stream.getvalue()

explosion_files = [f'techguns:effects/explosion1_{c}' for c in 'abcde']
events['minecraft'] = {'entity.generic.explode': {'replace': True, 'sounds': explosion_files}}
for namespace, definitions in events.items():
    content[f'assets/{namespace}/sounds.json'] = json.dumps(definitions, separators=(',', ':')).encode()
content['pack.mcmeta'] = json.dumps({'pack': {'pack_format': 3, 'description': 'Warfare Combat Audio 1.2 | Weapons and explosions'}}).encode()
content['CREDITS.txt'] = b'Warfare Combat Audio 1.2\nAudio based on the installed Techguns and MC Heli CE effects, remixed for this pack.\nTechguns: pWn3d_1337 and contributors - https://github.com/pWn3d1337/Techguns2\nMC Heli CE: original MC Heli authors, Warfactory and contributors - https://github.com/Warfactory-Official/McHeliCE\nOriginal mod notices and authorship remain applicable.\n'
pack = OUT / 'Warfare-Combat-Audio.zip'
with zipfile.ZipFile(pack, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for name, data in sorted(content.items()):
        z.writestr(name, data)
with zipfile.ZipFile(pack) as z:
    assert z.testzip() is None
    for namespace, definitions in events.items():
        for event, definition in definitions.items():
            assert definition['replace']
            for sound in definition['sounds']:
                sound = sound if isinstance(sound, str) else sound['name']
                ns, path = sound.split(':')
                assert f'assets/{ns}/sounds/{path}.ogg' in content
demo = np.concatenate([np.concatenate([x, np.zeros(int(RATE * 0.7))]) for _, x in preview])
sf.write(WORK.parent / 'outputs' / 'Warfare-Audio-Preview.wav', demo, RATE, subtype='PCM_16')
report = {'version': '1.2', 'files': len(records), 'total_ogg': sum(n.endswith('.ogg') for n in content), 'events': sum(map(len, events.values())), 'stereo_fixed': sum(r['source_channels'] > 1 for r in records), 'pack_sha256': hashlib.sha256(pack.read_bytes()).hexdigest(), 'preview_order': [n for n, _ in preview], 'samples': records}
(WORK / 'audio-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'samples'}))
