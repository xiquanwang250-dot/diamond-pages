"""缓存来源数据已公开引用的英雄和装备图标。"""
from pathlib import Path
from html import escape
from functools import lru_cache
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT/'data'/'images'
MANIFEST = IMAGE_DIR/'manifest.json'
CSS = '.hero-strip{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.hero-card{display:inline-flex;flex-direction:column;align-items:center;gap:4px;font-size:12px}.hero-card img{width:64px;height:64px;border:2px solid #c49b46;border-radius:10px;object-fit:cover}.inline-icon{width:30px;height:30px;object-fit:cover;vertical-align:middle;border-radius:6px;margin:2px 5px 2px 0}.gear{display:inline-block;margin:2px 8px 2px 0}'


@lru_cache(maxsize=1)
def manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}


def icon(kind, key, label='', prefix='images/', card=False):
    path = manifest().get(kind+':'+str(key))
    text = escape(str(label or key))
    if not path:
        return text
    image = f'<img class="inline-icon" loading="lazy" src="{escape(prefix+path,quote=True)}" alt="{text}" title="{text}">'
    return f'<span class="hero-card">{image}<span>{text}</span></span>' if card else image+text


def strip(names, prefix='images/'):
    return '<div class="hero-strip">'+''.join(icon('hero',n,n,prefix,True) for n in names)+'</div>'


def download():
    IMAGE_DIR.mkdir(parents=True,exist_ok=True)
    sources={}
    for filename in ('heroes.json','heroes_master7.json'):
        data=json.loads((ROOT/'data'/filename).read_text(encoding='utf-8'))
        for pack in data['packs']:
            for hero in pack['heroes']:
                if hero.get('icon','').startswith('https://'):
                    sources['hero:'+hero['name']]=hero['icon']
                for equipment in hero.get('topNormalEquipment',[])+hero.get('topNonNormalEquipment',[]):
                    if equipment.get('icon','').startswith('https://'):
                        sources['item:'+str(equipment['id'])]=equipment['icon']
    saved=dict(manifest())
    def fetch(entry):
        key,url=entry
        filename=hashlib.sha256(url.encode()).hexdigest()[:24]+'.png'
        target=IMAGE_DIR/filename
        if not target.exists():
            response=requests.get(url,timeout=25)
            response.raise_for_status()
            blob=response.content
            if not (blob.startswith(b'\x89PNG') or blob.startswith(b'\xff\xd8') or blob.startswith(b'RIFF') or blob.startswith(b'GIF8')):
                raise ValueError('非图片响应')
            target.write_bytes(blob)
        return key,filename
    failed=[]
    def safe(entry):
        try:return fetch(entry)
        except Exception as error:
            failed.append({'key':entry[0],'error':str(error)})
    with ThreadPoolExecutor(max_workers=6) as pool:
        for entry in pool.map(safe,sources.items()):
            if entry:saved[entry[0]]=entry[1]
    MANIFEST.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    (IMAGE_DIR/'failures.json').write_text(json.dumps(failed,ensure_ascii=False,indent=2),encoding='utf-8')
    print('saved',len(saved),'failed',len(failed),flush=True)


if __name__=='__main__':download()
