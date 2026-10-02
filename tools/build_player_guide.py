import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local/player-guide'
TRIGGER = '/trigger wbook set 1'
MARKER = '{Inventory:[{id:"minecraft:written_book",tag:{rvGuide:1b}}]}'
OBJECTIVES = {'wbook': 'trigger', 'wbOnce': 'dummy', 'wbPending': 'dummy', 'wbWait': 'dummy', 'wbUsed': 'dummy', 'wbHas': 'dummy'}


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
            page('RV · Начало', 'T — чат\nE — инвентарь\nJ — карта', 'Меню:\n/trigger menu set 1', 'Потерял книгу?\nМеню → «Книга»\n' + TRIGGER),
            page('Оружие', 'ЛКМ — огонь\nПКМ — прицел\nR — перезарядка', 'Не сработало? Проверь назначения в Настройки → Управление.'),
            page('Дрон', 'Поставь дрон. Возьми планшет и нажми ПКМ по дрону.', 'W/S — газ\nA/D — поворот\nМышь — наклон\nShift — выйти', 'Газ после подключения сброшен.'),
            page('Полёт', 'Angle — по умолчанию. Отпусти управление: дрон выровняется.', 'Acro выбирается в F8. Он сохраняет наклон: выравнивай сам.', 'Газ с клавиатуры сам не снижается.'),
            page('Боевой дрон', 'После взлёта удар о технику или блоки вызывает взрыв.', 'Ставь его на ровное место. Для первых полётов используй учебную зону.'),
            page('После переворота', 'Выйди из управления. Нажми Shift + ПКМ планшетом по свободному дрону на земле.', 'Дрон выровняется, газ сбросится. В воздухе это не работает.'),
            page('Пульт · F8', 'Подключи USB-пульт в режиме Joystick.', 'В F8 выбери устройство и оси: крен, тангаж, поворот, газ.', 'Откалибруй центр и полный ход. Проверь инверсию и сохрани.'),
            page('Перед взлётом', 'На пульте опусти газ до минимума. На геймпаде верни стик газа в центр.', 'При потере USB или фокуса окна газ сбрасывается.', 'Если устройство не найдено, проверь USB Joystick и F8.'),
            page('Если мало FPS', 'Сначала выключи шейдеры. Поставь дальность 6–8 чанков, частицы — уменьшенные.', 'Проверь FPS через F3. Меняй настройки по одной.', 'Закрой лишние приложения.'),
            page('FPS или сервер?', 'Картинка идёт рывками, FPS падает — снижай графику.', 'Картинка плавная, но блоки возвращаются и действия запаздывают — проверь связь и сервер.'),
        ]
    if language == 'en':
        return [
            page('RV · Start here', 'T — chat\nE — inventory\nJ — map', 'Menu:\n/trigger menu set 1', 'Lost this book?\nMenu → Book\n' + TRIGGER),
            page('Weapons', 'Left click — fire\nRight click — aim\nR — reload', 'No response? Check your key bindings in Options → Controls.'),
            page('UAV', 'Place the UAV. Hold the tablet and right-click the UAV.', 'W/S — throttle\nA/D — turn\nMouse — tilt\nShift — exit', 'Connecting resets throttle.'),
            page('Flight', 'Angle is the default. Release the controls to level out.', 'Choose Acro in F8. It keeps your tilt; level out yourself.', 'Keyboard throttle stays where you leave it.'),
            page('Combat UAV', 'After takeoff, hitting a vehicle or block triggers the bomb.', 'Place it on level ground. Practise your first flights in Training.'),
            page('After a flip', 'Exit the controls. Hold the tablet and Shift + right-click an empty UAV on the ground.', 'This levels the UAV and resets throttle. It does not work in the air.'),
            page('Controller · F8', 'Connect your USB radio in Joystick mode.', 'In F8, select the device and map roll, pitch, yaw and throttle.', 'Calibrate centre and full travel. Check inversion, then save.'),
            page('Before takeoff', 'Radio: lower throttle fully. Gamepad: centre the throttle stick.', 'Losing USB input or window focus cuts throttle.', 'No device? Check USB Joystick mode and F8.'),
            page('Low FPS?', 'Turn shaders off first. Set render distance to 6–8 chunks and reduce particles.', 'Check FPS with F3. Change one setting at a time.', 'Close unused apps.'),
            page('FPS or server?', 'Choppy picture and low FPS? Lower graphics settings.', 'Smooth picture, but blocks return or actions are delayed? Check the connection and server.'),
        ]
    raise ValueError('Language must be ru or en')


