"""Assemble a relocatable preview from frozen Python and pinned local runtimes."""
import hashlib,json,os,plistlib,shutil
from desktop_payload import assemble as assemble_desktop
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'dist/Lulu Preview.app'
PAYLOAD=APP/'Contents/Resources/app'
PAYLOAD.mkdir(parents=True,exist_ok=True)

def copy(source,destination,ignore=None):
 destination.parent.mkdir(parents=True,exist_ok=True)
 if source.is_dir(): shutil.copytree(source,destination,symlinks=True,dirs_exist_ok=True,ignore=ignore)
 else: shutil.copy2(source,destination)

copy(ROOT/'config.json',PAYLOAD/'agent/config.json')
assemble_desktop(ROOT/'desktop',PAYLOAD/'desktop')
copy(ROOT/'build/runtime/LuluRuntime',PAYLOAD/'runtime/LuluRuntime')
copy(Path.home()/'Downloads/Godot.app',PAYLOAD/'runtime/Godot.app')
ollama=Path('/Applications/Ollama.app/Contents/Resources')
for p in ollama.iterdir():
 if p.name.startswith(('ollama','lib','mlx','llama')) and not p.name.endswith('.png'): copy(p,PAYLOAD/'runtime'/p.name)
# Which local models ship inside the bundle: LULU_BUNDLE_TIER=4b (default, two 2507 models) or 8b (one hybrid model).
import sys
sys.path.insert(0,str(ROOT))
from lulu import backends
tier=os.environ.get('LULU_BUNDLE_TIER','4b')
spec=backends.TIERS[tier]
tags=sorted({spec['instruct'],spec['thinking']})
models=Path.home()/'.ollama/models'
licenses=PAYLOAD/'licenses';licenses.mkdir(exist_ok=True)
for tag in tags:
 name,_,version=tag.partition(':')
 manifest=Path('manifests/registry.ollama.ai/library')/name/(version or 'latest')
 if not (models/manifest).exists(): raise SystemExit(f'本机没有 {tag}，先运行 ollama pull {tag}')
 copy(models/manifest,PAYLOAD/'models'/manifest)
 config=json.loads((models/manifest).read_text())
 for layer in [config['config'],*config['layers']]:
  blob=layer['digest'].replace(':','-');copy(models/'blobs'/blob,PAYLOAD/'models/blobs'/blob)
 for layer in config['layers']:
  if layer['mediaType'].endswith('.license'):copy(models/'blobs'/layer['digest'].replace(':','-'),licenses/'QWEN-LICENSE.txt')
for p in [ROOT/'THIRD-PARTY-NOTICES.md']:
 if p.exists():copy(p,licenses/p.name)
(PAYLOAD/'agent/config.json').write_text(json.dumps({'backend':'ollama','tier':tier,'think':False},ensure_ascii=False,indent=2))
exe=APP/'Contents/MacOS/Lulu';exe.parent.mkdir(exist_ok=True)
exe.write_text('#!/bin/sh\nset -eu\nAPP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../Resources/app" && pwd)\ncd "$APP_ROOT/runtime"\nexec /usr/bin/arch -arm64 "$APP_ROOT/runtime/LuluRuntime/LuluRuntime" --root "$APP_ROOT" "$@"\n');exe.chmod(0o755)
with (APP/'Contents/Info.plist').open('wb') as f:
 plistlib.dump({'CFBundleName':'Lulu','CFBundleDisplayName':'Lulu Preview','CFBundleIdentifier':'local.lulu.preview','CFBundleVersion':'0.6.0','CFBundleShortVersionString':'0.6.0','CFBundleExecutable':'Lulu','CFBundlePackageType':'APPL','LSMinimumSystemVersion':'13.0','NSHighResolutionCapable':True,'LSArchitecturePriority':['arm64']},f)
(PAYLOAD/'BUILD.json').write_text(json.dumps({'version':'0.6-preview','platform':'macOS-arm64','tier':tier,'models':tags,'engine':'lulu-loop','includes':['Python','Godot','Ollama','model weights'],'windows_validated':False},indent=2))
print(APP)
