import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from release_contract import asset_hashes, mark_published, validate_candidate


class GitHubAPI:
    def __init__(self, token):
        self.token = token

    def __call__(self, method, path, data=None, content_type='application/json', allow_missing=False):
        url = path if path.startswith('https://') else 'https://api.github.com' + path
        if urllib.parse.urlsplit(url).hostname not in {'api.github.com', 'uploads.github.com'}:
            raise ValueError('Unexpected API host')
        body = json.dumps(data, ensure_ascii=False).encode('utf-8') if isinstance(data, dict) else data
        request = urllib.request.Request(url, data=body, method=method, headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'RV-release-tools', 'Content-Type': content_type, 'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with urllib.request.urlopen(request, timeout=240 if isinstance(data, bytes) else 25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            if allow_missing and method == 'GET' and error.code == 404:
                return None
            raise RuntimeError('GitHub API returned HTTP ' + str(error.code)) from None


def release_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Invalid release ID')
    return value


def validate_release(release, metadata, assets, known_id=None, allow_alias=False, complete=False, exact=False):
    if not isinstance(release, dict):
        raise ValueError('Invalid release response')
    identifier = release_id(release.get('id'))
    if known_id is not None and identifier != known_id:
        raise ValueError('Release ID changed')
    if type(release.get('draft')) is not bool or type(release.get('prerelease')) is not bool:
        raise ValueError('Invalid release publication status')
    if release['prerelease'] != metadata['prerelease']:
        raise ValueError('Existing release preview status differs from the requested publication mode')
    if release.get('target_commitish') != metadata['target_commitish']:
        raise ValueError('Existing release target differs from the verified source commit')
    alias = allow_alias and release['draft'] and re.fullmatch(r'untagged-[a-zA-Z0-9-]+', str(release.get('tag_name', '')))
    if release.get('tag_name') != metadata['tag_name'] and not alias:
        raise ValueError('Existing release tag differs from the expected version')
    if release.get('name') != metadata['name']:
        raise ValueError('Existing release name differs from the expected version')
    if exact and any(release.get(key) != metadata[key] for key in ('tag_name', 'target_commitish', 'name', 'body', 'draft', 'prerelease')):
        raise ValueError('Release metadata differs after the explicit update')
    entries = release.get('assets')
    if not isinstance(entries, list):
        raise ValueError('Invalid release asset list')
    names = set()
    for asset in entries:
        if not isinstance(asset, dict) or asset.get('name') not in assets:
            raise ValueError('Release contains unexpected assets')
        name = asset['name']
        if name in names:
            raise ValueError('Duplicate release asset: ' + name)
        names.add(name)
        if asset.get('digest') != assets[name]['digest'] or type(asset.get('size')) is not int or asset['size'] != assets[name]['size'] or asset.get('state') != 'uploaded':
            raise ValueError('Release checksum mismatch: ' + name)
    if (complete or not release['draft']) and names != set(assets):
        raise ValueError('Published release is incomplete; create a new version')
    return identifier


def find_release(api, prefix, metadata, assets, known_id=None):
    repository = api('GET', prefix)
    if not isinstance(repository, dict) or repository.get('permissions', {}).get('push') is not True:
        raise ValueError('Push access is required to discover existing draft releases')
    tagged = api('GET', prefix + '/releases/tags/' + metadata['tag_name'], allow_missing=True)
    if tagged is not None:
        validate_release(tagged, metadata, assets, known_id)
    releases = {}
    for page in range(1, 101):
        batch = api('GET', prefix + '/releases?per_page=100&page=' + str(page))
        if not isinstance(batch, list):
            raise ValueError('Invalid release listing')
        for release in batch:
            if not isinstance(release, dict):
                raise ValueError('Invalid release listing entry')
            identifier = release_id(release.get('id'))
            if identifier in releases:
                raise ValueError('Release listing changed during discovery; retry read-only discovery')
            releases[identifier] = release
        if len(batch) < 100:
            break
    else:
        raise ValueError('Release listing is incomplete')
    if tagged is not None:
        releases[release_id(tagged.get('id'))] = tagged
    known = api('GET', prefix + '/releases/' + str(known_id)) if known_id is not None else None
    if known is not None:
        if release_id(known.get('id')) != known_id:
            raise ValueError('Release ID changed')
        releases[known_id] = known
    matches = [release for release in releases.values() if release.get('tag_name') == metadata['tag_name'] or release.get('name') == metadata['name'] or release['id'] == known_id]
    if len(matches) > 1:
        raise ValueError('Multiple releases match the candidate; review the draft IDs')
    if not matches:
        if known_id is not None:
            raise ValueError('Known release is missing; refusing to create another draft')
        return None
    release = known if known is not None else api('GET', prefix + '/releases/' + str(matches[0]['id']))
    allow_alias = release.get('id') == known_id or release.get('body') == metadata['body']
    validate_release(release, metadata, assets, matches[0]['id'], allow_alias=allow_alias)
    return release


def save_upload_state(path, identity, identifier=None, create=False):
    state = {**identity, 'schema': 1, 'releaseId': identifier}
    if create:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(state, indent=2) + '\n')
        return
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def publish_candidate(api, repository, version, commit, directory, notes, publish=False, prerelease=False, known_id=None):
    directory = Path(directory)
    candidate = validate_candidate(directory, version)
    hashes = asset_hashes(directory)
    assets = {name: {'digest': 'sha256:' + digest, 'size': (directory / name).stat().st_size} for name, digest in hashes.items()}
    metadata = {'tag_name': 'v' + version, 'target_commitish': commit, 'name': 'RV Warfare ' + version + (' Preview' if prerelease else ''), 'body': notes, 'draft': True, 'prerelease': prerelease, 'make_latest': 'false'}
    identity = {'repository': repository, 'tag': metadata['tag_name'], 'commit': commit, 'prerelease': prerelease, 'assets': hashes}
    state_path = directory / '.release-upload.json'
    if known_id is not None:
        release_id(known_id)
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('schema') != 1 or any(state.get(key) != value for key, value in identity.items()):
            raise ValueError('Upload receipt belongs to another candidate')
        saved_id = state.get('releaseId')
        if saved_id is not None:
            release_id(saved_id)
            if known_id is not None and known_id != saved_id:
                raise ValueError('Requested release ID differs from the upload receipt')
            known_id = saved_id
    prefix = '/repos/' + repository
    release = find_release(api, prefix, metadata, assets, known_id)
    if candidate is not None and candidate['state'] == 'published':
        if candidate.get('sourceCommit') != commit or release is None or release['draft']:
            raise ValueError('Published candidate state differs from the remote release')
    if release is None:
        if state_path.exists():
            raise ValueError('Previous publication outcome is uncertain; refusing to create another draft')
        save_upload_state(state_path, identity, create=True)
        release = api('POST', prefix + '/releases', metadata)
        identifier = release_id(release.get('id'))
        save_upload_state(state_path, identity, identifier)
        validate_release(release, metadata, assets, identifier, exact=True)
    identifier = release_id(release.get('id'))
    save_upload_state(state_path, identity, identifier)
    path = prefix + '/releases/' + str(identifier)
    if release['draft']:
        release = api('PATCH', path, metadata)
        validate_release(release, metadata, assets, identifier, exact=True)
        release = api('GET', path)
        validate_release(release, metadata, assets, identifier, exact=True)
        upload_url = 'https://uploads.github.com' + path + '/assets'
        if release.get('upload_url', '').split('{', 1)[0] != upload_url:
            raise ValueError('Unexpected release upload URL')
        present = {asset['name'] for asset in release['assets']}
        for name, expected in assets.items():
            data = (directory / name).read_bytes()
            if 'sha256:' + hashlib.sha256(data).hexdigest() != expected['digest'] or len(data) != expected['size']:
                raise ValueError('Candidate changed during publication: ' + name)
            if name not in present:
                asset = api('POST', upload_url + '?name=' + urllib.parse.quote(name), data, 'application/zip' if name.endswith('.zip') else 'text/plain')
                validate_release({**release, 'assets': [asset]}, metadata, assets, identifier, exact=True)
            print('Verified uploaded asset:', name, flush=True)
        release = api('GET', path)
        validate_release(release, metadata, assets, identifier, complete=True, exact=True)
        validate_candidate(directory, version)
        if publish:
            final = {**metadata, 'draft': False, 'make_latest': 'false' if prerelease else 'true'}
            release = api('PATCH', path, final)
            validate_release(release, final, assets, identifier, complete=True, exact=True)
            release = api('GET', path)
            validate_release(release, final, assets, identifier, complete=True, exact=True)
    else:
        validate_release(release, {**metadata, 'draft': False}, assets, identifier, complete=True, exact=True)
        validate_candidate(directory, version)
    if not release['draft']:
        tagged = api('GET', prefix + '/releases/tags/' + metadata['tag_name'])
        validate_release(tagged, {**metadata, 'draft': False}, assets, identifier, complete=True, exact=True)
    return release


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=root / 'dist')
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--prerelease', action='store_true')
    parser.add_argument('--release-id', type=int)
    args = parser.parse_args()
    metadata = json.loads((root / 'src/release.json').read_text())
    repository = metadata['repository']
    if repository != 'rudyvale/rv-warfare':
        raise SystemExit('Unexpected repository')
    tag = 'v' + metadata['version']
    directory = args.directory.resolve()
    validate_candidate(directory, metadata['version'])
    subprocess.run([sys.executable, str(root / 'tools/verify_release.py'), '--directory', str(directory), '--tag', tag], check=True)
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
    release = publish_candidate(GitHubAPI(token), repository, metadata['version'], commit, directory, args.notes.read_text(encoding='utf-8'), args.publish, args.prerelease, args.release_id)
    if not release['draft']:
        subprocess.run([sys.executable, str(root / 'tools/verify_release.py'), '--directory', str(directory), '--tag', tag, '--remote'] + (['--prerelease'] if args.prerelease else []), check=True)
        mark_published(directory, metadata['version'], commit, release['html_url'])
    print(json.dumps({'url': release['html_url'], 'tag': tag, 'draft': release['draft'], 'prerelease': release['prerelease']}))


if __name__ == '__main__':
    main()