def quoted(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def book_nbt(language):
    title = 'RV · Памятка' if language == 'ru' else 'RV · Field guide'
    encoded = [quoted(json.dumps(value, ensure_ascii=False, separators=(',', ':'))) for value in pages(language)]
    return '{title:' + quoted(title) + ',author:"RV",generation:0,rvGuide:1b,rvGuideVersion:1,pages:[' + ','.join(encoded) + ']}'


def functions():
    result = {
        'book_setup': [f'scoreboard objectives add {name} {kind}' for name, kind in OBJECTIVES.items()],
        'book_tick': [
            'scoreboard players enable @a wbook',
            'scoreboard players add @a wbOnce 0',
            'scoreboard players add @a wbPending 0',
            'execute @a[score_wbOnce=0,score_wbPending=0] ~ ~ ~ function warfare:book_welcome',
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
            'scoreboard players set @s wbHas 1 ' + MARKER,
            'execute @s[score_wbHas_min=1] ~ ~ ~ function warfare:book_confirm',
        ],
        'book_confirm': [
            'scoreboard players set @s wbOnce 1',
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
    return '''# RV player book integration

Copy warfare/book_*.mcfunction into the world's data/functions/warfare folder while the server is stopped, then reload functions or restart.

Run `function warfare:book_setup` from the server console once per world. Re-running setup preserves all scores; existing-objective messages are harmless. The base package owns the existing `wlang` objective: 1 = Russian, 2 = English. A missing, zero or unsupported language waits for a selection.

Append `function warfare:book_tick` to the existing `warfare:tick` function AFTER language-selection handlers and starting-kit grants. Do not replace gameLoopFunction or the existing tick. The tick function runs in server context and discovers both existing and new players. Its first check is immediate, then pending requests retry every 20 game ticks (about one second at 20 TPS).

Optional welcome hook: `function warfare:book_welcome` after starting-kit grants, with @s bound to the joining player. This queues the initial book only if wbOnce is zero; the regular tick also handles discovery without the hook.

Add a Book / Книга button in BOTH player menus: clickEvent action run_command, value `/trigger wbook set 1`. This command is available to non-operators. To request from an existing function, call `function warfare:book_request` with @s bound to that player. Do not replace the existing guide trigger, which opens chat help. Mention that a full inventory needs one free main slot.

Only book_setup and book_tick may run directly in console context. All other book functions require one player as @s, for example `execute PlayerName ~ ~ ~ function warfare:book_request`.

The six new objectives are wbook (trigger), wbOnce, wbPending, wbWait, wbUsed, wbHas (dummy). Names fit the 1.12.2 limit. wbOnce is the persistent completion marker: do not reset it on login, death, startup or upgrades. Pending state is persistent, too. A dropped/lost book is replaced only on explicit request. Existing guide books in main inventory or offhand prevent duplicate copies, regardless of selected language. The item marker is rvGuide:1b, version rvGuideVersion:1.

Delivery counts occupied main slots 0–35; armour and offhand are not free main slots. The give command runs only with at least one empty main slot. After give, the item marker is read back before setting wbOnce=1 or clearing wbPending. No inventory clearing or replacement is used. Full inventories do not receive dropped books. After confirmed delivery, no inventory scan runs until another explicit request.

Run `python qa/test_player_guide.py`. For vanilla 1.12.2 parser and NBT matching verification, also pass `--vanilla-jar <minecraft_server.1.12.2.jar> --java <Java-8-bin/java.exe>`. Optional `--functions <path/to/warfare>` audits the integrated functions instead of the isolated artifact. The harness executes the generated command subset; it is not a multiplayer runtime or a rendered-book test. Final integration still requires a real non-operator joining, reading both locales, filling all 36 main slots and making room, reconnecting, restarting, and requesting a lost book.
'''


def build(output=OUTPUT):
    output = Path(output).resolve()
    if output != OUTPUT.resolve():
        raise ValueError('Only .local/player-guide is an allowed build destination')
    destination = output / 'warfare'
    destination.mkdir(parents=True, exist_ok=True)
    rendered = functions()
    for name, commands in rendered.items():
        if not re.fullmatch(r'book_[a-z_]+', name):
            raise ValueError('Invalid function name')
        (destination / (name + '.mcfunction')).write_text('\n'.join(commands) + '\n', encoding='utf-8')
    (output / 'INTEGRATION.md').write_text(integration(), encoding='utf-8')
    return destination


if __name__ == '__main__':
    argparse.ArgumentParser(description='Build isolated RV player-book functions for Minecraft 1.12.2.').parse_args()
    print(build())
