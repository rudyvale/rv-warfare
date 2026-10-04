import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import zipfile
import zlib

BASE_SHA256 = 'ea90ce380c54a45982b02f2ae61533517203e926da0f2d65d31e51d7dc3408bb'
COMPILER_SHA256 = '9cddda75f4a1b4469e73f44e7b61a3e897d0f657df4797f9106ffe88c4eeade0'
PACKAGE = 'com/norwood/mcheli/vm/'
SOURCES = ('VMCalibration.java', 'VMClient.java', 'VMCombat.java', 'VMComfort.java', 'VMComfortTransformer.java', 'VMControlMath.java', 'VMController.java', 'VMEasy.java', 'VMFeedback.java', 'VMFlight.java', 'VMImpact.java', 'VMLoginTransformer.java', 'VMMotor.java', 'VMPilot.java', 'VMProps.java', 'VMPropsTransformer.java', 'VMReflect.java', 'VMVec2f.java')
INNER_CLASSES = {'VMCalibration.java': ('VMCalibration$1', 'VMCalibration$2'), 'VMFeedback.java': ('VMFeedback$1',), 'VMProps.java': ('VMProps$1', 'VMProps$Damage', 'VMProps$FireRecord', 'VMProps$WorldBudget')}
LF_RESOURCES = {'assets/mcheli/helicopters/rc-goblin.yml', 'assets/mcheli/helicopters/rc-goblin-bomb.yml'}
RESOURCES = ('assets/mcheli/helicopters/rc-goblin-bomb.yml', 'assets/mcheli/helicopters/rc-goblin.yml', 'assets/mcheli/hud/rv_fpv.yml', 'assets/mcheli/models/helicopters/rc-goblin-bomb.mqo', 'assets/mcheli/models/helicopters/rc-goblin.mqo', 'assets/mcheli/models/planes/rv_fp1.mqo', 'assets/mcheli/models/planes/rv_geran.mqo', 'assets/mcheli/planes/rv_fp1.yml', 'assets/mcheli/planes/rv_geran.yml', 'assets/mcheli/rv-models.json', 'assets/mcheli/textures/helicopters/rc-goblin-1.png', 'assets/mcheli/textures/helicopters/rc-goblin-2.png', 'assets/mcheli/textures/helicopters/rc-goblin-bomb-1.png', 'assets/mcheli/textures/helicopters/rc-goblin-bomb.png', 'assets/mcheli/textures/helicopters/rc-goblin.png', 'assets/mcheli/textures/items/rc-goblin-bomb.png', 'assets/mcheli/textures/items/rc-goblin.png', 'assets/mcheli/textures/items/rv_fp1.png', 'assets/mcheli/textures/items/rv_geran.png', 'assets/mcheli/textures/planes/rv_fp1.png', 'assets/mcheli/textures/planes/rv_geran.png')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_member(name):
    require(isinstance(name, str) and name and not name.startswith('/') and '\\' not in name and ':' not in name and all(ord(char) >= 32 for char in name), 'Unsafe archive member')
    parts = name.rstrip('/').split('/')
    require(all(part not in ('', '.', '..') for part in parts), 'Unsafe archive member')
    return name


def read_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= 20000 and sum(item.file_size for item in infos) <= 1024 ** 3, 'Archive exceeds bounded overlay limits')
        names = set()
        contents = {}
        for info in infos:
            safe_member(info.orig_filename)
            require(info.orig_filename == info.filename, 'Archive member name was normalized')
            safe_member(info.filename)
            key = info.filename.rstrip('/').casefold()
            require(key not in names, 'Duplicate archive member')
            names.add(key)
            require(not info.flag_bits & 1 and not stat.S_ISLNK(info.external_attr >> 16), 'Unsupported archive member')
            require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and info.file_size <= 256 * 1024 ** 2, 'Unsupported archive compression or size')
            contents[info.filename] = archive.read(info)
        require(archive.testzip() is None, 'Archive CRC mismatch')
        return infos, contents, archive.comment


