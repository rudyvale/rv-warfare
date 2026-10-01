import argparse
import json
from pathlib import Path
import re


parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
root = args.root.resolve()
files = sorted(root.rglob('*.mcfunction'))
known = {path.relative_to(root).with_suffix('').as_posix().replace('/', ':', 1) for path in files}
errors = []
references = 0
messages = 0
buttons = []
enabled = set()


def read_buttons(value, location):
    if isinstance(value, dict):
        click = value.get('clickEvent', {})
        if click.get('action') == 'run_command':
            command = click.get('value', '')
            if command.startswith('/trigger '):
                match = re.fullmatch(r'/trigger ([a-zA-Z0-9_]+) (set|add) (-?\d+)', command)
                if not match:
                    errors.append(f'{location}: invalid trigger button')
                else:
                    buttons.append((match[1], location))
        for child in value.values():
            read_buttons(child, location)
    elif isinstance(value, list):
        for child in value:
            read_buttons(child, location)


for path in files:
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        location = f'{path.relative_to(root)}:{number}'
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.search(r'(?:^|\s)function\s+([a-z0-9_.-]+:[a-z0-9_./-]+)(?:\s|$)', line)
        if match:
            references += 1
            if match[1] not in known:
                errors.append(f'{location}: missing function {match[1]}')
        match = re.search(r'(?:^|\s)scoreboard players enable \S+ (\w+)', line)
        if match:
            enabled.add(match[1])
        match = re.search(r'(?:^|\s)tellraw \S+ (.+)$', line)
        if match:
            messages += 1
            try:
                read_buttons(json.loads(match[1]), location)
            except json.JSONDecodeError as error:
                errors.append(f'{location}: invalid tellraw JSON ({error.msg})')

for objective, location in buttons:
    if objective not in enabled:
        errors.append(f'{location}: button has no enable command for {objective}')

result = {'files': len(files), 'function_references': references, 'chat_messages': messages, 'trigger_buttons': len(buttons), 'errors': errors}
if args.output:
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
