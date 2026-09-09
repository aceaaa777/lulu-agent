"""列出仓库里所有含中文的字符串，按"怎么处理"分类，供翻译和 build_release.py --lang en 使用。

python packaging/extract_strings.py [输出.csv]
"""
import csv
import io
import re
import subprocess
import sys
import tokenize
from collections import OrderedDict
from pathlib import Path

# Windows consoles default to a legacy code page; these scripts print Chinese paths and messages.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r'[一-鿿]')
RE_CALL = re.compile(r're\.(?:compile|search|match|fullmatch|sub|findall|split|finditer)\(')
PROMPT_HINT = re.compile(r'你是|请用|用中文|只输出|输出 ?JSON|不要编造|回答|以下是|根据上面|按要点|格式：|要求：')
INPUT_FILES = {'lulu/timeparse.py', 'lulu/intent.py'}
MODEL_FILES = {'lulu/skills.py', 'lulu/writer.py', 'lulu/loop.py', 'lulu/research.py', 'lulu/companion.py', 'lulu/models.py', 'lulu/evidence.py'}
SKIP = re.compile(r'^(tests/|desktop/tests/|\.github/|packaging/i18n/|packaging/extract_strings\.py|packaging/localize\.py|desktop/assets/)|\.uid$|_test\.gd$')

CATS = OrderedDict([
    ('ui',        ('界面文案',         '直接替换')),
    ('backend',   ('后端反馈文案',     '直接替换')),
    ('prompt',    ('模型提示词',       '直接替换（含"用中文作答"→英文；要逐条核对）')),
    ('input',     ('中文输入识别规则', '不翻译。英文包另加英文规则或交给模型解析')),
    ('installer', ('安装脚本与说明',   '直接替换')),
    ('docs',      ('仓库文档',         '已有英文版/不进包')),
    ('fake',      ('演示模型脚本',     '测试用，英文包可不译')),
    ('config',    ('配置与元数据',     '看情况')),
])


def files():
    # -z: git would otherwise quote non-ASCII names (安装并启动 Lulu.command) and those files would be skipped
    out = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT, capture_output=True).stdout.decode('utf-8', 'surrogateescape')
    return [f for f in out.split('\0') if f and not SKIP.search(f) and not f.startswith(('build/', 'dist/')) and Path(ROOT, f).is_file()]


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


def py_strings(path, text):
    """yield (lineno, string_value, is_regex, is_prompt)"""
    lines = text.splitlines()
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1]+len(line)+1)
    index = {tok.start: i for i, tok in enumerate(toks)}
    for start, end, raw in string_literals(toks):
        if raw is None:
            raw = text[offsets[start[0]-1]+start[1]:offsets[end[0]-1]+end[1]]
        if not CJK.search(raw):
            continue
        i = index[start]
        prefix = re.match(r'[rRbBuUfF]*', raw).group(0).lower()
        body = raw[len(prefix):]
        quote = body[:3] if body[:3] in ('"""', "'''") else body[0]
        value = body[len(quote):-len(quote)]
        line = lines[start[0]-1]
        before = ' '.join(t.string for t in toks[max(0, i-6):i])
        is_regex = 'r' in prefix or bool(RE_CALL.search(before)) or bool(RE_CALL.search(line[:start[1]]))
        is_prompt = bool(PROMPT_HINT.search(value)) or ('prompt' in before.lower() or 'system' in before.lower()) or '\n' in value
        yield start[0], value, is_regex, is_prompt


def gd_strings(text):
    for n, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', line):
            value = m.group(1) if m.group(1) is not None else m.group(2)
            if CJK.search(value):
                yield n, value


def main(out_path):
    rows = OrderedDict()   # 中文 -> row

    def add(cat, where, value):
        value = value.strip()
        if not value or not CJK.search(value):
            return
        if value in rows:
            rows[value]['出现次数'] += 1
            return
        rows[value] = {'cat': cat, '首次出现': where, '出现次数': 1, '中文': value}

    for f in files():
        p = ROOT / f
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if not CJK.search(text):
            continue
        if f.endswith('.py'):
            for n, value, is_regex, is_prompt in py_strings(p, text):
                if f == 'lulu/fakemodel.py':
                    cat = 'fake'
                elif f in INPUT_FILES:
                    cat = 'backend' if re.search(r'[。！？，：]', value) and not is_regex else 'input'
                elif is_regex:
                    cat = 'input'
                elif f in MODEL_FILES and is_prompt:
                    cat = 'prompt'
                elif f.startswith('packaging/'):
                    cat = 'installer'
                else:
                    cat = 'backend'
                add(cat, f'{f}:{n}', value)
        elif f.endswith('.gd'):
            for n, value in gd_strings(text):
                add('ui', f'{f}:{n}', value)
        elif f.endswith(('.md', '.command', '.cmd', '.ps1', '.txt')):
            cat = 'docs' if f in ('README.md', 'THIRD-PARTY-NOTICES.md', 'README.en.md') else 'installer'
            for n, line in enumerate(text.splitlines(), 1):
                if CJK.search(line):
                    add(cat, f'{f}:{n}', line)
        else:
            for n, line in enumerate(text.splitlines(), 1):
                if CJK.search(line):
                    add('config', f'{f}:{n}', line)

    order = {k: i for i, k in enumerate(CATS)}
    items = sorted(rows.values(), key=lambda r: (order[r['cat']], r['首次出现']))
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['编号', '类别', '处理方式', '首次出现', '出现次数', '中文', 'English'])
        for i, r in enumerate(items, 1):
            name, how = CATS[r['cat']]
            w.writerow([i, name, how, r['首次出现'], r['出现次数'], r['中文'], ''])
    counts = {}
    for r in items:
        counts[CATS[r['cat']][0]] = counts.get(CATS[r['cat']][0], 0)+1
    for k, v in counts.items():
        print(f'{k}\t{v}')
    print(f'合计\t{len(items)} -> {out_path}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent.parent / '03_交接与需求' / 'lulu-全量文案表-zh.csv'))
