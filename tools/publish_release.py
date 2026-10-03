import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from release_contract import mark_published, validate_candidate

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, default=root / 'dist')
parser.add_argument('--notes', type=Path, required=True)
parser.add_argument('--publish', action='store_true')
parser.add_argument('--prerelease', action='store_true')
args = parser.parse_args()
metadata = json.loads((root / 'src/release.json').read_text())
repository = metadata['repository']
if repository != 'rudyvale/rv-warfare':
    raise SystemExit('Unexpected repository')
tag = 'v' + metadata['version']
directory = args.directory.resolve()
candidate = validate_candidate(directory, metadata['version'])
subprocess.run(['python', str(root / 'tools/verify_release.py'), '--directory', str(directory), '--tag', tag], check=True)
commit = subprocess.check_output(['git', 'rev-parse', tag + '^{commit}'], cwd=root, text=True).strip()
if subprocess.run(['git', 'diff', '--quiet', tag, '--'], cwd=root).returncode:
    raise SystemExit('Working sources differ from the release tag. Commit and verify the complete candidate first.')
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=root, text=True).strip()
if untracked:
    raise SystemExit('Untracked source files remain. Commit intended sources and keep temporary release notes under .local.')
remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/tags/' + tag, 'refs/tags/' + tag + '^{}'], cwd=root, text=True)
if commit not in [line.split()[0] for line in remote.splitlines()]:
    raise SystemExit('Push the release tag before publishing')
token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
if not token:
    result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n', capture_output=True, text=True, timeout=25, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'})
    token = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line).get('password')
if not token:
    raise SystemExit('Authenticate Git for github.com or set GH_TOKEN')

def api(method, path, data=None, content_type='application/json', allow_missing=False):
    url = path if path.startswith('https://') else 'https://api.github.com' + path
    if urllib.parse.urlsplit(url).hostname not in {'api.github.com', 'uploads.github.com'}:
        raise ValueError('Unexpected API host')
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if isinstance(data, dict) else data
    request = urllib.request.Request(url, data=body, method=method, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'RV-release-tools', 'Content-Type': content_type, 'X-GitHub-Api-Version': '2022-11-28'})
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if allow_missing and error.code == 404:
            return None
        raise RuntimeError('GitHub API returned HTTP ' + str(error.code)) from None

prefix = '/repos/' + repository
release = api('GET', prefix + '/releases/tags/' + tag, allow_missing=True)
if release is None:
    release = api('POST', prefix + '/releases', {'tag_name': tag, 'target_commitish': commit, 'name': 'RV Warfare ' + metadata['version'] + (' Preview' if args.prerelease else ''), 'body': args.notes.read_text(encoding='utf-8'), 'draft': True, 'prerelease': args.prerelease, 'make_latest': 'false'})
if release['prerelease'] != args.prerelease:
    raise SystemExit('Existing release preview status differs from the requested publication mode')
assets = [line.split('  ', 1)[1] for line in (directory / 'SHA256SUMS.txt').read_text().splitlines()] + ['SHA256SUMS.txt']
if any(asset['name'] not in assets for asset in release['assets']):
    raise SystemExit('Draft contains unexpected assets; review it before publishing')
for name in assets:
    file = directory / name
    data = file.read_bytes()
    digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    if candidate is not None and digest[7:] != candidate['assets'].get(name):
        raise SystemExit('Candidate changed during publication: ' + name)
    matches = [asset for asset in release['assets'] if asset['name'] == name]
    if len(matches) > 1:
        raise SystemExit('Duplicate release asset: ' + name)
    if matches:
        asset = matches[0]
    else:
        if not release['draft']:
            raise SystemExit('Published release is incomplete; create a new version')
        upload = release['upload_url'].split('{', 1)[0] + '?name=' + urllib.parse.quote(name)
        asset = api('POST', upload, data, 'application/zip' if name.endswith('.zip') else 'text/plain')
    if asset.get('digest') != digest or asset['size'] != len(data) or asset['state'] != 'uploaded':
        raise SystemExit('Release checksum mismatch: ' + name)
    print('Verified uploaded asset:', name, flush=True)
release = api('GET', prefix + '/releases/' + str(release['id']))
validate_candidate(directory, metadata['version'])
if len(release['assets']) != len(assets) or {asset['name'] for asset in release['assets']} != set(assets):
    raise SystemExit('Release asset list differs from verified local files')
if args.publish and release['draft']:
    release = api('PATCH', prefix + '/releases/' + str(release['id']), {'draft': False, 'prerelease': args.prerelease, 'make_latest': 'false' if args.prerelease else 'true'})
if not release['draft']:
    subprocess.run(['python', str(root / 'tools/verify_release.py'), '--directory', str(directory), '--tag', tag, '--remote'] + (['--prerelease'] if args.prerelease else []), check=True)
    mark_published(directory, metadata['version'], commit, release['html_url'])
print(json.dumps({'url': release['html_url'], 'tag': tag, 'draft': release['draft'], 'prerelease': release['prerelease']}))
