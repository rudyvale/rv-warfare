import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.parse
import zipfile


DOWNLOAD_HOSTS = frozenset({'www.curseforge.com', 'curseforge.com', 'edge.forgecdn.net', 'media.forgecdn.net', 'mediafilez.forgecdn.net', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'cdn.modrinth.com'})
EVIDENCE_HOSTS = DOWNLOAD_HOSTS | {'raw.githubusercontent.com', 'api.github.com', 'modrinth.com', 'www.modrinth.com', 'api.modrinth.com', 'modularmods.net', 'www.modularmods.net'}
SIDES = {'client', 'server', 'both'}
BASE_COMMIT = '31f3f234ccb39688357e145debd3e38a242e06fd'
BASE_SETUP_SHA256 = '200ba57416c60deeccb8bb592d56c6ca3df4567fcc845b9f15f54127c7d71e12'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(value):
    require(isinstance(value, str) and bool(value) and '\\' not in value and not value.startswith('/'), 'Unsafe vendor path')
    parts = value.split('/')
    for part in parts:
        require(part not in ('', '.', '..') and not re.search(r'[<>:"|?*\x00-\x1f]', part) and not part.endswith((' ', '.')), 'Unsafe vendor path')
        require(not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', part.split('.')[0], re.I), 'Reserved Windows vendor path')
    return value


def safe_url(value, hosts=DOWNLOAD_HOSTS):
    require(isinstance(value, str), 'Invalid official URL')
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme == 'https' and parsed.hostname in hosts and parsed.port in (None, 443) and not parsed.username and not parsed.password and not parsed.fragment, 'Unapproved official URL origin')
    require(not any(ord(c) < 32 for c in value), 'Invalid official URL characters')
    return value


def has_side(entry, side):
    return entry['side'] in (side, 'both')