def class_name(data):
    require(len(data) >= 10 and data[:4] == b'\xca\xfe\xba\xbe' and int.from_bytes(data[4:6], 'big') == 0 and int.from_bytes(data[6:8], 'big') == 52, 'Overlay class must use Java 8 major version 52')
    offset = 10
    pool = {}
    count = int.from_bytes(data[8:10], 'big')
    require(count > 1, 'Invalid class constant pool')
    def take(size):
        nonlocal offset
        require(offset + size <= len(data), 'Truncated class file')
        result = data[offset:offset + size]
        offset += size
        return result
    index = 1
    while index < count:
        tag = take(1)[0]
        if tag == 1:
            pool[index] = (tag, take(int.from_bytes(take(2), 'big')))
        elif tag in (7, 8, 16):
            pool[index] = (tag, int.from_bytes(take(2), 'big'))
        elif tag in (3, 4, 9, 10, 11, 12, 18):
            take(4)
        elif tag in (5, 6):
            take(8)
            index += 1
        elif tag == 15:
            take(3)
        else:
            raise ValueError('Unsupported Java 8 constant pool entry')
        index += 1
    take(2)
    this_class = pool.get(int.from_bytes(take(2), 'big'))
    require(this_class is not None and this_class[0] == 7, 'Invalid class identity')
    name = pool.get(this_class[1])
    require(name is not None and name[0] == 1, 'Invalid class name')
    try:
        return name[1].decode('ascii')
    except UnicodeDecodeError:
        raise ValueError('Unexpected controls class name') from None


def allowed_classes(sources):
    return {PACKAGE + name + '.class' for source in sources for name in (Path(source).stem, *INNER_CLASSES.get(source, ()))}


def resource_bytes(name, data):
    return data.replace(b'\r\n', b'\n') if name in LF_RESOURCES else data


def capture_sources(root, sources, resources, overrides):
    require(sources and len(sources) == len(set(sources)) and set(sources) <= set(SOURCES), 'Invalid controls source selection')
    require(len(resources) == len(set(resources)) and set(resources) <= set(RESOURCES), 'Invalid controls resource selection')
    selected = {'patches/controls/' + name for name in sources} | {'patches/controls/resources/' + name for name in resources}
    require(set(overrides) <= selected, 'Override is not an explicitly selected controls source')
    if set(sources) == set(SOURCES):
        require({path.name for path in (root / 'patches/controls').glob('*.java')} == set(SOURCES), 'Canonical controls source list changed')
    if set(resources) == set(RESOURCES):
        require({path.relative_to(root / 'patches/controls/resources').as_posix() for path in (root / 'patches/controls/resources').rglob('*') if path.is_file()} == set(RESOURCES), 'Canonical controls resource list changed')
    captured = {}
    for name in sorted(selected):
        path = Path(overrides.get(name, root / name)).resolve(strict=True)
        require(path.is_file(), 'Missing controls source file')
        data = path.read_bytes()
        if name.endswith('.java'):
            text = data.decode('utf-8-sig')
            require(re.search(r'\bpackage\s+com\.norwood\.mcheli\.vm\s*;', text) is not None and re.search(r'\bclass\s+' + re.escape(Path(name).stem) + r'\b', text) is not None, 'Unexpected controls source identity')
        captured[name] = data
    return captured


def overlay_archive(base_data, replacements, permitted, required, destination):
    infos, original, comment = read_archive(base_data)
    require(required <= set(replacements) and set(replacements) <= permitted, 'Overlay contains missing or unexpected members')
    for name, data in replacements.items():
        safe_member(name)
        if name.endswith('.class'):
            require(class_name(data) + '.class' == name, 'Class identity differs from archive path')
        else:
            require(name in original and name in RESOURCES, 'Overlay cannot add unrelated resources')
    with Path(destination).open('xb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
        archive.comment = comment
        for info in infos:
            archive.writestr(copy.copy(info), replacements.get(info.filename, original[info.filename]))
        for name in sorted(set(replacements) - set(original)):
            require(name.endswith('.class') and name.startswith(PACKAGE), 'Only captured controls classes may be added')
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, replacements[name])
    output_data = Path(destination).read_bytes()
    output_infos, result, result_comment = read_archive(output_data)
    require(list(original) == list(result)[:len(original)] and set(result) == set(original) | set(replacements) and result_comment == comment, 'Overlay changed the original archive structure')
    changed = sorted(name for name in original if original[name] != result[name])
    added = sorted(set(result) - set(original))
    require(set(changed + added) <= set(replacements), 'Overlay modified unrelated archive members')
    require(all(result[name] == data for name, data in replacements.items()), 'Overlay replacement bytes differ')
    unrelated = {name: digest(data) for name, data in original.items() if name not in replacements}
    return {'sha256': digest(output_data), 'bytes': len(output_data), 'members': len(output_infos), 'changedArchiveMembers': changed, 'addedArchiveMembers': added, 'unrelatedArchiveMembers': len(unrelated), 'unrelatedMemberMapSha256': digest(json.dumps(unrelated, sort_keys=True, separators=(',', ':')).encode()), 'unrelatedArchiveMembersBytePreserved': True, 'archiveCrcVerified': True}


