"""Export the desktop pet with Godot, headless, without opening the editor.

    python packaging/export_pet.py                     # linux + windows + macos + frames (whatever the host can do)
    python packaging/export_pet.py --targets windows,frames
    GODOT=/path/to/godot python packaging/export_pet.py --targets linux

Needs a Godot 4.4.1 editor binary (env GODOT, `godot` on PATH, or the usual download locations) and the matching
export templates; the templates (~1.2GB) are downloaded on first use into Godot's own templates folder. The frames
target packs the animation frames (desktop/assets/optimized, ~400MB) into build/pet/frames.pck, which the exported
program loads at startup; the three program targets deliberately leave the frames out so the download stays small.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'desktop'
OUT = ROOT / 'build' / 'pet'
GODOT_VERSION = '4.4.1'
TEMPLATES_URL = f'https://github.com/godotengine/godot/releases/download/{GODOT_VERSION}-stable/Godot_v{GODOT_VERSION}-stable_export_templates.tpz'
TARGETS = {
    'linux': ('Linux', 'linux/Lulu.x86_64', '--export-release'),
    'windows': ('Windows Desktop', 'windows/Lulu.exe', '--export-release'),
    'macos': ('macOS', 'macos/Lulu.zip', '--export-release'),
    'frames': ('frames', 'frames.pck', '--export-pack'),
}


def templates_dir():
    if sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support/Godot'
    elif os.name == 'nt':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'Godot'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'godot'
    return base / 'export_templates' / f'{GODOT_VERSION}.stable'


def find_godot():
    env = os.environ.get('GODOT')
    if env and Path(env).exists():
        return env
    for name in ['godot', 'godot4', 'Godot']:
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path.home() / 'Downloads/Godot.app/Contents/MacOS/Godot',
        Path('/Applications/Godot.app/Contents/MacOS/Godot'),
        Path(f'/tmp/Godot_v{GODOT_VERSION}-stable_linux.x86_64'),
        ROOT / 'build' / f'Godot_v{GODOT_VERSION}-stable_linux.x86_64',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Godot' / f'Godot_v{GODOT_VERSION}-stable_win64.exe',
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise SystemExit('找不到 Godot 4.4.1。设置环境变量 GODOT=<Godot 可执行文件路径> 后重试。')


def ensure_templates():
    folder = templates_dir()
    if (folder / 'version.txt').exists():
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder.parent / f'{GODOT_VERSION}.tpz'
    print(f'下载 Godot 导出模板（约 1.2GB）→ {archive}', flush=True)
    urllib.request.urlretrieve(TEMPLATES_URL, archive)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            name = member.filename
            if not name.startswith('templates/') or member.is_dir():
                continue
            target = folder / name[len('templates/'):]
            with z.open(member) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            if member.external_attr >> 16 & 0o111:
                target.chmod(0o755)
    archive.unlink(missing_ok=True)
    return folder


def run(godot, args):
    result = subprocess.run([godot, '--headless', '--path', str(PROJECT), *args], capture_output=True, text=True)
    noise = result.stdout + '\n' + result.stderr
    errors = [line for line in noise.splitlines() if 'ERROR' in line and 'audio' not in line.lower() and 'alsa' not in line.lower()]
    return result.returncode, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--targets', default='linux,windows,macos,frames')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    godot = find_godot()
    ensure_templates()
    if not (PROJECT / '.godot' / 'imported').exists():
        print('首次：导入桌宠资源…', flush=True)
        code, errors = run(godot, ['--editor', '--import', '--quit'])
        if errors:
            print('\n'.join(errors[:10]))
    if not (PROJECT / 'assets' / 'optimized.json').exists():
        print('注意：desktop/assets/optimized.json 不存在（动画帧不在这台机器上），frames 目标会被跳过。')
    for key in [t.strip() for t in args.targets.split(',') if t.strip()]:
        preset, rel, mode = TARGETS[key]
        if key == 'frames' and not (PROJECT / 'assets' / 'optimized.json').exists():
            continue
        target = (args.out / rel).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f'导出 {preset} → {target}', flush=True)
        code, errors = run(godot, [mode, preset, str(target)])
        if errors or not target.exists():
            print('\n'.join(errors[:20]))
            raise SystemExit(f'导出 {preset} 失败')
        print(f'  {target.stat().st_size/1024/1024:.0f} MB', flush=True)
    print('完成：', args.out)


if __name__ == '__main__':
    main()
