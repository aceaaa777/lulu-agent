"""Packaging: the release assembler and the launcher's package/pet discovery work on a stand-in layout."""
import json
import os
import subprocess
import sys
from pathlib import Path

import desktop_launcher

ROOT = Path(__file__).resolve().parents[1]


def fake_pet(tmp_path, platform):
    pet = tmp_path / 'pet' / platform
    pet.mkdir(parents=True)
    if platform == 'macos':
        import zipfile
        with zipfile.ZipFile(pet / 'Lulu.zip', 'w') as z:
            z.writestr('Lulu.app/Contents/MacOS/Lulu', b'#!/bin/sh\n')
            z.writestr('Lulu.app/Contents/Info.plist', '<plist/>')
    else:
        (pet / ('Lulu.exe' if platform == 'windows' else 'Lulu.x86_64')).write_bytes(b'MZ')
    frames = tmp_path / 'frames.pck'
    frames.write_bytes(b'GDPC' + b'\0' * 100)
    return pet, frames


def build(tmp_path, platform, *extra):
    pet, frames = fake_pet(tmp_path, platform)
    out = tmp_path / 'dist'
    cmd = [sys.executable, str(ROOT / 'packaging/build_release.py'), '--platform', platform, '--pet', str(pet), '--frames', str(frames), '--out', str(out), '--no-zip', *extra]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    return next(out.glob('Lulu-*'))


def test_release_layout_windows_full(tmp_path):
    folder = build(tmp_path, 'windows', '--full', '--frames-url', 'https://example.invalid/frames.pck')
    assert (folder / '安装并启动 Lulu.cmd').exists() and (folder / 'tools/安装并启动.ps1').exists()
    assert (folder / 'pet/Lulu.exe').exists() and (folder / 'pet/frames.pck').exists() and (folder / 'pet/frames.sha256').exists()
    assert (folder / 'agent/lulu/server.py').exists() and (folder / 'agent/entry.py').exists() and (folder / 'agent/安装本地模型.ps1').exists()
    assert not list((folder / 'agent').rglob('__pycache__'))
    release = json.loads((folder / 'release.json').read_text(encoding='utf-8'))
    assert release['edition'] == 'full' and release['platform'] == 'windows' and release['runtime'] == 'source' and release['frames_url'].startswith('https://')
    readme = (folder / '先看这里.md').read_text(encoding='utf-8')
    assert '完整版' in readme and 'SmartScreen' in readme and '{' not in readme
    assert json.loads((folder / 'agent/config.json').read_text(encoding='utf-8')) == {'backend': 'ollama', 'tier': 'auto', 'think': False}


def test_release_layout_macos_lite_with_runtime(tmp_path):
    runtime = tmp_path / 'LuluRuntime'
    runtime.mkdir(); (runtime / 'LuluRuntime').write_bytes(b'\xcf\xfa\xed\xfe'); (runtime / '_internal').mkdir()
    folder = build(tmp_path, 'macos', '--runtime', str(runtime))
    assert (folder / 'pet/Lulu.app/Contents/MacOS/Lulu').exists() and not (folder / 'pet/frames.pck').exists()
    assert (folder / 'runtime/LuluRuntime/LuluRuntime').exists()
    installer = folder / '安装并启动 Lulu.command'
    assert installer.exists() and (os.name == 'nt' or os.access(installer, os.X_OK))
    readme = (folder / '先看这里.md').read_text(encoding='utf-8')
    assert '轻量版' in readme and '不需要装 Python' in readme


def test_launcher_finds_package_root_and_exported_pet(tmp_path, monkeypatch):
    package = tmp_path / 'Lulu-x'
    (package / 'pet').mkdir(parents=True); (package / 'runtime/LuluRuntime').mkdir(parents=True)
    assert desktop_launcher.package_root(package / 'runtime/LuluRuntime') == package.resolve()
    assert desktop_launcher.package_root(tmp_path / 'nowhere') == (tmp_path / 'nowhere').resolve()
    monkeypatch.setattr(sys, 'platform', 'darwin')
    app = package / 'pet/Lulu.app/Contents/MacOS/Lulu'; app.parent.mkdir(parents=True); app.write_bytes(b'')
    command, how = desktop_launcher.find_pet(package)
    assert command == [str(app)] and how.startswith('exported')
    monkeypatch.setattr(sys, 'platform', 'linux')
    command, how = desktop_launcher.find_pet(package)
    assert command is None and '桌宠' in how   # a mac-only package on linux: says so instead of crashing
    (package / 'pet/Lulu.x86_64').write_bytes(b'')
    assert desktop_launcher.find_pet(package)[0] == [str(package / 'pet/Lulu.x86_64')]
