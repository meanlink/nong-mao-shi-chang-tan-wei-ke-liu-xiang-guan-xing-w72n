const WINDOW_OPTIONS = ['早市', '午市', '下午', '晚市'];
const claimStateLabels = {pending: '待补采', fulfilled: '已核销', cancelled: '已撤销'};
const claimStateStyles = {pending: 'amber', fulfilled: 'good', cancelled: 'bad'};

function todayInput() {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export async function resamplingPage(el, {get, post, put, esc, dt, role}) {
  const today = todayInput();
  const [quota, claims, stalls] = await Promise.all([
    get(`/resampling/quota?quota_date=${today}`),
    get(`/resampling/claims?quota_date=${today}`),
    get('/stalls'),
  ]);
  const canManage = role === 'admin';
  const canOperate = role === 'admin' || role === 'analyst';
  const live = claims.filter(c => c.status !== 'cancelled');
  const occupiedSlots = new Set();

  el.innerHTML = `
    <header>
      <div>
        <p class="eyebrow">MODULE 05 / RESAMPLING DESK</p>
        <h1>补采认领</h1>
        <p class="subtitle">按摊位和时段认领当日补采，全员共用管理员设定的名额。同一摊位时段只保留一张待补单，核销后名额不再退回。</p>
      </div>
      <span class="badge">${quota.configured ? `当日余量 ${quota.remaining} / ${quota.total}` : '当日名额未设定'}</span>
    </header>

    <section class="panel quota-panel">
      <div class="panel-title">
        <div><p class="eyebrow">当日共用名额</p><h3>${esc(quota.quota_date)}</h3></div>
        ${quota.configured
          ? `<span class="pill ${quota.remaining ? 'good' : 'bad'}">余量 ${quota.remaining} · 已占用 ${quota.used} / ${quota.total}</span>`
          : '<span class="pill bad">管理员尚未设定名额</span>'}
      </div>
      ${canManage ? `
        <form id="quota-form" class="quota-form">
          <label>名额日期<input type="date" name="quota_date" value="${today}" required></label>
          <label>当日名额<input type="number" name="total" min="0" max="999" value="${quota.total || 0}" required></label>
          <button class="action">保存当日名额</button>
          <p class="feedback" role="status"></p>
        </form>` : `<p class="muted">名额由市场管理员统一设定，巡场人员共用。${quota.updated_at ? `最近更新 ${dt(quota.updated_at)}` : ''}</p>`}
    </section>

    <div class="attribution-grid">
      <section class="panel">
        <div class="panel-title">
          <div><p class="eyebrow">认领一个补采摊位时段</p><h3>新建待补单</h3></div>
          <small>${live.length} 张有效单据</small>
        </div>
        ${canOperate ? (quota.configured && quota.remaining > 0 ? `
          <form id="claim-form" class="attribution-form">
            <label>摊位<select name="stall_id" required>${stalls.map(s =>
              `<option value="${s.id}">${esc(s.code)} · ${esc(s.name)}（${esc(s.zone)}）</option>`).join('')}
            </select></label>
            <label>日期<input type="date" name="claim_date" value="${today}" required></label>
            <label>时段<select name="window_label" required>${WINDOW_OPTIONS.map(w =>
              `<option value="${w}">${w}</option>`).join('')}</select></label>
            <label>补采说明<input name="note" maxlength="255" placeholder="例如：早市计数器漏记，需现场补点"></label>
            <button class="action">认领补采 ↗</button>
            <p class="feedback" role="status"></p>
          </form>` : '<p class="empty">当日名额已用完或尚未设定，暂时无法认领。</p>')
          : '<p class="empty">当前角色为只读，可查看下方单据状态与当日余量。</p>'}
      </section>

      <section class="panel attribution-history">
        <div class="panel-title">
          <div><p class="eyebrow">单据状态</p><h3>当日补采单</h3></div>
          <small>${claims.length} 张</small>
        </div>
        <p class="feedback attribution-notice" role="status"></p>
        ${claims.map(row => `
          <article class="attribution-record" data-claim="${row.id}">
            <div class="attribution-record-heading">
              <div><strong>${esc(row.stall_code)} · ${esc(row.stall_name)}</strong>
                <small>补采单 #${row.id} · ${esc(row.claim_date)} · ${esc(row.window_label)} · ${esc(row.claimed_by)}</small>
              </div>
              <span class="pill ${claimStateStyles[row.status]}">${claimStateLabels[row.status]}</span>
            </div>
            <dl>
              ${row.note ? `<div><dt>说明</dt><dd>${esc(row.note)}</dd></div>` : ''}
              <div><dt>认领时间</dt><dd>${dt(row.created_at)}</dd></div>
              ${row.sample_id ? `<div><dt>核销样本</dt><dd>#${row.sample_id}${row.sample_status ? ` · ${row.sample_status === 'valid' ? '有效' : '异常留档'}` : ''} ${dt(row.fulfilled_at)}</dd></div>` : ''}
              ${row.cancelled_at ? `<div><dt>撤销时间</dt><dd>${dt(row.cancelled_at)}（仅未核销单据可撤销并退回名额）</dd></div>` : ''}
            </dl>
            ${canOperate && row.status === 'pending' ? `
              <form class="attribution-form" data-cancel="${row.id}">
                <label>撤销备注（可选）<input name="note" maxlength="255" placeholder="撤销后名额立即退回，迟到补录仅留档"></label>
                <button class="attribution-return">撤销认领</button>
                <p class="feedback" role="status"></p>
              </form>` : ''}
          </article>`).join('') || '<p class="empty">当日还没有补采单。</p>'}
      </section>
    </div>`;

  const notice = el.querySelector('.attribution-notice');
  const quotaForm = el.querySelector('#quota-form');
  if (quotaForm) {
    quotaForm.addEventListener('submit', async event => {
      event.preventDefault();
      const f = new FormData(quotaForm);
      const feedback = quotaForm.querySelector('.feedback');
      try {
        const next = await put('/resampling/quota', {
          quota_date: f.get('quota_date'), total: Number(f.get('total')),
        });
        feedback.textContent = `名额已保存：${next.used}/${next.total} 已占用，余量 ${next.remaining}。`;
        await resamplingPage(el, {get, post, put, esc, dt, role});
        el.querySelector('.attribution-notice').textContent = '当日名额已更新。';
      } catch (error) {
        feedback.textContent = error.message;
      }
    });
  }

  const claimForm = el.querySelector('#claim-form');
  if (claimForm) {
    claimForm.addEventListener('submit', async event => {
      event.preventDefault();
      const f = new FormData(claimForm);
      const feedback = claimForm.querySelector('.feedback');
      try {
        await post('/resampling/claims', {
          stall_id: Number(f.get('stall_id')),
          claim_date: f.get('claim_date'),
          window_label: f.get('window_label'),
          note: f.get('note') || '',
        });
        await resamplingPage(el, {get, post, put, esc, dt, role});
        el.querySelector('.attribution-notice').textContent = '认领成功，已占用一个当日名额。';
      } catch (error) {
        feedback.textContent = error.message;
      }
    });
  }

  for (const form of el.querySelectorAll('form[data-cancel]')) {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const feedback = form.querySelector('.feedback');
      try {
        await post(`/resampling/claims/${form.dataset.cancel}/cancel`, {
          note: form.elements.note.value || '',
        });
        await resamplingPage(el, {get, post, put, esc, dt, role});
        el.querySelector('.attribution-notice').textContent = '认领已撤销，名额已退回。';
      } catch (error) {
        feedback.textContent = error.message;
      }
    });
  }
}
