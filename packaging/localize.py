"""Produce the English source tree from the Chinese one, at packaging time.

    python packaging/localize.py --lang en --out build/src-en

One codebase, two packages: this copies the repo (tracked and untracked-but-not-ignored files) to --out and replaces
every Chinese string literal that packaging/i18n/<lang>.csv translates. Replacement is by whole literal, never by
substring, so a sentence fragment is only touched where it stands alone as its own literal — exactly how the table
was extracted (packaging/extract_strings.py). The table's 中文输入识别规则 rows (regexes and cue words that read Chinese
input) are never applied; lulu/timeparse.py and lulu/intent.py stay Chinese in the English tree too, the English
build reads English input through lulu/timeparse_en.py and the tag row. lulu/lang.py is rewritten to LANG='<lang>' so
runtime code that must differ per language (time parsing, memory key length, cue words) switches on that.
Files whose name is itself a translated string (安装并启动 Lulu.command → Install and start Lulu.command) are renamed, and
every reference to the old name in scripts and docs is rewritten. Prints a report; --check fails on leftovers.
"""
import argparse
import csv
import io
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

# Windows consoles default to a legacy code page; these scripts print Chinese paths and messages.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r'[一-鿿]')
CJK_OR_PUNCT = re.compile(r'[一-鿿，。：、！？（）“”]')
SKIP_CATEGORIES = {'中文输入识别规则'}
KEEP_CHINESE = {'lulu/timeparse.py', 'lulu/intent.py', 'lulu/timeparse_en.py', 'lulu/lang.py', 'packaging/localize.py', 'packaging/extract_strings.py',
                'README.md', 'README.en.md'}   # docs are the repo page, not the package; README.en.md is already English
TEXT_SUFFIXES = ('.md', '.command', '.cmd', '.ps1', '.txt')
CODE_PATCHES = {'en': [('desktop/src/animation_state.gd', 'var english := false', 'var english := true')]}   # the pet holds up the "done" board
SKIP_COPY = re.compile(r'^(build/|dist/|\.git/|desktop/\.godot/|desktop/assets/optimized|tests/|desktop/tests/|\.github/|packaging/i18n/)|\.pyc$|__pycache__')
QUIET = re.compile(r'^desktop/assets/')   # copied as-is, no report


def load_table(path):
    table = {}
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            zh, en = row['中文'], row['English']
            if not en.strip() or row['类别'] in SKIP_CATEGORIES or zh == en:
                continue
            table[zh] = en
    return table


def repo_files():
    out = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT, capture_output=True).stdout.decode('utf-8', 'surrogateescape')
    return [f for f in out.split('\0') if f and not SKIP_COPY.search(f) and (ROOT / f).is_file()]


def requote(prefix, quote, text, original_quote_style_ok=True):
    """Rebuild a Python/GDScript string literal around new text, keeping the prefix (r/f/b…) and switching or escaping
    quotes when the new text contains the quote character. Braces of f-strings are left untouched."""
    if quote not in text:
        return prefix+quote+text+quote
    other = "'" if quote == '"' else '"'
    if len(quote) == 3:
        return prefix+quote+text.replace(quote, '\\'+quote[0]+quote[1:])+quote
    if 'f' not in prefix.lower() and other not in text:
        return prefix+other+text+other
    # escape the quote outside {…} so f-string expressions keep their own quoting
    pieces, depth, out = [], 0, []
    for ch in text:
        if 'f' in prefix.lower():
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth-1)
        out.append('\\'+ch if ch == quote and depth == 0 else ch)
    return prefix+quote+''.join(out)+quote


def string_literals(toks):
    """(start, end, raw) for every string literal. Python 3.12+ tokenizes an f-string into FSTRING_START … FSTRING_END
    instead of one STRING token; stitch those back into one literal so both interpreters see the same thing."""
    FS, FE = getattr(tokenize, 'FSTRING_START', None), getattr(tokenize, 'FSTRING_END', None)
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok.type == tokenize.STRING:
            yield tok.start, tok.end, tok.string
        elif FS is not None and tok.type == FS:
            depth, j = 0, i
            while j < len(toks):
                if toks[j].type == FS:
                    depth += 1
                elif toks[j].type == FE:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            yield tok.start, toks[j].end, None   # raw text is cut from the source by position
            i = j
        i += 1


def slice_source(source, start, end):
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1]+len(line))
    return source[offsets[start[0]-1]+start[1]:offsets[end[0]-1]+end[1]]


class Report:
    def __init__(self):
        self.replaced = 0
        self.used = set()
        self.leftover = []   # (file, line, text) — Chinese still present in a file we did translate


