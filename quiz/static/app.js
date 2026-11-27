(() => {
  const L = I18N[localStorage.getItem('vq_lang') || 'be'] || I18N.be;
  const t = (k, v = {}) => (L[k] || k).replace(/\{(\w+)\}/g, (_, x) => v[x] ?? '');
  const $ = (s) => document.querySelector(s);
  const AVATARS = ['🐱', '😼', '🐈', '🐈‍⬛', '🥸', '🦬', '🏰', '⚔️', '📜', '👑', '🦉', '🥔'];
  let me = null, game = null, timer = null, lastParams = {};

  document.querySelectorAll('[data-t]').forEach((el) => { el.textContent = t(el.dataset.t); });
  document.querySelectorAll('[data-ph]').forEach((el) => { el.placeholder = t(el.dataset.ph); });
  try { document.documentElement.dataset.theme = localStorage.getItem('vq_theme') || 'light'; } catch (e) {}

  async function api(path, opts = {}) {
    const r = await fetch(path, { method: opts.body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin', ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (r.status === 401) { show('login'); throw new Error('login'); }
    if (r.status === 409 && (await r.clone().json()).detail === 'player') { await loadPlayers(); throw new Error('player'); }
    if (!r.ok) { const e = new Error((await r.json().catch(() => ({}))).detail || 'error'); e.status = r.status; throw e; }
    return r.json();
  }
  const toast = (msg) => { const el = $('#toast'); el.textContent = msg; el.hidden = false; clearTimeout(el._t); el._t = setTimeout(() => (el.hidden = true), 3000); };

  function show(name) {
    document.querySelectorAll('.screen').forEach((s) => (s.hidden = s.id !== 's-' + name));
    $('#top').hidden = name === 'login';
    $('#who').hidden = !me?.player || name === 'players' || name === 'login';
    if (me?.player) $('#who-name').textContent = me.player.avatar + ' ' + me.player.name;
    window.scrollTo(0, 0);
  }

  // ---------- старт ----------
  async function boot() {
    try { me = await api('/api/me'); } catch (e) { return; }
    const sel = $('#f-era');
    me.eras.forEach((e) => sel.append(new Option(e, e)));
    me.player ? openMenu() : loadPlayers();
  }

  $('#login-form').onsubmit = async (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    try { await api('/api/login', { body: { username: f.get('username'), password: f.get('password') } }); $('#login-err').hidden = true; boot(); }
    catch (e) { $('#login-err').hidden = false; }
  };

  // ---------- гульцы ----------
  function avatarPicker(box, current, onPick) {
    box.replaceChildren(...AVATARS.map((a) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'av' + (a === current ? ' on' : ''); b.textContent = a;
      b.onclick = () => { box.querySelectorAll('.av').forEach((x) => x.classList.remove('on')); b.classList.add('on'); onPick(a); };
      return b;
    }));
  }
  let newAvatar = AVATARS[0];
  async function loadPlayers() {
    me = await api('/api/me');
    const list = await api('/api/players');
    const box = $('#player-tiles');
    box.replaceChildren();
    if (!list.length) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = t('no_players'); box.append(p); }
    list.forEach((p) => {
      const b = document.createElement('button'); b.className = 'tile';
      const a = document.createElement('span'); a.className = 'tile-av'; a.textContent = p.avatar;
      const n = document.createElement('span'); n.className = 'tile-name'; n.textContent = p.name;
      const s = document.createElement('span'); s.className = 'tile-sub'; s.textContent = p.games ? '🏆 ' + p.best : '';
      b.append(a, n, s);
      b.onclick = async () => { const r = await api('/api/player/select', { body: { id: p.id } }); me.player = r.player; openMenu(); };
      box.append(b);
    });
    avatarPicker($('#avatar-pick'), newAvatar, (a) => (newAvatar = a));
    show('players');
  }
  $('#new-player').onsubmit = async (ev) => {
    ev.preventDefault();
    const name = new FormData(ev.target).get('name');
    try { const r = await api('/api/players', { body: { name, avatar: newAvatar } }); me.player = r.player; ev.target.reset(); $('#np-err').hidden = true; openMenu(); }
    catch (e) { $('#np-err').textContent = t(e.message === 'taken' ? 'name_taken' : e.message === 'short' ? 'name_short' : 'err'); $('#np-err').hidden = false; }
  };
  $('#not-me').onclick = async () => {
    if (game && !confirmLeave()) return;
    stopTimer(); game = null;
    await api('/api/player/leave', { body: {} }); me.player = null; loadPlayers();
  };
  const confirmLeave = () => window.confirm(t('not_me_confirm'));

  // ---------- меню ----------
  async function openMenu() {
    game = null; stopTimer();
    $('#menu-name').textContent = me.player.name;
    show('menu');
    try {
      const s = await api('/api/stats');
      $('#menu-note').textContent = t('bank_note', { b: s.bank, e: 121, s: s.seen });
    } catch (e) {}
  }
  document.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => ({ menu: openMenu, stats: openStats, board: openBoard, settings: openSettings })[b.dataset.go]()));

  // ---------- гульня ----------
  $('#play').onclick = () => startGame({ era: $('#f-era').value || null, difficulty: +$('#f-diff').value || null });
  $('#r-again').onclick = () => startGame(lastParams);

  async function startGame(params) {
    lastParams = params;
    const r = await api('/api/game/start', { body: { count: 10, ...params } });
    if (!r.game) { toast(t('exhausted')); return; }
    if (r.exhausted) toast(t('exhausted_part'));
    game = { id: r.game, q: r.question, score: 0 };
    $('#g-score').textContent = '0';
    show('game'); renderQuestion();
  }

  function renderQuestion() {
    const q = game.q;
    game.answered = false;
    $('#g-progress').textContent = t('question_of', { n: q.idx + 1, t: q.total });
    $('#g-era').textContent = q.era || '';
    $('#g-question').textContent = q.question;
    $('#g-feedback').hidden = true;
    const box = $('#g-options');
    box.replaceChildren(...q.options.map((o, i) => {
      const b = document.createElement('button'); b.className = 'opt'; b.textContent = o;
      b.onclick = () => answer(i); return b;
    }));
    startTimer(q.time);
  }

  function startTimer(sec) {
    stopTimer();
    const fill = $('#g-timer'), t0 = performance.now();
    fill.style.width = '100%'; fill.classList.remove('low');
    timer = setInterval(() => {
      const left = 1 - (performance.now() - t0) / (sec * 1000);
      fill.style.width = Math.max(0, left * 100) + '%';
      if (left < 0.25) fill.classList.add('low');
      if (left <= 0) { stopTimer(); answer(-1); }
    }, 100);
  }
  function stopTimer() { clearInterval(timer); timer = null; }

  async function answer(choice) {
    if (!game || game.answered) return;
    game.answered = true; stopTimer();
    const opts = [...document.querySelectorAll('#g-options .opt')];
    opts.forEach((b) => (b.disabled = true));
    if (choice >= 0) opts[choice].classList.add('picked');
    let r;
    try { r = await api(`/api/game/${game.id}/answer`, { body: { idx: game.q.idx, choice } }); }
    catch (e) { toast(t('err')); return; }
    opts[r.correct].classList.add('right');
    if (choice >= 0 && !r.ok) opts[choice].classList.add('wrong');
    if (r.myth != null && choice === r.myth) opts[choice].classList.add('myth');
    const ans = game.q.options[r.correct];
    let v = r.ok ? t('right', { p: r.points }) : choice < 0 ? t('timeout', { a: ans }) : t('wrong', { a: ans });
    if (r.ok && r.streak >= 3) v += ' ' + t('streak', { s: r.streak });
    if (!r.ok && r.myth != null && choice === r.myth) v += ' ' + t('myth_note');
    $('#g-verdict').textContent = v;
    $('#g-verdict').className = 'verdict ' + (r.ok ? 'ok' : 'bad');
    $('#g-expl').textContent = r.explanation;
    const link = $('#g-link');
    if (/^https:\/\//.test(r.link)) { link.href = r.link; link.textContent = t('watch', { t: r.episode_title }); }
    $('#g-score').textContent = r.score;
    $('#g-next').textContent = t(r.next ? 'next' : 'finish');
    $('#g-next').className = 'btn primary ' + (r.ok ? 'ok' : 'bad');
    $('#g-feedback').hidden = false;
    game.last = r;
  }

  $('#g-next').onclick = async () => {
    const r = game.last;
    if (r.next) { game.q = r.next; api(`/api/game/${game.id}/next`, { body: {} }).catch(() => {}); renderQuestion(); }
    else finish(r);
  };
  $('#g-report').onclick = async () => {
    const text = window.prompt(t('report_prompt'));
    if (text === null) return;
    await api('/api/report', { body: { qid: game.q.id, text } }); toast(t('report_thanks'));
  };

  function finish(r) {
    const pct = r.right / r.total;
    $('#r-emoji').textContent = pct >= 0.8 ? '🏆🐱' : pct >= 0.5 ? '👍😼' : '🙀';
    $('#r-title').textContent = t(pct >= 0.8 ? 'result_great' : pct >= 0.5 ? 'result_good' : 'result_bad');
    $('#r-score').textContent = r.score;
    $('#r-line').textContent = t('result_line', { r: r.right, t: r.total, s: r.best_streak });
    game = null; show('result');
  }

  // ---------- статыстыка ----------
  async function openStats() {
    const s = await api('/api/stats');
    const pct = s.asked ? Math.round(s.right / s.asked * 100) + '%' : '—';
    const k = [['k_games', s.games], ['k_points', s.points], ['k_best', s.best], ['k_pct', pct], ['k_seen', s.seen + ' / ' + s.bank], ['k_streak', s.streak]];
    $('#st-kpis').replaceChildren(...k.map(([l, v]) => {
      const d = document.createElement('div'); d.className = 'kpi';
      const a = document.createElement('div'); a.className = 'kpi-v'; a.textContent = v;
      const b = document.createElement('div'); b.className = 'kpi-l'; b.textContent = t(l);
      d.append(a, b); return d;
    }));
    $('#st-eras').replaceChildren(...s.eras.map((e) => {
      const row = document.createElement('div'); row.className = 'bar-row';
      const l = document.createElement('div'); l.className = 'bar-l'; l.textContent = `${e.era || '—'} · ${e.right}/${e.asked}`;
      const tr = document.createElement('div'); tr.className = 'bar-t';
      const f = document.createElement('div'); f.className = 'bar-f'; f.style.width = (e.right / e.asked * 100) + '%';
      tr.append(f); row.append(l, tr); return row;
    }));
    show('stats');
  }

  async function openBoard(period = 'all') {
    document.querySelectorAll('[data-period]').forEach((b) => b.classList.toggle('on', b.dataset.period === period));
    const rows = await api('/api/leaderboard?period=' + period);
    const ol = $('#board');
    ol.replaceChildren();
    if (!rows.length) { const li = document.createElement('li'); li.className = 'muted'; li.textContent = t('board_empty'); ol.append(li); }
    rows.forEach((r, i) => {
      const li = document.createElement('li');
      const n = document.createElement('span'); n.className = 'b-name'; n.textContent = (['🥇', '🥈', '🥉'][i] || '') + ' ' + r.avatar + ' ' + r.name;
      const s = document.createElement('span'); s.className = 'b-score'; s.textContent = r.best;
      const sub = document.createElement('small'); sub.textContent = t('board_line', { g: r.games, p: r.pct });
      li.append(n, s, sub); ol.append(li);
    });
    show('board');
  }
  document.querySelectorAll('[data-period]').forEach((b) => (b.onclick = () => openBoard(b.dataset.period)));

  // ---------- налады ----------
  function openSettings() {
    $('#set-seen').checked = me.player.show_seen;
    avatarPicker($('#set-avatar'), me.player.avatar, async (a) => { const r = await api('/api/settings', { method: 'PUT', body: { avatar: a } }); me.player = r.player; show('settings'); });
    show('settings');
  }
  $('#set-seen').onchange = async (e) => { const r = await api('/api/settings', { method: 'PUT', body: { show_seen: e.target.checked } }); me.player = r.player; };
  document.querySelectorAll('[data-theme]').forEach((b) => (b.onclick = () => {
    document.documentElement.dataset.theme = b.dataset.theme;
    try { localStorage.setItem('vq_theme', b.dataset.theme); } catch (e) {}
  }));
  $('#logout').onclick = async () => { await api('/api/logout', { body: {} }); me = null; show('login'); };

  boot();
})();
