import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
from download_release_base import safe_entries
from release_contract import checksums, client_source_names, load_addon_map, managed_hashes, managed_policies, require_source_asset, required_mods, retirement_policy, validate_addon_resources
from third_party_sources import load_registry, verify_bundle, verify_vendor_manifest, verify_vendor_payload


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_sources(archive, tracked_root, client):
    prefix = 'RV-Setup/' if client else ''
    metadata = json.loads((tracked_root / 'src/release.json').read_text(encoding='utf-8-sig'))
    if client:
        sources = {name: tracked_root / 'src' / name for name in client_source_names(metadata['version'])}
        sources['READ-ME.md'] = tracked_root / 'pack/READ-ME.md'
        sources['server-defaults.json'] = tracked_root / 'pack/server-defaults.json'
    else:
        sources = {name: tracked_root / 'host' / name for name in ('README.md', 'warfare-launcher.py', 'play-owner.py', 'owner-panel.py', 'world_reset.py', 'host_runtime.py', 'porthole-status.py', 'run-server.py', 'launch-warfare.py', 'launcher-texts.json', 'Join-Server.ps1', 'Launch-Warfare.ps1', 'Start-All.ps1', 'Start-Server.ps1', 'Start-Porthole.ps1', 'Porthole-Host.ps1', 'Get-ClientMemory.ps1', 'Stop-All.ps1', 'Stop-Server.ps1', 'Check-OwnerConnection.ps1')}
        sources.update({name: tracked_root / 'src' / name for name in ('Check-WarfareUpdate.ps1', 'Warfare-Updates.ps1', 'Warfare-Connection.ps1', 'Warfare-Performance.ps1', 'Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1', 'Configure-Controller.ps1', 'release.json')})
    sources['THIRD-PARTY-NOTICES.md'] = tracked_root / 'pack/THIRD-PARTY-NOTICES.md'
    if tuple(map(int, metadata['version'].split('.'))) >= (1, 2, 0):
        sources['vendor-catalog.json'] = tracked_root / 'pack/vendor-catalog.json'
        sources['Warfare-VendorDownloads.ps1'] = tracked_root / 'src/Warfare-VendorDownloads.ps1'
        if metadata.get('managedModsSha256'):
            sources['rv-managed-mods.json'] = tracked_root / 'pack/rv-managed-mods.json'
        if client:
            for name in ('Warfare-Ambience.ps1', 'Warfare-ClientMods.ps1'):
                sources[name] = tracked_root / 'src' / name
        else:
            for name in ('server_vendors.py', 'Install-ServerVendors.ps1', 'Warfare-VendorDownloads.ps1'):
                sources[name] = tracked_root / 'host' / name
            require((tracked_root / 'host/Warfare-VendorDownloads.ps1').read_bytes() == (tracked_root / 'src/Warfare-VendorDownloads.ps1').read_bytes(), 'Host and client vendor download helper sources differ')
    for name, source in sources.items():
        require(prefix + name in archive.namelist(), 'Missing packaged source: ' + name)
        data = archive.read(prefix + name).decode('utf-8-sig').replace('\r\n', '\n')
        require(data == source.read_text(encoding='utf-8-sig'), 'Packaged source differs from the frozen checkout: ' + name)
    require(archive.read(prefix + 'code.ico') == (tracked_root / 'assets/code.ico').read_bytes(), 'Packaged icon differs from source')
    allowed = set(sources) | {'code.ico'}
    if client:
        allowed |= {'package-manifest.json', 'installer-files.json', 'payload.zip', 'runtime.zip', 'INSTALL.cmd', '\u0423\u0421\u0422\u0410\u041d\u041e\u0412\u0418\u0422\u042c.cmd', 'Play.cmd'}
    else:
        allowed.add('rv-addon-assets.json')
        if metadata.get('managedModsSha256'):
            owned = json.loads((tracked_root / 'pack/rv-managed-mods.json').read_text(encoding='utf-8'))
            allowed.update('host-owned/' + entry['path'] for entry in owned['mods'])
    require(set(archive.namelist()) == {prefix + name for name in allowed}, 'Unexpected files in release source archive')


def verify_host_map(archive, source):
    require(archive.read('rv-addon-assets.json') == Path(source).read_bytes(), 'Host addon resource map differs from the frozen source')


