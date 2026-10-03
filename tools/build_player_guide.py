import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local/player-guide'
TRIGGER = '/trigger wbook set 1'
EDITION = 4
MARKER = '{Inventory:[{id:"minecraft:written_book",tag:{rvGuide:1b,rvGuideVersion:' + str(EDITION) + '}}]}'
LANGUAGE_MARKERS = {code: MARKER.replace('rvGuideVersion:', 'rvGuideLang:' + str(code) + 'b,rvGuideVersion:') for code in (1, 2)}
OBJECTIVES = {'wbook': 'trigger', 'wbOnce': 'dummy', 'wbPending': 'dummy', 'wbWait': 'dummy', 'wbUsed': 'dummy', 'wbHas': 'dummy', 'wbEdition': 'dummy'}


def width(text):
    return sum(4 if char == ' ' else 3 if char in '.,:;!iIl\'|' else 8 if char in 'MWmwЖШЩЫЮжшщыю' else 6 for char in text)


def page(title, *paragraphs):
    lines = []
    for paragraph in (title, *paragraphs):
        if lines:
            lines.append('')
        for line in paragraph.splitlines():
            current = ''
            for word in line.split(' '):
                if width(word) > 114:
                    raise ValueError(f'Book word is too wide: {word}')
                candidate = current + (' ' if current else '') + word
                if current and width(candidate) > 114:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
    if len(lines) > 14:
        raise ValueError(f'Book page needs {len(lines)} lines: {title}')
    return {'text': '\n'.join(lines)}