def validate_catalog(catalog, allow_draft=False):
    require(catalog.get('schema') == 1 and catalog.get('minecraft') == '1.12.2' and catalog.get('loader') == 'forge' and catalog.get('javaMajor') == 8, 'Catalog must target Forge 1.12.2 and Java 8')
    require(catalog.get('state') in ('draft', 'pinned'), 'Invalid catalog state')
    require(allow_draft or catalog['state'] == 'pinned', 'Draft catalog cannot enter a release')
    base = catalog.get('baseline', {})
    require(base.get('version') == '1.1.0' and base.get('sourceCommit') == BASE_COMMIT and base.get('setupSha256') == BASE_SETUP_SHA256, 'Catalog baseline differs from immutable RV 1.1.0')
    baseline_files = base.get('files', [])
    managed_mods = catalog.get('managedMods', [])
    files = catalog.get('files')
    require(isinstance(baseline_files, list) and isinstance(managed_mods, list) and isinstance(files, list) and (allow_draft or bool(files)), 'Missing catalog files')
    known = {}
    for entry in baseline_files + managed_mods + files:
        component_id = entry.get('id')
        require(isinstance(component_id, str) and re.fullmatch('[a-z0-9][a-z0-9-]*', component_id) and component_id not in known, 'Invalid or duplicate component ID')
        require(entry.get('side') in SIDES and isinstance(entry.get('fileVersion'), str) and bool(entry['fileVersion']), 'Missing component side or file version')
        known[component_id] = entry
    paths = set()
    for entry in managed_mods:
        path = safe_path(entry.get('path'))
        require(path.startswith('mods/') and len(PurePosixPath(path).parts) == 2 and path.endswith('.jar'), 'RV managed mod target must be one bounded jar')
        require(path.casefold() not in paths, 'Duplicate Windows managed mod target')
        paths.add(path.casefold())
        require(type(entry.get('size')) is int and 0 < entry['size'] <= 1073741824 and re.fullmatch('[a-f0-9]{64}', str(entry.get('sha256', ''))), 'Missing exact RV managed mod pin')
        require(isinstance(entry.get('fml'), dict) and bool(entry['fml']) and set(entry.get('expectedModIds', [])) == set(entry['fml']), 'RV managed mod needs complete native FML identity')
        require(re.fullmatch('[a-f0-9]{64}', str(entry.get('nativeReceiptSha256', ''))), 'Missing RV managed mod native receipt')
        closure = entry.get('sourceFiles')
        require(isinstance(closure, dict) and bool(closure), 'Missing RV managed mod source closure')
        for name, digest in closure.items():
            safe_path(name)
            require(re.fullmatch('[a-f0-9]{64}', str(digest)), 'Invalid RV managed source digest')
    for entry in files:
        path = safe_path(entry.get('path'))
        require(path.startswith(('mods/', 'modularwarfare/')) and len(PurePosixPath(path).parts) == 2 and path.endswith(('.jar', '.zip')), 'Vendor target must be one bounded mod or content archive')
        require(path.casefold() not in paths, 'Duplicate Windows vendor target')
        paths.add(path.casefold())
        require(entry.get('kind') in ('mod', 'content-pack'), 'Invalid vendor artifact kind')
        require(type(entry.get('size')) is int and 0 < entry['size'] <= 1073741824, 'Invalid vendor download size')
        digest = entry.get('sha256')
        require(isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest), 'Missing exact vendor SHA-256')
        require(type(entry.get('projectId')) is int and entry['projectId'] > 0 and type(entry.get('fileId')) is int and entry['fileId'] > 0, 'Missing exact CurseForge project/file IDs')
        page = safe_url(entry.get('projectUrl'))
        require(re.fullmatch(r'https://(?:www\.)?curseforge.com/minecraft/mc-mods/[a-z0-9-]+', page) and entry.get('filePageUrl') == page + '/files/' + str(entry['fileId']), 'Official file page differs from the pin')
        urls = entry.get('officialUrls')
        require(isinstance(urls, list) and bool(urls) and len(set(urls)) == len(urls), 'Missing or duplicate official download URL')
        for url in urls:
            safe_url(url)
            parsed = urllib.parse.urlsplit(url)
            if parsed.hostname in ('edge.forgecdn.net', 'media.forgecdn.net', 'mediafilez.forgecdn.net'):
                file_id = str(entry['fileId'])
                expected = '/files/' + file_id[:-3] + '/' + str(int(file_id[-3:])) + '/' + urllib.parse.quote(PurePosixPath(path).name)
                require(parsed.path == expected, 'ForgeCDN URL differs from the pinned file ID/name')
        require(entry.get('delivery') in ('bundle', 'official-download', 'manual'), 'Invalid vendor delivery mode')
        rights = entry.get('rights', {})
        require(isinstance(rights.get('license'), str) and bool(rights['license']) and rights.get('reviewedSha256') == digest and type(rights.get('rehostAllowed')) is bool, 'Rights review must apply to these exact vendor bytes')
        evidence = rights.get('evidence')
        require(isinstance(evidence, list) and bool(evidence), 'Missing historical rights evidence')
        for item in evidence:
            require(item.get('kind') in ('archive-license', 'archive-metadata', 'source-license', 'author-permission', 'project-policy') and item.get('appliesToSha256') == digest and re.fullmatch('[a-f0-9]{64}', str(item.get('sha256', ''))), 'Unbound rights evidence')
            safe_url(item.get('url'), EVIDENCE_HOSTS)
        require(entry['delivery'] != 'bundle' or rights['rehostAllowed'], 'Vendor redistribution is not approved')
        require(entry['delivery'] != 'bundle' or any(item['kind'] in ('archive-license', 'source-license', 'author-permission') for item in evidence), 'Metadata alone does not authorize redistribution')
        require(entry['delivery'] == 'bundle' or not rights['rehostAllowed'], 'Non-bundled vendor has not been approved for rehosting')
        mod_ids = entry.get('expectedModIds', [])
        require(isinstance(mod_ids, list) and len(set(mod_ids)) == len(mod_ids) and all(re.fullmatch('[a-z0-9_]+', x) for x in mod_ids), 'Invalid expected FML IDs')
        require(entry['kind'] != 'mod' or bool(mod_ids), 'Mod entry requires actual declared FML identity')
        definitions = entry.get('definitionHashes', {})
        require(isinstance(definitions, dict) and (entry['kind'] != 'content-pack' or bool(definitions)), 'Content pack requires definition hashes, not invented FML IDs')
        for name, value in definitions.items():
            safe_path(name)
            require(re.fullmatch('[a-f0-9]{64}', str(value)), 'Invalid content definition digest')
        for embedded in entry.get('embedded', []):
            safe_path(embedded['member'])
            safe_path(embedded['path'])
            require(re.fullmatch('[a-f0-9]{64}', embedded['sha256']) and type(embedded['size']) is int and 0 < embedded['size'] <= entry['size'], 'Invalid embedded content pin')
    providers, declared = {}, {}
    for entry in known.values():
        fml = entry.get('fml', {})
        require(isinstance(fml, dict), 'Invalid native FML map')
        for mod_id, version in fml.items():
            require(re.fullmatch('[a-z0-9_]+', mod_id) and isinstance(version, str) and 0 < len(version) <= 128 and not any(c.isspace() for c in version), 'Invalid native FML ID/version')
            require(mod_id not in providers, 'Duplicate native FML ID: ' + mod_id)
            providers[mod_id] = entry['id']
        if entry in files:
            require(set(fml) <= set(entry.get('expectedModIds', [])), 'Native FML map contradicts artifact identity')
        for mod_id in set(entry.get('expectedModIds', [])) | set(fml):
            require(mod_id not in declared, 'Duplicate declared FML ID: ' + mod_id)
            declared[mod_id] = entry['id']
        requires = entry.get('requires', [])
        require(isinstance(requires, list), 'Invalid vendor dependency list')
        for dependency in requires:
            target = known.get(dependency.get('id'))
            require(target is not None and target['id'] != entry['id'], 'Missing or self-referential vendor dependency')
            require(dependency.get('fileVersion') == target['fileVersion'], 'Dependency differs from the pinned version')
            require(dependency.get('side') in SIDES, 'Missing dependency side')
            for side in ('client', 'server'):
                if has_side(entry, side) and has_side(dependency, side):
                    require(has_side(target, side), 'Client-only dependency required on a dedicated server')
    visiting, visited = set(), set()
    def visit(component_id):
        require(component_id not in visiting, 'Vendor dependency cycle')
        if component_id in visited:
            return
        visiting.add(component_id)
        for dependency in known[component_id].get('requires', []):
            visit(dependency['id'])
        visiting.remove(component_id)
        visited.add(component_id)
    for component_id in known:
        visit(component_id)
    return catalog