def localize_python(source, table, report, where):
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return source
    edits = []
    for start, end, raw in string_literals(toks):
        if raw is None:
            raw = slice_source(source, start, end)
        if not CJK_OR_PUNCT.search(raw):
            continue
        prefix = re.match(r'[rRbBuUfF]*', raw).group(0)
        body = raw[len(prefix):]
        quote = body[:3] if body[:3] in ('"""', "'''") else body[0]
        value = body[len(quote):-len(quote)]
        if value.strip() in table:
            lead = value[:len(value)-len(value.lstrip())]
            trail = value[len(value.rstrip()):]
            new = table[value.strip()]
            # the table keeps meaningful edge spaces itself; only re-add the ones the source had when the table dropped them
            if lead and not new.startswith(' '):
                new = lead+new
            if trail and not new.endswith(' '):
                new = new+trail
            edits.append((start, end, requote(prefix, quote, new)))
            report.used.add(value.strip()); report.replaced += 1
        elif CJK.search(value):
            report.leftover.append((where, start[0], value[:60]))
    return apply_edits(source, edits)


def apply_edits(source, edits):
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1]+len(line))
    text = source
    for (sl, sc), (el, ec), new in sorted(edits, key=lambda e: e[0], reverse=True):
        a, b = offsets[sl-1]+sc, offsets[el-1]+ec
        text = text[:a]+new+text[b:]
    return text


GD_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'')


def localize_gdscript(source, table, report, where):
    def swap(m):
        raw = m.group(0)
        quote = raw[0]
        value = raw[1:-1]
        if not CJK_OR_PUNCT.search(value):
            return raw
        if value.strip() in table:
            new = table[value.strip()]
            report.used.add(value.strip()); report.replaced += 1
            return requote('', quote, new)
        if CJK.search(value):
            report.leftover.append((where, source.count('\n', 0, m.start())+1, value[:60]))
        return raw
    return GD_STRING.sub(swap, source)


def localize_lines(source, table, report, where):
    out = []
    for n, line in enumerate(source.splitlines(keepends=True), 1):
        stripped = line.strip('\r\n')
        key = stripped.strip()
        if CJK.search(stripped):
            if key in table:
                indent = stripped[:len(stripped)-len(stripped.lstrip())]
                line = indent+table[key]+line[len(stripped):]
                report.used.add(key); report.replaced += 1
            else:
                report.leftover.append((where, n, stripped[:60]))
        out.append(line)
    return ''.join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lang', default='en')
    parser.add_argument('--out', type=Path, default=ROOT / 'build' / 'src-en')
    parser.add_argument('--table', type=Path)
    parser.add_argument('--check', action='store_true', help='exit 1 when translated files still hold Chinese literals')
    args = parser.parse_args()
    table = load_table(args.table or ROOT / 'packaging' / 'i18n' / f'{args.lang}.csv')
    report = Report()
    if args.out.exists():
        shutil.rmtree(args.out)
    renames = {}   # old relative path -> new relative path
    for rel in repo_files():
        src = ROOT / rel
        name = Path(rel).name
        new_rel = rel
        two = Path(rel).parent.name+'/'+name   # the table may know the file as tools/安装并启动.ps1
        if name in table or two in table:
            new_name = Path(table[name] if name in table else table[two]).name
            new_rel = str(Path(rel).with_name(new_name))
            renames[rel] = new_rel
        dst = args.out / new_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel in KEEP_CHINESE or QUIET.search(rel) or not (rel.endswith(('.py', '.gd')) or rel.endswith(TEXT_SUFFIXES)):
            shutil.copy2(src, dst)
            continue
        try:
            source = src.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            shutil.copy2(src, dst)
            continue
        if not CJK_OR_PUNCT.search(source):
            shutil.copy2(src, dst)
            continue
        if rel.endswith('.py'):
            text = localize_python(source, table, report, rel)
        elif rel.endswith('.gd'):
            text = localize_gdscript(source, table, report, rel)
        else:
            text = localize_lines(source, table, report, rel)
        dst.write_text(text, encoding='utf-8')
        shutil.copymode(src, dst)
    # references to renamed files, wherever they are written as plain text (paths in scripts, docs, build lists)
    names = {Path(old).name: Path(new).name for old, new in renames.items()}
    for path in args.out.rglob('*'):
        if path.is_file() and path.suffix in ('.py', '.gd', '.md', '.command', '.cmd', '.ps1', '.yml', '.txt'):
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            new = text
            for old_name, new_name in names.items():
                new = new.replace(old_name, new_name)
            if new != text:
                path.write_text(new, encoding='utf-8')
    # code that differs per language beyond string literals
    for rel, before, after in CODE_PATCHES.get(args.lang, []):
        path = args.out / rel
        text = path.read_text(encoding='utf-8')
        assert text.count(before) == 1, (rel, before)
        path.write_text(text.replace(before, after), encoding='utf-8')
    (args.out / 'lulu' / 'lang.py').write_text((ROOT / 'lulu' / 'lang.py').read_text(encoding='utf-8').replace("LANG = 'zh'", f"LANG = '{args.lang}'"), encoding='utf-8')
    unused = sorted(set(table)-report.used, key=len)
    print(f'{args.lang}: {report.replaced} literals replaced, {len(renames)} files renamed, {len(unused)} table rows unused, {len(report.leftover)} Chinese literals left')
    for old, new in renames.items():
        print(f'  renamed {old} -> {new}')
    for where, line, text in report.leftover[:400]:
        print(f'  left   {where}:{line}  {text}')
    if args.check and report.leftover:
        sys.exit(1)
    return 0


if __name__ == '__main__':
    main()
