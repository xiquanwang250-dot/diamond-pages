/* 无令牌云端更新入口。只有仓库拥有者在GitHub确认运行后才会抓取并发布。 */
(()=>{
'use strict';
const repo='xiquanwang250-dot/diamond-pages',workflow='update-data.yml';
const toolbar=document.createElement('div');toolbar.className='cloud-update-bar';
toolbar.innerHTML='<button type="button" id="cloudUpdate">更新数据</button><span id="cloudUpdateStatus" role="status" aria-live="polite">大师场 · 最近3天</span><a href="https://github.com/'+repo+'/actions/workflows/'+workflow+'" target="_blank" rel="noopener">查看更新任务</a>';
document.querySelector('.head').after(toolbar);
const css=document.createElement('style');css.textContent='.cloud-update-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0;color:var(--muted);font-size:12px}.cloud-update-bar button{width:auto;padding:8px 14px;min-height:38px}.cloud-update-bar a{color:var(--gold)}@media(max-width:760px){.cloud-update-bar{gap:8px;font-size:11px}.cloud-update-bar span{flex:1;min-width:150px}.cloud-update-bar button{font-size:12px}}';document.head.append(css);
const button=document.getElementById('cloudUpdate'),status=document.getElementById('cloudUpdateStatus');let active=null,timer=null,busy=false;
const api='https://api.github.com/repos/'+repo+'/actions/workflows/'+workflow+'/runs?event=workflow_dispatch&per_page=5';
async function snapshot(){const r=await fetch(new URL('./data/update.json?t='+Date.now(),document.baseURI),{cache:'no-store'});if(r.status===404)return null;if(!r.ok)throw Error('暂时无法读取新快照');return r.json();}
function stop(){clearInterval(timer);timer=null;active=null;button.disabled=false;button.textContent='更新数据';}
async function applyLatest(info){
 window.DiamondPublishedData?.clearCache();await load();await loadHeroes();
 try{IMAGE_MAP=await fetch('/api/local-images').then(r=>r.json());renderHeroes();if(RESULT)render(RESULT.rows,false);window.refreshLineupImages?.();}catch{}
 status.textContent=`更新完成：${info.packs}卡包、${info.offers}条拍品，${info.version}，大师场最近3天。`;stop();
}
async function poll(){
 if(busy||!active)return;busy=true;
 try{
  if(Date.now()-active.since>25*60*1000){status.textContent='已停止等待；可在“查看更新任务”确认结果后刷新网页。';stop();return;}
  const r=await fetch(api,{cache:'no-store',headers:{Accept:'application/vnd.github+json'}});
  if(!r.ok){status.textContent='暂时无法查询进度，更新任务仍可在GitHub查看。';return;}
  const runs=(await r.json()).workflow_runs||[];
  const run=active.runId?runs.find(r=>r.id===active.runId):runs.find(r=>r.head_branch==='main'&&new Date(r.created_at).getTime()>=active.since-10000);
  if(!run){status.textContent='请在GitHub点击 Run workflow（运行工作流）确认更新；本页会自动载入完成后的数据。';return;}
  active.runId=run.id;
  if(run.status!=='completed'){status.textContent='GitHub正在抓取并发布数据，请保留此页，完成后自动载入。';return;}
  if(run.conclusion!=='success'){status.textContent='本次更新未完成（'+run.conclusion+'），保留原数据；请查看GitHub任务日志。';stop();return;}
  const info=await snapshot();
  if(info&&String(info.runId)===String(run.id))await applyLatest(info);
  else status.textContent='任务已完成，正在等待新网页数据发布生效…';
 }catch{status.textContent='网络暂时中断，稍后继续查询；已有数据仍可使用。';}finally{busy=false;}
}
button.onclick=()=>{
 window.open('https://github.com/'+repo+'/actions/workflows/'+workflow,'_blank','noopener');
 if(active)return;
 active={since:Date.now(),runId:null};button.disabled=true;button.textContent='等待更新…';
 status.textContent='已打开GitHub：登录仓库账号，点击 Run workflow 确认运行。';
 timer=setInterval(poll,20000);poll();
};
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&active)poll();});
snapshot().then(info=>{if(info&&!active)status.textContent='上次更新：'+new Date(info.updatedAt).toLocaleString('zh-CN')+' · 大师场近3天';}).catch(()=>{});
})();