def load_catalog(path, allow_draft=False):
    return validate_catalog(json.loads(Path(path).read_text(encoding='utf-8-sig')), allow_draft)


def files_for_side(catalog, side):
    require(side in ('client', 'server'), 'Expected client or server side')
    return [entry for entry in catalog['files'] if has_side(entry, side)]


def protocol_maps(catalog):
    common, client = {}, {}
    for entry in catalog['baseline'].get('files', []) + catalog.get('managedMods', []) + catalog['files']:
        require(set(entry.get('expectedModIds', [])) <= set(entry.get('fml', {})), 'Actual native FML versions are not complete')
        if has_side(entry, 'client'):
            client.update(entry.get('fml', {}))
        if entry['side'] == 'both':
            common.update(entry.get('fml', {}))
    return {'requiredMods': common, 'clientRequiredMods': client}


def validate_release_catalog(catalog, metadata, catalog_sha256, first_party=None):
    validate_catalog(catalog)
    require(metadata.get('vendorCatalogSha256') == catalog_sha256, 'Release vendor catalog digest differs from its frozen bytes')
    maps = protocol_maps(catalog)
    require(first_party is None or isinstance(first_party, dict), 'Invalid explicit first-party native mod map')
    for mod_id, version in (first_party or {}).items():
        require(re.fullmatch('[a-z0-9_]+', mod_id) and isinstance(version, str) and 0 < len(version) <= 128 and not any(character.isspace() for character in version), 'Invalid explicit first-party native version')
        require(mod_id not in maps['clientRequiredMods'], 'First-party map contradicts an existing mod identity')
        maps['requiredMods'][mod_id] = version
        maps['clientRequiredMods'][mod_id] = version
    for field, expected in maps.items():
        require(metadata.get(field) == expected, 'Release ' + field + ' differs from actual native catalog versions')
    require(len((json.dumps(metadata, ensure_ascii=False, indent=2) + '\n').encode('utf-8')) + 3 <= 4096, 'Release metadata exceeds the immutable older updater limit')
    return catalog


