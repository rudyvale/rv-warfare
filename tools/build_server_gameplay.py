import argparse
import json
from pathlib import Path
import shutil


parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--baseline', type=Path, default=Path(__file__).resolve().parents[1] / 'pack/server-functions/warfare')
parser.add_argument('--book', type=Path)
args = parser.parse_args()
root = args.output / 'warfare'
root.mkdir(parents=True, exist_ok=True)
for source in [args.baseline, args.book]:
    if source:
        for path in source.glob('*.mcfunction'):
            shutil.copy2(path, root / path.name)


def write(name, commands):
    (root / (name + '.mcfunction')).write_text('\n'.join(commands) + '\n', encoding='utf-8')


def message(text, color='green', actionbar=False):
    return ('title @s actionbar ' if actionbar else 'tellraw @s ') + json.dumps({'text': text, 'color': color}, ensure_ascii=False)


def button(label, objective, value=1, color='aqua', hint=None):
    item = {'text': '[' + label + '] ', 'color': color, 'clickEvent': {'action': 'run_command', 'value': '/trigger ' + objective + ' set ' + str(value)}}
    if hint:
        item['hoverEvent'] = {'action': 'show_text', 'value': hint}
    return item


def probe_item(name, item, data=0, maximum=0):
    selector = '@s[score_w_probe=' + str(maximum) + ',score_w_free_min=1]'
    write(name, ['scoreboard players set @s w_probe 0', 'scoreboard players add @s w_probe 1 {Inventory:[{id:"' + item + '"}]}', 'function warfare:space', 'execute ' + selector + ' ~ ~ ~ give @s ' + item + ' 1 ' + str(data), 'execute ' + selector + ' ~ ~ ~ scoreboard players add @s w_given 1'])


def supply_unstackable(name, item, target):
    selector = '@s[score_w_probe=' + str(target - 1) + ',score_w_free_min=1]'
    step = ['scoreboard players set @s w_probe 0', 'stats entity @s set AffectedItems @s w_probe', 'clear @s ' + item + ' -1 0', 'stats entity @s clear AffectedItems', 'function warfare:space', 'execute ' + selector + ' ~ ~ ~ give @s ' + item + ' 1 0', 'execute ' + selector + ' ~ ~ ~ scoreboard players add @s w_given 1']
    write(name, step * target)


def supply_stack(name, item, target):
    commands = ['scoreboard players set @s w_probe 0', 'stats entity @s set AffectedItems @s w_probe', 'clear @s ' + item + ' -1 0', 'stats entity @s clear AffectedItems', 'function warfare:space']
    for current in range(target):
        selector = '@s[score_w_probe=' + str(current) + ',score_w_probe_min=' + str(current) + ',score_w_free_min=1]'
        commands += ['execute ' + selector + ' ~ ~ ~ give @s ' + item + ' ' + str(target-current) + ' 0', 'execute ' + selector + ' ~ ~ ~ scoreboard players add @s w_given 1']
    write(name, commands)


for item in ['m4', 'scar', 'aug', 'as50', 'lmg', 'minigun', 'combatshotgun']:
    probe_item('item_' + item, 'techguns:' + item)
supply_unstackable('item_drone', 'mcheli:rc-goblin-bomb', 3)
probe_item('item_tablet', 'mcheli:uav_tablet')
probe_item('item_geran', 'mcheli:rv_geran')
probe_item('item_fp1', 'mcheli:rv_fp1')
supply_stack('item_bandage', 'firstaid:bandage', 4)
supply_stack('item_plaster', 'firstaid:plaster', 4)
for number, slot, item in [(103, 'head', 'iron_helmet'), (102, 'chest', 'iron_chestplate'), (101, 'legs', 'iron_leggings'), (100, 'feet', 'iron_boots')]:
    write('armor_' + slot, ['scoreboard players set @s w_probe 0', 'scoreboard players add @s w_probe 1 {Inventory:[{Slot:' + str(number) + 'b}]}', 'execute @s[score_w_probe=0] ~ ~ ~ replaceitem entity @s slot.armor.' + slot + ' minecraft:' + item, 'execute @s[score_w_probe=0] ~ ~ ~ scoreboard players add @s w_given 1'])
write('space', ['scoreboard players set @s w_used 0'] + ['scoreboard players add @s w_used 1 {Inventory:[{Slot:' + str(slot) + 'b}]}' for slot in range(36)] + ['scoreboard players set @s w_free 36', 'scoreboard players operation @s w_free -= @s w_used'])

