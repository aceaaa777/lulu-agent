"""Cheap GDScript sanity check for a localized tree (no Godot at hand): every string literal must close on its own line
and quotes must balance, so a translation that smuggled in an unescaped quote is caught before the CI export."""
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; these scripts print Chinese paths and messages.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def check(path):
    problems = []
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        i, quote = 0, None
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == '\\':
                    i += 2
                    continue
                if line.startswith(quote, i):
                    i += len(quote)
                    quote = None
                    continue
            else:
                if ch == '#':
                    break
                if line.startswith('"""', i) or line.startswith("'''", i):
                    quote = line[i:i+3]
                    i += 3
                    continue
                if ch in '"\'':
                    quote = ch
            i += 1
        if quote and len(quote) == 1:
            problems.append(f'{path}:{n}: unterminated string  {line.strip()[:100]}')
    return problems


if __name__ == '__main__':
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    bad = [p for f in root.rglob('*.gd') for p in check(f)]
    print('\n'.join(bad) or f'gdscript strings OK ({sum(1 for _ in root.rglob("*.gd"))} files)')
    sys.exit(1 if bad else 0)
