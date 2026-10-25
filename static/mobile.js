/* 手机展示层：直接读取原有 RESULT，不参与估值计算。 */
(()=>{
const media=matchMedia('(max-width: 760px)'),results=document.querySelector('.results'),tbody=document.getElementById('tbody');
const cards=document.createElement('div');cards.id='mobileResults';cards.className='mobile-results';results.querySelector('.tablewrap').after(cards);
const detailState=new Set();
function mobileResults(){
 const current=typeof RESULT!=='undefined'?RESULT:null;
 if(!current){cards.innerHTML='<p class="mobile-empty">'+esc(tbody.querySelector('.empty')?.textContent||'正在计算…')+'</p>';return;}
 const context=current.pack.key+':'+current.round;
 cards.innerHTML=current.rows.map((r,i)=>{
  const key=context+':'+r['名称'],bid=r['建议最高出价'],delta=r['天赋收益增量'];
  const fields=[['理论最高价',r['理论最高出价']==null?'—':Number(r['理论最高出价']).toFixed(2)],['样本数',fmt(r['样本数'])],['使用率',pct(r['使用率(%)'])],['亚军率（估计）',pct(r['P2估计(%)'])],['季军率（估计）',pct(r['P3估计(%)'])],['买入预期奖金',fmt(r['天赋预期收益'])],['不买预期奖金',fmt(r['不买预期收益'])],['分布可行范围',r['理论价区间下限']==null?'—':fmt(r['理论价区间下限'])+'～'+fmt(r['理论价区间上限'])]];
  return `<article class="mobile-bid-card"><div class="mobile-card-heading"><div class="mobile-talent"><span class="mobile-rank">${i+1}</span><div>${localIcon('talent',r['名称'],r['名称'])}</div></div><div class="mobile-bid"><span>建议最高出价</span><strong>${fmt(bid)}</strong><small class="mobile-theoretical">理论最高价 ${r['理论最高出价']==null?'—':Number(r['理论最高出价']).toFixed(2)}</small></div></div><div class="mobile-card-metrics"><div><span>冠军率</span><b>${pct(r['P1(%)'])}</b></div><div><span>${current.algorithm==='maxent-v1'?'推算前三率':'前三率'}</span><b>${pct(r['前三比例(%)'])}</b></div><div><span>收益增量</span><b class="${delta>0?'good':'bad'}">${delta>0?'+':''}${fmt(delta)}</b></div></div>${bid===null?'<p class="mobile-no-bid">当前条件无法估价，请查看详情或调整不买名次。</p>':''}<details class="mobile-card-details" data-key="${esc(key)}" ${detailState.has(key)?'open':''}><summary>详细指标 <span>样本 ${r['样本数']==null?'未知':fmt(r['样本数'])}</span></summary><dl>${fields.map(([label,value])=>`<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>${r['估值警告']?`<p class="note">${esc(r['估值警告'])}</p>`:''}</details></article>`;
 }).join('')||'<p class="mobile-empty">该轮没有天赋记录</p>';
 cards.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)detailState.add(d.dataset.key);else detailState.delete(d.dataset.key)}));
}
new MutationObserver(mobileResults).observe(tbody,{childList:true});mobileResults();

const bar=document.querySelector('.battlebar'),controls=bar.querySelector('.battle-controls');
for(const id of ['packSearch','manualRank','budget','event'])document.getElementById(id).parentElement.classList.add('mobile-extra-control');
document.getElementById('pack').parentElement.classList.add('mobile-pack-control');
document.getElementById('round').parentElement.classList.add('mobile-round-control');
document.getElementById('pool').parentElement.classList.add('mobile-pool-control');
document.getElementById('calc').parentElement.classList.add('mobile-calc-control');
controls.id='battleControls';
const extra=document.createElement('button');extra.type='button';extra.className='mobile-options-toggle';extra.setAttribute('aria-expanded','false');extra.setAttribute('aria-controls','battleControls');extra.textContent='更多条件：不买名次 / 预算 / 特殊事件';
extra.onclick=()=>{const opened=bar.classList.toggle('mobile-expanded');extra.setAttribute('aria-expanded',String(opened));extra.textContent=opened?'收起更多条件':'更多条件：不买名次 / 预算 / 特殊事件'};controls.after(extra);

const matched=document.getElementById('matchedLineups'),fold=document.createElement('details');fold.className='mobile-lineup-fold';
const summary=document.createElement('summary');summary.textContent='对应阵容 / 装备查询';fold.append(summary);matched.before(fold);fold.append(matched);
function layout(){fold.open=!media.matches;}
media.addEventListener('change',layout);window.addEventListener('resize',layout);layout();

const content=document.getElementById('lineupContent');
function tableLabels(){content.querySelectorAll('table').forEach(table=>{const heads=[...table.querySelectorAll('thead th')].map(h=>h.textContent);table.querySelectorAll('tbody tr').forEach(row=>[...row.cells].forEach((cell,i)=>cell.dataset.label=heads[i]||''));});}
new MutationObserver(tableLabels).observe(content,{childList:true,subtree:true});tableLabels();
})();
