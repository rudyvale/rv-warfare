import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def compare(candidate, runtime):
    with zipfile.ZipFile(candidate) as original, zipfile.ZipFile(runtime) as loaded:
        assert original.testzip() is None and loaded.testzip() is None
        expected = set(original.namelist())
        actual = set(loaded.namelist())
        assert len(expected) == len(original.namelist())
        assert len(actual) == len(loaded.namelist())
        assert expected <= actual, sorted(expected - actual)
        added = sorted(actual - expected)
        changed = sorted(name for name in expected if original.read(name) != loaded.read(name))
    allowed = {'com/norwood/mcheli/uav/WarfareQuickUav.class', 'com/norwood/mcheli/vm/VMPilot.class'}
    assert set(changed) == allowed, changed
    assert all(re.fullmatch(r'(RVCombatAcceptance|VMControlsRuntime|VMControlsClientRuntime)(\$[^/]+)?\.class', name) for name in added), added
    return {'runtime_sha256': digest(runtime), 'unchanged_members': len(expected) - len(changed), 'test_hook_members': changed, 'test_helpers': added}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--props', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--qa-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    mch = digest(args.candidate)
    tg = digest(args.props)
    source = digest(args.qa_source)
    report = {'candidate_sha256': mch, 'props_sha256': tg, 'acceptance_source_sha256': source}
    for environment in ('server', 'client'):
        folder = args.runtime_root / environment / 'mods'
        mcheli = list(folder.glob('mcheli*.jar'))
        techguns = list(folder.glob('techguns*.jar'))
        assert len(mcheli) == len(techguns) == 1, environment
        report[environment] = compare(args.candidate, mcheli[0])
        assert digest(techguns[0]) == tg, environment + ' Techguns differs from candidate'
    for name in ('runtime-result', 'client-result', 'combat-result'):
        result = json.loads((args.runtime_root / (name + '.json')).read_text(encoding='utf-8'))
        assert result['success'] and result['artifact_sha256'] == mch, name
        if name != 'client-result':
            assert result['props_sha256'] == tg and result['acceptance_source_sha256'] == source, name
        report[name] = {'passed': True, 'logged_passes': sum('] PASS ' in line for line in result['checks'])}
        if name == 'combat-result':
            evidence = '\n'.join(result['checks'])
            for marker in ('upper turret hit registers damage', '20-block projectile stops at extra box, yaw=135.0', 'wall occludes tank', 'armed fast FPV stops at rotated extra box', 'repeated motion call cannot deal second blast damage', 'registered damage destroys real tank', 'rifle breaks actual glass block', 'bullet hits and destroys dropped item', 'second hit breaks empty item frame', 'incendiary projectile starts actual wood burn', '[RV combat QA] COMPLETE'):
                assert marker in evidence, marker
            assert '[RV combat QA] FAIL ' not in evidence
    report['passed'] = True
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('server', 'client')}, indent=2))


if __name__ == '__main__':
    main()
