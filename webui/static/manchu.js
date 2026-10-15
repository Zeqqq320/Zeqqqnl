/* 满族音乐 · 交互逻辑
   数据契约：
     POST /api/playlist {platform:'ethnos', id:'t03'} -> {sid, tracks[], name, cover, count}
     GET  /api/preview?sid&id&n&s&src          音频流
     GET  /api/cover?url=                       封面代理
     POST /api/lyric {sid, id, name, artist}    歌词
     POST /api/ui/state {d:{cm_my_playlists}}   收藏持久化
     POST /api/resolve {name, singer, src, dur} 直链过期后换新源
*/

(function () {
  'use strict';

  var GROUP = 't03';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* 八旗 —— 音源映射。八旗色制正好对应八个音源, 曲目左侧色点即"旗属" */
  var BANNERS = [
    { name: '正黄', color: '#E9C46A', src: '网易云' },
    { name: '镶黄', color: '#D4A845', src: '酷狗' },
    { name: '正白', color: '#F1EDE3', src: '酷我' },
    { name: '镶白', color: '#DCD6C6', src: '咪咕' },
    { name: '正红', color: '#C0392B', src: 'B站' },
    { name: '镶红', color: '#9E2B25', src: 'MyFreeMP3' },
    { name: '正蓝', color: '#3A6EA5', src: '音乐库' },
    { name: '镶蓝', color: '#24405F', src: '光音·微信' },
  ];
  var DEFAULT_BANNER = { name: '其它', color: '#B4B2A9', src: '' };

  function bannerOf(src) {
    for (var i = 0; i < BANNERS.length; i++) {
      if (BANNERS[i].src === src) return BANNERS[i];
    }
    return DEFAULT_BANNER;
  }

  var state = {
    sid: '', title: '', cover: '',
    all: [], view: [], fav: [],
    idx: -1, mode: 'order', sort: 'default', tab: 'all', q: '',
    lyric: [], lyricIdx: -1
  };

  var audio = new Audio();
  audio.preload = 'none';
  audio.volume = 0.85;

  /* ---------------- 工具 ---------------- */
  function fmt(s) {
    s = Math.max(0, Math.round(Number(s) || 0));
    var m = Math.floor(s / 60), ss = s % 60;
    return m + ':' + (ss < 10 ? '0' : '') + ss;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('show'); }, 2200);
  }

  /* ---------------- 八旗图例 ---------------- */
  function renderLegend() {
    var counts = {};
    state.all.forEach(function (t) { counts[t.src] = (counts[t.src] || 0) + 1; });
    var used = BANNERS.filter(function (b) { return counts[b.src]; });
    var html = used.map(function (b) {
      return '<div class="legend-row" title="' + esc(b.name + '旗 · ' + b.src) + '">' +
        '<i class="legend-dot" style="background:' + b.color + '"></i>' +
        '<span>' + esc(b.src) + '</span>' +
        '<span class="c">' + (counts[b.src] || 0) + '</span></div>';
    }).join('');
    $('#legend').innerHTML = html || '<div class="legend-row"><span>暂无</span></div>';
  }

  /* ---------------- 加载曲库 ---------------- */
  function load() {
    $('#list').innerHTML = '<div class="loading">正在打开满族曲库…</div>';
    fetch('/api/playlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'ethnos', id: GROUP })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.building) { setTimeout(load, 1500); return; }
        if (!d || !d.tracks) throw new Error('曲库为空');
        state.sid = d.sid || '';
        state.title = d.name || '满族音乐';
        state.cover = d.cover || '';
        state.all = d.tracks.map(function (t, i) {
          return {
            i: i,
            id: t.id,
            name: t.song_name || '未知曲目',
            singer: t.singers || '未知歌手',
            album: t.album || '',
            dur: Number(t.duration_s) || 0,
            src: t.source_cn || t.source || '',
            cover: t.cover_url || '',
            ok: t.previewable !== false
          };
        });
        loadFav();
        apply();
        renderLegend();
        $('#count').innerHTML = '共 <b>' + state.all.length + '</b> 首';
        var head = $('.content-head h2');
        if (head) head.textContent = state.title;
      })
      .catch(function (e) {
        $('#list').innerHTML = '<div class="empty">曲库加载失败：' + esc(e.message) + '</div>';
      });
  }

  /* ---------------- 收藏 ---------------- */
  function loadFav() {
    try {
      var v = JSON.parse(localStorage.getItem('manchu_fav') || '[]');
      if (Array.isArray(v)) state.fav = v;
    } catch (e) { state.fav = []; }
    fetch('/api/ui/state').then(function (r) { return r.json(); }).then(function (d) {
      var remote = (d && d.v && d.v.cm_my_playlists);
      if (Array.isArray(remote) && remote.length) {
        state.fav = remote;
        localStorage.setItem('manchu_fav', JSON.stringify(state.fav));
        apply();
      }
    }).catch(function () {});
  }
  function saveFav() {
    localStorage.setItem('manchu_fav', JSON.stringify(state.fav));
    fetch('/api/ui/state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ d: { cm_my_playlists: state.fav } })
    }).catch(function () {});
  }
  function isFav(id) { return state.fav.indexOf(id) >= 0; }
  function toggleFav(id) {
    var p = state.fav.indexOf(id);
    if (p >= 0) { state.fav.splice(p, 1); toast('已取消收藏'); }
    else { state.fav.push(id); toast('已加入收藏'); }
    saveFav(); apply();
  }

  /* ---------------- 过滤与排序 ---------------- */
  function apply() {
    var q = state.q.trim().toLowerCase();
    var arr = state.all.filter(function (t) {
      if (state.tab === 'fav' && !isFav(t.id)) return false;
      if (state.tab === 'queue' && t.i !== curAllIdx()) return false;
      if (!q) return true;
      return (t.name + ' ' + t.singer + ' ' + t.album).toLowerCase().indexOf(q) >= 0;
    });
    if (state.sort === 'name') arr.sort(function (a, b) { return a.name.localeCompare(b.name, 'zh'); });
    else if (state.sort === 'dur') arr.sort(function (a, b) { return b.dur - a.dur; });
    else arr.sort(function (a, b) { return a.i - b.i; });
    state.view = arr;
    render();
    syncCounts();
  }
  function curAllIdx() {
    var cur = state.view[state.idx];
    return cur ? cur.i : -1;
  }
  function syncCounts() {
    $('#n-all').textContent = state.all.length;
    $('#n-fav').textContent = state.fav.length;
    $('#n-queue').textContent = state.idx >= 0 ? 1 : 0;
  }

  /* ---------------- 渲染列表 ---------------- */
  function render() {
    var el = $('#list');
    if (!state.view.length) {
      el.innerHTML = '<div class="empty">' +
        (state.tab === 'fav' ? '还没有收藏，点右侧星标添加' : '没有匹配的曲目') + '</div>';
      return;
    }
    var html = '';
    state.view.forEach(function (t, k) {
      var playing = (k === state.idx);
      var b = bannerOf(t.src);
      html += '<div class="row' + (playing ? ' playing' : '') + (t.ok ? '' : ' dim') + '" data-k="' + k + '">' +
        '<div class="flag"><i style="background:' + b.color + '" title="' + esc(b.name + '旗 · ' + t.src) + '"></i>' +
          '<span class="idx">' + (k + 1) + '</span></div>' +
        '<div class="t-name" title="' + esc(t.name) + '">' + esc(t.name) + '</div>' +
        '<div class="t-sub" title="' + esc(t.singer) + '">' + esc(t.singer) + '</div>' +
        '<div class="t-sub c-album" title="' + esc(t.album) + '">' + esc(t.album || '—') + '</div>' +
        '<div class="t-dur">' + (t.dur ? fmt(t.dur) : '--:--') + '</div>' +
        '<div class="fav' + (isFav(t.id) ? ' on' : '') + '" data-fav="' + esc(t.id) + '">' +
          (isFav(t.id) ? '★' : '☆') + '</div>' +
        '</div>';
    });
    el.innerHTML = html;
  }

  /* ---------------- 播放 ---------------- */
  function play(k, autoplay) {
    var t = state.view[k];
    if (!t) return;
    if (!t.ok) { toast('该曲目暂无可播放音源'); return; }
    state.idx = k;
    var url = '/api/preview?sid=' + encodeURIComponent(t.sid || state.sid) +
      '&id=' + encodeURIComponent(t.id) +
      '&n=' + encodeURIComponent(t.name) +
      '&s=' + encodeURIComponent(t.singer) +
      '&src=' + encodeURIComponent(t.src);
    audio.src = url;
    audio.load();
    if (autoplay !== false) audio.play().catch(function () { toast('播放失败，可换一首试试'); });

    $('#now-name').textContent = t.name;
    $('#now-artist').textContent = t.singer + (t.src ? ' · ' + t.src : '');
    var cv = $('#cover');
    var img = t.cover ? ('/api/cover?url=' + encodeURIComponent(t.cover)) : '';
    cv.style.backgroundImage = img ? 'url("' + img + '")' : '';
    $('#lyric-now-n').textContent = t.name;
    $('#lyric-now-a').textContent = t.singer;
    fetchLyric(t);
    render();
    syncCounts();
  }

  function next(user) {
    if (!state.view.length) return;
    var k;
    if (state.mode === 'shuffle') {
      k = Math.floor(Math.random() * state.view.length);
    } else {
      k = state.idx + 1;
      if (k >= state.view.length) {
        if (state.mode === 'loop' && !user) { audio.currentTime = 0; audio.play(); return; }
        k = 0;
      }
    }
    play(k);
  }
  function prev() {
    if (!state.view.length) return;
    var k = state.idx - 1;
    if (k < 0) k = state.view.length - 1;
    play(k);
  }

  /* ---------------- 直链过期自愈 ---------------- */
  var healTimer = null;
  function heal() {
    var t = state.view[state.idx];
    if (!t || t._healing || t._healed) return;
    t._healing = 1;
    var idxAtStart = state.idx;   // 换源是异步的, 期间用户可能已切歌/改排序, 记下起点防止播错
    toast('链接已过期，正在重新获取音源…');
    fetch('/api/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: t.name, singer: t.singer, src: t.src, dur: t.dur })
    }).then(function (r) { return r.json(); }).then(function (d) {
      t._healing = 0; t._healed = 1;
      if (!d || !d.sid) throw new Error((d && d.error) || '没有可用的替代音源');
      t.sid = d.sid;
      t.id = d.id;
      if (d.source) { t.src = d.source; if (d.source_cn) t.source_cn = d.source_cn; }
      if (state.view[state.idx] !== t) { render(); renderLegend(); return; }  // 期间已切歌, 只更新数据不抢播
      toast('已换到' + (d.source || '新') + '音源');
      play(idxAtStart);
    }).catch(function (e) {
      t._healing = 0; t._healed = 1;
      toast(e.message || '无法获取音源，试试下一首');
    });
  }

  /* ---------------- 歌词 ---------------- */
  function fetchLyric(t) {
    state.lyric = []; state.lyricIdx = -1;
    $('#lyric-body').innerHTML = '<p>歌词加载中…</p>';
    fetch('/api/lyric', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sid: t.sid || state.sid, id: t.id, name: t.name, artist: t.singer })
    }).then(function (r) { return r.json(); }).then(parseLyric).catch(function () {
      $('#lyric-body').innerHTML = '<p>暂无歌词</p>';
    });
  }
  function parseLyric(d) {
    var raw = (d && d.lyric) ? String(d.lyric) : '';
    if (!raw || /^(null|none)$/i.test(raw)) {
      $('#lyric-body').innerHTML = '<p>暂无歌词</p>';
      return;
    }
    var lines = [], re = /\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\](.*)/g, m;
    while ((m = re.exec(raw))) {
      var txt = m[4].trim();
      if (!txt) continue;
      // 小数位可能是 2 位([00:12.34])或 3 位([00:12.345]), 按实际位数归一, 否则整段歌词会偏移
      lines.push({ t: (+m[1]) * 60 + (+m[2]) + (m[3] ? +m[3] / Math.pow(10, m[3].length) : 0), text: txt });
    }
    if (!lines.length) {
      $('#lyric-body').innerHTML = raw.split(/\n+/).map(function (s) {
        return '<p>' + esc(s.trim()) + '</p>';
      }).join('');
      state.lyric = [];
      return;
    }
    lines.sort(function (a, b) { return a.t - b.t; });
    state.lyric = lines; state.lyricIdx = -1;
    $('#lyric-body').innerHTML = lines.map(function (l, i) {
      return '<p data-i="' + i + '">' + esc(l.text) + '</p>';
    }).join('');
  }
  function syncLyric(time) {
    if (!state.lyric.length) return;
    var k = -1;
    for (var i = 0; i < state.lyric.length; i++) {
      if (state.lyric[i].t <= time + 0.35) k = i; else break;
    }
    if (k === state.lyricIdx) return;
    state.lyricIdx = k;
    $$('#lyric-body p').forEach(function (p, i) { p.classList.toggle('on', i === k); });
    var cur = $$('#lyric-body p')[k];
    var box = $('#lyric-body');
    if (cur && !box.classList.contains('vertical')) {
      box.scrollTop = cur.offsetTop - box.clientHeight / 2 + cur.clientHeight / 2;
    } else if (cur) {
      box.scrollLeft = cur.offsetLeft - box.clientWidth / 2 + cur.clientWidth / 2;
    }
  }

  /* ---------------- 主题与竖排 ---------------- */
  function initTheme() {
    var saved = localStorage.getItem('manchu_theme');
    if (saved === 'night') document.body.classList.add('night');
    else if (!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      document.body.classList.add('night');
    }
    $('#btn-theme').addEventListener('click', function () {
      var night = document.body.classList.toggle('night');
      localStorage.setItem('manchu_theme', night ? 'night' : 'day');
      toast(night ? '夜祭模式' : '日间模式');
    });
  }
  function initVertical() {
    var saved = localStorage.getItem('manchu_vertical') === '1';
    var box = $('#lyric-body'), btn = $('#btn-vertical');
    if (saved) { box.classList.add('vertical'); btn.classList.add('on'); }
    btn.addEventListener('click', function () {
      var on = box.classList.toggle('vertical');
      btn.classList.toggle('on', on);
      localStorage.setItem('manchu_vertical', on ? '1' : '0');
      toast(on ? '竖排（满文书写习惯）' : '横排');
    });
  }

  /* ---------------- 事件 ---------------- */
  function bind() {
    $('#list').addEventListener('click', function (e) {
      var f = e.target.closest('.fav');
      if (f) { toggleFav(f.getAttribute('data-fav')); e.stopPropagation(); return; }
      var row = e.target.closest('.row');
      if (row) play(+row.getAttribute('data-k'));
    });

    var si = $('#q');
    si.addEventListener('input', function () {
      state.q = si.value;
      $('.search').classList.toggle('has', !!si.value);
      apply();
    });
    $('.search .clear').addEventListener('click', function () {
      si.value = ''; state.q = ''; $('.search').classList.remove('has'); apply(); si.focus();
    });

    $$('.nav-item').forEach(function (b) {
      b.addEventListener('click', function () {
        state.tab = b.getAttribute('data-tab');
        $$('.nav-item').forEach(function (x) { x.classList.toggle('on', x === b); });
        apply();
      });
    });

    $$('.sorts button').forEach(function (b) {
      b.addEventListener('click', function () {
        state.sort = b.getAttribute('data-sort');
        $$('.sorts button').forEach(function (x) { x.classList.toggle('on', x === b); });
        apply();
      });
    });

    $('#btn-play').addEventListener('click', function () {
      if (audio.paused) {
        if (!audio.src) { if (state.view.length) play(0); return; }
        audio.play().catch(function () { toast('播放失败'); });
      } else audio.pause();
    });
    $('#btn-prev').addEventListener('click', function () { prev(); });
    $('#btn-next').addEventListener('click', function () { next(true); });
    $('#btn-mode').addEventListener('click', function () {
      state.mode = state.mode === 'order' ? 'loop' : (state.mode === 'loop' ? 'shuffle' : 'order');
      var txt = { order: '顺序播放', loop: '单曲循环', shuffle: '随机播放' }[state.mode];
      $('#btn-mode').classList.toggle('on', state.mode !== 'order');
      $('#btn-mode').title = txt;
      toast(txt);
    });

    $('#seek').addEventListener('click', function (e) {
      if (!audio.duration) return;
      var r = this.getBoundingClientRect();
      audio.currentTime = (e.clientX - r.left) / r.width * audio.duration;
    });
    $('#vol').addEventListener('click', function (e) {
      var r = this.getBoundingClientRect();
      audio.volume = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      paintVol();
    });

    audio.addEventListener('play', function () {
      $('#btn-play').innerHTML = icon('pause');
      document.body.classList.add('playing');
    });
    audio.addEventListener('pause', function () {
      $('#btn-play').innerHTML = icon('play');
      document.body.classList.remove('playing');
    });
    audio.addEventListener('timeupdate', function () {
      var d = audio.duration || 0;
      $('#t-cur').textContent = fmt(audio.currentTime);
      $('#t-all').textContent = fmt(d || (state.view[state.idx] ? state.view[state.idx].dur : 0));
      if (d) $('#seek .fill').style.width = (audio.currentTime / d * 100) + '%';
      syncLyric(audio.currentTime);
    });
    audio.addEventListener('ended', function () { next(false); });
    audio.addEventListener('error', function () { if (audio.src) heal(); });
    audio.addEventListener('loadstart', function () {
      clearTimeout(healTimer);
      healTimer = setTimeout(function () { if (audio.readyState < 3) heal(); }, 8000);
    });
    audio.addEventListener('canplay', function () { clearTimeout(healTimer); });

    document.addEventListener('keydown', function (e) {
      if (/input|textarea/i.test(e.target.tagName)) {
        if (e.key === 'Escape') e.target.blur();
        return;
      }
      if (e.code === 'Space') { e.preventDefault(); $('#btn-play').click(); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); next(true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
      else if (e.key === '/') { e.preventDefault(); $('#q').focus(); }
    });
  }

  function paintVol() { $('#vol .fill').style.width = (audio.volume * 100) + '%'; }

  function icon(k) {
    var s = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">';
    if (k === 'play') return s + '<path d="M4 2.5v11l9-5.5z"/></svg>';
    return s + '<path d="M4.5 2.5h2.2v11H4.5zM9.3 2.5h2.2v11H9.3z"/></svg>';
  }

  /* ---------------- 启动 ---------------- */
  document.addEventListener('DOMContentLoaded', function () {
    $('#btn-play').innerHTML = icon('play');
    paintVol();
    initTheme();
    initVertical();
    bind();
    load();
  });
})();
