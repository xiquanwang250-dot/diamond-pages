/* 用静态快照和浏览器算法替代 Flask API；所有路径兼容 GitHub 项目子目录。 */
(()=>{
const nativeFetch=window.fetch.bind(window),base=new URL('../',document.currentScript.src),cache=new Map(),recordKey='diamond-records-v1';
const response=(obj,status=200)=>new Response(JSON.stringify(obj),{status,headers:{'Content-Type':'application/json;charset=utf-8'}});
async function read(path){if(!cache.has(path)){const url=new URL(path,base);url.searchParams.set('v','20261025equip4');cache.set(path,nativeFetch(url,{cache:'no-cache'}).then(async r=>{if(!r.ok)throw Error('快照读取失败：'+path);return r.json()}).catch(e=>{cache.delete(path);throw e}));}return cache.get(path);}
function records(){try{return JSON.parse(localStorage.getItem(recordKey)||'[]')}catch{return []}}
const normalized=value=>Array.isArray(value)?value.map(normalized):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,normalized(value[k])])):value;
const stable=value=>JSON.stringify(normalized(value));
window.fetch=async(input,init={})=>{
 const url=new URL(typeof input==='string'?input:input.url,base),path=url.pathname,apiAt=path.indexOf('/api/');
 if(url.origin!==base.origin||apiAt<0)return nativeFetch(input,init);
 const api=path.slice(apiAt),method=init.method||'GET';
 try{
  if(api==='/api/data')return response(await read('data/data.json'));
  if(api==='/api/heroes')return response(await read('data/heroes.json'));
  if(api==='/api/local-images')return response(await read('data/images/manifest.json'));
  if(api==='/api/calculate'&&method==='POST')return response(DiamondEngine.calculate(await read('data/data.json'),JSON.parse(init.body),records()));
  if(api==='/api/research'){const r=records();return response({records:r.length,matches:new Set(r.map(x=>x.match_id)).size,backtest:DiamondEngine.backtest(r)});}
  if(api==='/api/records/import'&&method==='POST'){
   const incoming=DiamondEngine.validateRecords(JSON.parse(init.body).records),existing=records(),byId=new Map(existing.map(r=>[r.id,r]));
   for(const row of incoming){if(byId.has(row.id)&&stable(byId.get(row.id))!==stable(row))throw Error('已有id内容冲突，未写入；请更换id或核对原始记录。');byId.set(row.id,row);}
   const merged=DiamondEngine.validateRecords([...byId.values()]);try{localStorage.setItem(recordKey,JSON.stringify(merged))}catch{throw Error('浏览器存储空间不足或未授权存储；本次未导入，请减少记录数量。')}
   return response({ok:true,added:merged.length-existing.length,total:merged.length});
  }
  if(api.startsWith('/api/pack-lineups/')){const saved=await read('data/pack_lineup_matches.json'),key=decodeURIComponent(api.slice('/api/pack-lineups/'.length)),p=saved.packs.find(p=>p.packKey===key);if(!p)return response({error:'该卡包尚无匹配数据。'},404);return response({packName:p.packName,status:p.status,candidates:p.candidates.slice(0,p.status==='高匹配候选'?1:2),note:saved.meta.note});}
  if(/^\/api\/lineups\/\d+$/.test(api))return response(await read('data/lineups/'+api.split('/').pop()+'.json'));
  return response({error:'静态版不直接抓取上游网站，请由维护者更新数据快照后发布。'},403);
 }catch(e){return response({error:e.message},400)}
};
})();