def pages(language):
    if language == 'ru':
        return [
            page('RV · Начало', 'T — чат\nE — инвентарь\nJ — карта', 'F7 — меню игры', 'Потерял книгу?\nF7 → «Руководство»\n' + TRIGGER),
            page('Первый запуск', 'В «Играть» выбери мышь и клавиатуру либо USB-пульт.', 'Для пульта выбери устройство и проверь оси. Затем выбери сервер.', 'Настройку можно повторить в лаунчере.'),
            page('Спавн', 'Общая площадка:\nX: 0\nY: 65\nZ: -210', 'Вернуться:\n/trigger spawn set 1', 'Для всех игроков. Команду выбери в меню.'),
            page('Снаряжение', 'F7 → Снаряжение', 'Выбери оружие, магазины, еду, броню и дроны.', 'Проверь набор, затем подтверди выдачу. Можно оставить свои вещи.'),
            page('Пополнение', 'Полный инвентарь? Освободи место: набор выдаётся целиком.', 'Повторная выдача — через 10 секунд.', 'Проверь магазины. Патроны разных модов не подходят друг к другу.'),
            page('Режим игры', 'F7 → Сессия', 'Свободная игра — без раунда. Тренировка — для полётов и стрельбы.', 'Для командного раунда выбери команду и снаряжение.'),
            page('Начало раунда', 'Подтверди набор или оставь свои вещи. Нажми «Готов».', 'Старт — по голосам готовых игроков. Нужны обе команды.', 'До конца отсчёта старт можно отменить.'),
            page('Оружие', 'ЛКМ — огонь\nПКМ — прицел\nR — перезарядка', 'Не сработало? Проверь назначения в Настройки → Управление.'),
            page('Танк', 'ПКМ — сесть.\nW/A/S/D — ехать.\nМышь — навести.\nЛКМ — выстрел.', 'G / СКМ — оружие.\nZ — приближение.\nY — выйти.', 'По умолчанию.\nТекущие — на HUD.'),
            page('Боекомплект', 'R — перезарядка.\nI — груз техники.', 'Проверь боекомплект и выбранное оружие на HUD.', 'Пассажирское место может не управлять пушкой.'),
            page('Попадание', 'ПОПАДАНИЕ — без потери HP.', 'УРОН −N — минус N HP.', 'УНИЧТОЖЕНО — цель разрушена.', 'Эту метку подтверждает сервер.'),
            page('Ранения', 'Выйди из техники.\nH — осмотр ран.', 'Здоровье рук, ног, головы и тела учитывается отдельно.', 'Проверь клавишу:\nНастройки → Управление\nFirst Aid'),
            page('Бинты', 'Возьми бинт или пластырь. Нажми ПКМ.', 'Удерживай кнопку раненой части тела до конца.', 'Здоровье восстанавливается постепенно. Пополни запас через «Набор».'),
            page('FPV-коптер', 'Поставь FPV. Возьми планшет и нажми ПКМ по коптеру.', 'Мышь — смотреть и поворачивать.\nShift — выйти.', 'Easy — обычный режим для мыши и клавиатуры.'),
            page('Полёт · Easy', 'W/S — вперёд/назад\nA/D — влево/вправо\nSpace — вверх\nЛевый Ctrl — вниз', 'Отпусти кнопки: коптер тормозит и зависает.', 'Это клавиши по умолчанию. Текущие — на HUD.'),
            page('Взлёт · Easy', 'После подключения на земле нажми Space для взлёта.', 'При потере фокуса окна двигатель отключается. Коптер снижается.', 'Вернись в окно и нажми Space, чтобы продолжить полёт.'),
            page('Боевой FPV', 'После взлёта удар о технику или блоки вызывает взрыв.', 'Ставь его на ровное место. Для первых полётов используй учебную зону.'),
            page('После переворота', 'Выйди из управления. Нажми Shift + ПКМ планшетом по свободному дрону на земле.', 'Дрон выровняется, газ сбросится. В воздухе это не работает.'),
            page('Герань и FP-1', 'Нужна ровная свободная полоса. Поставь самолёт, возьми планшет и нажми ПКМ по нему.', 'W — набрать газ.\nМышь — наклон.\nS — убавить газ.\nY — выйти.'),
            page('Полёт самолёта', 'A/D — крен влево/вправо.', 'Самолёту нужна скорость. Он не зависает.', 'При выходе газ сбрасывается. Самолёт продолжает двигаться и снижается.'),
            page('Пульт · F8', 'Подключи USB-пульт в режиме Joystick.', 'В F8 выбери устройство и оси: крен, тангаж, поворот, газ.', 'Откалибруй центр и полный ход. Проверь инверсию и сохрани.'),
            page('Режимы пульта', 'Angle выравнивает коптер, когда отпускаешь стики.', 'Acro сохраняет наклон: выравнивай сам.', 'Выбор — в F8.\nНа клавиатуре начни с Easy.'),
            page('Перед взлётом', 'На пульте опусти газ до минимума. На геймпаде верни стик газа в центр.', 'При потере USB или фокуса окна газ сбрасывается.', 'Если устройство не найдено, проверь USB Joystick и F8.'),
            page('Качество', 'В лаунчере открой Настройки → Профиль.', 'Low — меньше эффектов.\nBalanced — обычный.\nQuality — подробнее.', 'Если мало FPS, начни с Low.'),
            page('Если мало FPS', 'Выключи шейдеры. Начни с дальности 4–6 чанков, частицы — уменьшенные.', 'Проверь FPS через F3. Меняй настройки по одной.', 'Закрой лишние приложения.'),
            page('FPS или сервер?', 'Картинка идёт рывками, FPS падает — снижай графику.', 'Картинка плавная, но блоки возвращаются и действия запаздывают — проверь связь и сервер.'),
            page('Звуки окружения', 'Фон природы задаёт AmbientSounds. Громкость зависит от профиля лаунчера.', 'Если фон мешает слышать мотор и выстрелы, начни с Low.', 'Громкость игры:\nНастройки → Звуки'),
            page('Инвентарь', 'Mouse Tweaks помогает перекладывать вещи в инвентаре.', 'Закрой его перед полётом, стрельбой или лечением.', 'Для нового набора нужны свободные слоты.'),
            page('ModularWarfare', 'ЛКМ — огонь\nПКМ — прицел\nR — перезарядка\nV — режим огня', 'N — осмотреть оружие.\nU — извлечь магазин.\nF6 — фонарь.', 'Это клавиши новой оружейной системы.'),
            page('Магазины', 'Для ModularWarfare нужны свои магазины и патроны.', 'Патроны Techguns к этому оружию не подходят.', 'Если R не работает, проверь нужный магазин в инвентаре.'),
        ]
    if language == 'en':
        return [
            page('RV · Start here', 'T — chat\nE — inventory\nJ — map', 'F7 — game menu', 'Lost this book?\nF7 → Guide\n' + TRIGGER),
            page('First launch', 'In Play, choose mouse and keyboard or a USB controller.', 'Select your device and check its axes. Then choose a server.', 'Repeat setup in launcher settings.'),
            page('Spawn', 'Shared lobby:\nX: 0\nY: 65\nZ: -210', 'Return:\n/trigger spawn set 1', 'Everyone can use it. Choose your team in the menu.'),
            page('Equipment', 'F7 → Gear', 'Choose your weapon, magazines, food, armour and drones.', 'Check the preview, then confirm. You can keep your existing gear.'),
            page('Resupply', 'Inventory full? Make room: the whole kit must fit.', 'Wait 10 seconds before requesting another kit.', 'Check magazines. Ammo from different mods does not interchange.'),
            page('Game mode', 'F7 → Session', 'Free play has no round. Training is for flying and shooting.', 'For a team round, choose your team and equipment.'),
            page('Starting a round', 'Confirm a kit or keep your gear. Press Ready.', 'Ready players vote to start. Both teams are required.', 'You can cancel before the countdown ends.'),
            page('Weapons', 'Left click — fire\nRight click — aim\nR — reload', 'No response? Check your key bindings in Options → Controls.'),
            page('Tank', 'Right click — enter.\nW/A/S/D — drive.\nMouse — aim.\nLeft click — fire.', 'G / middle click — weapon.\nZ — zoom.\nY — exit.', 'Default keys.\nCurrent keys: HUD.'),
            page('Ammunition', 'R — reload.\nI — vehicle cargo.', 'Check your ammunition and selected weapon on the HUD.', 'A passenger seat may not control the cannon.'),
            page('Impact', 'HIT · no damage — HP did not decrease.', 'DAMAGE −N — lost N HP.', 'DESTROYED — target destroyed.', 'The server confirms this marker.'),
            page('Wounds', 'Leave the vehicle.\nH — check wounds.', 'Arms, legs, head and body have separate health.', 'Check the binding:\nOptions → Controls\nFirst Aid'),
            page('Bandages', 'Hold a bandage or plaster. Right-click.', 'Hold the injured body part button until it finishes.', 'Healing is gradual. Refill supplies through Kit.'),
            page('FPV quad', 'Place the FPV. Hold the tablet and right-click the quad.', 'Mouse — look and turn.\nShift — exit.', 'Easy is the standard mouse and keyboard mode.'),
            page('Flight · Easy', 'W/S — forward/back\nA/D — left/right\nSpace — up\nLeft Ctrl — down', 'Release the keys: the quad brakes and hovers.', 'Default keys.\nCurrent keys: HUD.'),
            page('Takeoff · Easy', 'After connecting on the ground, press Space to take off.', 'Losing window focus cuts the motor. The quad descends.', 'Return to the window and press Space to resume flight.'),
            page('Impact FPV', 'After takeoff, hitting a vehicle or block triggers the bomb.', 'Place it on level ground. Practise your first flights in Training.'),
            page('After a flip', 'Exit the controls. Hold the tablet and Shift + right-click an empty UAV on the ground.', 'This levels the UAV and resets throttle. It does not work in the air.'),
            page('Geran and FP-1', 'Use a clear, level runway. Place the aircraft, hold the tablet and right-click it.', 'W — increase throttle.\nMouse — pitch.\nS — reduce throttle.\nY — exit.'),
            page('Fixed-wing flight', 'A/D — bank left/right.', 'An aircraft needs speed to fly. It cannot hover.', 'Leaving the controls cuts throttle. The aircraft keeps moving and descends.'),
            page('Controller · F8', 'Connect your USB radio in Joystick mode.', 'In F8, select the device and map roll, pitch, yaw and throttle.', 'Calibrate centre and full travel. Check inversion, then save.'),
            page('Radio modes', 'Angle levels the quad when you release the sticks.', 'Acro keeps your tilt; level out yourself.', 'Choose in F8.\nStart with Easy when using a keyboard.'),
            page('Before takeoff', 'Radio: lower throttle fully. Gamepad: centre the throttle stick.', 'Losing USB input or window focus cuts throttle.', 'No device? Check USB Joystick mode and F8.'),
            page('Quality', 'Open Settings → Profile in the launcher.', 'Low — fewer effects.\nBalanced — standard.\nQuality — more detail.', 'Start with Low if FPS is low.'),
            page('Low FPS?', 'Turn shaders off. Start with 4–6 chunks of render distance and reduce particles.', 'Check FPS with F3. Change one setting at a time.', 'Close unused apps.'),
            page('FPS or server?', 'Choppy picture and low FPS? Lower graphics settings.', 'Smooth picture, but blocks return or actions are delayed? Check the connection and server.'),
            page('Ambient sounds', 'AmbientSounds adds nature sounds. The launcher profile sets their volume.', 'Start with Low if the background masks engines or gunfire.', 'Game volume:\nOptions → Sounds'),
            page('Inventory', 'Mouse Tweaks helps move items while your inventory is open.', 'Close inventory before flying, firing or healing.', 'Keep free slots before requesting a kit.'),
            page('ModularWarfare', 'Left click — fire\nRight click — aim\nR — reload\nV — fire mode', 'N — inspect.\nU — unload magazine.\nF6 — flashlight.', 'These keys belong to the new weapon system.'),
            page('Magazines', 'ModularWarfare uses its own magazines and ammunition.', 'Techguns ammunition does not fit these weapons.', 'If R does nothing, check for a compatible magazine in inventory.'),
        ]
    raise ValueError('Language must be ru or en')


