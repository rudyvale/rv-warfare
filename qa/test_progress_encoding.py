import os
from pathlib import Path
import subprocess


root = Path(__file__).resolve().parents[1]
script = root / 'qa/encoding-case.ps1'
helper = root / 'src/Warfare-Connection.ps1'
message = 'Распаковка сборки и Java 8…'
shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
for codepage in [866, 1251, 65001]:
    script.write_text(f"[Console]::OutputEncoding = [Text.Encoding]::GetEncoding({codepage})\n. '{helper}'\nWrite-Host '{message}'\nWrite-Output '{message}'\n", encoding='utf-8-sig')
    result = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    lines = result.stdout.decode('utf-8').splitlines()
    assert lines == [message, message], (codepage, lines)
    print(f'UTF-8 progress from code page {codepage}: PASS')