def external_managed_files(catalog, manifest, side):
    managed = {}
    for entry in manifest.get('managedFiles', []):
        path = safe_path(entry.get('path'))
        require(path.casefold() not in managed, 'Duplicate managed vendor destination')
        managed[path.casefold()] = entry
    external = {}
    for entry in files_for_side(catalog, side) + [item for item in catalog.get('managedMods', []) if has_side(item, side)]:
        target = managed.get(entry['path'].casefold())
        require(target is not None and target['path'] == entry['path'] and target.get('sha256') == entry['sha256'] and target.get('existingOnly', False) is False, 'Acquired vendor pin is missing or differs from the managed manifest')
        if entry in catalog['files'] and entry['delivery'] != 'bundle':
            external[entry['path']] = entry['sha256']
    for entry in catalog['files'] + catalog.get('managedMods', []):
        require(has_side(entry, side) or entry['path'].casefold() not in managed, 'Client-only vendor cannot enter the managed server manifest')
    return external


def verify_managed_sources(catalog, root):
    for entry in catalog.get('managedMods', []):
        for name, digest in entry['sourceFiles'].items():
            require(sha256_file(Path(root) / safe_path(name)) == digest, 'RV managed mod source differs from its frozen closure: ' + name)
    return True


def verify_first_party_proof(proof_path, catalog, manifest, archive, root):
    if proof_path is None:
        return {}
    proof = json.loads(Path(proof_path).read_text(encoding='utf-8-sig'))
    require(proof.get('schema') == 1 and isinstance(proof.get('mods'), list) and bool(proof['mods']), 'Invalid first-party source/binary/native proof')
    composed = validate_catalog({**catalog, 'managedMods': proof['mods']})
    require(all(entry['side'] == 'both' for entry in proof['mods']), 'First-party compatibility module must have a common native identity')
    verify_managed_sources(composed, root)
    verify_managed_delivery(composed, manifest, archive, 'client')
    native, artifacts = {}, {}
    for receipt in proof.get('nativeReceipts', []):
        require(receipt.get('side') in ('client', 'server') and receipt['side'] not in native, 'Invalid or duplicate first-party native receipt side')
        path = Path(root) / safe_path(receipt.get('path'))
        require(sha256_file(path) == receipt.get('sha256'), 'First-party native receipt changed after verification')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        require(data.get('success') is True and isinstance(data.get('mods'), dict), 'First-party native receipt is incomplete')
        native[receipt['side']] = data['mods']
        require(isinstance(data.get('artifacts'), dict), 'First-party native receipt is missing the loaded artifact digests')
        artifacts[receipt['side']] = data['artifacts']
    require(set(native) == {'client', 'server'}, 'Both first-party native runtime receipts are required')
    result = {}
    for entry in proof['mods']:
        require(entry['nativeReceiptSha256'] in {receipt['sha256'] for receipt in proof['nativeReceipts']}, 'First-party native identity is not bound to its receipt')
        require(archive.getinfo(entry['path']).file_size == entry['size'], 'First-party managed binary size differs')
        require(all(values.get(entry['path']) == entry['sha256'] for values in artifacts.values()), 'First-party loaded native binary differs from its frozen artifact')
        for mod_id, version in entry['fml'].items():
            require(all(values.get(mod_id) == version for values in native.values()), 'First-party native runtime version differs from its source/binary proof')
            result[mod_id] = version
    return result


