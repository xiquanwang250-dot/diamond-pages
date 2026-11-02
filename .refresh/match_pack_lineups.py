"""生成可复核的多对多候选表；分数为组成相似度，不是对应概率。"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from html import escape
import json
import math

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'pack_lineup_matches.json'


def composition(pack_heroes, heroes, core, idf):
    rates = {h['name']: h['appearRate']/100 for h in pack_heroes}
    names = {h['name'] for h in heroes if h.get('name')}
    weights = {n: r*r*idf.get(n, 1) for n, r in rates.items()}
    shared = names & rates.keys()
    coverage = sum(weights[n] for n in shared)/max(sum(weights.values()), 1e-12)
    observed = len(shared)/max(len(names), 1)
    core_coverage = len(core & rates.keys())/max(len(core), 1) if core else observed
    return dict(score=round(100*(.55*coverage+.30*observed+.15*core_coverage), 2),
                weightedCoverage=round(coverage, 4), lineupCoverage=round(observed, 4),
                coreCoverage=round(core_coverage, 4),
                sharedHeroes=sorted(shared, key=lambda n: -rates[n]),
                missingHeroes=sorted(names-rates.keys()),
                unmatchedPackHeroes=sorted(rates.keys()-names, key=lambda n: -rates[n]))


def match(packs, snapshot, details):
    rows = snapshot['lineups']
    frequency = Counter(n for r in rows for n in {h['name'] for h in r['heroes']})
    idf = {n: 1+math.log((len(rows)+1)/(count+1)) for n,count in frequency.items()}
    detail_by_key = {r['lineupKey']: r for r in details['details']}
    results = []
    for pack in packs['packs']:
        candidates = []
        for index,row in enumerate(rows, 1):
            detail = detail_by_key.get(row['lineupKey'], {})
            names = {h['id']: h['name'] for h in row['heroes']}
            core = {names[h['id']] for h in row.get('coreHeroes', []) if h['id'] in names}
            base = composition(pack['heroes'], row['heroes'], core, idf)
            best, best_key, best_names = base, row['lineupKey'], list(names.values())
            for variant in detail.get('variants', []):
                # 低样本变阵不参与判定，但完整详情仍保留。
                if variant.get('count', 0) < 50:
                    continue
                vnames = {h['name'] for h in variant['heroes'] if h.get('name')}
                score = composition(pack['heroes'], variant['heroes'], core & vnames, idf)
                if score['score'] > best['score']:
                    best, best_key, best_names = score, variant['lineupKey'], sorted(vnames)
            equipment_shared, equipment_total = 0, 0
            hero_by_id = {h['id']: h['name'] for h in detail.get('heroes', [])}
            hero_eq = {hero_by_id.get(h['heroId'], h.get('heroName')): h for h in detail.get('heroEquipment', [])}
            for hero in pack['heroes']:
                gear = hero_eq.get(hero['name'])
                if not gear:
                    continue
                a = {str(i['id']) for i in hero.get('topNormalEquipment', [])+hero.get('topNonNormalEquipment', [])}
                b = {str(i['itemId']) for i in sorted(gear.get('items', []), key=lambda i:-i.get('appearanceRate',0))[:10]}
                equipment_shared += len(a & b)
                equipment_total += len(a)
            candidates.append(dict(**best, lineupKey=row['lineupKey'], lineupIndex=index,
                lineupName='、'.join(names.values()), matchedLineupKey=best_key,
                matchedHeroes=best_names, matchType='主阵容' if best_key==row['lineupKey'] else '变阵',
                baseScore=base['score'], equipmentOverlap=round(equipment_shared/equipment_total,4) if equipment_total else None,
                championRateDifference=round(pack['pack']['top1Rate']-100*row['firstRate'],2),
                averageRankDifference=round(pack['pack']['averageRank']-row['avgPlacement'],3)))
        candidates.sort(key=lambda c: (-c['score'], -c['baseScore'], c['lineupKey']))
        top = candidates[0]['score']
        for c in candidates:
            c['retained'] = c['score'] >= 75 and top-c['score'] <= 6
        retained = [c for c in candidates if c['retained']]
        status = '高匹配候选' if len(retained)==1 and top>=90 and top-candidates[1]['score']>=6 else '待确认'
        results.append(dict(packKey=pack['pack']['key'], packName=pack['pack']['name'],
                            status=status, retainedCount=len(retained), candidates=candidates,
                            heroCount=len(pack['heroes'])))
    q=snapshot['meta']['query']
    return dict(meta=dict(generatedAt=datetime.now(timezone.utc).isoformat(),
        packSource=packs['meta'], lineupSource=snapshot['meta'],
        scopeAligned=packs['meta']['days']==q['time'] and packs['meta']['venue']=='master',
        note='55个卡包×22条排行榜阵容的候选关系，非概率或逐局归属；不递归下载变阵。两边具体统计起止日及卡包版本仍待核实。',
        method='分数=55%高出场英雄加权覆盖+30%阵容英雄覆盖+15%核心英雄覆盖。权重=出场率平方×逆阵容频率。主阵容及至少50场的变阵取最高分；装备与胜率仅辅助复核。',
        thresholds='保留分数≥75且距第一名≤6分；唯一候选≥90且领先第二名≥6分标高匹配候选，其余待确认。阈值为启发式，未经真值校准。'), packs=results)


def report(result):
    from local_images import strip, CSS
    e=lambda x:escape(str(x),quote=True)
    cards=[]
    for p in result['packs']:
        rows=[]
        # 全部候选可展开查看，避免隐藏少见的一包多阵容。
        for c in p['candidates']:
            rows.append(f'<tr><td>{"保留" if c["retained"] else "备选"}</td><td><a href="datawxq_details/{c["lineupIndex"]:02d}.html">{e(c["lineupName"])}</a></td><td>{c["score"]} / {c["baseScore"]}</td><td>{e(c["matchType"])}<br>{e("、".join(c["matchedHeroes"]))}</td><td>{e("、".join(c["sharedHeroes"]))}</td><td>{e("、".join(c["missingHeroes"])) or "无"}</td><td>{e(c["equipmentOverlap"])}</td><td>{c["championRateDifference"] if c["championRateDifference"] is not None else "—"}百分点 / {c["averageRankDifference"] if c["averageRankDifference"] is not None else "—"}</td></tr>')
        head='<tr><th>候选</th><th>阵容详情</th><th>匹配分/主阵容分</th><th>匹配组成</th><th>共同英雄</th><th>未在前9英雄中</th><th>装备重合比例</th><th>冠军率差/均名差</th></tr>'
        retained=[r for r,c in zip(rows,p['candidates']) if c['retained']]
        hero_strip=strip(p['candidates'][0]['matchedHeroes'])
        if not retained: retained=rows[:1]
        cards.append(f'<section data-name="{e(p["packName"])}"><h2>{e(p["packName"])} · {e(p["status"])} · 保留{p["retainedCount"]}条</h2><p>第一候选组成</p>{hero_strip}<div class="scroll"><table>{head}{"".join(retained)}</table></div><details><summary>查看全部22条候选</summary><div class="scroll"><table>{head}{"".join(rows)}</table></div></details></section>')
    reverse=[]
    for index in sorted({c['lineupIndex'] for p in result['packs'] for c in p['candidates']}):
        related=[p['packName'] for p in result['packs'] if any(c['retained'] and c['lineupIndex']==index for c in p['candidates'])]
        name=next(c['lineupName'] for c in result['packs'][0]['candidates'] if c['lineupIndex']==index)
        reverse.append(f'<tr><td>{e(name)}</td><td>{e("、".join(related)) or "暂无保留候选"}</td></tr>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>卡包与阵容对应表</title><style>'+CSS+'body{background:#0b1020;color:#edf2fb;font:14px/1.7 sans-serif;margin:24px}section,details{background:#151d30;padding:12px;margin:12px 0;border-radius:8px}a,summary{color:#f5c66a}table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #334155;text-align:left;min-width:95px}.scroll{overflow:auto}input{padding:10px;width:300px}h2{font-size:18px}</style><h1>卡包与阵容多对多候选表</h1><p>最近3天大师场统计，沿用原对应关系和匹配分数；卡包仅有前9英雄；分数是相似度，不是对应概率。自动结果均需复核；不用于合并胜率或估值。未出现的英雄不代表零出场。</p><p>'+e(result['meta']['method'])+'</p><p>'+e(result['meta']['thresholds'])+'</p><details><summary>按阵容反查卡包</summary><div class="scroll"><table>'+''.join(reverse)+'</table></div></details><input placeholder="搜索卡包" oninput="document.querySelectorAll(\'section\').forEach(s=>s.hidden=!s.dataset.name.includes(this.value))">'+''.join(cards)+'</html>'


if __name__ == '__main__':
    from app import atomic_json
    read=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
    result=match(read('heroes_master7.json'),read('datawxq_master.json'),read('datawxq_master_details.json'))
    atomic_json(OUTPUT,result)
    OUTPUT.with_suffix('.html').write_text(report(result),encoding='utf-8')
    print(Counter(p['status'] for p in result['packs']))
    print('retained relations',sum(p['retainedCount'] for p in result['packs']))
    print('best scores',sorted(p['candidates'][0]['score'] for p in result['packs']))
