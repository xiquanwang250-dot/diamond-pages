"""下载万象大数据公开阵容排行；不使用账号凭据。"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import secrets
import time
import requests
from html import escape

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data' / 'datawxq_master.json'
API = 'https://api.datatft.com'


def export_html(data, details=None):
    from local_images import strip, icon, CSS
    detail_links = {}
    detail_file = ROOT / 'data' / 'datawxq_master_details.json'
    if details is not None or detail_file.exists():
        saved = details if details is not None else json.loads(detail_file.read_text(encoding='utf-8'))
        if saved['meta']['query'] == data['meta']['query']:
            detail_links = {r['lineupKey']: f'datawxq_details/{i:02d}.html'
                            for i, r in enumerate(saved['details'], 1)}
            detail_links.update({r.get('lookupKey',r['lineupKey']):f'datawxq_details/{i:02d}.html'
                                 for i,r in enumerate(saved['details'],1)})
    def pct(value):
        return f'{float(value)*100:.1f}%'
    cards = []
    for index, row in enumerate(data['lineups'], 1):
        names = {h['id']: h['name'] for h in row['heroes']}
        heroes = '、'.join(names.values())
        commanders = '；'.join(f"{c['name']} {pct(c['appearanceRate'])}" for c in row.get('commanders', []))
        units = ''.join('<tr><td>'+icon('hero',names.get(u['heroId'],u['heroId']))+'</td><td>'+pct(u['appearanceRate'])+'</td><td>'+str(u['count'])+'</td><td>'+pct(u.get('awakenedRate',0))+'</td><td>'+''.join('<span class="gear">'+icon('item',i,n)+'</span>' for i,n in zip(u.get('itemIds',[]),u.get('itemNames',u.get('itemIds',[]))))+'</td></tr>' for u in row.get('recommendedUnits',[]))
        detail_link = ('<p><a href="'+detail_links[row['lineupKey']]+'">查看本地完整阵容详情</a></p>') if row['lineupKey'] in detail_links else ''
        cards.append(f'''<section><h2>{index}. {escape(heroes)}</h2>{strip(names.values())}{detail_link}
<p>场次 {row['count']} · {row['lineupSize']}人阵容 · {row['variantCount']}种变阵</p>
<div class="stats">登场率 <b>{pct(row['appearanceRate'])}</b>　登顶率 <b>{pct(row['firstRate'])}</b>　前三率 <b>{pct(row['top3Rate'])}</b>　平均名次 <b>{float(row['avgPlacement']):.2f}</b></div>
<p>常用棋手：{escape(commanders)}</p><details><summary>英雄出场率与推荐装备</summary><div class="table"><table><thead><tr><th>英雄</th><th>阵容内出场率</th><th>场次</th><th>觉醒率</th><th>推荐装备（未解析时为ID）</th></tr></thead><tbody>{units}</tbody></table></div></details></section>''')
    meta = data['meta']
    header = escape(f"钻石狂潮 · 大师场 · {meta['query']['version']} · 最近{meta['query']['time']}天 · 最少50场 · 共{meta['total']}条阵容")
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>大师场阵容排行 · 本地快照</title><style>body{{background:#0b1020;color:#edf2fb;font:15px/1.7 'Microsoft YaHei',sans-serif;margin:24px auto;padding:0 18px;max-width:1250px}}section{{background:#151d30;border:1px solid #2b3850;border-radius:12px;padding:18px;margin:16px 0}}h1{{font-size:24px}}h2{{font-size:19px}}p{{color:#aebcd2}}b,summary,a{{color:#f5c66a}}summary{{cursor:pointer}}table{{border-collapse:collapse;width:100%;min-width:650px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #2b3850}}.table{{overflow:auto}}{CSS}</style><h1>{header}</h1><p>下载时间（UTC）：{escape(meta['downloadedAt'])}。这是独立来源的本地快照，不参与当前天赋估值。<a href="{escape(meta['source'], quote=True)}">原网站</a></p><p>展开各阵容可看英雄统计。此处出场率表示该阵容统计中的英雄出场比例，不是抽卡概率。已下载的详情可通过各阵容的“查看本地完整阵容详情”打开；文字和数值可离线查看。</p>{''.join(cards)}</html>'''


def query(payload, endpoint='/wzwxq/lineups/search'):
    # 公开网页请求模块的常规签名，与未登录浏览器请求一致。
    stamp, nonce, device = str(int(time.time()*1000)), secrets.token_hex(8), 'did'+secrets.token_hex(12)[:23]
    signature = hashlib.md5((stamp+nonce+device+'koTefnFEdaYDuLFmXyzt').encode()).hexdigest()
    response = requests.post(API+endpoint, json=payload, timeout=45,
                             headers={'t':stamp, 'nonce':nonce, 'did':device, 'signature':signature,
                                      'Accept-Language':'CN', 'Browser-Language':'ZH-CN', 'App-Platform':'wzwxq',
                                      'Origin':'https://www.datawxq.com', 'Referer':'https://www.datawxq.com/'})
    response.raise_for_status()
    result = response.json()
    if result.get('code') is not None and int(result['code']) not in (0, 1, 200):
        raise ValueError(result.get('message') or result.get('msg') or '接口返回错误')
    return result.get('data', result)


def download(days=7, progress=None, version='v261008'):
    from app import atomic_json
    payload = dict(version=version, gameType='4', subModeName='大师场', time=days,
                   operator='AND', advancedMode=False, filters=[], exclusions=[],
                   page=1, pageSize=12, minimumCount=50, sortBy='appearanceRate')
    pages, lineups, seen = [], [], set()
    for page in range(1, 501):
        payload['page'] = page
        data = query(payload)
        rows = data.get('lineups')
        if not isinstance(rows, list):
            raise ValueError('接口没有返回lineups，原文件不变。')
        pages.append(data)
        for row in rows:
            key = row.get('lineupKey')
            if not key or key in seen:
                raise ValueError('阵容标识缺失或分页重复，原文件不变。')
            seen.add(key)
            lineups.append(row)
        total = int(data.get('total', len(lineups)))
        if progress:
            progress(page, len(lineups), total)
        if len(lineups) >= total:
            break
        if not rows:
            raise ValueError('分页提前结束，原文件不变。')
        time.sleep(.2)
    else:
        raise ValueError('分页超过上限，原文件不变。')
    if not lineups or len(lineups) != total:
        raise ValueError('排行数量不完整，原文件不变。')
    name_file = ROOT / 'data' / 'datawxq_item_names.json'
    names = json.loads(name_file.read_text(encoding='utf-8')) if name_file.exists() else {}
    for row in lineups:
        for unit in row.get('recommendedUnits', []):
            unit['itemNames'] = [names.get(i, i) for i in unit.get('itemIds', [])]
    result = dict(meta=dict(source='https://www.datawxq.com/lineups?gameType=4&subModeName=大师场',
                            api=API+'/wzwxq/lineups/search', query={**payload, 'page':1},
                            downloadedAt=datetime.now(timezone.utc).isoformat(), total=total,
                            sampleCount=pages[0].get('sampleCount'),
                            note='独立来源的排行快照；图片保留原始地址，数值和文字保存在本地。'),
                  lineups=lineups, rawPages=pages)
    atomic_json(DATA_FILE, result)
    DATA_FILE.with_suffix('.html').write_text(export_html(result), encoding='utf-8')
    return result


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, choices=[1, 2, 3, 5, 7], default=7)
    parser.add_argument('--version', default='v261008')
    args = parser.parse_args()
    result = download(args.days, lambda p,n,total: print(f'第{p}页 {n}/{total}', flush=True), args.version)
    print('保存到', DATA_FILE)
    print('字段', list(result['lineups'][0]))
    print(json.dumps(result['lineups'][0], ensure_ascii=False)[:8000])
