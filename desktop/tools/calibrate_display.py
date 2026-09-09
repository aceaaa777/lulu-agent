"""Measure standing silhouettes; write uniform display transforms, never edit PNGs.
The explicitly retained 8166 close-up is intentionally excluded.
"""
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'assets'
ORIGINALS=ROOT.parent.parent/'artifacts/animation-originals'
SOURCE=ORIGINALS if ORIGINALS.exists() else ROOT
manifest=json.loads((ROOT/'clips.json').read_text())
REFERENCES={'base':0,'7736':362,'9514':531,'2806':868,'2700':989,
    '2822':990,'7305':1327,'7477':1328,'7716':1736,'9641':1905,
    '8290':1906,'3013':2267,'3051':2460,'4321':2581,'6157':2687,
    '6507':2784,'6968':2905}

def original_rect(code):
    if code in manifest['native_banks']:return (0.,20.,528.,297.)
    scale=manifest.get('legacy_display_scale',.92)
    return (264-160*scale,280-280*scale,320*scale,320*scale)

def source_path(frame):
    if frame<362:return SOURCE/'frames'/f'frame_{frame:04d}.png'
    for bank in manifest['banks']:
        if bank['start']<=frame<bank['start']+bank['count']:
            return SOURCE/'scenes'/bank['code']/f"{frame-bank['start']:04d}.png"
    raise ValueError(frame)

def bounds(code,frame):
    rect=original_rect(code)
    image=Image.open(source_path(frame)).convert('RGBA')
    canvas=Image.new('RGBA',(528,320))
    canvas.alpha_composite(image.resize((round(rect[2]),round(rect[3]))),(round(rect[0]),round(rect[1])))
    return canvas.getchannel('A').point(lambda x:255 if x>240 else 0).getbbox()

reference=bounds('2822',990)
height=reference[3]-reference[1];center=(reference[0]+reference[2])/2;floor=reference[3]
calibration={}
for code,frame in REFERENCES.items():
    box=bounds(code,frame);scale=height/(box[3]-box[1])
    x=center-(box[0]+box[2])/2*scale;y=floor-box[3]*scale
    rect=original_rect(code)
    calibration[code]={'reference_frame':frame,'source_bounds':list(box),'scale':scale,
        'rect':[round(rect[0]*scale+x,5),round(rect[1]*scale+y,5),round(rect[2]*scale,5),round(rect[3]*scale,5)]}
manifest['display_calibration']=calibration
manifest['intentional_closeup_banks']=['8166']
(ROOT/'clips.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
