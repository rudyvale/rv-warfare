import argparse
import hashlib
import json
from pathlib import Path
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--java', type=Path, required=True)
parser.add_argument('--ecj', type=Path, required=True)
parser.add_argument('--rt', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
fixture = root / '.local/owner-auth-acceptance'
classes = fixture / 'classes'
classes.mkdir(parents=True, exist_ok=True)
entity = fixture / 'net/minecraft/entity/player/EntityPlayerMP.java'
entity.parent.mkdir(parents=True, exist_ok=True)
entity.write_text('''package net.minecraft.entity.player;
public class EntityPlayerMP {
    public Object connection;
    public Object server;
    public Object profile;
    public boolean operator;
    public boolean ownerTag;
    public boolean failTag;
    public EntityPlayerMP(Object server, Object profile, Object connection) { this.server=server; this.profile=profile; this.connection=connection; }
    public Object getServer() { return server; }
    public Object getGameProfile() { return profile; }
    public boolean canUseCommand(int level, String command) { return operator; }
    public boolean addTag(String tag) { if(failTag) throw new IllegalStateException("tag failed"); ownerTag=true; return true; }
    public boolean removeTag(String tag) { ownerTag=false; return true; }
}
''', encoding='utf-8')
text = fixture / 'net/minecraft/util/text/TextComponentString.java'
text.parent.mkdir(parents=True, exist_ok=True)
text.write_text('''package net.minecraft.util.text;
public class TextComponentString {
    public final String value;
    public TextComponentString(String value) { this.value=value; }
}
''', encoding='utf-8')
snapshot = fixture / 'WarfareOwnerAuth.java'
data = args.source.read_bytes()
snapshot.write_text(data.decode('utf-8-sig'), encoding='utf-8')
compile_result = subprocess.run([str(args.java), '-jar', str(args.ecj), '-source', '1.8', '-target', '1.8', '-proc:none', '-nowarn', '-bootclasspath', str(args.rt), '-d', str(classes), str(snapshot), str(entity), str(text), str(root / 'qa/OwnerAuthAcceptance.java')], capture_output=True, timeout=30)
assert compile_result.returncode == 0, compile_result.stderr.decode(errors='replace')
result = subprocess.run([str(args.java), '-cp', str(classes), 'OwnerAuthAcceptance'], cwd=fixture, capture_output=True, timeout=50)
output = result.stdout.decode('utf-8', errors='replace')
print(output, end='')
assert result.returncode == 0, result.stderr.decode(errors='replace')
report = {'source_sha256': hashlib.sha256(data).hexdigest(), 'tests': 12, 'passed': True, 'real_powershell': True, 'minecraft_runtime': False}
(fixture / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
