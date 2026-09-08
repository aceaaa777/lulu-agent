"""Ship imported textures once; editable WebP originals stay in development source.

Godot's .import sidecars map logical image paths to .godot/imported/*.ctex.
A runtime (not editor) needs the mapping and imported texture, not a second image.
"""
from pathlib import Path
import shutil,re

def assemble(source: Path, destination: Path, include_tests=False):
 if destination.exists():shutil.rmtree(destination)
 destination.mkdir(parents=True)
 for folder in ['src','assets']+(['tests'] if include_tests else []):
  for p in (source/folder).rglob('*'):
   if not p.is_file():continue
   if p.suffix in ['.png','.webp','.csv','.translation']:continue
   q=destination/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
   if p.suffix=='.import':
    refs=re.findall(r'"res://(\.godot/imported/[^"\n]+)"',p.read_text())
    for ref in set(refs):
     original=source/ref
     if not original.is_file():raise FileNotFoundError(original)
     target=destination/ref;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
 for name in ['project.godot','main.tscn']:
  shutil.copy2(source/name,destination/name)
 for name in ['global_script_class_cache.cfg','uid_cache.bin']:
  p=source/'.godot'/name
  if p.exists():shutil.copy2(p,destination/'.godot'/name)
 if not (destination/'assets/optimized.json').exists():raise ValueError('Optimize and import frames first')
 return sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path);parser.add_argument('--tests',action='store_true');a=parser.parse_args()
 print(assemble(a.source,a.destination,a.tests))