def verify(directory, tag=None, remote=False):
    root = Path(directory).resolve()
    expected = checksums(root)
    tracked_root = Path(__file__).resolve().parents[1]
    tracked = json.loads((tracked_root / 'pack/package-manifest.json').read_text(encoding='utf-8-sig'))
    source_metadata = json.loads((tracked_root / 'src/release.json').read_text(encoding='utf-8-sig'))
    vendor_catalog = None
    first_party = None
    for name, digest in expected.items():
        with (root / name).open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == digest, 'Asset checksum mismatch: ' + name)
        with zipfile.ZipFile(root / name) as archive:
            safe_entries(archive)
            if name == 'RV-World-Template.zip':
                forbidden = {'ops.json', 'whitelist.json', 'usercache.json', 'usernamecache.json', 'banned-players.json', 'banned-ips.json', 'logs', 'playerdata', 'stats', 'advancements'}
                for entry in archive.namelist():
                    require(not any(part.casefold() in forbidden for part in entry.replace('\\', '/').split('/')), 'Private world entry: ' + entry)
    if tuple(map(int, source_metadata['version'].split('.'))) >= (1, 2, 0):
        from vendor_catalog import first_party_proof_path, load_catalog, sha256_file, validate_release_catalog, verify_first_party_proof, verify_managed_delivery
        catalog_path = tracked_root / 'pack/vendor-catalog.json'
        vendor_catalog = load_catalog(catalog_path)
        with zipfile.ZipFile(root / 'RV-Setup.zip') as setup:
            with zipfile.ZipFile(io.BytesIO(setup.read('RV-Setup/payload.zip'))) as payload:
                first_party = verify_first_party_proof(first_party_proof_path(source_metadata, tracked_root), vendor_catalog, tracked, payload, tracked_root)
        validate_release_catalog(vendor_catalog, source_metadata, sha256_file(catalog_path), first_party)
    for name, digest in expected.items():
        with zipfile.ZipFile(root / name) as archive:
            safe_entries(archive)
            names = archive.namelist()
            if name == 'RV-World-Template.zip':
                forbidden = {'ops.json', 'whitelist.json', 'usercache.json', 'usernamecache.json', 'banned-players.json', 'banned-ips.json', 'logs', 'playerdata', 'stats', 'advancements'}
                for entry in names:
                    require(not any(part.casefold() in forbidden for part in entry.replace('\\', '/').split('/')), 'Private world entry: ' + entry)
                continue
            if name == 'RV-Third-Party-Sources.zip':
                verify_bundle(root / name, tracked_root / 'pack/third-party-sources.json', tracked_root / 'pack/THIRD-PARTY-NOTICES.md')
                continue
            path = 'RV-Setup/release.json' if name == 'RV-Setup.zip' else 'release.json'
            metadata = json.loads(archive.read(path).decode('utf-8-sig'))
            version = metadata['version']
            required_mods(metadata)
            if vendor_catalog is not None:
                require(len(archive.read(path)) <= 4096, 'Packaged metadata exceeds the immutable older updater limit')
                prefix = 'RV-Setup/' if name == 'RV-Setup.zip' else ''
                require(archive.read(prefix + 'vendor-catalog.json') == catalog_path.read_bytes(), 'Packaged vendor catalog differs from the frozen source bytes')
                if source_metadata.get('managedModsSha256'):
                    require(archive.read(prefix + 'rv-managed-mods.json') == (tracked_root / 'pack/rv-managed-mods.json').read_bytes(), 'Packaged RV managed mod proof differs from the frozen source bytes')
                validate_release_catalog(vendor_catalog, metadata, sha256_file(catalog_path), first_party)
            require(metadata['repository'] == 'rudyvale/rv-warfare', 'Wrong package repository')
            if tag:
                require('v' + version == tag, 'Archive version differs from release tag: ' + name)
            if tuple(map(int, version.split('.'))) >= (1, 1, 0):
                require_source_asset(expected, version)
                verify_sources(archive, tracked_root, name == 'RV-Setup.zip')
                if name == 'RV-Host-Tools.zip':
                    verify_host_map(archive, tracked_root / 'pack/rv-addon-assets.json')
                    if metadata.get('managedModsSha256'):
                        owned = json.loads((tracked_root / 'pack/rv-managed-mods.json').read_text(encoding='utf-8'))
                        for entry in owned['mods']:
                            data = archive.read('host-owned/' + entry['path'])
                            require(len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'], 'Host owned mod differs from its frozen source/native proof: ' + entry['path'])
            if name == 'RV-Setup.zip':
                manifest = json.loads(archive.read('RV-Setup/package-manifest.json').decode('utf-8-sig'))
                require(managed_hashes(manifest) == managed_hashes(tracked), 'Package gameplay differs from tracked manifest')
                require(managed_policies(manifest) == managed_policies(tracked), 'Package preservation policy differs from tracked manifest')
                require(retirement_policy(manifest) == retirement_policy(tracked), 'Package mod retirement or OptiFine policy differs from tracked manifest')
                source_registry = None
                if tuple(map(int, version.split('.'))) >= (1, 1, 0):
                    source_registry = load_registry(tracked_root / 'pack/third-party-sources.json')
                    verify_vendor_manifest(manifest, source_registry)
                require(manifest['version'] == version, 'Package manifest version differs')
                require(len(manifest['archives']) == 2 and {item['path'] for item in manifest['archives']} == {'payload.zip', 'runtime.zip'}, 'Unexpected binary archives')
                if tuple(map(int, version.split('.'))) >= (1, 1, 0):
                    require('RV-Setup/Warfare-Performance.ps1' in names, 'Missing performance helper')
                for binary in manifest['archives']:
                    data = archive.read('RV-Setup/' + binary['path'])
                    require(hashlib.sha256(data).hexdigest() == binary['sha256'], 'Nested archive checksum mismatch: ' + binary['path'])
                    if binary['path'] == 'payload.zip':
                        with zipfile.ZipFile(io.BytesIO(data)) as payload:
                            safe_entries(payload)
                            if vendor_catalog is not None:
                                verify_managed_delivery(vendor_catalog, manifest, payload, 'client')
                            else:
                                for item in manifest['managedFiles']:
                                    require(hashlib.sha256(payload.read(item['path'])).hexdigest() == item['sha256'], 'Managed file checksum mismatch: ' + item['path'])
                            if tuple(map(int, version.split('.'))) >= (1, 1, 0):
                                verify_vendor_payload(payload, source_registry)
                                require(payload.read('THIRD-PARTY-NOTICES.md') == (tracked_root / 'pack/THIRD-PARTY-NOTICES.md').read_bytes(), 'Installed third-party notices differ from the frozen source')
                                mod_data = payload.read('mods/mcheli-ce-1.5.1-rv.jar')
                                resource_map = load_addon_map(tracked_root / 'pack/rv-addon-assets.json', hashlib.sha256(mod_data).hexdigest())
                                with zipfile.ZipFile(io.BytesIO(mod_data)) as builtin:
                                    validate_addon_resources(manifest, payload, builtin, resource_map)
                    else:
                        expected_runtime = next(item['sha256'] for item in tracked['archives'] if item['path'] == 'runtime.zip')
                        require(binary['sha256'] == expected_runtime, 'Runtime differs from tracked manifest')
                defaults = json.loads(archive.read('RV-Setup/server-defaults.json').decode('utf-8-sig'))
                require(defaults['connectionTarget'] == '', 'Public package contains a personal server target')
    if vendor_catalog is not None:
        from audit_public_archives import audit_archives
        audit = audit_archives([root / name for name in expected], vendor_catalog)
        require(audit.get('passed') is True, 'RV 1.2.0 nested vendor archive audit failed')
    if remote:
        require(tag, '--remote requires --tag')
        url = 'https://api.github.com/repos/rudyvale/rv-warfare/releases/tags/' + tag
        request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'RV-release-verifier'})
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
        require(not release['draft'] and not release['prerelease'] and release['tag_name'] == tag, 'Release is not public and stable at the expected tag')
        require({asset['name'] for asset in release['assets']} == set(expected) | {'SHA256SUMS.txt'} and len(release['assets']) == len(expected) + 1, 'Unexpected release assets')
        checksum_asset = next(asset for asset in release['assets'] if asset['name'] == 'SHA256SUMS.txt')
        checksum_file = root / 'SHA256SUMS.txt'
        require(checksum_asset['digest'] == 'sha256:' + hashlib.sha256(checksum_file.read_bytes()).hexdigest() and checksum_asset['size'] == checksum_file.stat().st_size and checksum_asset['state'] == 'uploaded', 'Checksum file mismatch')
        for name, digest in expected.items():
            assets = [asset for asset in release['assets'] if asset['name'] == name]
            require(len(assets) == 1 and assets[0]['state'] == 'uploaded', 'Release asset is not uploaded: ' + name)
            require(assets[0]['digest'] == 'sha256:' + digest and assets[0]['size'] == (root / name).stat().st_size, 'Remote asset checksum or size mismatch: ' + name)
        with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/rudyvale/rv-warfare/releases/latest', headers={'User-Agent': 'RV-release-verifier'}), timeout=30) as response:
            require(json.load(response)['tag_name'] == tag, 'Release is not latest')
    return {'verified': sorted(expected), 'tag': tag, 'remote': remote}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--tag')
    parser.add_argument('--remote', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.tag, args.remote)))
