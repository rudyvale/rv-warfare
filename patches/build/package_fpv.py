from pathlib import Path
import hashlib
import json
import re
import zipfile

work = Path(__file__).resolve().parent
source = work.parent.parent / 'new-chat-2' / 'work' / 'mcheli-ce-1.5.1-warfare-fix3.jar'
classes = work / 'fpv-classes'
target = work / 'mcheli-ce-1.5.1-warfare-fix8.jar'
with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as new:
    for info in old.infolist():
        changed = classes / info.filename
        data = changed.read_bytes() if changed.is_file() else old.read(info.filename)
        if info.filename in ('assets/mcheli/helicopters/rc-goblin.yml', 'assets/mcheli/helicopters/rc-goblin-bomb.yml'):
            text = data.decode('utf-8')
            bomb = info.filename.endswith('-bomb.yml')
            text = text.replace('DEFAULT: RC Goblin with Bomb', 'DEFAULT: FPV Goblin with Bomb').replace('DEFAULT: RC Goblin\n', 'DEFAULT: FPV Goblin\n')
            text = text.replace('DisplayName:\n', 'DisplayName:\n  ru_ru: "FPV-дрон (' + ('бомба' if bomb else 'разведка') + ')"\n')
            text = re.sub(r'^MaxFuel: \d+$', 'MaxFuel: 600', text, flags=re.M)
            text = re.sub(r'^MaxHP: \d+$', 'MaxHP: 30', text, flags=re.M)
            data = text.encode('utf-8')
        new.writestr(info, data)
    new.write(classes / 'com/norwood/mcheli/uav/WarfareFpv.class', 'com/norwood/mcheli/uav/WarfareFpv.class')
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist()) == len(set(archive.namelist()))
report = {'jar': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size, 'math_checks': 9, 'runtime': 'pending', 'controls': {'W/S': 'throttle', 'A/D': 'yaw', 'mouse': 'pitch/roll'}, 'gravity': 9.81, 'max_thrust_to_weight': 4, 'hover_throttle': 0.5, 'motor_time_constant_ms': 100, 'max_fuel': 600, 'max_hp': 30}
(work / 'fpv-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
