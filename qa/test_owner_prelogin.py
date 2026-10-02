import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import uuid


parser = argparse.ArgumentParser()
parser.add_argument('--java', type=Path, required=True)
parser.add_argument('--ecj', type=Path, required=True)
parser.add_argument('--rt', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
fixture = root / '.local/rv-1.1.0' / ('owner-prelogin-' + uuid.uuid4().hex)
classes = fixture / 'classes'
classes.mkdir(parents=True)
text = fixture / 'TextComponentString.java'
text.write_text('package net.minecraft.util.text; public class TextComponentString { public final String value; public TextComponentString(String value) { this.value=value; } }', encoding='utf-8')
source = root / 'patches/owner/WarfareOwnerAuth.java'
result = subprocess.run([str(args.java), '-jar', str(args.ecj), '-1.8', '-encoding', 'UTF-8', '-proc:none', '-nowarn', '-bootclasspath', str(args.rt), '-d', str(classes), str(source), str(text), str(root / 'qa/OwnerLoginAcceptance.java')], capture_output=True, timeout=30)
assert result.returncode == 0, result.stderr.decode(errors='replace')
result = subprocess.run([str(args.java), '-cp', str(classes), 'OwnerLoginAcceptance'], cwd=fixture, capture_output=True, timeout=40)
output = result.stdout.decode('utf-8', errors='replace')
print(output, end='')
assert result.returncode == 0, result.stderr.decode(errors='replace')
report = {'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'tests': 10, 'passed': True, 'realPowershell': True, 'minecraftRuntime': False, 'actualTCPChecker': False}
(fixture / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