for name, data, limit, count in [('rifle', 13, 15, 16), ('sniper', 19, 15, 16), ('lmg', 15, 15, 16), ('minigun', 17, 7, 8), ('shotgun', 2, 31, 32), ('food', 0, 15, 16)]:
    item = 'minecraft:cooked_beef' if name == 'food' else 'techguns:itemshared'
    selector = '@s[score_w_probe=' + str(limit) + ',score_w_free_min=1]'
    write('ammo_' + name, ['scoreboard players set @s w_probe 0', 'stats entity @s set AffectedItems @s w_probe', 'clear @s ' + item + ' ' + str(data) + ' 0', 'stats entity @s clear AffectedItems', 'function warfare:space', 'execute ' + selector + ' ~ ~ ~ give @s ' + item + ' ' + str(count) + ' ' + str(data), 'execute ' + selector + ' ~ ~ ~ scoreboard players add @s w_given 1'])

write('kit', ['function warfare:item_m4', 'function warfare:ammo_rifle', 'function warfare:ammo_food'] + ['function warfare:armor_' + key for key in ['head', 'chest', 'legs', 'feet']] + ['function warfare:item_tablet', 'function warfare:item_drone', 'function warfare:item_geran', 'function warfare:item_fp1', 'function warfare:item_bandage', 'function warfare:item_plaster', 'scoreboard players set @s kit 0', 'scoreboard players set @s w_supply 100', 'scoreboard players tag @s add w_kit', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Снаряжение готово.'), 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('Kit ready.')])
for index, (role, items, ammo, ru, en) in enumerate([
    ('assault', ['scar', 'aug'], ['rifle'], 'SCAR и AUG готовы.', 'SCAR and AUG ready.'),
    ('sniper', ['as50'], ['sniper'], 'AS50 готова.', 'AS50 ready.'),
    ('support', ['lmg', 'minigun'], ['lmg', 'minigun'], 'LMG и Minigun готовы.', 'LMG and Minigun ready.'),
    ('breacher', ['combatshotgun'], ['shotgun'], 'Дробовик готов.', 'Shotgun ready.'),
], 1):
    write('loadout_' + role, ['function warfare:item_' + item for item in items] + ['function warfare:ammo_' + item for item in ammo] + ['scoreboard players set @s w_class ' + str(index), 'scoreboard players set @s loadout 0', 'scoreboard players set @s w_supply 40', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message(ru), 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message(en)])
write('ammo', ['execute @s[score_w_class=1] ~ ~ ~ function warfare:ammo_rifle', 'execute @s[score_w_class=2,score_w_class_min=2] ~ ~ ~ function warfare:ammo_sniper', 'execute @s[score_w_class=3,score_w_class_min=3] ~ ~ ~ function warfare:ammo_lmg', 'execute @s[score_w_class=3,score_w_class_min=3] ~ ~ ~ function warfare:ammo_minigun', 'execute @s[score_w_class=4,score_w_class_min=4] ~ ~ ~ function warfare:ammo_shotgun', 'scoreboard players set @s ammo 0', 'scoreboard players set @s w_ammo 100', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Патроны готовы.'), 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('Ammo ready.')])
write('drone', ['function warfare:item_tablet', 'function warfare:item_drone', 'scoreboard players set @s drone 0', 'scoreboard players set @s w_drone 100', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:drone_tip_ru', 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:drone_tip_en'])
write('wing', ['function warfare:item_tablet', 'function warfare:item_geran', 'function warfare:item_fp1', 'scoreboard players set @s wing 0'])
write('wait_wing', ['scoreboard players set @s wing 0'])
write('spawn', ['tp @s 0 65 -210', 'scoreboard players set @s spawn 0'])
write('training', ['tp @s -48 65 -210', 'scoreboard players set @s training 0', 'execute @s[score_w_drone=0] ~ ~ ~ function warfare:drone'])
write('wait_supply', ['scoreboard players set @s kit 0', 'scoreboard players set @s loadout 0', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Подожди пару секунд.', 'gray', True), 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('Wait a moment.', 'gray', True)])
write('wait_drone', ['scoreboard players set @s drone 0', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Дрон уже выдан.', 'gray', True), 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('UAV already supplied.', 'gray', True)])
write('wait_ammo', ['scoreboard players set @s ammo 0'])
write('init_ui', ['scoreboard players add @s ' + name + ' 0' for name in ['wlang', 'kills', 'w_supply', 'w_drone', 'w_wing', 'w_ammo', 'w_class', 'w_probe', 'w_used', 'w_free', 'w_given', 'w_admin']] + ['scoreboard players tag @s add w_ui2'])

for language, number in [('ru', 1), ('en', 2)]:
    ru = language == 'ru'
    rows = [
        [{'text': '\nRV\n', 'color': 'gold', 'bold': True}, button('Синяя' if ru else 'Blue', 'blue'), button('Красная' if ru else 'Red', 'red', color='red'), button('Спавн' if ru else 'Spawn', 'spawn', color='yellow'), button('Учебка' if ru else 'Training', 'training')],
        [button('Набор' if ru else 'Kit', 'kit', color='green'), button('Оружие' if ru else 'Weapons', 'arsenal'), button('Патроны' if ru else 'Ammo', 'ammo'), button('Дрон' if ru else 'UAV', 'drone')],
        [button('Крыло' if ru else 'Wing', 'wing'), button('Книга' if ru else 'Book', 'wbook'), button('Помощь' if ru else 'Guide', 'guide'), button('Звук' if ru else 'Sound', 'sound'), button('Русский', 'lang_ru', color='gray'), button('English', 'lang_en', color='gray')],
    ]
    write('help_' + language, ['tellraw @s ' + json.dumps(row, ensure_ascii=False) for row in rows] + ['execute @s[tag=v_owner] ~ ~ ~ function warfare:admin_' + language])
    write('entry_' + language, ['tellraw @s ' + json.dumps([{'text': 'RV: ', 'color': 'gold'}, button('Меню' if ru else 'Menu', 'menu'), button('Книга' if ru else 'Book', 'wbook', hint='Освободи один слот, если инвентарь полон.' if ru else 'Make one free inventory slot if full.')], ensure_ascii=False)])
    guns = [{'text': '\nОружие\n' if ru else '\nWeapons\n', 'color': 'gold'}, button('Штурм' if ru else 'Assault', 'loadout', 1, hint='SCAR + AUG'), button('Снайпер' if ru else 'Sniper', 'loadout', 2, hint='AS50'), button('Пулемёты' if ru else 'Support', 'loadout', 3, hint='LMG + Minigun'), button('Дробовик' if ru else 'Shotgun', 'loadout', 4, hint='Combat Shotgun'), {'text': '\n'}, button('Назад' if ru else 'Back', 'menu')]
    write('arsenal_' + language, ['tellraw @s ' + json.dumps(guns, ensure_ascii=False)])
    guide = [{'text': '\nПомощь\n' if ru else '\nGuide\n', 'color': 'gold'}, button('Запуск' if ru else 'Start', 'ui_start'), button('Управление' if ru else 'Controls', 'ui_ctrl'), button('Дроны' if ru else 'UAV', 'ui_uav'), button('Друзья' if ru else 'Friends', 'ui_friend')]
    write('guide_' + language, ['tellraw @s ' + json.dumps(guide, ensure_ascii=False), 'execute @s[tag=v_owner] ~ ~ ~ tellraw @s ' + json.dumps(button('Админ' if ru else 'Admin', 'ui_admin'), ensure_ascii=False)])
    admin = [{'text': 'Админ: ' if ru else 'Admin: ', 'color': 'dark_gray'}]
    for title, command in [('WorldEdit', '//wand'), ('Творческий' if ru else 'Creative', '/gamemode 1'), ('Выживание' if ru else 'Survival', '/gamemode 0'), ('Телепорт' if ru else 'Teleport', '/tp ')]:
        admin.append({'text': '[' + title + '] ', 'color': 'aqua', 'clickEvent': {'action': 'suggest_command', 'value': command}})
    write('admin_' + language, ['tellraw @s[tag=v_owner] ' + json.dumps(admin, ensure_ascii=False)])
    write('lang_' + language, ['scoreboard players set @s wlang ' + str(number), 'scoreboard players set @s lang_' + language + ' 0', 'function warfare:help', 'function warfare:drone_tip_' + language])
write('language', ['tellraw @s ' + json.dumps([{'text': '\nRV\nВыбери язык / Choose a language\n', 'color': 'gold'}, button('Русский', 'lang_ru', color='green'), button('English', 'lang_en')], ensure_ascii=False)])
write('arsenal', ['execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:arsenal_ru', 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:arsenal_en', 'scoreboard players set @s arsenal 0'])
write('guide', ['execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:guide_ru', 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:guide_en', 'scoreboard players set @s guide 0'])
write('ui_admin', ['execute @s[tag=v_owner,score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:guide_admin_ru', 'execute @s[tag=v_owner,score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:guide_admin_en', 'scoreboard players set @s ui_admin 0'])
write('drone_tip_ru', [message('Дрон: поставь → планшет → ПКМ по дрону. F8 — пульт и режим, Shift — выйти.')])
write('drone_tip_en', [message('UAV: place → tablet → right-click UAV. F8: controller/mode. Shift: exit.')])
write('adminhelp', ['execute @s[tag=v_owner,score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:admin_ru', 'execute @s[tag=v_owner,score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:admin_en'])
write('welcome', ['execute @s[tag=!w_ui2] ~ ~ ~ function warfare:init_ui', 'scoreboard players add @s wlang 0', 'scoreboard players add @s kills 0', 'title @s times 10 50 20', 'title @s title {"text":"RV","color":"gold"}', 'scoreboard players tag @s add w_seen', 'execute @s[tag=!w_kit] ~ ~ ~ function warfare:kit', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:entry_ru', 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:entry_en', 'execute @s[score_wlang=0] ~ ~ ~ function warfare:language'])
for language in ('ru', 'en'):
    write('guide_ctrl_' + language, [message('Управление танком и FPV — в книге. На HUD показаны текущие клавиши.' if language == 'ru' else 'Tank and FPV controls are in the book. The HUD shows current bindings.', 'gray'), 'function warfare:book_request'])
    write('guide_uav_' + language, ['function warfare:drone_tip_' + language, 'function warfare:book_request'])
write('help', ['execute @s[score_wlang=0] ~ ~ ~ function warfare:language', 'execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:help_ru', 'execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:help_en', 'scoreboard players set @s menu 0', 'scoreboard players enable @s menu'])
guides = {
    'start': ('Запусти RV. Для игры нажми Play / Играть. Владелец включает сервер отдельной кнопкой Start server / Запустить сервер. Остановить сервер можно кнопкой Stop server / Остановить сервер: мир сохранится. В клиентском окне укажи ник и код хозяина или выбери сохранённое подключение. Steam и Porthole должны быть запущены.', 'Open RV and click Play. The host uses the separate Start server button. Stop server saves the world before closing. In the client window choose a nickname and enter the host code or use a saved connection. Steam and Porthole must be running.'),
    'ctrl': ('T — чат; /trigger menu set 1 — меню. Tab — список игроков; в чате Tab дополняет команды и ники. J — карта, E — инвентарь и поиск JEI. Techguns: ЛКМ — огонь, ПКМ — прицел, R — перезарядка. MCH: W/S — газ, A/D — поворот, мышь — наклон; I — оборудование, G/средняя кнопка — смена оружия, Shift — выход. F8 — настройка USB-пульта, калибровка и режим FPV. Для FPS выключи шейдеры, поставь дальность 6–8 чанков и отключи облака. Звук: Options → Music & Sounds; Master, Players и Blocks выше нуля.', 'T: chat; /trigger menu set 1: menu. Tab: player list and chat command/name completion. J: map; E: inventory and JEI. Techguns: left click fire, right click aim, R reload. MCH: W/S throttle, A/D turn, mouse tilt; I equipment, G/middle mouse switch weapon, Shift exit. F8 opens USB controller selection, calibration and FPV mode. For higher FPS turn shaders off, use 6–8 chunks and disable clouds. Sound: Options → Music & Sounds; turn up Master, Players and Blocks.'),
    'uav': ('Поставь дрон на землю, возьми планшет и нажми ПКМ по дрону. Газ после подключения сброшен: поднимай его плавно. F8 — пульт, калибровка, Angle/Acro. Angle выравнивает дрон; Acro сохраняет наклон и требует практики. 50% газа держит высоту при горизонтальном положении. Shift — выход. Shift+ПКМ планшетом по свободному наземному дрону — выровнять перевёрнутый дрон. Перед подключением USB-пульта опусти газ вниз. Тренируйся в учебной зоне.', 'Place a UAV on the ground, hold the tablet and right-click the UAV. Throttle resets on connection: increase it smoothly. F8: controller, calibration, Angle/Acro. Angle levels the UAV; Acro holds attitude and needs practice. At level attitude, 50% throttle hovers. Shift exits. Shift+right-click with the tablet levels a free grounded UAV. Lower USB throttle before connecting. Practise in Training.'),
    'friend': ('Распакуй RV-Setup.zip, открой Install.cmd, затем Play. Все игроки используют одну версию сборки RV. Steam должен работать; введи текущий код хозяина в окне подключения. При смене кода обнови его там же. Porthole соединяет игроков через общий сеанс. Ник каждого игрока должен отличаться.', 'Extract RV-Setup.zip, open Install.cmd, then Play. Everyone uses the same RV pack version. Keep Steam running and enter the current host code in the connection window. If the code changes, update it there. Porthole connects players through the shared session. Each player needs a different nickname.'),
    'admin': ('WorldEdit: //wand выдаёт инструмент; ЛКМ/ПКМ выделяют два угла. //pos1 и //pos2 выделяют текущие позиции; //set, //copy, //paste, //undo изменяют выделение. /gamemode 1 — творчество, /gamemode 0 — выживание, /tp — телепорт. Админ-права проверяются сервером при подключении владельца.', 'WorldEdit: //wand gives the selection tool; left/right click select two corners. //pos1 and //pos2 select your current position; //set, //copy, //paste and //undo edit the selection. /gamemode 1: creative; /gamemode 0: survival; /tp: teleport. The server verifies owner permissions on connection.'),
}
for topic, texts in guides.items():
    if topic in ('ctrl', 'uav'):
        continue
    for language, text in zip(['ru', 'en'], texts):
        prefix = 'execute @s[tag=v_owner] ~ ~ ~ ' if topic == 'admin' else ''
        write('guide_' + topic + '_' + language, [prefix + message(text, 'white')])
for name, cooldown in [('kit', 'w_supply'), ('loadout_assault', 'w_supply'), ('loadout_sniper', 'w_supply'), ('loadout_support', 'w_supply'), ('loadout_breacher', 'w_supply'), ('drone', 'w_drone'), ('wing', 'w_wing'), ('ammo', 'w_ammo')]:
    path = root / (name + '.mcfunction')
    commands = [line for line in path.read_text(encoding='utf-8').splitlines() if not ('tellraw ' in line or 'function warfare:drone_tip_' in line or line.startswith('scoreboard players set @s ' + cooldown))]
    commands.insert(0, 'scoreboard players set @s w_given 0')
    commands += ['scoreboard players set @s ' + cooldown + ' 20', 'execute @s[score_w_given_min=1] ~ ~ ~ scoreboard players set @s ' + cooldown + (' 40' if name.startswith('loadout_') else ' 100'), 'function warfare:space', 'function warfare:supply_result']
    if name == 'drone':
        commands += ['execute @s[score_w_given_min=1,score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:drone_tip_ru', 'execute @s[score_w_given_min=1,score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:drone_tip_en']
    write(name, commands)
write('supply_result', ['execute @s[score_w_given_min=1,score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Снаряжение пополнено.'), 'execute @s[score_w_given_min=1,score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('Supplies added.'), 'execute @s[score_w_given=0,score_w_free_min=1,score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Снаряжение уже есть.', 'gray', True), 'execute @s[score_w_given=0,score_w_free_min=1,score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('Already supplied.', 'gray', True), 'execute @s[score_w_free=0,score_wlang=1,score_wlang_min=1] ~ ~ ~ ' + message('Инвентарь полон. Освободи один слот.', 'yellow', True), 'execute @s[score_w_free=0,score_wlang=2,score_wlang_min=2] ~ ~ ~ ' + message('Inventory full. Make one free slot.', 'yellow', True)])

tick = ['execute @a[tag=!w_ui2] ~ ~ ~ function warfare:init_ui', 'scoreboard players add @a w_wing 0', 'scoreboard players remove @a[score_w_supply_min=1] w_supply 1', 'scoreboard players remove @a[score_w_drone_min=1] w_drone 1', 'scoreboard players remove @a[score_w_wing_min=1] w_wing 1', 'scoreboard players remove @a[score_w_ammo_min=1] w_ammo 1', 'scoreboard players set @a w_admin 0', 'scoreboard players set @a[tag=v_owner] w_admin 1', 'execute @a[score_kit_min=1,score_kit=1,score_w_supply_min=1] ~ ~ ~ function warfare:wait_supply', 'execute @a[score_loadout_min=1,score_loadout=4,score_w_supply_min=1] ~ ~ ~ function warfare:wait_supply', 'execute @a[score_kit_min=1,score_kit=1,score_w_supply=0] ~ ~ ~ function warfare:kit']
for index, role in enumerate(['assault', 'sniper', 'support', 'breacher'], 1):
    tick.append('execute @a[score_loadout_min=' + str(index) + ',score_loadout=' + str(index) + ',score_w_supply=0] ~ ~ ~ function warfare:loadout_' + role)
tick += ['execute @a[score_drone_min=1,score_drone=1,score_w_drone_min=1] ~ ~ ~ function warfare:wait_drone', 'execute @a[score_drone_min=1,score_drone=1,score_w_drone=0] ~ ~ ~ function warfare:drone', 'execute @a[score_ammo_min=1,score_ammo=1,score_w_ammo_min=1] ~ ~ ~ function warfare:wait_ammo', 'execute @a[score_ammo_min=1,score_ammo=1,score_w_ammo=0] ~ ~ ~ function warfare:ammo']
tick += ['execute @a[score_wing_min=1,score_wing=1,score_w_wing_min=1] ~ ~ ~ function warfare:wait_wing', 'execute @a[score_wing_min=1,score_wing=1,score_w_wing=0] ~ ~ ~ function warfare:wing']
actions = {'menu': 'help', 'blue': 'blue', 'red': 'red', 'lobby': 'lobby', 'spawn': 'spawn', 'sound': 'sound', 'lang_ru': 'lang_ru', 'lang_en': 'lang_en', 'guide': 'guide', 'ui_start': 'ui_start', 'ui_ctrl': 'ui_ctrl', 'ui_uav': 'ui_uav', 'ui_friend': 'ui_friend', 'arsenal': 'arsenal', 'training': 'training'}
tick += ['execute @a[score_' + key + '_min=1,score_' + key + '=1] ~ ~ ~ function warfare:' + value for key, value in actions.items()]
tick += ['execute @a[tag=v_owner,score_ui_admin_min=1,score_ui_admin=1] ~ ~ ~ function warfare:ui_admin', 'scoreboard players set @a[tag=!v_owner] ui_admin 0', 'scoreboard players enable @a[tag=v_owner] ui_admin']
triggers = list(actions) + ['kit', 'drone', 'wing', 'ammo']
for key in triggers:
    tick += ['scoreboard players set @a[score_' + key + '=-1] ' + key + ' 0', 'scoreboard players set @a[score_' + key + '_min=2] ' + key + ' 0', 'scoreboard players enable @a ' + key]
tick += ['scoreboard players set @a[score_loadout=-1] loadout 0', 'scoreboard players set @a[score_loadout_min=5] loadout 0', 'scoreboard players enable @a loadout', 'scoreboard players set @a[score_ui_admin=-1] ui_admin 0', 'scoreboard players set @a[score_ui_admin_min=2] ui_admin 0', 'function warfare:book_tick']
tick.insert(1, 'execute @a[tag=!w_seen] ~ ~ ~ function warfare:welcome')
write('tick', tick)
setup = ['scoreboard objectives add ' + key + ' dummy' for key in ['wlang', 'w_supply', 'w_drone', 'w_wing', 'w_ammo', 'w_class', 'w_probe', 'w_used', 'w_free', 'w_given', 'w_admin']]
setup += ['scoreboard objectives add kills playerKillCount Kills']
setup += ['scoreboard objectives add ' + key + ' trigger' for key in sorted(set(triggers + ['loadout', 'ui_admin']))]
setup += ['function warfare:book_setup', 'scoreboard teams add blue Blue', 'scoreboard teams add red Red', 'scoreboard teams option blue color blue', 'scoreboard teams option red color red', 'scoreboard teams option blue friendlyfire false', 'scoreboard teams option red friendlyfire false', 'scoreboard objectives setdisplay sidebar kills', 'gamerule keepInventory true', 'gamerule doMobSpawning false', 'gamerule doFireTick true', 'gamerule mobGriefing true', 'gamerule spawnRadius 0', 'setworldspawn 0 65 -210', 'gamerule gameLoopFunction warfare:tick', 'worldborder center 0 0', 'worldborder set 1280']
write('boot', setup)
(args.output / 'setup-commands.txt').write_text('\n'.join(setup) + '\n', encoding='utf-8')
print(json.dumps({'functions': len(list(root.glob('*.mcfunction'))), 'generated': str(root)}))
