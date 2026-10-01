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
    if name not in {'VM-Setup.zip', 'VM-Host-Tools.zip'} or name in expected:
        raise SystemExit('Unexpected checksum entry')
    expected[name] = digest
if set(expected) != {'VM-Setup.zip', 'VM-Host-Tools.zip'}:
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
        path = 'VM-Setup/release.json' if name == 'VM-Setup.zip' else 'release.json'
        version = json.loads(archive.read(path).decode('utf-8-sig'))['version']
        if args.tag:
            assert 'v' + version == args.tag, (name, version, args.tag)
        if name == 'VM-Setup.zip':
            defaults = json.loads(archive.read('VM-Setup/server-defaults.json').decode('utf-8-sig'))
            assert defaults['connectionTarget'] == '', 'Public package contains a personal server target'
if args.remote:
    assert args.tag, '--remote requires --tag'
    url = 'https://api.github.com/repos/rudyvale/vm-warfare/releases/tags/' + args.tag
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'VM-release-verifier'})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    assert not release['draft'] and not release['prerelease'], 'Release is not public and stable'
    for name, digest in expected.items():
        assets = [a for a in release['assets'] if a['name'] == name]
        assert len(assets) == 1 and assets[0]['state'] == 'uploaded', name
        assert assets[0]['digest'] == 'sha256:' + digest, name
        assert assets[0]['size'] == (root / name).stat().st_size, name
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/rudyvale/vm-warfare/releases/latest', headers={'User-Agent': 'VM-release-verifier'}), timeout=30) as response:
        assert json.load(response)['tag_name'] == args.tag, 'Release is not latest'
print(json.dumps({'verified': sorted(expected), 'tag': args.tag, 'remote': args.remote}))