def first_party_proof_path(metadata, root):
    path = Path(root) / 'pack/rv-managed-mods.json'
    digest = metadata.get('managedModsSha256')
    if digest is None:
        require(not path.exists(), 'RV managed mod proof is missing its release digest')
        return None
    require(re.fullmatch('[a-f0-9]{64}', str(digest)) and path.is_file() and sha256_file(path) == digest, 'RV managed mod proof differs from its release digest')
    return path


def verify_managed_delivery(catalog, manifest, archive, side):
    external = external_managed_files(catalog, manifest, side)
    names = set(archive.namelist())
    require(not (set(external) & names), 'Official-download vendor path appears inside the public payload')
    for entry in manifest['managedFiles']:
        if entry['path'] in external:
            continue
        require(entry['path'] in names, 'Bundled managed file is missing from the payload: ' + entry['path'])
        with archive.open(entry['path']) as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256'], 'Bundled managed file differs from its manifest: ' + entry['path'])
    return external


def verify_artifact(entry, path):
    path = Path(path)
    require(path.stat().st_size == entry['size'] and sha256_file(path) == entry['sha256'], 'Vendor artifact checksum or size mismatch')
    with zipfile.ZipFile(path) as archive:
        seen, total, max_major = set(), 0, 0
        for info in archive.infolist():
            name = safe_path(info.filename.rstrip('/'))
            require(name.casefold() not in seen, 'Duplicate vendor ZIP path')
            seen.add(name.casefold())
            total += info.file_size
            require(total <= 4294967296 and len(seen) <= 100000, 'Vendor ZIP exceeds inspection limits')
            if name.endswith('.class') and not name.startswith('META-INF/versions/'):
                with archive.open(info) as stream:
                    header = stream.read(8)
                require(len(header) == 8 and header[:4] == b'\xca\xfe\xba\xbe', 'Invalid vendor class header')
                major = int.from_bytes(header[6:8], 'big')
                require(major <= 52, 'Vendor requires a Java version newer than Java 8')
                max_major = max(max_major, major)
        require(archive.testzip() is None, 'Vendor ZIP CRC failed')
        for name, digest in entry.get('definitionHashes', {}).items():
            require(hashlib.sha256(archive.read(name)).hexdigest() == digest, 'Content definition differs from the pin')
        for embedded in entry.get('embedded', []):
            info = archive.getinfo(embedded['member'])
            require(info.file_size == embedded['size'], 'Embedded content size mismatch')
            with archive.open(info) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            require(digest == embedded['sha256'], 'Embedded content checksum mismatch')
    return {'id': entry['id'], 'sha256': entry['sha256'], 'bytes': entry['size'], 'maxJavaClassMajor': max_major, 'crcPassed': True}


def audit_public_files(catalog, files, side):
    folded = {}
    for name, digest in files.items():
        safe_path(name)
        require(name.casefold() not in folded, 'Duplicate public Windows path')
        folded[name.casefold()] = digest
    forbidden = set()
    for entry in catalog['files']:
        if entry['delivery'] != 'bundle':
            forbidden.add(entry['sha256'])
            forbidden.update(item['sha256'] for item in entry.get('embedded', []))
    require(not (forbidden & set(files.values())), 'Official-download-only vendor bytes leaked into the public package')
    for entry in files_for_side(catalog, side):
        if entry['delivery'] == 'bundle':
            require(folded.get(entry['path'].casefold()) == entry['sha256'], 'Bundled vendor is missing or differs from its pin')
    for entry in catalog['files']:
        if not has_side(entry, side):
            require(entry['sha256'] not in set(files.values()), 'Vendor for the other side leaked into the public package')
    return True
