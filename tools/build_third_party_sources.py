import argparse
import json
from pathlib import Path
from third_party_sources import build_bundle

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='Build the verified original vendor source and license release asset.')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--cache', type=Path, default=root / '.local/third-party-sources')
args = parser.parse_args()
print(json.dumps(build_bundle(root / 'pack/third-party-sources.json', root / 'pack/THIRD-PARTY-NOTICES.md', args.output, args.cache)))
