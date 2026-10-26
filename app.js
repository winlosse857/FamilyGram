const API = (window.SERVER_URL || '').replace(/\/$/, '');
const $ = s => document.querySelector(s);
let token = localStorage.getItem('token'), me = localStorage.getItem('me');
let peer = null, sock = null, mode = 'login';
const show = id => document.querySelectorAll('.screen').forEach(e => e.classList.toggle('on', e.id === id));
const hhmm = ts => new Date(ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
async function api(path, opt = {}) {
  const r = await fetch(API + path, {...opt, headers: {'Content-Type': 'application/json', ...(token ? {Authorization: 'Bearer ' + token} : {})}});
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.error || 'Ошибка ' + r.status); e.status = r.status; throw e; }
  return d;
}
function logout() { localStorage.clear(); token = me = peer = null; if (sock) sock.disconnect(); show('welcome'); }
function renderList(items, empty) {
  const box = $('#list'); box.innerHTML = '';
  if (!items.length) { box.innerHTML = '<div class="empty"></div>'; box.firstChild.textContent = empty; return; }
  items.forEach(i => {
    const row = document.createElement('div'); row.className = 'row';
    const ava = document.createElement('div'); ava.className = 'ava'; ava.textContent = i.name[0];
    const t = document.createElement('div'); const b = document.createElement('b'); b.textContent = i.name;
    const s = document.createElement('small'); s.textContent = i.text || 'Написать сообщение';
    t.append(b, s); row.append(ava, t); row.onclick = () => openChat(i.name); box.append(row);
  });
}
async function loadChats() { renderList(await api('/api/chats'), 'Пока нет чатов. Найдите человека по имени выше.'); }
function connect() {
  if (sock) sock.disconnect(); sock = io(API || undefined, {auth: {token}});
  sock.on('message', m => { if (peer && (m.from === peer || m.to === peer)) addMsg(m); if (!peer) loadChats().catch(() => {}); });
}
async function start() { show('chats'); connect(); try { await loadChats(); } catch (e) { if (e.status === 401) logout(); } }
function addMsg(m) {
  const box = $('#msgs'), d = document.createElement('div'); d.className = 'm ' + (m.from === me ? 'me' : 'in');
  d.append(document.createTextNode(m.text)); const t = document.createElement('time'); t.textContent = hhmm(m.ts); d.append(t); box.append(d); box.scrollTop = box.scrollHeight;
}
async function openChat(name) { peer = name; $('#peerName').textContent = name; $('#msgs').innerHTML = ''; show('chat'); (await api('/api/messages/' + encodeURIComponent(name))).forEach(addMsg); }
$('#go').onclick = () => show('auth');
$('#swap').onclick = () => {
  mode = mode === 'login' ? 'register' : 'login'; const reg = mode === 'register';
  $('#authTitle').textContent = reg ? 'Регистрация' : 'Вход'; $('#authBtn').textContent = reg ? 'Создать аккаунт' : 'Войти';
  $('#swap').textContent = reg ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'; $('#p').autocomplete = reg ? 'new-password' : 'current-password';
};
$('#authForm').onsubmit = async e => {
  e.preventDefault(); $('#err').textContent = '';
  try {
    const d = await api('/api/' + mode, {method: 'POST', body: JSON.stringify({username: $('#u').value, password: $('#p').value})});
    token = d.token; me = d.username; localStorage.setItem('token', token); localStorage.setItem('me', me); $('#p').value = ''; start();
  } catch (x) { $('#err').textContent = x.message === 'Failed to fetch' ? 'Нет связи с сервером' : x.message; }
};
$('#out').onclick = logout;
$('#back').onclick = () => { peer = null; show('chats'); loadChats().catch(() => {}); };
$('#search').oninput = async e => {
  const v = e.target.value.trim(); if (v.length < 2) return loadChats().catch(() => {});
  const names = await api('/api/users?q=' + encodeURIComponent(v)).catch(() => []); renderList(names.map(name => ({name})), 'Никого не нашли');
};
$('#sendForm').onsubmit = e => { e.preventDefault(); const text = $('#text').value.trim(); if (text && peer) { sock.emit('send', {to: peer, text}); $('#text').value = ''; } };
if (token) start();
