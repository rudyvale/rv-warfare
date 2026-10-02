import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--tag')
parser.add_argument('--remote', action='store_true')
args = parser.parse_args()
root = args.directory.resolve()
expected = {}
for line in (root / 'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
    digest, name = line.split('  ', 1)
    if name not in {'RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-World-Template.zip'} or name in expected:
        raise SystemExit('Unexpected checksum entry')
    expected[name] = digest
if not {'RV-Setup.zip', 'RV-Host-Tools.zip'}.issubset(expected):
    raise SystemExit('Incomplete checksum file')
for name, digest in expected.items():
    with (root / name).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest, name
    with zipfile.ZipFile(root / name) as archive:
        assert archive.testzip() is None, name
        names = archive.namelist()
        assert len(names) == len(set(n.casefold() for n in names)), name
        for entry in names:
            assert not entry.startswith(('/', '\\')) and ':' not in entry and '..' not in entry.replace('\\', '/').split('/'), entry
        if name == 'RV-World-Template.zip':
            forbidden = {'ops.json', 'whitelist.json', 'usercache.json', 'usernamecache.json', 'banned-players.json', 'banned-ips.json', 'logs', 'playerdata', 'stats', 'advancements'}
            for entry in names:
                assert not any(p.casefold() in forbidden for p in entry.replace('\\', '/').split('/')), entry
            continue
        path = 'RV-Setup/release.json' if name == 'RV-Setup.zip' else 'release.json'
        version = json.loads(archive.read(path).decode('utf-8-sig'))['version']
        if args.tag:
            assert 'v' + version == args.tag, (name, version, args.tag)
        if name == 'RV-Setup.zip':
            defaults = json.loads(archive.read('RV-Setup/server-defaults.json').decode('utf-8-sig'))
            assert defaults['connectionTarget'] == '', 'Public package contains a personal server target'
if args.remote:
    assert args.tag, '--remote requires --tag'
    url = 'https://api.github.com/repos/rudyvale/rv-warfare/releases/tags/' + args.tag
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'RV-release-verifier'})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    assert not release['draft'] and not release['prerelease'], 'Release is not public and stable'
    for name, digest in expected.items():
        assets = [a for a in release['assets'] if a['name'] == name]
        assert len(assets) == 1 and assets[0]['state'] == 'uploaded', name
        assert assets[0]['digest'] == 'sha256:' + digest, name
        assert assets[0]['size'] == (root / name).stat().st_size, name
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/rudyvale/rv-warfare/releases/latest', headers={'User-Agent': 'RV-release-verifier'}), timeout=30) as response:
        assert json.load(response)['tag_name'] == args.tag, 'Release is not latest'
print(json.dumps({'verified': sorted(expected), 'tag': args.tag, 'remote': args.remote}))
