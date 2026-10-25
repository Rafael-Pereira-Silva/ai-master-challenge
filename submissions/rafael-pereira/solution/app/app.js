/* Lead Scorer — interface. JavaScript puro, script clássico (funciona em file:// e no GitHub Pages).
   Tudo o que aparece com número vem de window.LEAD_DATA (contrato em data-contract.md).
   A interface filtra, mas nunca reordena: a ordem dos deals é a do data.js. */
(function () {
  'use strict';

  var D = window.LEAD_DATA;
  function $(id) { return document.getElementById(id); }

  if (!D || !D.meta || !D.people || !D.snapshots || !D.snapshots.length) {
    $('no-data').hidden = false;
    return;
  }
  $('app').hidden = false;

  /* ------------------------------------------------------------------ constantes de interface */
  var CATS = ['Foque', 'Reative', 'Limpe', 'Qualifique'];   // identificadores das listas (vêm do contrato)
  var PAGE_SIZE = 30;                                        // quantos cards por vez (parâmetro de layout)
  var TEST = 'teste';
  var TODAY = 'hoje';

  /* ------------------------------------------------------------------ formatação PT-BR */
  var nf0 = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
  var nf1 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  var nf2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  // Arredonda metade para cima, descartando ruído de ponto flutuante (igual ao fmt.py do motor).
  function rhu(x) { return Math.round(Number(Number(x).toFixed(10))); }
  function num(n) { return nf0.format(rhu(n)); }
  function usd(n) { return 'US$ ' + num(n); }
  function pct0(f) { return num(f * 100) + '%'; }
  function pct1(f) { return nf1.format(Number((f * 100).toFixed(10))) + '%'; }
  function dec2(f) { return nf2.format(Number(Number(f).toFixed(10))); }
  function dateBR(iso) {
    if (!iso) { return ''; }
    var p = String(iso).split('-');
    return p[2] + '/' + p[1] + '/' + p[0];
  }
  var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ESC[c]; }); }
  function plural(n, one, many) { return n === 1 ? one : many; }
  function days(n) { return num(n) + ' ' + plural(n, 'dia', 'dias'); }
  function joinPt(parts) {
    if (parts.length < 2) { return parts.join(''); }
    return parts.slice(0, -1).join(', ') + ' e ' + parts[parts.length - 1];
  }
  function byName(a, b) { return a.localeCompare(b, 'pt-BR', { sensitivity: 'base' }); }

  /* ------------------------------------------------------------------ índices */
  var HORIZON = D.meta.horizon_days;
  var agentsByName = {};
  var managersByName = {};
  D.people.agents.forEach(function (a) { agentsByName[a.name] = a; });
  D.people.managers.forEach(function (m) { managersByName[m.name] = m; });
  var snapByDate = {};
  D.snapshots.forEach(function (s) { snapByDate[s.date] = s; });
  var todaySnap = D.snapshots.filter(function (s) { return s.mode === TODAY; })[0] || D.snapshots[0];

  // contagem de deals por vendedor em cada snapshot (para "sem deals abertos" no seletor)
  var perAgentCache = {};
  function perAgent(snap) {
    if (!perAgentCache[snap.date]) {
      var m = {};
      snap.deals.forEach(function (d) { m[d.agent] = (m[d.agent] || 0) + 1; });
      perAgentCache[snap.date] = m;
    }
    return perAgentCache[snap.date];
  }

  /* ------------------------------------------------------------------ estado (no location.hash) */
  var state = { vendedor: '', manager: '', regiao: '', modo: '', aba: '' };   // aba vazia = automática (1ª lista com deals)
  var activeCat = 'Foque';                                                    // lista aberta agora

  function normalize(s) {
    if (s.regiao && D.people.regions.indexOf(s.regiao) < 0) { s.regiao = ''; }
    var m = s.manager ? managersByName[s.manager] : null;
    if (s.manager && !m) { s.manager = ''; m = null; }
    if (m && s.regiao && m.region !== s.regiao) { s.manager = ''; }
    var a = s.vendedor ? agentsByName[s.vendedor] : null;
    if (s.vendedor && !a) { s.vendedor = ''; a = null; }
    if (a && s.manager && a.manager !== s.manager) { s.vendedor = ''; }
    if (a && s.regiao && a.region !== s.regiao) { s.vendedor = ''; }
    if (!snapByDate[s.modo] || snapByDate[s.modo] === todaySnap) { s.modo = ''; }
    if (CATS.indexOf(s.aba) < 0) { s.aba = ''; }
    return s;
  }
  function parseHash() {
    var p = new URLSearchParams((location.hash || '').replace(/^#/, ''));
    return normalize({
      vendedor: p.get('vendedor') || '', manager: p.get('manager') || '', regiao: p.get('regiao') || '',
      modo: p.get('modo') || '', aba: p.get('aba') || ''
    });
  }
  function serialize(s) {
    var p = new URLSearchParams();
    if (s.vendedor) { p.set('vendedor', s.vendedor); }
    if (s.manager) { p.set('manager', s.manager); }
    if (s.regiao) { p.set('regiao', s.regiao); }
    if (s.modo) { p.set('modo', s.modo); }
    if (s.aba) { p.set('aba', s.aba); }
    return p.toString();
  }
  var lastHash = '';
  function writeHash() {
    lastHash = serialize(state);
    var url = lastHash ? '#' + lastHash : location.pathname + location.search;
    try { history.replaceState(null, '', url); }
    catch (e) { location.hash = lastHash; }
  }

  function currentSnap() { return state.modo ? snapByDate[state.modo] : todaySnap; }
  function isTest(snap) { return snap.mode === TEST; }

  /* ------------------------------------------------------------------ dados filtrados */
  function filterDeals(snap) {
    var s = state;
    return snap.deals.filter(function (d) {
      return (!s.vendedor || d.agent === s.vendedor) &&
             (!s.manager || d.manager === s.manager) &&
             (!s.regiao || d.region === s.regiao);
    });
  }
  function groupByCat(list) {
    var g = {};
    CATS.forEach(function (c) { g[c] = []; });
    list.forEach(function (d) { if (g[d.cat]) { g[d.cat].push(d); } });
    return g;
  }
  function statsOf(groups) {
    var st = {};
    CATS.forEach(function (c) {
      var n = 0, valor = 0, ev = 0;
      groups[c].forEach(function (d) { n += 1; valor += d.price; if (d.ev != null) { ev += d.ev; } });
      st[c] = { n: n, valor: valor, ev: ev };
    });
    return st;
  }

  /* ------------------------------------------------------------------ controles (barra e filtros) */
  var modeSel = $('mode-select');
  var agentSel = $('filter-agent');
  var managerSel = $('filter-manager');
  var regionSel = $('filter-region');
  var lastOptions = { agent: null, manager: null, region: null };

  modeSel.innerHTML = D.snapshots.map(function (s) {
    return '<option value="' + esc(s.date) + '">' + esc(s.label) + '</option>';
  }).join('');

  function setOptions(sel, key, html, value) {
    if (lastOptions[key] !== html) { sel.innerHTML = html; lastOptions[key] = html; }
    sel.value = value;
  }

  function renderControls(snap) {
    modeSel.value = snap.date;

    setOptions(regionSel, 'region',
      '<option value="">Todas as regiões</option>' + D.people.regions.slice().sort(byName).map(function (r) {
        return '<option value="' + esc(r) + '">' + esc(r) + '</option>';
      }).join(''), state.regiao);

    var mans = D.people.managers.filter(function (m) { return !state.regiao || m.region === state.regiao; })
      .sort(function (a, b) { return byName(a.name, b.name); });
    setOptions(managerSel, 'manager',
      '<option value="">Todos os managers</option>' + mans.map(function (m) {
        return '<option value="' + esc(m.name) + '">' + esc(m.name) + '</option>';
      }).join(''), state.manager);

    var counts = perAgent(snap);
    var html = '<option value="">Todos os vendedores — escolha seu nome</option>';
    mans.forEach(function (m) {
      if (state.manager && m.name !== state.manager) { return; }
      var ags = D.people.agents.filter(function (a) { return a.manager === m.name; })
        .sort(function (a, b) { return byName(a.name, b.name); });
      if (!ags.length) { return; }
      html += '<optgroup label="' + esc('Time de ' + m.name + ' — ' + m.region) + '">' + ags.map(function (a) {
        var suffix = !a.has_deals ? ' (sem deals no CRM)' : (!counts[a.name] ? ' (sem deals abertos)' : '');
        return '<option value="' + esc(a.name) + '">' + esc(a.name + suffix) + '</option>';
      }).join('') + '</optgroup>';
    });
    setOptions(agentSel, 'agent', html, state.vendedor);
  }

  function renderBanner(snap) {
    var el = $('test-banner');
    if (!isTest(snap)) { el.hidden = true; el.innerHTML = ''; return; }
    el.hidden = false;
    el.innerHTML = '<div class="wrap banner-in"><p><strong>Modo teste</strong> — o que o score recomendaria em ' +
      dateBR(snap.date) + ' e o que aconteceu até ' + dateBR(D.meta.reference_date) +
      '. Só entra o que se sabia naquela data.</p>' +
      '<p class="banner-note" data-testid="test-banner-note">Os números de resultado são do time inteiro de propósito: ' +
      'não mostramos taxa de vitória por vendedor, porque a diferença entre vendedores é compatível com ruído.</p>' +
      '<button type="button" class="btn" id="back-today" data-testid="back-to-today">Voltar para hoje</button></div>';
  }

  /* ------------------------------------------------------------------ frase de ação */
  function scopeText() {
    var a = state.vendedor ? agentsByName[state.vendedor] : null;
    if (a) { return a.name + ' · time de ' + a.manager + ' · ' + a.region; }
    if (state.manager) { return 'Time de ' + state.manager + ' · ' + managersByName[state.manager].region; }
    if (state.regiao) { return 'Região ' + state.regiao + ' · todos os managers'; }
    return 'Todos os vendedores · todos os managers e regiões';
  }
  function nHtml(c, text) { return '<span class="n cat-' + c + '">' + text + '</span>'; }

  // Sem Foque nem Reative e com Prospecting: a receita nova está no Qualifique (não existe no modo teste).
  function noLiveDeals(snap, st) {
    return !isTest(snap) && !st.Foque.n && !st.Reative.n && st.Qualifique.n > 0;
  }
  // Primeira tela: sem vendedor escolhido, pede o nome (a visão do manager continua igual).
  function renderHint() {
    var el = $('pick-hint');
    el.hidden = !!state.vendedor;
    el.textContent = state.vendedor ? '' : 'Escolha seu nome em “Quem é você?” para ver só os seus deals.';
  }

  function renderAction(snap, st, total) {
    $('scope-label').textContent = scopeText();
    var el = $('action-summary');
    if (!total) {
      var ag = state.vendedor ? agentsByName[state.vendedor] : null;
      if (ag && !ag.has_deals) { el.innerHTML = '<strong>' + esc(ag.name) + '</strong> não tem deals no CRM (cadastro sem pipeline).'; }
      else { el.textContent = 'Nenhum deal para priorizar nesta seleção.'; }
      return;
    }
    var parts = [];
    var newRevenue = noLiveDeals(snap, st);
    if (newRevenue) {
      parts.push('qualifique ' + nHtml('Qualifique', num(st.Qualifique.n)) + ' em Prospecting (a receita nova está no Qualifique)');
    }
    if (st.Foque.n) { parts.push('foque em ' + nHtml('Foque', num(st.Foque.n)) + ' ' + plural(st.Foque.n, 'deal', 'deals')); }
    if (st.Reative.n) { parts.push('reative ' + nHtml('Reative', num(st.Reative.n)) + ' antes que ' + plural(st.Reative.n, 'esfrie', 'esfriem')); }
    if (st.Limpe.n) {
      parts.push('limpe ' + nHtml('Limpe', num(st.Limpe.n)) + ' do CRM (' + nHtml('Limpe', usd(st.Limpe.valor)) + ' parados)');
    }
    if (!newRevenue && !isTest(snap) && st.Qualifique.n) { parts.push('qualifique ' + nHtml('Qualifique', num(st.Qualifique.n)) + ' em Prospecting'); }
    var lead = isTest(snap) ? 'Em ' + dateBR(snap.date) + ' o score teria dito: ' : 'Esta semana: ';
    el.innerHTML = lead + joinPt(parts) + '.';
  }

  /* ------------------------------------------------------------------ abas = KPIs */
  var tabsEl = $('tabs');
  var tabRefs = {};
  CATS.forEach(function (c) {
    var b = document.createElement('button');
    b.type = 'button';
    b.id = 'tab-' + c;
    b.className = 'tab cat-' + c;
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-controls', 'panel');
    b.setAttribute('data-testid', 'tab-' + c);
    b.innerHTML = '<span class="tab-name">' + c + '</span>' +
      '<span class="tab-count" data-testid="count-' + c + '"></span>' +
      '<span class="tab-value"></span>';
    tabsEl.appendChild(b);
    tabRefs[c] = { btn: b, count: b.querySelector('.tab-count'), value: b.querySelector('.tab-value') };
  });

  function renderTabs(snap, st) {
    CATS.forEach(function (c) {
      var r = tabRefs[c];
      var off = isTest(snap) && c === 'Qualifique';
      r.count.setAttribute('data-count', off ? '0' : String(st[c].n));
      r.count.textContent = off ? '—' : num(st[c].n);
      r.value.textContent = off ? 'indisponível no teste' : usd(st[c].valor) + ' de tabela';
      var sel = activeCat === c;
      r.btn.setAttribute('aria-selected', sel ? 'true' : 'false');
      r.btn.tabIndex = sel ? 0 : -1;
    });
  }

  tabsEl.addEventListener('click', function (e) {
    var b = e.target.closest('.tab');
    if (!b) { return; }
    state.aba = b.id.replace('tab-', '');
    commit();
  });
  tabsEl.addEventListener('keydown', function (e) {
    var i = CATS.indexOf(activeCat), k = e.key;
    if (k === 'ArrowRight' || k === 'ArrowDown') { i = (i + 1) % CATS.length; }
    else if (k === 'ArrowLeft' || k === 'ArrowUp') { i = (i + CATS.length - 1) % CATS.length; }
    else if (k === 'Home') { i = 0; }
    else if (k === 'End') { i = CATS.length - 1; }
    else { return; }
    e.preventDefault();
    state.aba = CATS[i];
    commit();
    tabRefs[activeCat].btn.focus();
  });

  /* ------------------------------------------------------------------ resultado do modo teste */
  function renderResults(snap) {
    var el = $('results');
    if (!isTest(snap) || !snap.outcome_summary) { el.hidden = true; el.innerHTML = ''; return; }
    var html = '<h2>O que aconteceu até ' + dateBR(D.meta.reference_date) +
      ' <span class="muted">(todos os vendedores; os filtros não mudam estes números)</span></h2><div class="results-grid">';
    CATS.forEach(function (c) {
      var o = snap.outcome_summary[c];
      if (!o) { return; }
      html += '<div class="res cat-' + c + '" data-testid="backtest-summary-' + c + '" data-n="' + o.n +
        '" data-pct="' + (o.pct_ganhos * 100).toFixed(1) + '">' +
        '<span class="res-name">' + c + '</span>' +
        '<span class="res-pct">' + pct1(o.pct_ganhos) + '</span>' +
        '<span class="res-sub">foram ganhos, de ' + num(o.n) + ' ' + plural(o.n, 'deal', 'deals') +
        ' · ' + usd(o.receita_ganha) + ' de receita</span></div>';
    });
    el.innerHTML = html + '</div>';
    el.hidden = false;
  }

  /* ------------------------------------------------------------------ carteira do time */
  var teamEl = $('team');
  var lastTeamKey = null;

  function renderTeam(snap, list) {
    if (state.vendedor) { teamEl.innerHTML = ''; lastTeamKey = null; return; }
    var key = [snap.date, state.manager, state.regiao].join('|');
    if (key === lastTeamKey) { return; }
    var existing = teamEl.querySelector('details');
    var wasOpen = existing && lastTeamKey !== null && lastTeamKey.split('|').slice(1).join('|') === key.split('|').slice(1).join('|')
      ? existing.open : null;
    lastTeamKey = key;

    var ags = D.people.agents.filter(function (a) {
      return (!state.manager || a.manager === state.manager) && (!state.regiao || a.region === state.regiao);
    }).sort(function (a, b) { return byName(a.name, b.name); });
    var counts = {};
    list.forEach(function (d) {
      var c = counts[d.agent] || (counts[d.agent] = { Foque: 0, Reative: 0, Limpe: 0, Qualifique: 0 });
      c[d.cat] += 1;
    });
    var test = isTest(snap);
    var open = wasOpen !== null ? wasOpen : !!(state.manager || state.regiao);

    var rows = ags.map(function (a) {
      var c = counts[a.name] || { Foque: 0, Reative: 0, Limpe: 0, Qualifique: 0 };
      var total = c.Foque + c.Reative + c.Limpe + c.Qualifique;
      var alert = !a.has_deals ? 'Sem deals no CRM (cadastro sem pipeline)' : (!total ? 'Sem deals abertos' : '');
      var tds = CATS.map(function (cat) {
        if (test && cat === 'Qualifique') { return '<td class="zero">—</td>'; }
        return '<td' + (c[cat] ? '' : ' class="zero"') + '>' + num(c[cat]) + '</td>';
      }).join('');
      return '<tr data-agent="' + esc(a.name) + '"><th scope="row"><button type="button" class="link-btn" data-pick="' +
        esc(a.name) + '">' + esc(a.name) + '</button>' +
        (alert ? '<span class="row-alert">' + esc(alert) + '</span>' : '') + '</th>' + tds + '</tr>';
    }).join('');

    teamEl.innerHTML = '<details class="team"' + (open ? ' open' : '') + ' data-testid="team-details">' +
      '<summary>Carteira do time <span class="muted">· ' + num(ags.length) + ' ' + plural(ags.length, 'vendedor', 'vendedores') + '</span></summary>' +
      '<p class="team-note">Só contagens de deals por lista, em ordem alfabética. Sem taxa de vitória por vendedor: a diferença entre vendedores é compatível com ruído.</p>' +
      '<div class="table-wrap"><table data-testid="team-table"><thead><tr><th>Vendedor</th>' +
      CATS.map(function (c) { return '<th class="th-' + c + '">' + c + '</th>'; }).join('') +
      '</tr></thead><tbody>' + rows + '</tbody></table></div></details>';
  }

  teamEl.addEventListener('click', function (e) {
    var b = e.target.closest('[data-pick]');
    if (!b) { return; }
    state.vendedor = b.getAttribute('data-pick');
    normalize(state);
    commit();
    window.scrollTo(0, 0);
  });

  /* ------------------------------------------------------------------ painel da lista e cards */
  var panelEl = $('panel');
  var cardsEl = $('cards');
  var emptyEl = $('empty');
  var moreWrap = $('more');
  var moreBtn = $('more-btn');
  var shownEl = $('shown-count');
  var items = [];
  var shown = 0;

  /* Aviso do Foque com idade alta: vem de backtest.notes (calculada do JSON de métricas pelo build). */
  function foqueWarning() {
    var notes = (D.backtest && D.backtest.notes) || [];
    for (var i = 0; i < notes.length; i++) {
      if (notes[i].indexOf('No Foque, ') === 0) {
        return ' <span class="foque-warning" data-testid="foque-warning"><strong>Atenção:</strong> ' + esc(notes[i]) + '</span>';
      }
    }
    return '';
  }

  function instruction(cat, m) {
    switch (cat) {
      case 'Foque':
        return '<strong>Avance</strong> estes deals primeiro: a chance de ganho só começa a cair depois de ' + days(m.knot_days) +
          ' abertos. Ordem: maior valor esperado (chance × preço de tabela).' + foqueWarning();
      case 'Reative':
        return '<strong>Fale com o cliente esta semana:</strong> a chance já está caindo, e nenhum deal foi ganho depois de ' +
          days(m.limpe_after_days) + ' abertos. Ordem: maior valor esperado.';
      case 'Limpe':
        return '<strong>Pergunte ao cliente se ainda quer comprar:</strong> se não, marque Lost no CRM; se sim, atualize o deal. Estes deals estão abertos há mais tempo do que qualquer deal já ganho (' +
          days(m.limpe_after_days) + '). Ordem: maior valor de tabela.';
      default:
        return '<strong>Marque a primeira conversa ou descarte:</strong> estes deals ainda estão em Prospecting, sem data de engajamento, então não há score. Ordem: maior valor de tabela.';
    }
  }

  function emptyInfo(snap, cat, list) {
    var a = state.vendedor ? agentsByName[state.vendedor] : null;
    if (cat === 'Qualifique' && isTest(snap)) {
      return { kind: 'qualifique-indisponivel',
        html: '<p><strong>Indisponível no modo teste:</strong> o CRM não registra quando o deal entrou em Prospecting.</p>' };
    }
    if (a && !a.has_deals) {
      return { kind: 'sem-deals',
        html: '<p><strong>' + esc(a.name) + ' não tem deals no CRM.</strong></p>' +
          '<p>É um cadastro sem pipeline: não há nada para priorizar. Se isso estiver errado, confira com ' + esc(a.manager) + '.</p>' };
    }
    if (!list.length) {
      return { kind: 'sem-deals-nesta-data',
        html: '<p><strong>' + (a ? esc(a.name) + ' não tem' : 'Não há') + ' deals abertos ' +
          (isTest(snap) ? 'em ' + dateBR(snap.date) : 'agora') + ' nesta seleção.</strong></p>' +
          '<p>' + (a ? (isTest(snap) ? 'Nesta data o vendedor ainda não tinha deals abertos, ou todos já estavam fechados.'
                                     : 'Os deals deste vendedor já estão fechados.')
                     : 'Mude os filtros ou clique em Limpar.') + '</p>' };
    }
    return { kind: 'lista-vazia',
      html: '<p><strong>Nenhum deal em ' + cat + ' nesta seleção.</strong></p><p>Veja as outras abas.</p>' };
  }

  function dueText(d) {
    if (d.cat === 'Foque' && d.days_to_knot != null) {
      return d.days_to_knot === 0 ? 'a chance começa a cair hoje' : 'a chance começa a cair em ' + days(d.days_to_knot);
    }
    if (d.cat === 'Reative' && d.days_to_limpe != null) {
      return d.days_to_limpe === 0 ? 'último dia antes de virar Limpe' : 'vira Limpe em ' + days(d.days_to_limpe);
    }
    return '';
  }

  function outcomeHtml(o) {
    var t;
    if (o.status === 'Ganho') {
      t = '<strong>Ganho</strong> em ' + dateBR(o.close_date) + (o.close_value != null ? ' · ' + usd(o.close_value) : '');
    } else if (o.status === 'Perdido') {
      t = '<strong>Perdido</strong>' + (o.close_date ? ' em ' + dateBR(o.close_date) : '');
    } else {
      t = '<strong>Ainda aberto</strong> em ' + dateBR(D.meta.reference_date);
    }
    return '<p class="outcome" data-testid="outcome-badge" data-status="' + esc(o.status) + '">' + t + '</p>';
  }

  function cardHtml(d) {
    var id = esc(d.id);
    var acct = d.account ? '<span class="acct">' + esc(d.account) + '</span>'
                         : '<span class="acct no-acct">Conta não informada</span>';
    var score = d.score == null ? '<span class="score none">Sem score</span>'
                                : '<span class="score">Score ' + d.score + '</span>';
    var l2 = score + '<span class="price">' + usd(d.price) + '</span>';
    if (d.p != null) {
      l2 += '<span class="chance" title="Chance de ganho nos próximos ' + days(HORIZON) + '">chance ' +
        (d.p > 0 && d.p < 0.005 ? '&lt;' + pct0(0.01) : pct0(d.p)) + '</span>';
    }
    var meta = [];                                   // 3ª linha: idade e prazo (quebra como texto corrido)
    if (d.age != null) { meta.push('há ' + days(d.age)); }
    var due = dueText(d);
    if (due) { meta.push('<span class="due">' + due + '</span>'); }
    var why = (d.why && d.why.length) ? d.why : [''];
    var whyHtml = why.map(function (s, i) {
      return '<p' + (i ? ' class="why-more" hidden' : '') + '>' + esc(s) + '</p>';
    }).join('');
    var rows = [
      ['Vendedor', d.agent], ['Manager', d.manager], ['Região', d.region],
      ['Engajado em', d.engage_date ? dateBR(d.engage_date) : 'sem data de engajamento'],
      ['Valor esperado', d.ev != null ? usd(d.ev) : 'sem estimativa (Prospecting)'],
      ['ID', d.id]
    ].map(function (r) { return '<dt>' + r[0] + '</dt><dd>' + esc(r[1]) + '</dd>'; }).join('');

    return '<article class="card cat-' + esc(d.cat) + '" data-testid="deal-card" data-id="' + id + '">' +
      '<button type="button" class="card-toggle" aria-expanded="false" aria-controls="det-' + id + '">' +
        '<span class="l1">' + acct + '<span class="prod">' + esc(d.product) + '</span></span>' +
        '<span class="l2">' + l2 + '</span>' +
        (meta.length ? '<span class="meta">' + meta.join(' · ') + '</span>' : '') +
      '</button>' +
      '<div class="card-why" data-testid="card-why" data-n="' + why.length + '">' + whyHtml + '</div>' +
      (d.outcome ? outcomeHtml(d.outcome) : '') +
      '<div class="card-detail" id="det-' + id + '" hidden><dl>' + rows + '</dl></div>' +
      '</article>';
  }

  function updateMore() {
    var all = shown >= items.length;
    moreWrap.hidden = items.length <= PAGE_SIZE;
    shownEl.textContent = 'Mostrando ' + num(shown) + ' de ' + num(items.length);
    moreBtn.hidden = all;
    moreBtn.textContent = 'Mostrar mais ' + num(Math.min(PAGE_SIZE, items.length - shown));
  }
  function appendCards() {
    var end = Math.min(items.length, shown + PAGE_SIZE), html = '', i;
    for (i = shown; i < end; i += 1) { html += cardHtml(items[i]); }
    var first = shown;
    cardsEl.insertAdjacentHTML('beforeend', html);
    shown = end;
    updateMore();
    return cardsEl.children[first];
  }
  moreBtn.addEventListener('click', function () {
    var firstNew = appendCards();
    var b = firstNew && firstNew.querySelector('.card-toggle');
    if (b) { b.focus({ preventScroll: true }); }
  });

  function toggleCard(card) {
    var btn = card.querySelector('.card-toggle');
    var open = btn.getAttribute('aria-expanded') !== 'true';
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    card.querySelector('.card-detail').hidden = !open;
    var extra = card.querySelectorAll('.why-more');
    for (var i = 0; i < extra.length; i += 1) { extra[i].hidden = !open; }
  }
  cardsEl.addEventListener('click', function (e) {
    var card = e.target.closest('.card');
    if (!card || e.target.closest('.card-detail')) { return; }
    var sel = window.getSelection && String(window.getSelection());
    if (sel && !e.target.closest('.card-toggle')) { return; }   // selecionando texto das frases: não recolhe
    toggleCard(card);
  });

  function renderPanel(snap, groups, list) {
    var cat = activeCat;
    panelEl.className = 'panel cat-' + cat;
    panelEl.setAttribute('aria-labelledby', 'tab-' + cat);
    $('instruction').innerHTML = instruction(cat, snap.model);
    // sem nenhum deal na seleção (ou lista indisponível), só o aviso explicativo: a instrução e as abas seriam ruído
    $('instruction').hidden = !list.length || (isTest(snap) && cat === 'Qualifique');
    tabsEl.hidden = !list.length;
    items = groups[cat] || [];
    shown = 0;
    cardsEl.innerHTML = '';
    var unavailable = isTest(snap) && cat === 'Qualifique';
    var agent = state.vendedor ? agentsByName[state.vendedor] : null;
    var showEmpty = unavailable || !items.length || (agent && !agent.has_deals);
    if (showEmpty) {
      var info = emptyInfo(snap, cat, list);
      emptyEl.innerHTML = info.html;
      emptyEl.setAttribute('data-kind', info.kind);
      emptyEl.hidden = false;
      moreWrap.hidden = true;
      if (unavailable) { items = []; }
      return;
    }
    emptyEl.hidden = true;
    emptyEl.innerHTML = '';
    emptyEl.removeAttribute('data-kind');
    appendCards();
  }

  /* ------------------------------------------------------------------ como funciona / teste no passado */
  function renderHow(snap) {
    $('how-list').innerHTML = (snap.how_it_works || []).map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('');
  }

  function fmtMetric(kind, v) {
    if (v == null) { return '—'; }
    return kind === 'dec' ? dec2(v) : pct1(v);
  }
  function renderBacktest(snap) {
    var b = D.backtest, box = $('backtest');
    if (!b || !b.rows || !b.rows.length || !b.metrics || !b.metrics.length) { box.hidden = true; return; }
    box.hidden = false;
    var cuts = [], byCut = {}, methods = [], mlabel = {};
    b.rows.forEach(function (r) {
      if (!byCut[r.cut]) { byCut[r.cut] = { label: r.cut_label, vals: {} }; cuts.push(r.cut); }
      byCut[r.cut].vals[r.method] = r;
      if (methods.indexOf(r.method) < 0) { methods.push(r.method); mlabel[r.method] = r.method_label; }
    });
    var hasActive = cuts.indexOf(snap.date) >= 0;
    var html = '<div class="box-body">';
    if (b.headline) { html += '<p class="bt-line head" data-testid="backtest-headline">' + esc(b.headline) + '</p>'; }
    if (b.criterion_text) { html += '<p class="bt-line">' + esc(b.criterion_text) + '</p>'; }
    html += '<p class="bt-line muted">Como ler: em cada data de corte, ordenamos os deals que estavam abertos por cada método e vemos quanto do que foi ganho depois caiu no topo da lista. Maior é melhor; o número em negrito é o melhor de cada linha.' +
      (hasActive ? ' A linha destacada é a data da foto que você está vendo.' : '') + '</p>';
    b.metrics.forEach(function (mt) {
      html += '<div class="table-wrap"><table class="bt-table" data-metric="' + esc(mt.key) + '"><caption>' + esc(mt.label) +
        '</caption><thead><tr><th>Corte</th>' + methods.map(function (m) { return '<th>' + esc(mlabel[m]) + '</th>'; }).join('') +
        '</tr></thead><tbody>';
      cuts.forEach(function (c) {
        var vals = methods.map(function (m) { var r = byCut[c].vals[m]; return r ? r[mt.key] : null; });
        var best = Math.max.apply(null, vals.filter(function (v) { return v != null; }));
        html += '<tr' + (c === snap.date ? ' class="is-active"' : '') + ' data-cut="' + esc(c) + '"><th scope="row">' + esc(byCut[c].label) + '</th>' +
          vals.map(function (v) {
            return '<td' + (v != null && v === best ? ' class="best"' : '') + '>' + fmtMetric(mt.kind, v) + '</td>';
          }).join('') + '</tr>';
      });
      html += '</tbody></table></div>';
    });
    if (b.notes && b.notes.length) {
      html += '<ul class="bt-notes">' + b.notes.map(function (n) { return '<li>' + esc(n) + '</li>'; }).join('') + '</ul>';
    }
    $('backtest-body').innerHTML = html + '</div>';
  }

  /* ------------------------------------------------------------------ rodapé */
  $('foot').innerHTML = 'Dados de ' + dateBR(D.meta.reference_date) + ' · gerado por <code>' + esc(D.meta.generated_by) + '</code>';

  /* ------------------------------------------------------------------ orquestração */
  var lastHowKey = null;
  // Aba escolhida pela pessoa; se ela ainda não escolheu, abre a 1ª lista que tem deals
  // (um vendedor sem nada em Foque não deve cair numa tela vazia).
  function pickCat(snap, st) {
    if (state.aba) { return state.aba; }
    if (noLiveDeals(snap, st)) { return 'Qualifique'; }
    for (var i = 0; i < CATS.length; i += 1) {
      if (isTest(snap) && CATS[i] === 'Qualifique') { continue; }
      if (st[CATS[i]].n) { return CATS[i]; }
    }
    return CATS[0];
  }
  function render() {
    var snap = currentSnap();
    var list = filterDeals(snap);
    var groups = groupByCat(list);
    var st = statsOf(groups);
    activeCat = pickCat(snap, st);
    renderControls(snap);
    renderBanner(snap);
    renderAction(snap, st, list.length);
    renderHint();
    renderTabs(snap, st);
    renderResults(snap);
    renderTeam(snap, list);
    renderPanel(snap, groups, list);
    if (lastHowKey !== snap.date) { renderHow(snap); renderBacktest(snap); lastHowKey = snap.date; }
  }
  function commit() { normalize(state); writeHash(); render(); }

  /* ------------------------------------------------------------------ eventos */
  modeSel.addEventListener('change', function () {
    state.modo = modeSel.value === todaySnap.date ? '' : modeSel.value;
    commit();
  });
  agentSel.addEventListener('change', function () { state.vendedor = agentSel.value; commit(); });
  managerSel.addEventListener('change', function () { state.manager = managerSel.value; commit(); });
  regionSel.addEventListener('change', function () { state.regiao = regionSel.value; commit(); });
  $('filter-clear').addEventListener('click', function () {
    state.vendedor = ''; state.manager = ''; state.regiao = '';
    commit();
  });
  $('test-banner').addEventListener('click', function (e) {
    if (e.target.closest('#back-today')) { state.modo = ''; commit(); modeSel.focus(); }
  });
  $('how-btn').addEventListener('click', function () {
    var d = $('how');
    d.open = true;
    d.scrollIntoView();
    d.querySelector('summary').focus({ preventScroll: true });
  });
  window.addEventListener('hashchange', function () {
    var s = parseHash();
    if (serialize(s) === lastHash) { return; }
    state = s;
    lastHash = serialize(state);
    render();
  });

  state = parseHash();
  lastHash = serialize(state);
  try {
    render();
  } catch (err) {
    console.error(err);
    $('action-summary').textContent = 'Não foi possível montar a página. Rode python -m scorer.build de novo.';
    throw err;
  }
})();
