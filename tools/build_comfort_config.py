import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--native-config', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
medical = (args.native_config / 'firstaid.cfg').read_text(encoding='utf-8')
assert medical.count('B:allowNaturalRegeneration=false') == 1
medical = medical.replace('B:allowNaturalRegeneration=false', 'B:allowNaturalRegeneration=true').replace('S:pos=TOP_LEFT', 'S:pos=TOP_RIGHT').replace('B:enableEasterEggs=true', 'B:enableEasterEggs=false')
medical = '\n'.join(line.rstrip() for line in medical.splitlines() if line.strip() and not line.lstrip().startswith('#')) + '\n'
(args.output / 'firstaid.cfg').write_text(medical, encoding='utf-8')
visuals = json.loads((args.native_config / 'enhancedvisuals-client.json').read_text(encoding='utf-8'))
handlers = visuals['handlers']
for handler in handlers.values():
    if 'blur' in handler:
        handler['blur']['disabled'] = True
handlers['explosion']['dust']['opacity'] = .22
handlers['explosion']['dustAmount']['maxValue'] = 6
handlers['explosion']['explosionSoundTime']['maxValue'] = 35
handlers['damage']['opacity'] = .35
handlers['heartbeat']['heartbeatVolume'] = .25
handlers['heartbeat']['lowhealth']['opacity'] = .25
(args.output / 'enhancedvisuals-client.json').write_text(json.dumps(visuals, indent=2) + '\n', encoding='utf-8')
handlers['explosion']['dust']['disabled'] = True
handlers['damage']['opacity'] = .2
handlers['heartbeat']['lowhealth']['opacity'] = .2
(args.output / 'enhancedvisuals-low.json').write_text(json.dumps(visuals, indent=2) + '\n', encoding='utf-8')
(args.output / 'enhancedvisuals.json').write_text(json.dumps({'messages': {'deathMessages': ['You were killed.']}}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.output.iterdir()) if p.is_file()}, indent=2))
