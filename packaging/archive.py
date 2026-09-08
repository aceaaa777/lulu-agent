"""ZIP64 archive with Unix executable/symlink modes and verified file CRCs."""
import hashlib,os,stat,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'dist'
app=root/'Lulu Preview.app'
target=root/'Lulu-0.3-macOS-arm64.zip'
temporary=root/'Lulu-0.3-macOS-arm64.building.zip'
with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
 for base,dirs,files in os.walk(app,followlinks=False):
  for name in dirs+files:
   p=Path(base)/name;rel=p.relative_to(root).as_posix()
   if p.is_symlink():
    info=zipfile.ZipInfo(rel);info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
    z.writestr(info,os.readlink(p))
   elif p.is_file():z.write(p,rel)
print('Written',temporary.stat().st_size,flush=True)
with zipfile.ZipFile(temporary) as z:
 bad=z.testzip()
 if bad:raise RuntimeError('CRC failed: '+bad)
 print('Verified',len(z.infolist()),'entries',flush=True)
temporary.replace(target)
h=hashlib.sha256()
with target.open('rb') as f:
 for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
(root/'Lulu-0.3-macOS-arm64.sha256').write_text(h.hexdigest()+'  '+target.name+'\n')
print(target,flush=True)
