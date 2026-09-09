"""Lossless, reversible runtime frame preparation; originals remain outside desktop."""
from pathlib import Path
from PIL import Image,ImageChops
from concurrent.futures import ProcessPoolExecutor
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def convert(item):
 index,path,out=item
 im=Image.open(path).convert('RGBA');box=im.getchannel('A').getbbox() or (0,0,1,1)
 box=(max(0,box[0]-2),max(0,box[1]-2),min(im.width,box[2]+2),min(im.height,box[3]+2))
 crop=im.crop(box);crop.save(out,'WEBP',lossless=True,exact=True,method=4)
 decoded=Image.open(out).convert('RGBA')
 if decoded.tobytes()!=crop.tobytes():raise ValueError('Lossless mismatch '+str(path))
 # Pixels removed must all be fully transparent; visible RGBA is unchanged.
 restored=Image.new('RGBA',im.size);restored.paste(decoded,box[:2])
 if restored.getchannel('A').tobytes()!=im.getchannel('A').tobytes():raise ValueError('Alpha mismatch')
 return str(index),{'path':'res://assets/optimized/'+out.name,'crop':[box[0],box[1],crop.width,crop.height,im.width,im.height],'original_bytes':path.stat().st_size,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
def main():
 manifest=json.loads((ROOT/'assets/clips.json').read_text());out=ROOT/'assets/optimized';out.mkdir(exist_ok=True)
 original=ROOT.parent/'artifacts/animation-originals'
 assets=original if original.exists() else ROOT/'assets'
 items=[(i,assets/'frames'/f'frame_{i:04}.png',out/f'{i:04}.webp') for i in range(362)]
 for bank in manifest['banks']:
  for j in range(bank['count']):
   i=bank['start']+j;items.append((i,assets/'scenes'/bank['code']/f'{j:04}.png',out/f'{i:04}.webp'))
 with ProcessPoolExecutor(max_workers=4) as pool:result=dict(pool.map(convert,items,chunksize=8))
 (ROOT/'assets/optimized.json').write_text(json.dumps(result,separators=(',',':')))
 stats={'frames':len(result),'original_bytes':sum(v['original_bytes'] for v in result.values()),'compressed_bytes':sum(v['bytes'] for v in result.values()),'original_rgba_bytes':sum(v['crop'][4]*v['crop'][5]*4 for v in result.values()),'cropped_rgba_bytes':sum(v['crop'][2]*v['crop'][3]*4 for v in result.values()),'all_decoded_rgba_exact':True}
 (ROOT.parent/'validation/animation-optimization/compression.json').write_text(json.dumps(stats,indent=2));print(stats,flush=True)
if __name__=='__main__':main()
