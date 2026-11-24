const stateLabels = {pending: '待复核', approved: '已批准', rejected: '已退回'};
const stateStyles = {pending: 'amber', approved: 'good', rejected: 'bad'};
const noteField = 'required minlength="8" maxlength="500" rows="3"';

export async function attributionPage(el, {get, post, esc, dt, role}) {
  const [samples, corrections, campaigns, stalls] = await Promise.all([
    get('/samples?status=conflicting'), get('/attribution-corrections'),
    get('/campaigns'), get('/stalls'),
  ]);
  const pending = corrections.filter(row => row.status === 'pending');
  const pendingSamples = new Set(pending.map(row => row.sample_id));
  const eligible = samples.filter(sample => !pendingSamples.has(sample.id));
  const stallZones = new Map(stalls.map(stall => [stall.id, stall.zone]));
  const canSubmit = role === 'analyst';
  const canReview = role === 'admin';

  el.innerHTML = `
    <header>
      <div>
        <h1>活动归属复核</h1>
        <p class="subtitle">核对客流样本的活动区域与采样时段。更正获批后，下一次偏相关分析采用更正记录。</p>
      </div>
      <span class="badge">${pending.length} 单待复核</span>
    </header>
    <div class="attribution-grid">
      <section class="panel attribution-source">
        <div class="panel-title"><div><h3>待核对样本</h3></div><small>${samples.length} 条活动冲突</small></div>
        ${samples.length ? `<ul class="attribution-samples">${samples.map(sample => `
          <li>
            <div><strong>${esc(sample.stall_code)} · ${esc(sample.stall_name)}</strong>
              <small>#${sample.id} · ${dt(sample.sampled_at)} · ${sample.footfall} 人 / ${sample.transactions} 笔</small></div>
            ${pendingSamples.has(sample.id) ? '<span class="pill amber">已提交</span>' : ''}
            <p>原始标签 ${esc(sample.campaign_label || '无')} · ${esc(sample.issue_reason)}</p>
          </li>`).join('')}</ul>` : '<p class="empty">当前没有活动归属冲突。</p>'}
        ${canSubmit && eligible.length ? `
          <form id="correction-form" class="attribution-form">
            <h3>提交归属更正</h3>
            <label>冲突样本<select name="sample_id">${eligible.map(sample => `
              <option value="${sample.id}">#${sample.id} · ${esc(sample.stall_code)} · ${dt(sample.sampled_at)}</option>`).join('')}
            </select></label>
            <label>拟归属活动<select name="proposed_campaign_id"></select></label>
            <label>核对依据<textarea name="evidence" ${noteField} placeholder="填写活动排期、收银登记或摊主回执的核对结果"></textarea></label>
            <button class="action">提交复核 ↗</button>
            <p class="feedback" role="status"></p>
          </form>` : ''}
      </section>
      <section class="panel attribution-history">
        <div class="panel-title"><div><h3>更正记录</h3></div><small>${corrections.length} 单</small></div>
        <p class="feedback attribution-notice" role="status"></p>
        ${corrections.map(row => `
          <article class="attribution-record" data-correction="${row.id}">
            <div class="attribution-record-heading">
              <div><strong>${esc(row.stall_code)} · ${esc(row.stall_name)}</strong>
                <small>更正单 #${row.id} · 样本 #${row.sample_id} · ${dt(row.sampled_at)}</small></div>
              <span class="pill ${stateStyles[row.status]}">${stateLabels[row.status]}</span>
            </div>
            <dl>
              <div><dt>原始标签</dt><dd>${esc(row.original_label || '无')} · ${esc(row.original_issue)}</dd></div>
              <div><dt>拟归属</dt><dd>${esc(row.proposed_campaign_name || '日常客流（无活动）')}</dd></div>
              <div><dt>核对依据</dt><dd>${esc(row.evidence)} <small>${esc(row.requested_by)} · ${dt(row.created_at)}</small></dd></div>
              ${row.review_note ? `<div><dt>复核意见</dt><dd>${esc(row.review_note)} <small>${esc(row.reviewed_by)} · ${dt(row.reviewed_at)}</small></dd></div>` : ''}
            </dl>
            ${row.replacement_sample_id ? `<p class="attribution-result">更正样本 #${row.replacement_sample_id} 已纳入有效采样 · <a href="#/analysis">进入偏相关复核 ↗</a></p>` : ''}
            ${canReview && row.status === 'pending' ? `
              <form class="attribution-form" data-review="${row.id}">
                <label>管理员复核意见<textarea name="note" ${noteField} placeholder="填写查验结论或补证要求"></textarea></label>
                <div class="attribution-actions"><button class="action" value="approve">批准更正</button>
                  <button class="attribution-return" value="reject">退回补证</button></div>
                <p class="feedback" role="status"></p>
              </form>` : ''}
          </article>`).join('') || '<p class="empty">提交的更正与复核结果会在这里显示。</p>'}
      </section>
    </div>`;

  const submit = el.querySelector('#correction-form');
  if (submit) {
    const picker = submit.elements.sample_id;
    const options = submit.elements.proposed_campaign_id;
    const showCampaigns = () => {
      const sample = eligible.find(item => item.id === Number(picker.value));
      const valid = campaigns.filter(campaign =>
        (campaign.target_zone === '全场' || campaign.target_zone === stallZones.get(sample.stall_id)) &&
        sample.sampled_at >= campaign.starts_at && sample.sampled_at <= campaign.ends_at);
      options.innerHTML = '<option value="">日常客流（无活动）</option>' + valid.map(campaign =>
        `<option value="${campaign.id}">${esc(campaign.name)} · ${esc(campaign.target_zone)}</option>`).join('');
    };
    picker.addEventListener('change', showCampaigns);
    showCampaigns();
    submit.addEventListener('submit', event => {
      event.preventDefault();
      const fields = new FormData(submit);
      const campaignId = fields.get('proposed_campaign_id');
      save(submit, '/attribution-corrections', {
        sample_id: Number(fields.get('sample_id')),
        proposed_campaign_id: campaignId ? Number(campaignId) : null,
        evidence: fields.get('evidence'),
      }, '更正已提交，等待管理员复核。');
    });
  }

  for (const form of el.querySelectorAll('form[data-review]')) {
    form.addEventListener('submit', event => {
      event.preventDefault();
      const decision = event.submitter?.value;
      if (!decision) return;
      save(form, `/attribution-corrections/${form.dataset.review}/review`, {
        decision, note: form.elements.note.value,
      }, decision === 'approve' ? '已批准，有效采样已更新。' : '已退回，分析师可补证并重新提交。');
    });
  }

  async function save(form, path, payload, message) {
    const feedback = form.querySelector('.feedback');
    const buttons = form.querySelectorAll('button');
    buttons.forEach(button => { button.disabled = true; });
    try {
      await post(path, payload);
    } catch (error) {
      feedback.textContent = error.message;
      buttons.forEach(button => { button.disabled = false; });
      return;
    }
    try {
      await attributionPage(el, {get, post, esc, dt, role});
      el.querySelector('.attribution-notice').textContent = message;
    } catch {
      feedback.textContent = '更正已保存。请刷新页面查看最新记录。';
    }
  }
}
