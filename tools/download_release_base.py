import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import zipfile
from release_contract import required_mods


REPOSITORY = 'rudyvale/rv-warfare'
REQUIRED = {'release.json', 'package-manifest.json', 'installer-files.json', 'payload.zip', 'runtime.zip', 'Install-Warfare.ps1', 'Play-Warfare.ps1', 'Warfare-Launcher.ps1', 'Warfare-Connection.ps1', 'Warfare-Updates.ps1', 'Check-WarfareUpdate.ps1', 'Configure-Controller.ps1', 'code.ico'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_entries(archive):
    names = set()
    size = 0
    for entry in archive.infolist():
        name = entry.filename.replace('\\', '/')
        parts = name.rstrip('/').split('/')
        if name.startswith('/') or ':' in name or any(part in ('', '.', '..') or part.endswith((' ', '.')) for part in parts):
            raise ValueError('Unsafe archive path')
        if name.casefold() in names:
            raise ValueError('Duplicate archive path')
        names.add(name.casefold())
        size += entry.file_size
    if size > 4294967296 or len(names) > 100000:
        raise ValueError('Archive exceeds extraction limits')
    if archive.testzip() is not None:
        raise ValueError('Archive CRC failed')


def download(tag, output):
    if not re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', tag):
        raise ValueError('A stable version tag is required')
    output = output.resolve()
    if output.exists():
        raise ValueError('Baseline output already exists; choose a new directory')
    request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + '/releases/tags/' + tag, headers={'User-Agent': 'RV-release-base', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    if release['draft'] or release['prerelease'] or release['tag_name'] != tag:
        raise ValueError('Baseline release is not public and stable')
    assets = [asset for asset in release['assets'] if asset['name'] == 'RV-Setup.zip']
    if len(assets) != 1:
        raise ValueError('Baseline package is missing or duplicated')
    asset = assets[0]
    url = 'https://github.com/' + REPOSITORY + '/releases/download/' + tag + '/RV-Setup.zip'
    if asset['browser_download_url'] != url or asset['state'] != 'uploaded' or not re.fullmatch(r'sha256:[0-9a-f]{64}', asset.get('digest', '')):
        raise ValueError('Baseline asset origin or checksum is invalid')
    if not 0 < asset['size'] <= 2147483648:
        raise ValueError('Baseline asset size is invalid')
    output.mkdir(parents=True)
    archive_path = output / 'RV-Setup.zip'
    started = time.monotonic()
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'RV-release-base'}), timeout=30) as response, archive_path.open('xb') as stream:
        origin = urllib.parse.urlsplit(response.url)
        if origin.scheme != 'https' or origin.hostname not in {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}:
            raise ValueError('Unexpected baseline download redirect')
        received = 0
        while data := response.read(1024 * 1024):
            received += len(data)
            if received > asset['size'] or time.monotonic() - started > 600:
                raise ValueError('Baseline download exceeds its limit')
            stream.write(data)
    if received != asset['size'] or digest(archive_path) != asset['digest'][7:]:
        raise ValueError('Baseline download checksum or size mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        safe_entries(archive)
        if any(not name.startswith('RV-Setup/') for name in archive.namelist()):
            raise ValueError('Unexpected baseline package root')
        metadata = json.loads(archive.read('RV-Setup/release.json').decode('utf-8-sig'))
        if metadata.get('version') != tag[1:] or metadata.get('repository') != REPOSITORY:
            raise ValueError('Baseline release metadata mismatch')
        required_mods(metadata)
        required = set(REQUIRED)
        if tuple(map(int, tag[1:].split('.'))) >= (1, 1, 0):
            required.update({'Warfare-Performance.ps1', 'Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1', 'THIRD-PARTY-NOTICES.md'})
        if any('RV-Setup/' + name not in archive.namelist() for name in required):
            raise ValueError('Baseline package is incomplete')
        archive.extractall(output)
    package = output / 'RV-Setup'
    manifest = json.loads((package / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    if manifest['version'] != tag[1:] or len(manifest['archives']) != 2 or {entry['path'] for entry in manifest['archives']} != {'payload.zip', 'runtime.zip'}:
        raise ValueError('Baseline manifest mismatch')
    for item in manifest['archives']:
        path = package / item['path']
        if digest(path) != item['sha256']:
            raise ValueError('Baseline nested archive checksum mismatch')
        with zipfile.ZipFile(path) as archive:
            safe_entries(archive)
            if item['path'] == 'payload.zip':
                managed = set()
                for entry in manifest['managedFiles']:
                    name = entry['path'].replace('\\', '/')
                    if name.casefold() in managed or name not in archive.namelist() or hashlib.sha256(archive.read(name)).hexdigest() != entry['sha256']:
                        raise ValueError('Baseline managed file checksum mismatch')
                    managed.add(name.casefold())
    report = {'passed': True, 'tag': tag, 'repository': REPOSITORY, 'releaseUrl': release['html_url'], 'assetSha256': asset['digest'][7:], 'assetBytes': received, 'packageRoot': str(package), 'managedFiles': len(manifest['managedFiles']), 'manifestSha256': digest(package / 'package-manifest.json'), 'archives': manifest['archives']}
    (output / 'baseline-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download and validate an immutable public RV binary baseline into a new directory.')
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(download(args.tag, args.output), indent=2))