def quoted(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def book_nbt(language):
    title = 'RV · Памятка' if language == 'ru' else 'RV · Field guide'
    encoded = [quoted(json.dumps(value, ensure_ascii=False, separators=(',', ':'))) for value in pages(language)]
    return '{title:' + quoted(title) + ',author:"RV",generation:0,rvGuide:1b,rvGuideLang:' + ('1b' if language == 'ru' else '2b') + ',rvGuideVersion:' + str(EDITION) + ',pages:[' + ','.join(encoded) + ']}'


def functions():
    result = {
        'book_setup': [f'scoreboard objectives add {name} {kind}' for name, kind in OBJECTIVES.items()],
        'book_tick': [
            'scoreboard players enable @a wbook',
            'scoreboard players add @a wbOnce 0',
            'scoreboard players add @a wbPending 0',
            'scoreboard players add @a wbEdition 0',
            'execute @a[score_wbOnce=0,score_wbPending=0] ~ ~ ~ function warfare:book_welcome',
            f'execute @a[score_wbOnce_min=1,score_wbEdition={EDITION - 1},score_wbPending=0] ~ ~ ~ function warfare:book_queue',
            'execute @a[score_wbook_min=1] ~ ~ ~ function warfare:book_request',
            'scoreboard players add @a[score_wbPending_min=1] wbWait 1',
            'execute @a[score_wbPending_min=1,score_wbWait_min=20] ~ ~ ~ function warfare:book_check',
        ],
        'book_welcome': [
            'scoreboard players add @s wbOnce 0',
            'execute @s[score_wbOnce=0] ~ ~ ~ function warfare:book_queue',
        ],
        'book_queue': ['scoreboard players set @s wbPending 1', 'scoreboard players set @s wbWait 19'],
        'book_request': [
            'scoreboard players set @s wbook 0',
            'scoreboard players enable @s wbook',
            'function warfare:book_queue',
        ],
        'book_check': [
            'scoreboard players set @s wbWait 0',
            'function warfare:book_verify',
            'execute @s[score_wbPending_min=1,score_wlang_min=1,score_wlang=2] ~ ~ ~ function warfare:book_space',
        ],
        'book_verify': [
            'scoreboard players set @s wbHas 0',
            'scoreboard players set @s[score_wlang_min=1,score_wlang=1] wbHas 1 ' + LANGUAGE_MARKERS[1],
            'scoreboard players set @s[score_wlang_min=2,score_wlang=2] wbHas 1 ' + LANGUAGE_MARKERS[2],
            'execute @s[score_wbHas_min=1] ~ ~ ~ function warfare:book_confirm',
        ],
        'book_confirm': [
            'scoreboard players set @s wbOnce 1',
            f'scoreboard players set @s wbEdition {EDITION}',
            'scoreboard players set @s wbPending 0',
            'scoreboard players set @s wbWait 0',
        ],
        'book_space': ['scoreboard players set @s wbUsed 0'] + [
            f'scoreboard players add @s wbUsed 1 {{Inventory:[{{Slot:{slot}b}}]}}' for slot in range(36)
        ] + [
            f'execute @s[score_wbUsed=35,score_wlang_min={code},score_wlang={code}] ~ ~ ~ function warfare:book_give_{language}'
            for code, language in ((1, 'ru'), (2, 'en'))
        ],
    }
    for language in ('ru', 'en'):
        result[f'book_give_{language}'] = ['give @s minecraft:written_book 1 0 ' + book_nbt(language), 'function warfare:book_verify']
    return result


def integration():
    return f'''# RV player book integration

Copy warfare/book_*.mcfunction into the world's data/functions/warfare folder while the server is stopped, then reload functions or restart.

Run `function warfare:book_setup` from the server console once per world. Re-running setup preserves all scores; existing-objective messages are harmless. The base package owns the existing `wlang` objective: 1 = Russian, 2 = English. A missing, zero or unsupported language waits for a selection.

Append `function warfare:book_tick` to the existing `warfare:tick` function AFTER language-selection handlers. Joining must not grant a combat kit: players choose and confirm equipment in the RV experience menu. Do not replace gameLoopFunction or the existing tick. The tick function runs in server context and discovers both existing and new players. Its first check is immediate, then pending requests retry every 20 game ticks (about one second at 20 TPS).

Optional welcome hook: `function warfare:book_welcome` after starting-kit grants, with @s bound to the joining player. This queues the initial book only if wbOnce is zero; the regular tick also handles discovery without the hook.

The native F7 Session menu opens the guide through its Guide / Руководство button. Legacy chat menus use clickEvent action run_command, value `/trigger wbook set 1`. This command is available to non-operators. To request from an existing function, call `function warfare:book_request` with @s bound to that player. Do not replace the existing guide trigger, which opens chat help. Mention that a full inventory needs one free main slot.

Only book_setup and book_tick may run directly in console context. All other book functions require one player as @s, for example `execute PlayerName ~ ~ ~ function warfare:book_request`.

The seven objectives are wbook (trigger), wbOnce, wbPending, wbWait, wbUsed, wbHas and wbEdition (dummy). Names fit the 1.12.2 limit. wbOnce is the persistent completion marker: do not reset it on login, death, startup or upgrades. Pending state is persistent, too. wbEdition records the latest confirmed edition. Run book_setup on an existing world to add wbEdition without resetting old scores.

Edition {EDITION} is delivered once to existing players with wbOnce=1 and wbEdition below {EDITION}. Older books and other inventory items remain intact; a full inventory waits for one free main slot. A current edition in the selected language, in main inventory or offhand, confirms the request without another copy. Changing language does not add a book automatically; explicitly requesting the other language preserves the existing book and adds the selected translation once space is available. After confirmation, losing this edition does not trigger an automatic replacement; use the explicit request instead. The item marker is rvGuide:1b with rvGuideVersion:{EDITION} and rvGuideLang:1b (Russian) or 2b (English).

Delivery counts occupied main slots 0–35; armour and offhand are not free main slots. The give command runs only with at least one empty main slot. After give, the item marker is read back before setting wbOnce=1 or clearing wbPending. No inventory clearing or replacement is used. Full inventories do not receive dropped books. After confirmed delivery, no inventory scan runs until another explicit request.

Run `python qa/test_player_guide.py`. For vanilla 1.12.2 parser and NBT matching verification, also pass `--vanilla-jar <minecraft_server.1.12.2.jar> --java <Java-8-bin/java.exe>`. Optional `--functions <path/to/warfare>` audits the integrated functions instead of the isolated artifact. The harness executes the generated command subset; it is not a multiplayer runtime or a rendered-book test. Final integration still requires a real non-operator joining, reading both locales, filling all 36 main slots and making room, reconnecting, restarting, and requesting a lost book.
'''


def build(output=OUTPUT):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.local').resolve()):
        raise ValueError('Player-guide output must remain inside the workspace .local directory')
    destination = output / 'warfare'
    destination.mkdir(parents=True, exist_ok=True)
    rendered = functions()
    for name, commands in rendered.items():
        if not re.fullmatch(r'book_[a-z_]+', name):
            raise ValueError('Invalid function name')
        (destination / (name + '.mcfunction')).write_text('\n'.join(commands) + '\n', encoding='utf-8', newline='\n')
    (output / 'INTEGRATION.md').write_text(integration(), encoding='utf-8', newline='\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build isolated RV player-book functions for Minecraft 1.12.2.')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(build(arguments.output))
