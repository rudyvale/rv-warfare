import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('player_guide_builder', ROOT / 'tools/build_player_guide.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
FUNCTION_ROOT = builder.OUTPUT / 'warfare'


class Snbt:
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def space(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def take(self, expected):
        self.space()
        if self.text[self.pos:self.pos + 1] != expected:
            raise ValueError(f'Expected {expected} at {self.pos}')
        self.pos += 1

    def string(self):
        self.take('"')
        result = ''
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == '"':
                return result
            if char == '\\':
                char = self.text[self.pos]
                self.pos += 1
                if char not in ('"', '\\'):
                    raise ValueError('Unsupported 1.12.2 SNBT escape')
            result += char
        raise ValueError('Unterminated SNBT string')

    def value(self):
        self.space()
        char = self.text[self.pos]
        if char == '"':
            return self.string()
        if char == '{':
            self.pos += 1
            result = {}
            self.space()
            while self.text[self.pos] != '}':
                match = re.match(r'[A-Za-z0-9_]+', self.text[self.pos:])
                if match is None:
                    raise ValueError('Invalid SNBT key')
                key = match[0]
                self.pos += len(key)
                self.take(':')
                if key in result:
                    raise ValueError('Duplicate SNBT key')
                result[key] = self.value()
                self.space()
                if self.text[self.pos] != ',':
                    break
                self.pos += 1
                self.space()
            self.take('}')
            return result
        if char == '[':
            self.pos += 1
            result = []
            self.space()
            while self.text[self.pos] != ']':
                result.append(self.value())
                self.space()
                if self.text[self.pos] != ',':
                    break
                self.pos += 1
            self.take(']')
            return result
        match = re.match(r'-?\d+[bBsSlL]?', self.text[self.pos:])
        if match is None:
            raise ValueError(f'Unsupported SNBT value at {self.pos}')
        self.pos += len(match[0])
        return int(match[0].rstrip('bBsSlL'))

    def parse(self):
        result = self.value()
        self.space()
        if self.pos != len(self.text):
            raise ValueError('Trailing SNBT content')
        return result


def matches(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and matches(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and (not actual if not expected else all(any(matches(value, item) for item in actual) for value in expected))
    return type(expected) is type(actual) and expected == actual


def read_functions():
    return {path.stem: [line for line in path.read_text(encoding='utf-8-sig').splitlines() if line and not line.startswith('#')] for path in FUNCTION_ROOT.glob('book_*.mcfunction')}


class Player:
    def __init__(self, name, language=1):
        self.name = name
        self.scores = {} if language is None else {'wlang': language}
        self.inventory = {}
        self.enabled = set()
        self.dropped = []
        self.cancel_give = False

    def fill(self):
        self.inventory = {slot: {'id': 'minecraft:stone', 'Count': 1} for slot in range(36)}

    def nbt(self):
        return {'Inventory': [dict(item, Slot=slot) for slot, item in self.inventory.items()]}

    def books(self):
        return [item for item in self.inventory.values() if item.get('id') == 'minecraft:written_book' and item.get('tag', {}).get('rvGuide') == 1]


class Model:
    def __init__(self, players):
        self.players = players
        self.functions = read_functions()
        self.objectives = {'wlang': 'dummy'}
        self.calls = []
        self.gives = 0
        self.nbt_checks = 0
        self.run('book_setup')

    def selected(self, selector, player):
        match = re.fullmatch(r'@(a|s)(?:\[(.+)\])?', selector)
        if match is None:
            raise ValueError('Unsupported selector: ' + selector)
        candidates = self.players if match[1] == 'a' else [player] if player else []
        if match[1] == 's' and player is None:
            raise ValueError('@s requires player context')
        for candidate in candidates:
            keep = True
            for condition in (match[2] or '').split(','):
                if not condition:
                    continue
                name, bound = condition.split('=')
                if not name.startswith('score_'):
                    raise ValueError('Unsupported selector condition')
                minimum = name.endswith('_min')
                objective = name[6:-4] if minimum else name[6:]
                score = candidate.scores.get(objective)
                keep &= score is not None and (score >= int(bound) if minimum else score <= int(bound))
            if keep:
                yield candidate

    def run(self, function, player=None, depth=0):
        if depth > 20:
            raise ValueError('Function recursion')
        self.calls.append((function, player.name if player else None))
        for line in self.functions[function]:
            self.command(line, player, depth)

    def command(self, line, player, depth):
        if line.startswith('function warfare:'):
            self.run(line.split(':', 1)[1], player, depth + 1)
            return
        match = re.fullmatch(r'execute (\S+) ~ ~ ~ (.+)', line)
        if match:
            for target in list(self.selected(match[1], player)):
                self.command(match[2], target, depth + 1)
            return
        match = re.fullmatch(r'scoreboard objectives add (\w+) (dummy|trigger)', line)
        if match:
            self.objectives.setdefault(match[1], match[2])
            return
        match = re.fullmatch(r'scoreboard players (set|add|enable) (\S+) (\w+)(?: (-?\d+))?(?: (\{.+\}))?', line)
        if match:
            action, selector, objective, number, data = match.groups()
            if objective not in self.objectives:
                raise ValueError('Missing objective: ' + objective)
            for target in list(self.selected(selector, player)):
                if data:
                    self.nbt_checks += 1
                    if not matches(Snbt(data).parse(), target.nbt()):
                        continue
                if action == 'enable':
                    if self.objectives[objective] != 'trigger':
                        raise ValueError('Only triggers can be enabled')
                    target.enabled.add(objective)
                    target.scores.setdefault(objective, 0)
                else:
                    target.scores[objective] = int(number) + (target.scores.get(objective, 0) if action == 'add' else 0)
            return
        match = re.fullmatch(r'give (@s) minecraft:written_book 1 0 (\{.+\})', line)
        if match:
            self.gives += 1
            item = {'id': 'minecraft:written_book', 'Count': 1, 'tag': Snbt(match[2]).parse()}
            for target in self.selected(match[1], player):
                if target.cancel_give:
                    continue
                empty = next((slot for slot in range(36) if slot not in target.inventory), None)
                if empty is None:
                    target.dropped.append(item)
                else:
                    target.inventory[empty] = item
            return
        raise ValueError('Unsupported command: ' + line)

    def tick(self, count=1):
        for _ in range(count):
            self.run('book_tick')

    def request(self, player):
        if 'wbook' not in player.enabled:
            raise ValueError('Trigger is locked')
        player.enabled.remove('wbook')
        player.scores['wbook'] = 1


class PlayerGuideTests(unittest.TestCase):
    def test_both_books_parse_and_pages_fit(self):
        for language in ('ru', 'en'):
            line = read_functions()['book_give_' + language][0]
            book = Snbt(line.split(' 1 0 ', 1)[1]).parse()
            self.assertLessEqual(len(book['title']), 32)
            self.assertEqual(book['rvGuide'], 1)
            self.assertEqual(book['rvGuideVersion'], 2)
            self.assertEqual(book['author'], 'RV')
            self.assertEqual(len(book['pages']), 24)
            for encoded in book['pages']:
                text = json.loads(encoded)['text']
                self.assertLessEqual(len(text.splitlines()), 14)
                self.assertTrue(all(builder.width(line) <= 114 for line in text.splitlines()))
            all_text = '\n'.join(json.loads(page)['text'] for page in book['pages'])
            for required in ('/trigger wbook set 1', '/trigger menu set 1', '/trigger spawn set 1', '/trigger kit set 1', '/trigger drone set 1', '/trigger wing set 1', 'X: 0', 'Y: 65', 'Z: -210', 'FP-1', 'First Aid', 'Easy', 'Space', 'Ctrl', 'F8', 'Angle', 'Acro', 'USB', '4–6', 'F3', 'Low', 'Balanced', 'Quality', 'HUD', 'HP'):
                self.assertIn(required, all_text)
            for required in (('Танк', 'ЛКМ — выстрел', 'ПОПАДАНИЕ', 'УРОН', 'УНИЧТОЖЕНО') if language == 'ru' else ('Tank', 'Left click — fire', 'HIT', 'DAMAGE', 'DESTROYED')):
                self.assertIn(required, all_text)

    def test_no_destructive_or_modern_commands_and_all_refs_exist(self):
        functions = read_functions()
        self.assertEqual(set(functions), set(builder.functions()))
        for commands in functions.values():
            for line in commands:
                self.assertNotRegex(line.split(' {', 1)[0], r'\b(clear|replaceitem|kill|summon|data|schedule)\b|execute (as|if|unless|store)\b')
                for target in re.findall(r'function warfare:(\w+)', line):
                    self.assertIn(target, functions)
        self.assertTrue(all(len(name) <= 16 for name in builder.OBJECTIVES))

    def test_first_entry_in_each_language(self):
        for language, title in ((1, 'RV · Памятка'), (2, 'RV · Field guide')):
            player = Player('New', language)
            model = Model([player])
            model.tick()
            self.assertEqual([book['tag']['title'] for book in player.books()], [title])
            self.assertEqual(player.scores['wbOnce'], 1)
            self.assertEqual(player.scores['wbPending'], 0)

    def test_existing_player_is_discovered_without_welcome_hook(self):
        player = Player('Existing')
        player.scores['kills'] = 17
        player.inventory[0] = {'id': 'techguns:m4', 'Count': 1, 'tag': {'ammo': 7}}
        model = Model([player])
        model.tick()
        self.assertEqual(len(player.books()), 1)
        self.assertEqual(player.inventory[0]['tag']['ammo'], 7)
        self.assertEqual(player.scores['kills'], 17)

    def test_old_edition_is_upgraded_once_without_replacing_inventory(self):
        player = Player('Veteran')
        player.scores = {'wlang': 1, 'wbOnce': 1, 'kills': 17}
        old = {'id': 'minecraft:written_book', 'Count': 1, 'tag': {'rvGuide': 1, 'rvGuideVersion': 1, 'title': 'Old guide'}}
        weapon = {'id': 'techguns:m4', 'Count': 1, 'tag': {'ammo': 7}}
        player.inventory = {0: deepcopy(old), 1: deepcopy(weapon)}
        model = Model([player])
        model.tick(100)
        self.assertEqual(player.inventory[0], old)
        self.assertEqual(player.inventory[1], weapon)
        self.assertEqual(player.scores['kills'], 17)
        self.assertEqual(player.scores['wbEdition'], 2)
        self.assertEqual([book['tag']['rvGuideVersion'] for book in player.books()], [1, 2])
        self.assertEqual(model.gives, 1)
        checks = model.nbt_checks
        model.tick(100)
        self.assertEqual(model.nbt_checks, checks)

    def test_full_inventory_upgrade_survives_restart_and_waits_for_space(self):
        player = Player('FullVeteran')
        player.scores = {'wlang': 2, 'wbOnce': 1}
        player.fill()
        player.inventory[0] = {'id': 'minecraft:written_book', 'Count': 1, 'tag': {'rvGuide': 1, 'rvGuideVersion': 1}}
        before = deepcopy(player.inventory)
        model = Model([player])
        model.tick(100)
        self.assertEqual(player.inventory, before)
        self.assertEqual((model.gives, player.scores['wbEdition'], player.scores['wbPending']), (0, 0, 1))
        rejoined = deepcopy(player)
        restarted = Model([rejoined])
        del rejoined.inventory[35]
        restarted.tick(20)
        self.assertEqual(rejoined.inventory[0], before[0])
        self.assertEqual(rejoined.inventory[35]['tag']['rvGuideVersion'], 2)
        self.assertEqual(rejoined.scores['wbEdition'], 2)
        self.assertEqual(rejoined.dropped, [])

    def test_current_edition_offhand_confirms_migration_without_free_slot(self):
        player = Player('AlreadyUpgraded')
        player.scores = {'wlang': 1, 'wbOnce': 1}
        player.fill()
        player.inventory[-106] = {'id': 'minecraft:written_book', 'Count': 1, 'tag': {'rvGuide': 1, 'rvGuideVersion': 2}}
        before = deepcopy(player.inventory)
        model = Model([player])
        model.tick(100)
        self.assertEqual(player.inventory, before)
        self.assertEqual((model.gives, player.scores['wbEdition'], player.scores['wbPending']), (0, 2, 0))

    def test_each_of_36_free_main_slots_is_usable(self):
        for slot in range(36):
            player = Player('Slot')
            player.fill()
            del player.inventory[slot]
            model = Model([player])
            model.tick()
            self.assertEqual(player.inventory[slot]['id'], 'minecraft:written_book')
            self.assertEqual(len(player.inventory), 36)
            self.assertEqual(player.dropped, [])

    def test_full_inventory_waits_without_drops_then_delivers(self):
        player = Player('Full')
        player.fill()
        before = deepcopy(player.inventory)
        model = Model([player])
        model.tick(200)
        self.assertEqual(player.inventory, before)
        self.assertEqual((model.gives, player.scores['wbOnce'], player.scores['wbPending']), (0, 0, 1))
        self.assertEqual(player.dropped, [])
        del player.inventory[35]
        model.tick(20)
        self.assertEqual(len(player.books()), 1)
        self.assertEqual(player.scores['wbOnce'], 1)
        self.assertEqual(player.dropped, [])

    def test_empty_armour_and_offhand_do_not_count_as_main_space(self):
        player = Player('Armour')
        player.fill()
        model = Model([player])
        model.tick(50)
        self.assertEqual(model.gives, 0)
        player.inventory[100] = {'id': 'minecraft:iron_boots', 'Count': 1}
        player.inventory[-106] = {'id': 'minecraft:shield', 'Count': 1}
        model.tick(20)
        self.assertEqual(model.gives, 0)
        del player.inventory[7]
        model.tick(20)
        self.assertEqual(len(player.books()), 1)
        self.assertEqual(player.inventory[-106]['id'], 'minecraft:shield')

    def test_failed_give_does_not_complete_delivery(self):
        player = Player('Cancelled')
        player.cancel_give = True
        model = Model([player])
        model.tick()
        self.assertEqual((player.scores['wbOnce'], player.scores['wbPending']), (0, 1))
        player.cancel_give = False
        model.tick(20)
        self.assertEqual((len(player.books()), player.scores['wbOnce']), (1, 1))

    def test_pending_is_checked_once_per_20_ticks(self):
        player = Player('Wait')
        player.fill()
        model = Model([player])
        model.tick(200)
        self.assertEqual(sum(name == 'book_space' for name, _ in model.calls), 10)
        self.assertEqual(model.nbt_checks, 370)

    def test_no_scanning_after_delivery(self):
        player = Player('Done')
        model = Model([player])
        model.tick()
        checks = model.nbt_checks
        model.tick(500)
        self.assertEqual(model.nbt_checks, checks)
        self.assertEqual(model.gives, 1)

    def test_language_unset_zero_or_unknown_waits(self):
        for language in (None, 0, 3, -1):
            player = Player('Language', language)
            model = Model([player])
            model.tick(100)
            self.assertEqual(model.gives, 0)
            self.assertEqual(sum(name == 'book_space' for name, _ in model.calls), 0)
            player.scores['wlang'] = 2
            model.tick(20)
            self.assertEqual(player.books()[0]['tag']['title'], 'RV · Field guide')

    def test_relog_restart_and_death_keep_completion(self):
        player = Player('Persistent')
        model = Model([player])
        model.tick()
        player.inventory.clear()
        saved_scores = deepcopy(player.scores)
        rejoined = Player('Persistent')
        rejoined.scores = saved_scores
        restarted = Model([rejoined])
        restarted.run('book_welcome', rejoined)
        restarted.run('book_setup')
        restarted.tick(100)
        self.assertEqual(restarted.gives, 0)
        self.assertEqual(rejoined.scores['wbOnce'], 1)

    def test_pending_survives_restart(self):
        player = Player('Pending')
        player.fill()
        model = Model([player])
        model.tick(7)
        rejoined = deepcopy(player)
        restarted = Model([rejoined])
        restarted.tick(13)
        self.assertEqual(restarted.gives, 0)
        del rejoined.inventory[0]
        restarted.tick(20)
        self.assertEqual(len(rejoined.books()), 1)

    def test_explicit_lost_book_request_and_no_automatic_replacement(self):
        player = Player('Lost')
        model = Model([player])
        model.tick()
        player.inventory.clear()
        model.tick(100)
        self.assertEqual(model.gives, 1)
        model.request(player)
        model.tick()
        self.assertEqual((model.gives, len(player.books())), (2, 1))
        for _ in range(10):
            model.request(player)
            model.tick()
        self.assertEqual((model.gives, len(player.books())), (2, 1))

    def test_existing_book_offhand_and_locale_change_do_not_duplicate(self):
        player = Player('Offhand')
        model = Model([player])
        model.tick()
        player.inventory[-106] = player.inventory.pop(0)
        player.scores['wlang'] = 2
        model.request(player)
        model.tick()
        self.assertEqual(model.gives, 1)
        self.assertEqual(len(player.books()), 1)

    def test_reissue_with_full_inventory_waits(self):
        player = Player('Reissue')
        model = Model([player])
        model.tick()
        player.fill()
        model.request(player)
        model.tick(100)
        self.assertEqual(model.gives, 1)
        self.assertEqual(player.dropped, [])
        del player.inventory[4]
        model.tick(20)
        self.assertEqual((model.gives, len(player.books())), (2, 1))

    def test_multiplayer_context_and_pending_are_independent(self):
        russian, english, full = Player('Ru', 1), Player('En', 2), Player('Full', 1)
        full.fill()
        model = Model([russian, english, full])
        model.tick(30)
        self.assertEqual(russian.books()[0]['tag']['title'], 'RV · Памятка')
        self.assertEqual(english.books()[0]['tag']['title'], 'RV · Field guide')
        self.assertEqual(full.books(), [])
        russian.inventory.clear()
        model.request(russian)
        model.tick()
        self.assertEqual([len(p.books()) for p in model.players], [1, 1, 0])
        self.assertEqual(full.dropped, [])

    def test_unrelated_books_do_not_count_as_guide(self):
        player = Player('OtherBook')
        player.inventory[0] = {'id': 'minecraft:written_book', 'Count': 1, 'tag': {'title': 'Other', 'author': 'RV'}}
        model = Model([player])
        model.tick()
        self.assertEqual(len(player.inventory), 2)
        self.assertEqual(len(player.books()), 1)


def vanilla_check(vanilla_jar, java):
    function_lines = [line for lines in read_functions().values() for line in lines]
    compounds = [line[line.index('{'):] for line in function_lines if '{' in line]
    book_tags = [line.split(' 1 0 ', 1)[1] for line in function_lines if line.startswith('give ')]
    slots = [line[line.index('{'):] for line in read_functions()['book_space'] if '{' in line]
    filled = ','.join('{Slot:' + str(slot) + 'b,id:"minecraft:stone",Count:1b}' for slot in range(36))
    almost = ','.join('{Slot:' + str(slot) + 'b,id:"minecraft:stone",Count:1b}' for slot in range(35))
    payload = {'compounds': compounds, 'books': book_tags, 'slots': slots, 'inventories': [
        {'nbt': '{Inventory:[' + filled + ']}', 'occupied': 36},
        {'nbt': '{Inventory:[' + almost + ',{Slot:-106b,id:"minecraft:shield",Count:1b},{Slot:100b,id:"minecraft:iron_boots",Count:1b}]}', 'occupied': 35},
        {'nbt': '{Inventory:[]}', 'occupied': 0},
    ], 'matches': [
        {'expected': builder.MARKER, 'actual': '{Inventory:[{Slot:-106b,id:"minecraft:written_book",Count:1b,tag:{rvGuide:1b,rvGuideVersion:2}}]}', 'result': True},
        {'expected': builder.MARKER, 'actual': '{Inventory:[{Slot:0b,id:"minecraft:written_book",Count:1b,tag:{rvGuide:1b,rvGuideVersion:1}}]}', 'result': False},
        {'expected': builder.MARKER, 'actual': '{Inventory:[{Slot:0b,id:"minecraft:written_book",Count:1b,tag:{rvGuide:1b}}]}', 'result': False},
        {'expected': builder.MARKER, 'actual': '{Inventory:[{Slot:0b,id:"minecraft:written_book",Count:1b,tag:{title:"RV"}}]}', 'result': False},
        {'expected': builder.MARKER, 'actual': '{Inventory:[{Slot:0b,id:"minecraft:book",Count:1b,tag:{rvGuide:1b}}]}', 'result': False},
    ]}
    script = '''var Files=Java.type('java.nio.file.Files'), Paths=Java.type('java.nio.file.Paths');
var data=JSON.parse(new java.lang.String(Files.readAllBytes(Paths.get(arguments[0])), 'UTF-8'));
var Parser=Java.type('gp'), Util=Java.type('gj'), Book=Java.type('akf');
var checks=0;
function check(ok, name) { if(!ok) throw new Error(name); checks++; }
data.compounds.forEach(function(text) { check(Parser.a(text) !== null, 'SNBT parse'); });
data.books.forEach(function(text) { check(Book.b(Parser.a(text)), 'written_book validity'); });
data.matches.forEach(function(test) { check(Util.a(Parser.a(test.expected), Parser.a(test.actual), true) === test.result, 'NBT marker matching'); });
data.inventories.forEach(function(test) {
    var actual=Parser.a(test.nbt), count=0;
    data.slots.forEach(function(slot) { if(Util.a(Parser.a(slot), actual, true)) count++; });
    check(count === test.occupied, 'occupied main slot count');
});
print('VANILLA_CHECKS=' + checks);
'''
    nashorn = java.resolve().parents[1] / 'lib/ext/nashorn.jar'
    if not nashorn.exists():
        raise ValueError('Use the bundled Java 8 runtime for Nashorn checks')
    with tempfile.TemporaryDirectory(prefix='rv-player-guide-qa-') as folder:
        folder = Path(folder)
        (folder / 'input.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        (folder / 'check.js').write_text(script, encoding='utf-8')
        process = subprocess.run([str(java), '-cp', os.pathsep.join((str(vanilla_jar.resolve()), str(nashorn))), 'jdk.nashorn.tools.Shell', str(folder / 'check.js'), '--', str(folder / 'input.json')], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        if process.returncode or not re.search(r'VANILLA_CHECKS=\d+', process.stdout):
            raise RuntimeError(process.stdout + process.stderr)
        print(process.stdout.strip())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check the RV player-book functions without changing a live world.')
    parser.add_argument('--functions', type=Path)
    parser.add_argument('--vanilla-jar', type=Path)
    parser.add_argument('--java', type=Path)
    args = parser.parse_args()
    if bool(args.vanilla_jar) != bool(args.java):
        parser.error('--vanilla-jar and --java are required together')
    if args.functions:
        FUNCTION_ROOT = args.functions.resolve()
    else:
        builder.build()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlayerGuideTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.vanilla_jar:
        vanilla_check(args.vanilla_jar, args.java)
