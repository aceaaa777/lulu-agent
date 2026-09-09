"""Assemble a release folder + zip + sha256 for one platform.

    python packaging/build_release.py --platform macos                                   # 源码版（需要 Python 3.11+）
    python packaging/build_release.py --platform windows --runtime build/runtime/LuluRuntime   # 自带运行环境

The animation frames (pet/frames.pck, the whole point of Lulu) are always inside the package. `--lite` leaves them out
and lets the installer download them — kept only for experiments, never for what users download.
Inputs: build/pet/<platform>/ and build/pet/frames.pck from packaging/export_pet.py (or --pet / --frames), and
optionally a PyInstaller LuluRuntime folder (--runtime); without it the package is a 源码版 that needs Python 3.11+.
Layout of the result:
    Lulu-<version>-<platform>/
        安装并启动 Lulu.command | .cmd (+ tools/安装并启动.ps1)   先看这里.md   release.json   LICENSE / notices
        pet/   Lulu.app | Lulu.exe | Lulu.x86_64, frames.pck, frames.sha256
        runtime/LuluRuntime/   (when --runtime given)
        agent/ lulu/, entry.py, run.py, desktop_launcher.py, requirements, config.json, 安装本地模型.*, 后端体检.*
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
import zipfile
from pathlib import Path

# Windows consoles default to a legacy code page; these scripts print Chinese paths and messages.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
# read VERSION without importing the server (this script must run on a bare Python, no aiohttp installed)
VERSION = re.search(r"^VERSION\s*=\s*'([^']+)'", (ROOT / 'lulu/server.py').read_text(encoding='utf-8'), re.M).group(1)
# the language of THIS tree (packaging/localize.py writes lulu/lang.py); the English tree names its packages Lulu-<v>-en-<platform>
LANG = re.search(r"^LANG\s*=\s*'([^']+)'", (ROOT / 'lulu/lang.py').read_text(encoding='utf-8'), re.M).group(1)

PLATFORMS = {
    'macos': {'name': 'macOS · Apple 芯片 / Intel', 'pet': ['Lulu.zip'], 'installer': '安装并启动 Lulu.command',
              'data_dir': '~/Library/Application Support/Lulu/', 'log_path': '~/Library/Application Support/Lulu/logs/desktop.log',
              'security': ['首次双击可能出现“无法验证”，只显示“完成”。点“完成”后再双击一次；若仍被拦，到“系统设置 → 隐私与安全性 → 仍要打开”。',
                           '这版没有 Apple 开发者签名与公证。安装脚本会移除隔离标记并在本机签名。']},
    'windows': {'name': 'Windows 10/11 · 64 位', 'pet': ['Lulu.exe'], 'installer': '安装并启动 Lulu.cmd',
                'data_dir': '%LOCALAPPDATA%\\Lulu\\', 'log_path': '%LOCALAPPDATA%\\Lulu\\logs\\desktop.log',
                'security': ['SmartScreen 可能显示“Windows 已保护你的电脑”。确认下载自本项目后，点“更多信息 → 仍要运行”。这版没有代码签名证书。',
                             'Windows 包由 CI 构建并通过冒烟测试，尚未在真实 Windows 电脑上安装验收。遇到问题欢迎反馈。']},
    'linux': {'name': 'Linux · x86_64', 'pet': ['Lulu.x86_64'], 'installer': '安装并启动 Lulu.command',
              'data_dir': '~/.local/share/Lulu/', 'log_path': '~/.local/share/Lulu/logs/desktop.log',
              'security': ['第一次运行前给脚本加执行权限：chmod +x "{installer}"。']},
}
AGENT_FILES = ['entry.py', 'run.py', 'desktop_launcher.py', 'requirements.txt', 'constraints.txt', 'THIRD-PARTY-NOTICES.md',
               '安装本地模型.command', '安装本地模型.ps1', '安装本地模型.cmd', '后端体检.command', '后端体检.cmd']


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(source, target, ignore=None):
    shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True, ignore=ignore)


def zip_folder(folder, target):
    """ZIP64 with Unix modes and symlinks kept (the macOS .app needs both)."""
    temporary = target.with_suffix('.building.zip')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
        for base, dirs, files in os.walk(folder, followlinks=False):
            for name in sorted(dirs + files):
                p = Path(base) / name
                rel = p.relative_to(folder.parent).as_posix()
                if p.is_symlink():
                    info = zipfile.ZipInfo(rel); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(info, os.readlink(p))
                elif p.is_file():
                    z.write(p, rel)
    with zipfile.ZipFile(temporary) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError('zip 校验失败: ' + bad)
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', choices=PLATFORMS, required=True)
    parser.add_argument('--lite', action='store_true', help='实验用：不放 frames.pck，安装时下载。用户下载的包永远不用这个')
    parser.add_argument('--pet', type=Path, help='导出的桌宠目录（默认 build/pet/<platform>）')
    parser.add_argument('--frames', type=Path, default=ROOT / 'build/pet/frames.pck')
    parser.add_argument('--frames-url', default=os.environ.get('LULU_FRAMES_URL', ''), help='轻量版安装时下载 frames.pck 的地址')
    parser.add_argument('--runtime', type=Path, help='PyInstaller 打好的 LuluRuntime 目录；不给就是源码版')
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    parser.add_argument('--no-zip', action='store_true')
    args = parser.parse_args()
    spec = PLATFORMS[args.platform]
    pet_dir = args.pet or ROOT / 'build/pet' / args.platform
    args.full = not args.lite
    edition = 'full' if args.full else 'lite'
    edition_name = '' if args.full else '轻量版（安装时下载动画包）'
    name = f'Lulu-{VERSION}-' + ('' if LANG == 'zh' else LANG+'-') + args.platform + ('' if args.full else '-lite')
    target = args.out / name
    if target.exists():
        shutil.rmtree(target)
    (target / 'pet').mkdir(parents=True)

    # pet
    for file in spec['pet']:
        source = pet_dir / file
        if not source.exists():
            raise SystemExit(f'缺少桌宠导出文件 {source}，先运行 packaging/export_pet.py --targets {args.platform}')
        if file.endswith('.zip'):
            with zipfile.ZipFile(source) as z:
                for member in z.infolist():
                    out = target / 'pet' / member.filename
                    if member.is_dir():
                        out.mkdir(parents=True, exist_ok=True); continue
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, open(out, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    mode = member.external_attr >> 16
                    if mode:
                        out.chmod(mode & 0o777)
        else:
            shutil.copy2(source, target / 'pet' / file)
            (target / 'pet' / file).chmod(0o755)
    frames_hash = ''
    if args.frames.exists():
        frames_hash = sha256(args.frames)
        (target / 'pet/frames.sha256').write_text(f'{frames_hash}  frames.pck\n', encoding='utf-8')
        if args.full:
            shutil.copy2(args.frames, target / 'pet/frames.pck')
    elif args.full:
        raise SystemExit(f'缺少 {args.frames}（动画资源包，Lulu 的核心）：先运行 packaging/export_pet.py --targets frames，或从 Release 下载。')
    else:
        print(f'提示：没有 {args.frames}，轻量版将不带校验值，安装时只能信任下载结果。')
    if not args.full and not args.frames_url:
        print('提示：轻量版没有 --frames-url，安装脚本将无法自动下载动画包。')

    # runtime
    if args.runtime:
        if not (args.runtime / ('LuluRuntime.exe' if args.platform == 'windows' else 'LuluRuntime')).exists():
            raise SystemExit(f'{args.runtime} 里没有 LuluRuntime 可执行文件')
        copy_tree(args.runtime, target / 'runtime/LuluRuntime')
        if args.platform != 'windows':
            (target / 'runtime/LuluRuntime/LuluRuntime').chmod(0o755)

    # agent source (small; also the scripts the installer calls)
    agent = target / 'agent'
    copy_tree(ROOT / 'lulu', agent / 'lulu', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for file in AGENT_FILES:
        if (ROOT / file).exists():
            shutil.copy2(ROOT / file, agent / file)
    (agent / 'config.json').write_text(json.dumps({'backend': 'ollama', 'tier': 'auto', 'think': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    for extra in ['LICENSE', 'THIRD-PARTY-NOTICES.md']:
        if (ROOT / extra).exists():
            shutil.copy2(ROOT / extra, target / extra)

    # installer + readme + release.json
    installer_dir = ROOT / 'packaging/installer'
    shutil.copy2(installer_dir / spec['installer'], target / spec['installer'])
    if args.platform == 'windows':
        (target / 'tools').mkdir(exist_ok=True)
        shutil.copy2(installer_dir / 'tools/安装并启动.ps1', target / 'tools/安装并启动.ps1')
    for p in [target / spec['installer'], *agent.glob('*.command')]:
        p.chmod(0o755)
    release = {'version': VERSION, 'lang': LANG, 'platform': args.platform, 'edition': edition, 'edition_name': edition_name, 'frames_sha256': frames_hash,
               'frames_url': args.frames_url, 'runtime': 'bundled' if args.runtime else 'source', 'built': time.strftime('%Y-%m-%d')}
    (target / 'release.json').write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding='utf-8')
    readme = (installer_dir / '先看这里.md').read_text(encoding='utf-8').format(
        version=VERSION, edition='' if args.full else '（轻量版）', platform_name=spec['name'], installer=spec['installer'],
        security_lines='\n\n'.join(line.replace('{installer}', spec['installer']) for line in spec['security']),
        data_dir=spec['data_dir'], log_path=spec['log_path'], build_date=release['built'])
    (target / '先看这里.md').write_text(readme, encoding='utf-8')
    size = sum(p.stat().st_size for p in target.rglob('*') if p.is_file())
    print(f'{target}  ({size/1024/1024:.0f} MB)')
    if not args.no_zip:
        zip_path = args.out / f'{name}.zip'
        zip_folder(target, zip_path)
        (args.out / f'{name}.sha256').write_text(f'{sha256(zip_path)}  {zip_path.name}\n', encoding='utf-8')
        print(f'{zip_path}  ({zip_path.stat().st_size/1024/1024:.0f} MB)')


if __name__ == '__main__':
    main()