def build(root, game, base, compiler, output, sources=None, resources=None, overrides=None):
    root, game, base, compiler, output = (Path(path).resolve() for path in (root, game, base, compiler, output))
    require(output.is_relative_to(root / '.local') and output != root / '.local' and not output.exists(), 'Overlay output must be a new private directory under .local')
    require(not game.is_relative_to(output) and not output.is_relative_to(game), 'Overlay output cannot be inside the installed game')
    forbidden = {'world', 'world_nether', 'world_the_end', 'saves', 'mods', 'runtime', 'libraries', 'config', 'mcheli_addons', 'public', 'releases', 'rv-setup', 'rv-host-tools'}
    require(not any(part.casefold() in forbidden for part in output.relative_to(root / '.local').parts), 'Overlay output cannot be inside a game world or package')
    require(not any((parent / 'level.dat').exists() or (parent / 'session.lock').exists() for parent in (output, *output.parents) if parent.is_relative_to(root / '.local')), 'Overlay output cannot be inside a private world')
    require(base.is_file() and compiler.is_file(), 'Missing pinned base or compiler')
    base_data = base.read_bytes()
    require(digest(base_data) == BASE_SHA256, 'Base JAR differs from the pinned production SHA-256')
    compiler_data = compiler.read_bytes()
    require(digest(compiler_data) == COMPILER_SHA256, 'Compiler differs from pinned ECJ 4.6.1')
    infos, original, comment = read_archive(base_data)
    selected_sources = sorted(SOURCES if sources is None else sources)
    selected_resources = sorted(RESOURCES if resources is None else resources)
    captured = capture_sources(root, selected_sources, selected_resources, overrides or {})
    permitted_classes = allowed_classes(selected_sources)
    require(set(selected_resources) <= set(original), 'Pinned base is missing selected controls resources')
    required_classes = {PACKAGE + Path(name).stem + '.class' for name in selected_sources} | (set(original) & permitted_classes)
    java = game / 'runtime/bin/java.exe'
    require(java.is_file() and (game / 'libraries').is_dir(), 'Missing Java runtime or library directory')
    libraries = sorted((game / 'libraries').rglob('*.jar'))
    require(libraries, 'Missing Java compile dependencies')
    version = subprocess.run([str(java), '-version'], check=True, capture_output=True, text=True, timeout=25)
    java_version = version.stdout + version.stderr
    require(re.search(r'version\s+"1\.8\.', java_version) is not None, 'Overlay compilation requires the existing Java 8 runtime')
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / 'inputs'
    inputs.mkdir()
    input_data = {'inputs/base.jar': base_data, 'inputs/ecj-4.6.1.jar': compiler_data}
    dependency_names = []
    dependency_origins = {}
    for index, path in enumerate(libraries):
        require(path.resolve().is_relative_to(game / 'libraries'), 'Compile dependency escapes the game library directory')
        name = 'inputs/libraries/' + str(index).zfill(3) + '-' + path.name
        input_data[name] = path.read_bytes()
        dependency_names.append(name)
        dependency_origins[name] = path.relative_to(game).as_posix()
    for name, data in captured.items():
        input_data['captured-source/' + name] = data
    for name, data in input_data.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    captured_hashes = {name: digest(data) for name, data in captured.items()}
    capture = {'schema': 1, 'baseSha256': BASE_SHA256, 'compilerSha256': COMPILER_SHA256, 'javaSha256': file_digest(java), 'javaVersion': java_version.strip(), 'sourceFiles': captured_hashes, 'sourceOverrides': sorted(overrides or {}), 'selectedSources': selected_sources, 'selectedResources': selected_resources, 'inputFiles': {name: digest(data) for name, data in input_data.items()}, 'dependencyOrigins': dependency_origins, 'builderSha256': file_digest(__file__)}
    capture['resourceNormalization'] = {name: 'CRLF to LF' for name in selected_resources if name in LF_RESOURCES}
    capture['resourceOverlaySha256'] = {name: digest(resource_bytes(name, captured['patches/controls/resources/' + name])) for name in selected_resources}
    capture_path = output / 'capture.json'
    capture_path.write_text(json.dumps(capture, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    classes = output / 'classes'
    classes.mkdir()
    command = [str(java), '-jar', str(output / 'inputs/ecj-4.6.1.jar'), '-1.8', '-encoding', 'UTF-8', '-nowarn', '-proc:none', '-sourcepath', str(output / 'captured-source/patches/controls'), '-classpath', os.pathsep.join(str(output / name) for name in ['inputs/base.jar', *dependency_names]), '-d', str(classes), *(str(output / 'captured-source/patches/controls' / name) for name in selected_sources)]
    recipe = {'schema': 1, 'command': command, 'java': str(java), 'javaSha256': capture['javaSha256'], 'pythonVersion': platform.python_version(), 'zlibVersion': zlib.ZLIB_RUNTIME_VERSION, 'zipCompressionLevel': 5, 'asmReapplied': False, 'inputCaptureSha256': file_digest(capture_path)}
    (output / 'recipe.json').write_text(json.dumps(recipe, indent=2) + '\n', encoding='utf-8')
    compiled = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=180)
    (output / 'compile.txt').write_text(compiled.stdout + compiled.stderr, encoding='utf-8')
    compiled.check_returncode()
    require(all(file_digest(output / name) == expected for name, expected in capture['inputFiles'].items()), 'Captured compile input changed during compilation')
    replacements = {}
    for path in sorted(classes.rglob('*')):
        if not path.is_file():
            continue
        name = path.relative_to(classes).as_posix()
        require(name in permitted_classes, 'Compiler emitted an unexpected overlay member')
        data = path.read_bytes()
        require(class_name(data) + '.class' == name, 'Compiler class identity differs from its path')
        replacements[name] = data
    for name in selected_resources:
        replacements[name] = resource_bytes(name, captured['patches/controls/resources/' + name])
    candidate = output / 'mcheli-controls-overlay.jar'
    proof = overlay_archive(base_data, replacements, permitted_classes | set(selected_resources), required_classes | set(selected_resources), candidate)
    proof.update(schema=1, baseSha256=BASE_SHA256, compilerSha256=COMPILER_SHA256, sourceFiles=captured_hashes, resourceNormalization=capture['resourceNormalization'], capturedInputSha256=file_digest(capture_path), recipeSha256=file_digest(output / 'recipe.json'), overlayMemberSha256={name: digest(data) for name, data in replacements.items()}, javaClassMajor=52, asmReapplied=False, nativeVerified=False, hardwareTested=False, published=False, scope='Private first-party controls overlay; no archive hooks reapplied', candidate=candidate.name)
    (output / 'build.json').write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return proof


def parse_override(value):
    name, separator, path = value.partition('=')
    require(separator and name and path, 'Override must use canonical-source=path')
    return name, Path(path)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=root)
    parser.add_argument('--game', type=Path, default=Path(os.environ.get('RV_GAME_ROOT', str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Warfare-1.12.2'))))
    parser.add_argument('--base-jar', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, default=root / '.local/tools/ecj-4.6.1.jar')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', action='append')
    parser.add_argument('--resource', action='append')
    parser.add_argument('--override', action='append', default=[], type=parse_override)
    args = parser.parse_args()
    require(len(args.override) == len(dict(args.override)), 'Duplicate source override')
    print(json.dumps(build(args.root, args.game, args.base_jar, args.compiler, args.output, args.source, args.resource, dict(args.override)), sort_keys=True))


if __name__ == '__main__':
    main()
