/* Whole-pack expected payouts share the auction calculator's maximum-entropy model. */
(() => {
  'use strict';
  const scriptBase = new URL('.', document.currentScript.src);
  const imageBase = new URL('../images/', scriptBase);
  if (document.querySelector('script[src*="static-api.js"]')) {
    imageBase.pathname = scriptBase.pathname.replace(/static\/$/, 'data/images/');
  }
  const panel = document.createElement('details');
  panel.className = 'panel reward-ranking';
  panel.open = true;
  panel.innerHTML = `<summary>阵容平均收益排行</summary>
    <div class="reward-toolbar"><input type="search" aria-label="搜索收益排行" placeholder="搜索卡包或英雄">
    <label>排序<select><option value="reward">平均预期奖金</option><option value="win">夺冠率</option><option value="rank">平均名次</option><option value="usage">使用率</option></select></label></div>
    <p class="note reward-meta">正在读取数据…</p><div class="reward-list"></div>`;
  document.querySelector('.results').after(panel);
  const search = panel.querySelector('input');
  const sort = panel.querySelector('select');
  const list = panel.querySelector('.reward-list');
  const meta = panel.querySelector('.reward-meta');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const percent = value => Number.isFinite(value) ? value.toFixed(1) + '%' : '—';
  let data, heroes, images = {}, request = 0;

  function portrait(name) {
    const file = images['hero:' + name];
    return file ? `<img src="${escape(new URL(file, imageBase))}" alt="" loading="lazy">` : '';
  }

  function render() {
    if (!data) return;
    const pool = Number(document.getElementById('pool').value);
    const event = document.getElementById('event').value;
    if (!Number.isFinite(pool) || pool < 0 || pool > 1e12) {
      meta.textContent = '请输入有效奖池金额。';
      list.replaceChildren();
      return;
    }
    const query = search.value.trim().toLowerCase();
    const rows = data.packs.map(pack => {
      const members = heroes.packs.find(row => row.pack.key === pack.key)?.heroes || [];
      let estimate = null;
      try { estimate = MaxentEngine.estimate(pack, pool, event); } catch {}
      return {pack, members, estimate};
    });
    const score = row => ({reward: row.estimate?.reward, win: row.pack.top1Rate, rank: -row.pack.averageRank, usage: row.pack.sampleShare})[sort.value];
    rows.sort((a, b) => Number(!a.estimate) - Number(!b.estimate) || (score(b) ?? -Infinity) - (score(a) ?? -Infinity) || a.pack.name.localeCompare(b.pack.name, 'zh-CN'));
    const filtered = rows.map((row, index) => ({...row, position: index + 1})).filter(row => !query || (row.pack.name + ' ' + row.members.map(h => h.name).join(' ')).toLowerCase().includes(query));
    meta.textContent = `${data.meta?.days || '—'}天 · ${data.meta?.venue === 'master' ? '大师场' : '当前分场'} · 奖池 ${pool.toLocaleString('zh-CN')} · ${event === 'winner_take_all' ? '夺冠独享' : '普通分配 50% / 30% / 20%'} · ${filtered.length} / ${rows.length} 个卡包。平均收益为整体预期奖金，未扣拍卖支出；普通分配的亚军、季军率由最大熵模型推算。${data.meta?.fetchedAt ? ' 数据更新于 ' + new Date(data.meta.fetchedAt).toLocaleString('zh-CN') : ''}`;
    list.innerHTML = filtered.map(({pack, members, estimate, position}) => `<article class="reward-card">
      <span class="reward-position">${position}</span><div class="reward-identity"><button class="reward-pack" type="button" data-pack="${escape(pack.key)}">${escape(pack.name)}</button>
      <div class="reward-heroes">${members.slice(0, 9).map(hero => `<span title="${escape(hero.name)}">${portrait(hero.name)}<small>${escape(hero.name)}</small></span>`).join('')}</div></div>
      <div class="reward-metrics"><div><span>平均预期奖金</span><b class="reward-value">${estimate ? Math.round(estimate.reward).toLocaleString('zh-CN') : '无法估算'}</b></div>
      <div><span>使用率</span><b>${percent(pack.sampleShare)}</b></div><div><span>夺冠率</span><b>${percent(pack.top1Rate)}</b></div><div><span>平均名次</span><b>${Number.isFinite(pack.averageRank) ? pack.averageRank.toFixed(2) : '—'}</b></div></div></article>`).join('') || '<p class="empty">没有匹配的阵容</p>';
  }

  async function reload() {
    const current = ++request;
    try {
      const read = async path => {
        const response = await fetch(path);
        const value = await response.json();
        if (!response.ok) throw Error(value.error || '读取失败');
        return value;
      };
      if (!globalThis.MaxentEngine) {
        for (const name of ['valuation.js', 'maxent-engine.js']) {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = new URL(name, scriptBase);
            script.onload = resolve;
            script.onerror = () => reject(Error('收益算法加载失败'));
            document.head.append(script);
          });
        }
      }
      const values = await Promise.all([read('/api/data'), read('/api/heroes'), read('/api/local-images')]);
      if (current !== request) return;
      [data, heroes, images] = values;
      render();
    } catch (error) {
      if (current === request) meta.textContent = '排行读取失败：' + error.message;
    }
  }
  search.addEventListener('input', render);
  sort.addEventListener('change', render);
  for (const id of ['pool', 'event']) document.getElementById(id).addEventListener('input', render);
  list.addEventListener('click', event => {
    const button = event.target.closest('[data-pack]');
    if (!button) return;
    const select = document.getElementById('pack');
    const option = Array.from(select.options).find(option => option.value === button.dataset.pack);
    if (!option && data) {
      document.getElementById('packSearch').value = '';
      select.replaceChildren(...data.packs.map(pack => new Option(pack.name, pack.key)));
    }
    select.value = button.dataset.pack;
    select.dispatchEvent(new Event('change', {bubbles:true}));
    document.querySelector('.battlebar').scrollIntoView({behavior:'smooth', block:'start'});
  });
  window.refreshRewardRanking = reload;
  reload();
})();
