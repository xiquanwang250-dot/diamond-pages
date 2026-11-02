"""保存排行榜对应的全部详情响应及离线可读页面。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json
import time

from fetch_datawxq import ROOT, DATA_FILE, query

DETAIL_FILE = ROOT / 'data' / 'datawxq_master_details.json'
HTML_DIR = ROOT / 'data' / 'datawxq_details'
FIELDS = {'count':'场次', 'appearanceRate':'出场率', 'firstRate':'登顶率', 'top3Rate':'前三率',
          'avgPlacement':'平均名次', 'similarity':'相似度', 'avgLevel':'平均等级', 'mvpRate':'MVP率',
          'placementDelta':'名次差', 'averageItemCount':'平均装备数', 'awakenedRate':'觉醒率',
          'threeItemRate':'三装备率', 'lineupKey':'阵容标识', 'lineupCode':'阵容代码',
          'heroId':'英雄', 'itemId':'装备', 'id':'名称', 'name':'名称', 'heroName':'英雄名',
          'itemName':'装备名', 'itemNames':'装备组合', 'itemIds':'装备ID', 'heroes':'阵容英雄',
          'addedHeroes':'加入英雄', 'removedHeroes':'移除英雄', 'cardType':'类型'}


def detail_html(detail, meta, index, names):
    from local_images import strip, icon, CSS, manifest
    hero_names = {}
    for row in [detail]+detail.get('variants', []):
        for hero in row.get('heroes', []):
            if hero.get('name'):
                hero_names[hero['id']] = hero['name']
    for row in detail.get('heroEquipment', []):
        if row.get('heroName'):
            hero_names[row['heroId']] = row['heroName']

    def value(key, val):
        if val is None:
            return '—'
        if key in ('appearanceRate','firstRate','top3Rate','similarity','mvpRate','awakenedRate','threeItemRate'):
            return f'{float(val)*100:.2f}%'
        if key == 'heroId':
            return hero_names.get(str(val), names.get(str(val), str(val)))
        if key in ('id', 'itemId'):
            return names.get(str(val), hero_names.get(str(val), str(val)))
        if key in ('heroes', 'addedHeroes', 'removedHeroes'):
            return '、'.join(h.get('name') or hero_names.get(h['id'], names.get(h['id'], h['id'])) for h in val)
        if isinstance(val, list):
            return '、'.join(str(x) for x in val)
        if isinstance(val, float):
            return f'{val:.4f}'
        return str(val)

    def table(rows, title):
        if not rows:
            return f'<p>{escape(title)}：接口未返回记录。</p>'
        keys = [key for key in FIELDS if any(key in r for r in rows)]
        head = ''.join(f'<th>{FIELDS[k]}</th>' for k in keys)
        def cell(k,r):
            val=r.get(k)
            if val is None:return '—'
            if k=='heroId':return icon('hero',value(k,val),prefix='../images/')
            if k=='id' and 'talent-id:'+str(val) in manifest():return icon('talent-id',val,value(k,val),prefix='../images/')
            if k=='itemId':return icon('item',val,value(k,val),prefix='../images/')
            if k=='itemIds':return ''.join(icon('item',i,names.get(str(i),str(i)),prefix='../images/')+' ' for i in val)
            if k=='heroes':return strip([h.get('name',hero_names.get(h['id'],h['id'])) for h in val],prefix='../images/')
            return escape(value(k,val))
        body = ''.join('<tr>'+''.join(f'<td>{cell(k,r)}</td>' for k in keys)+'</tr>' for r in rows)
        return f'<details><summary>{escape(title)}（{len(rows)}条）</summary><div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>'

    freshness=detail.get('_snapshot',{})
    notice=('<p style="padding:12px;border:1px solid #f5c66a;color:#f5c66a">'+escape(freshness.get('message',''))+'</p>') if freshness.get('message') else ''
    content = notice+strip([h['name'] for h in detail['heroes']],prefix='../images/')+table(detail.get('variants', []), '相似变阵')
    content += table(detail.get('commanders', []), '棋手统计')
    content += table(detail.get('talents', []), '天赋与技能统计')
    content += table(detail.get('recommendedUnits', []), '推荐英雄及装备')
    for hero in detail.get('heroEquipment', []):
        label = value('heroId', hero['heroId'])
        content += f'<details><summary>英雄装备详情：{escape(label)} · {hero.get("count",0)}场</summary>'
        content += table([hero], '英雄整体统计')+table(hero.get('items', []), '单装备统计')+table(hero.get('builds', []), '三装备组合')+'</details>'
    for number, board in enumerate(detail.get('referenceBoards', []), 1):
        moment = datetime.fromtimestamp(board['gameTime']/1000, timezone.utc).isoformat() if board.get('gameTime') else '—'
        units = [dict(name=u.get('hero_name',u.get('hero_id','')), level=u.get('level'),
                      x=u.get('position_x'), z=u.get('position_z'), awakened=u.get('is_awakened'),
                      equipment='、'.join(u.get('item_names', u.get('item_ids',[])))) for u in board.get('units', [])]
        content += f'<details><summary>参考站位 {number} · 第{board.get("placement","—")}名 · {moment}</summary><p>坐标为原接口x/z坐标，未转换棋盘朝向。</p><div class="scroll"><table><tr><th>英雄</th><th>等级</th><th>x</th><th>z</th><th>觉醒</th><th>装备</th></tr>'
        content += ''.join('<tr>'+''.join('<td>'+escape(str(u[k]))+'</td>' for k in ('name','level','x','z','awakened','equipment'))+'</tr>' for u in units)+'</table></div></details>'
    title = '、'.join(h['name'] for h in detail['heroes'])
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · 本地阵容详情</title><style>body{{background:#0b1020;color:#edf2fb;font:14px/1.7 'Microsoft YaHei',sans-serif;margin:24px auto;padding:0 18px;max-width:1500px}}details{{border:1px solid #2b3850;background:#151d30;padding:12px;margin:12px 0;border-radius:8px}}summary,a{{color:#f5c66a;cursor:pointer}}table{{border-collapse:collapse;min-width:600px;width:100%}}td,th{{border-bottom:1px solid #2b3850;text-align:left;padding:8px;white-space:nowrap}}.scroll{{overflow:auto}}pre{{white-space:pre-wrap;word-break:break-all}}h1{{font-size:22px}}{CSS}</style><a href="index.html">返回详情目录</a><h1>{index}. {escape(title)}</h1><p>大师场 · 版本 {escape(meta['query']['version'])} · 最近{meta['query']['time']}天 · 下载时间UTC {escape(meta['downloadedAt'])}</p><p>详情总场次 {value('count',detail['count'])}，登顶率 {value('firstRate',detail['firstRate'])}，前三率 {value('top3Rate',detail['top3Rate'])}，平均名次 {value('avgPlacement',detail['avgPlacement'])}。显示全部接口返回记录，未再按前端最小样本过滤；低样本结果应谨慎解读。</p>{content}<details><summary>完整原始响应（所有字段）</summary><pre>{escape(json.dumps(detail,ensure_ascii=False,indent=2))}</pre></details></html>'''


def write_reports(result):
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    names_file = ROOT/'data'/'datawxq_item_names.json'
    names = json.loads(names_file.read_text(encoding='utf-8')) if names_file.exists() else {}
    links = []
    for index, detail in enumerate(result['details'], 1):
        filename = f'{index:02d}.html'
        meta=result['meta']
        if detail.get('_snapshot',{}).get('status')=='historical':
            meta={**meta,'query':detail['_snapshot']['query'],'downloadedAt':detail['_snapshot']['fetchedAt']}
        (HTML_DIR/filename).write_text(detail_html(detail,meta,index,names),encoding='utf-8')
        title = '、'.join(h['name'] for h in detail['heroes'])
        links.append(f'<li><a href="{filename}">{escape(title)}</a>（{detail["count"] if detail["count"] is not None else "暂无统计"}场）</li>')
    (HTML_DIR/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>大师场阵容详情目录</title><style>body{font:16px/2 sans-serif;margin:30px;background:#0b1020;color:#edf2fb}a{color:#f5c66a}{CSS}</style><h1>大师场阵容详情 · 本地快照</h1><p>与排行相同筛选条件；下载时间不同，场次可能略有变化。</p><ol>'+''.join(links)+'</ol>',encoding='utf-8')


def download(progress=None):
    from app import atomic_json
    snapshot = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    rows = snapshot['lineups']
    if len(rows) != snapshot['meta']['total']:
        raise ValueError('本地排行不完整，停止下载详情。')

    def fetch(row):
        payload = {**snapshot['meta']['query'], 'lineupKey':row['lineupKey'], 'page':1}
        for attempt in range(3):
            try:
                detail = query(payload, '/wzwxq/lineups/detail')
                if detail.get('lineupKey') != row['lineupKey']:
                    raise ValueError('详情阵容标识不匹配')
                for field in ('variants','heroEquipment','commanders','talents','referenceBoards','heroes','recommendedUnits'):
                    if not isinstance(detail.get(field), list):
                        raise ValueError('缺少详情字段：'+field)
                return detail
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt+1)

    fetched = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        pending = {executor.submit(fetch,row):row['lineupKey'] for row in rows}
        for task in as_completed(pending):
            fetched[pending[task]] = task.result()
            if progress:
                progress(len(fetched),len(rows))
    result = dict(meta={**snapshot['meta'], 'downloadedAt':datetime.now(timezone.utc).isoformat(),
                        'api':'https://api.datatft.com/wzwxq/lineups/detail',
                        'note':'排行对应阵容详情的完整响应；未递归下载变阵的详情。'},
                  details=[fetched[row['lineupKey']] for row in rows])
    atomic_json(DETAIL_FILE,result)
    write_reports(result)
    return result


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    result = download(lambda done,total:print(f'详情 {done}/{total}',flush=True))
    print('保存到',DETAIL_FILE)
    print('离线目录',HTML_DIR/'index.html')
