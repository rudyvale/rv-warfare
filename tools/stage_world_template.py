import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys


def stage(template, functions, output):
    import nbtlib
    from nbtlib import Byte, Compound, File, Int, List, String
    template, functions, output = template.resolve(), functions.resolve(), output.resolve()
    if output.exists() or output == template or template in output.parents:
        raise ValueError('Output must be a new directory outside the pristine template')
    manifest = json.loads((template.parent / 'world-template-manifest.json').read_text(encoding='utf-8'))
    world = output / template.name
    (world / 'region').mkdir(parents=True)
    for path in sorted((template / 'region').glob('r.*.*.mca')):
        shutil.copy2(path, world / 'region' / path.name)
    level = nbtlib.load(template / 'level.dat')
    data = level['Data']
    data['LevelName'] = String('RV Battlefield')
    data['GameRules']['gameLoopFunction'] = String('warfare:tick')
    data['GameRules']['doMobSpawning'] = String('false')
    data['GameRules']['doFireTick'] = String('true')
    data['GameRules']['keepInventory'] = String('true')
    data['GameRules']['spawnRadius'] = String('0')
    for name, value in [('SpawnX', 0), ('SpawnY', 65), ('SpawnZ', -210)]:
        data[name] = Int(value)
    level.save(world / 'level.dat', gzipped=True)
    target = world / 'data/functions/warfare'
    target.mkdir(parents=True)
    for path in sorted(functions.glob('*.mcfunction')):
        shutil.copy2(path, target / path.name)
    objectives = {}
    for path in sorted(target.glob('*.mcfunction')):
        for name, criteria in re.findall(r'^scoreboard objectives add (\w+) (\w+)', path.read_text(encoding='utf-8'), flags=re.MULTILINE):
            if name in objectives and objectives[name] != criteria:
                raise ValueError('Conflicting objective ' + name)
            objectives[name] = criteria
    score = Compound({'Objectives': List[Compound]([Compound({'Name': String(name), 'CriteriaName': String(criteria), 'DisplayName': String('Kills' if name == 'kills' else name)}) for name, criteria in sorted(objectives.items())]), 'PlayerScores': List[Compound]([]), 'Teams': List[Compound]([Compound({'Name': String(name), 'DisplayName': String(name.title()), 'Prefix': String(prefix), 'Suffix': String('§r'), 'AllowFriendlyFire': Byte(0), 'SeeFriendlyInvisibles': Byte(1), 'NameTagVisibility': String('always'), 'DeathMessageVisibility': String('always'), 'CollisionRule': String('always'), 'TeamColor': Byte(color), 'Players': List[String]([])}) for name, color, prefix in [('blue', 9, '§9'), ('red', 12, '§c')]]), 'DisplaySlots': Compound({'slot_1': String('kills')})})
    File({'data': score, 'DataVersion': Int(1343)}).save(world / 'data/scoreboard.dat', gzipped=True)
    for name in ('blue', 'red'):
        position = ' '.join(str(value) for value in manifest[name])
        path = target / (name + '.mcfunction')
        path.write_text('scoreboard teams join ' + name + ' @s\ntp @s ' + position + '\nspawnpoint @s ' + position + '\nscoreboard players set @s ' + name + ' 0\nfunction warfare:help\n', encoding='utf-8')
    manifest.update(functionsIncluded=True, playerBookIncluded=True, scoreboardIncluded=True, gameLoopFunction='warfare:tick', bootFunction='warfare:boot', scoreboardPlayerEntries=0, functionCount=len(list(target.glob('*.mcfunction'))), spawn=[0,65,-210], spawnRadius=0)
    manifest['files'] = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(world.rglob('*')) if path.is_file()}
    (output / 'world-template-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'INSTALL-NEW-WORLD.md').write_text('Extract the world folder into your Forge 1.12.2 server and set level-name=Battlefield-Extended in server.properties. Use the matching RV server mods. Start the server; scoreboard objectives, teams, menus and guide delivery are already initialized. Run function warfare:boot once from the console when using a custom runner. Keep server view-distance=6. Never replace a live world with this template; back it up and merge missing chunks separately. The template contains no player accounts or operator policy.\n', encoding='utf-8')
    print(json.dumps({'world': str(world), 'functions': manifest['functionCount'], 'objectives': len(objectives), 'privatePlayerEntries': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--functions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python-libs', type=Path)
    args = parser.parse_args()
    if args.python_libs:
        sys.path.insert(0, str(args.python_libs))
    stage(args.template, args.functions, args.output)
