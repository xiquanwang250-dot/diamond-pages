"""公开静态站点的全量数据更新。先暂存整套数据，全部成功后替换；不改算法或卡包关联。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin,quote,urlparse
from html import escape
import argparse,copy,hashlib,json,math,os,re,secrets,shutil,tempfile,time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

WXQ='https://wxq666.top';DATAWXQ='https://www.datawxq.com';API='https://api.datatft.com'
class NoSamples(ValueError):pass

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def session():
    s=requests.Session()
    # 本地可显式选择直连；云端使用runner正常网络，不访问任何本地账号凭据。
    if os.environ.get('DIAMOND_DIRECT')=='1':s.trust_env=False
    s.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=['GET','POST'])))
    return s
def get_json(url):
    r=session().get(url,timeout=35,headers={'User-Agent':'Mozilla/5.0','Referer':WXQ+'/'})
    r.raise_for_status();return r.json()
def query(payload,endpoint):
    stamp=str(int(time.time()*1000));nonce=secrets.token_hex(8);device='did'+secrets.token_hex(12)[:23]
    signature=hashlib.md5((stamp+nonce+device+'koTefnFEdaYDuLFmXyzt').encode()).hexdigest()
    r=session().post(API+endpoint,json=payload,timeout=45,headers={'t':stamp,'nonce':nonce,'did':device,'signature':signature,'Accept-Language':'CN','Browser-Language':'ZH-CN','App-Platform':'wzwxq','Origin':DATAWXQ,'Referer':DATAWXQ+'/'})
    r.raise_for_status();result=r.json();message=str(result.get('message') or result.get('msg') or '')
    if result.get('code') is not None and int(result['code']) not in (0,1,200):
        if '样本过少' in message or '样本不足' in message:raise NoSamples(message)
        raise ValueError('阵容接口失败：'+message)
    return result.get('data',result)
def number(obj,key,low,high):
    value=obj.get(key)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('接口字段无效：'+key)
    return value
def graph(mapping):
    return [(p['packKey'],[(c['lineupKey'],c['lineupIndex'],c['score'],c['retained']) for c in p['candidates']]) for p in mapping['packs']]

def latest_version():
    s=session();r=s.get(DATAWXQ,timeout=35);r.raise_for_status()
    entry=next((urljoin(DATAWXQ,p) for p in re.findall(r'<script[^>]*src="([^"]+)',r.text) if '/assets/index-' in p and 'legacy' not in p),None)
    if not entry:raise ValueError('无法识别阵容网站入口，保留旧数据。')
    r=s.get(entry,timeout=35);r.raise_for_status()
    desktop=re.search(r'(?:\./|assets/)(desktop-main-[A-Za-z0-9_-]+\.js)',r.text)
    if desktop:
        r=s.get(DATAWXQ+'/assets/'+desktop.group(1),timeout=35);r.raise_for_status()
    choices=re.search(r'\[\{value:"(v\d{6})",label:"\1"',r.text)
    if not choices:raise ValueError('无法读取上游当前版本，不使用旧版本冒充更新。')
    return choices.group(1)

def fetch_packs(stamp):
    listing=get_json(WXQ+'/api/v1/diamond/packs?days=3&venue=master');packs=listing.get('data')
    if not isinstance(packs,list) or not packs:raise ValueError('卡包列表为空，保留旧数据。')
    keys=[p.get('key') for p in packs]
    if len(set(keys))!=len(keys) or any(not isinstance(k,str) or not k.startswith('pack-') for k in keys):raise ValueError('卡包标识缺失或重复。')
    def fetch(pack):
        url=WXQ+'/api/v1/diamond/packs/'+quote(pack['key'],safe='')+'?days=3&venue=master';raw=get_json(url);d=raw.get('data',raw)
        if d.get('pack',{}).get('key')!=pack['key']:raise ValueError('卡包详情错配。')
        if not isinstance(d.get('rounds'),list) or not isinstance(d.get('heroes'),list):raise ValueError('卡包详情缺少轮次或英雄。')
        return pack,d,raw.get('meta',{}),url
    with ThreadPoolExecutor(max_workers=3) as pool:details=list(pool.map(fetch,packs))
    items=[];heroes=[];rounds=set();sources={};empty_packs=[]
    for pack,d,meta,url in details:
        number(pack,'top1Rate',0,100);number(pack,'averageRank',1,6)
        hero_rows=d['heroes']
        for h in hero_rows:
            number(h,'appearRate',0,100);number(h,'avgLevel',0,1e9)
            if not isinstance(h.get('name'),str):raise ValueError('英雄名称缺失。')
            if h.get('icon'):sources['hero:'+h['name']]=urljoin(WXQ,h['icon'])
            for e in h.get('topNormalEquipment',[])+h.get('topNonNormalEquipment',[]):
                if e.get('icon'):sources['item:'+str(e['id'])]=urljoin(WXQ,e['icon'])
        heroes.append(dict(pack=d['pack'],heroes=hero_rows,meta=meta,sourceUrl=url));count=0
        for rd in d['rounds']:
            rnd=rd.get('auctionRound')
            if isinstance(rnd,bool) or not isinstance(rnd,int) or not 1<=rnd<=12 or not isinstance(rd.get('items'),list):raise ValueError('拍卖轮次无效。')
            rounds.add(rnd)
            for item in rd['items']:
                for field,lo,hi in [('top1Rate',0,100),('averageRank',1,6),('usageRate',0,100)]:number(item,field,lo,hi)
                if item.get('type') not in ('talent','equipment') or not item.get('name'):raise ValueError('拍品名称或类型无效。')
                n=item.get('sampleCount');top3=item.get('top3Rate')
                if n is not None:number(item,'sampleCount',0,1e12)
                if top3 is not None:number(item,'top3Rate',0,100)
                items.append({'阵容':pack['name'],'阵容标识':pack['key'],'回合':rnd,'名称':item['name'],'类型':item['type'],'平均排名':item['averageRank'],'样本数':n,'第一名比例(%)':item['top1Rate'],'前三比例(%)':top3,'使用率(%)':item['usageRate'],'描述':item.get('description',''),'id':str(item['id']),'icon':item.get('icon'),'平均成交价':item.get('averageCostEnergy')})
                if item.get('icon'):
                    icon=urljoin(WXQ,item['icon']);sources['talent:'+item['name']]=icon
                    sources[('talent-id:' if item['type']=='talent' else 'item:')+str(item['id'])]=icon
                count+=1
        if not count or not hero_rows:
            empty_packs.append(dict(key=pack['key'],name=pack['name'],offers=count,heroes=len(hero_rows)))
    if not items or not any(p['heroes'] for p in heroes):raise ValueError('全部拍品或英雄统计为空，保留旧数据。')
    local=datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    meta=dict(days=3,venue='master',updatedAt=local,fetchedAt=stamp,snapshot=local[:10],auctionRounds=sorted(rounds),source=WXQ,algorithm='maxent-v1',emptyPacks=empty_packs,top3Observed=all(t['前三比例(%)'] is not None for t in items),sampleCountsObserved=all(t['样本数'] is not None for t in items),note='自动更新的大师场最近3天公开快照；部分卡包可能暂无拍品或英雄统计，不使用旧数值填充。亚军、季军及用于估值的前三率为模型推算，缺失字段不编造。')
    return dict(packs=packs,talents=items,meta=meta),dict(packs=heroes,meta=dict(days=3,venue='master',updatedAt=stamp,source=WXQ,expectedPacks=len(packs),downloadedPacks=len(heroes),failed=[],emptyPacks=empty_packs)),sources

def fetch_lineups(data,stamp):
    old_mapping=read(data/'pack_lineup_matches.json');original=graph(old_mapping)
    version=latest_version();print('阵容版本：'+version,flush=True)
    payload=dict(version=version,gameType='4',subModeName='大师场',time=3,operator='AND',advancedMode=False,filters=[],exclusions=[],page=1,pageSize=12,minimumCount=50,sortBy='appearanceRate')
    rows=[];pages=[];seen=set()
    for page in range(1,501):
        result=query({**payload,'page':page},'/wzwxq/lineups/search');batch=result.get('lineups')
        if not isinstance(batch,list):raise ValueError('阵容排行缺少lineups。')
        pages.append(result)
        for row in batch:
            if not row.get('lineupKey') or row['lineupKey'] in seen:raise ValueError('阵容分页重复或标识缺失。')
            seen.add(row['lineupKey']);rows.append(row)
        total=int(result.get('total',0))
        if len(rows)==total and total>0:break
        if not batch or len(rows)>total:raise ValueError('阵容分页不完整。')
    else:raise ValueError('阵容分页超过上限。')
    if not rows:raise ValueError('新阵容排行为空。')
    ranking=dict(meta=dict(source=DATAWXQ+'/lineups?gameType=4&subModeName=大师场',api=API+'/wzwxq/lineups/search',query=payload,downloadedAt=stamp,total=total,sampleCount=pages[0].get('sampleCount')),lineups=rows)
    old_details=[]
    for path in sorted((data/'lineups').glob('*.json'),key=lambda p:int(p.stem)):
        old_details.append(read(path)['detail'])
    if not old_details:raise ValueError('原有阵容槽位缺失。')
    keys=[r.get('lookupKey',r['lineupKey']) for r in old_details]
    for p in old_mapping['packs']:
        for c in p['candidates']:
            if keys[c['lineupIndex']-1]!=c['lineupKey']:raise ValueError('原有对应关系与槽位不一致。')
    for row in rows:
        if row['lineupKey'] not in keys:keys.append(row['lineupKey'])
    existing={r.get('lookupKey',r['lineupKey']):r for r in old_details};ranked={r['lineupKey']:r for r in rows}
    def fetch(key):
        try:row=query({**payload,'lineupKey':key},'/wzwxq/lineups/detail')
        except NoSamples:
            source=ranked.get(key) or existing.get(key)
            if not source:raise ValueError('无法恢复阵容身份。')
            row={k:copy.deepcopy(source[k]) for k in ('lineupKey','heroes')}
            row.update({k:None for k in ('count','appearanceRate','avgPlacement','firstRate','top3Rate')})
            row.update({k:[] for k in ('variants','heroEquipment','recommendedUnits')})
            if key in ranked:
                row.update({k:copy.deepcopy(ranked[key].get(k)) for k in ('count','appearanceRate','avgPlacement','firstRate','top3Rate','recommendedUnits')});status='summary_only';message='近3天详情样本不足，仅展示本次排行摘要，不使用旧详情填充。'
            else:status='unavailable';message='原有对应阵容近3天样本不足；只保留对应关系及英雄身份，不使用历史统计。'
        else:
            if not isinstance(row,dict) or not row.get('lineupKey') or not isinstance(row.get('heroes'),list):raise ValueError('阵容详情缺少身份字段。')
            for field in ('variants','heroEquipment','recommendedUnits'):
                if not isinstance(row.get(field),list):raise ValueError('阵容详情缺少字段：'+field)
            for field in ('firstRate','top3Rate','appearanceRate'):number(row,field,0,1)
            number(row,'count',0,1e12);number(row,'avgPlacement',1,6)
            status='current' if row['lineupKey']==key else 'source_redirect';message='' if status=='current' else '沿用原对应关系；官网对该查询返回调整后的主阵容，统计按当前英雄组成展示。'
        row['lookupKey']=key;row['_snapshot']=dict(status=status,message=message,query=payload,fetchedAt=stamp)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:details=list(pool.map(fetch,keys))
    assert graph(old_mapping)==original
    return ranking,dict(meta={**ranking['meta'],'api':API+'/wzwxq/lineups/detail'},details=details),old_mapping

def image_cache(data,sources):
    folder=data/'images';folder.mkdir(exist_ok=True);manifest=read(folder/'manifest.json');failed=[]
    allowed={'wxq666.top','www.wxq666.top','datawxq.com','www.datawxq.com','api.datatft.com','game.gtimg.cn','game.gtimg.cn','img.datatft.com','cdn.datatft.com'}
    def fetch(pair):
        key,url=pair;name=hashlib.sha256(url.encode()).hexdigest()[:24]+'.png';path=folder/name
        try:
            if urlparse(url).scheme!='https' or urlparse(url).hostname not in allowed:raise ValueError('图标域名未登记')
            if not path.exists():
                r=session().get(url,timeout=25);r.raise_for_status();blob=r.content
                if len(blob)>5_000_000 or not blob.startswith((b'\x89PNG',b'\xff\xd8',b'RIFF',b'GIF8')):raise ValueError('图标响应无效')
                path.write_bytes(blob)
            return key,name
        except Exception:failed.append(key);return key,None
    with ThreadPoolExecutor(max_workers=4) as pool:
        for key,name in pool.map(fetch,sources.items()):
            if name:manifest[key]=name
    write(folder/'manifest.json',manifest)
    return len(failed)

def render_reports(stage,ranking,details,mapping):
    import fetch_datawxq as listing,fetch_datawxq_details as reports,local_images,match_pack_lineups
    listing.ROOT=reports.ROOT=local_images.ROOT=stage
    listing.DATA_FILE=stage/'data/datawxq_master.json'
    local_images.IMAGE_DIR=stage/'data/images';local_images.MANIFEST=local_images.IMAGE_DIR/'manifest.json';local_images.manifest.cache_clear()
    reports.HTML_DIR=stage/'data/datawxq_details'
    reports.write_reports(details)
    (stage/'data/datawxq_master.html').write_text(listing.export_html(ranking,details),encoding='utf-8')
    (stage/'data/pack_lineup_matches.html').write_text(match_pack_lineups.report(mapping),encoding='utf-8')

def refresh(site):
    site=site.resolve();original=site/'data'
    if not (original/'data.json').exists():raise ValueError('未找到网站数据目录。')
    stamp=datetime.now(timezone.utc).isoformat();print('开始更新：大师场，最近3天',flush=True)
    with tempfile.TemporaryDirectory(prefix='diamond-refresh-',dir=site.parent) as temp:
        stage=Path(temp)/'site';data=stage/'data';shutil.copytree(original,data)
        valuation,heroes,sources=fetch_packs(stamp);print(f"卡包 {len(valuation['packs'])}，拍品 {len(valuation['talents'])}，英雄统计已获取",flush=True)
        ranking,details,mapping=fetch_lineups(data,stamp)
        packs={p['key']:p for p in valuation['packs']}
        for p in mapping['packs']:
            pack=packs.get(p['packKey'])
            for c in p['candidates']:
                row=details['details'][c['lineupIndex']-1]
                c['championRateDifference']=round(pack['top1Rate']-100*row['firstRate'],2) if pack and row.get('firstRate') is not None else None
                c['averageRankDifference']=round(pack['averageRank']-row['avgPlacement'],3) if pack and row.get('avgPlacement') is not None else None
        mapping['meta'].update(packSource=heroes['meta'],lineupSource=details['meta'],relationshipStrategy='reuse-original',note='自动更新大师场最近3天统计，原卡包对应关系、顺序及匹配分保留；缺少新样本不使用旧值填充。')
        for row in ranking['lineups']:
            for hero in row['heroes']:
                if hero.get('icon'):sources['hero:'+hero['name']]=urljoin(DATAWXQ,hero['icon'])
        icon_failures=image_cache(data,sources)
        write(data/'data.json',valuation);write(data/'heroes.json',heroes);write(data/'pack_lineup_matches.json',mapping)
        write(data/'datawxq_master.json',ranking);write(data/'datawxq_master_details.json',details)
        public_keys=('lineupKey','lookupKey','_snapshot','heroes','count','appearanceRate','avgPlacement','firstRate','top3Rate','recommendedUnits','variants','heroEquipment')
        for i,row in enumerate(details['details'],1):write(data/'lineups'/f'{i}.json',dict(detail={k:row.get(k) for k in public_keys},meta=details['meta']))
        render_reports(stage,ranking,details,mapping)
        result=dict(updatedAt=stamp,runId=os.environ.get('GITHUB_RUN_ID'),days=3,venue='master',version=ranking['meta']['query']['version'],packs=len(valuation['packs']),offers=len(valuation['talents']),lineups=len(ranking['lineups']),detailSlots=len(details['details']),iconFailures=icon_failures,relationshipStrategy='reuse-original')
        write(data/'update.json',result)
        # 完整暂存并渲染后再替换；失败时还原原目录。CI还会保存完整旧数据artifact及Git历史。
        backup=site/('.data-before-refresh-'+str(time.time_ns()))
        os.replace(original,backup)
        try:shutil.move(str(data),str(original))
        except BaseException:
            os.replace(backup,original);raise
        if os.environ.get('GITHUB_ACTIONS')=='true':shutil.rmtree(backup)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--site-root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    refresh(args.site_root)
