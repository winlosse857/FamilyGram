"""Zvon — сервер: регистрация, вход, личные чаты 1 на 1 (Flask + Socket.IO + SQLite)."""
import os, re, secrets, sqlite3, time
from functools import wraps
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import check_password_hash, generate_password_hash

DB = os.environ.get("DB_PATH", "zvon.db")
app = Flask(__name__, static_folder="www", static_url_path="")
CORS(app)
sio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
sid_user = {}

def q(sql, args=(), one=False):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(sql, args).fetchall()
        con.commit()
        return (rows[0] if rows else None) if one else rows
    finally:
        con.close()

q("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pw TEXT, token TEXT)""")
q("""CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, sender TEXT, recipient TEXT, text TEXT, ts INTEGER)""")

def user_by_token(t):
    r = q("SELECT username FROM users WHERE token=?", (t,), one=True) if t else None
    return r["username"] if r else None

def auth(f):
    @wraps(f)
    def w(*a, **k):
        me = user_by_token(request.headers.get("Authorization", "")[7:])
        if not me: return jsonify(error="Нужно войти"), 401
        return f(me, *a, **k)
    return w

@app.get("/")
def index(): return app.send_static_file("index.html")

def creds():
    d = request.get_json(silent=True) or {}
    return str(d.get("username", "")).strip().lower(), str(d.get("password", ""))

@app.post("/api/register")
def register():
    u, p = creds()
    if not re.fullmatch(r"[a-z0-9_]{3,20}", u): return jsonify(error="Имя: 3–20 символов, латиница, цифры, _"), 400
    if len(p) < 6: return jsonify(error="Пароль: минимум 6 символов"), 400
    if q("SELECT 1 FROM users WHERE username=?", (u,), one=True): return jsonify(error="Это имя уже занято"), 409
    t = secrets.token_urlsafe(32)
    q("INSERT INTO users(username,pw,token) VALUES(?,?,?)", (u, generate_password_hash(p), t))
    return jsonify(token=t, username=u)

@app.post("/api/login")
def login():
    u, p = creds(); r = q("SELECT pw FROM users WHERE username=?", (u,), one=True)
    if not r or not check_password_hash(r["pw"], p): return jsonify(error="Неверное имя или пароль"), 401
    t = secrets.token_urlsafe(32); q("UPDATE users SET token=? WHERE username=?", (t, u))
    return jsonify(token=t, username=u)

@app.get("/api/users")
@auth
def users(me):
    s = re.sub(r"[^a-z0-9_]", "", request.args.get("q", "").lower())
    rows = q("SELECT username FROM users WHERE username LIKE ? AND username!=? LIMIT 20", (s + "%", me))
    return jsonify([r["username"] for r in rows])

@app.get("/api/chats")
@auth
def chats(me):
    seen = {}
    for r in q("SELECT sender,recipient,text,ts FROM messages WHERE sender=? OR recipient=? ORDER BY id DESC", (me, me)):
        peer = r["recipient"] if r["sender"] == me else r["sender"]
        seen.setdefault(peer, {"name": peer, "text": r["text"], "ts": r["ts"]})
    return jsonify(list(seen.values()))

@app.get("/api/messages/<peer>")
@auth
def history(me, peer):
    rows = q("""SELECT sender,recipient,text,ts FROM messages WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) ORDER BY id DESC LIMIT 200""", (me, peer, peer, me))
    return jsonify([{"from": r["sender"], "to": r["recipient"], "text": r["text"], "ts": r["ts"]} for r in reversed(rows)])

@sio.on("connect")
def on_connect(a=None):
    me = user_by_token((a or {}).get("token"))
    if not me: return False
    sid_user[request.sid] = me; join_room(me)

@sio.on("disconnect")
def on_disconnect(*_): sid_user.pop(request.sid, None)

@sio.on("send")
def on_send(d):
    me = sid_user.get(request.sid); to, text = str((d or {}).get("to", "")), str((d or {}).get("text", "")).strip()[:2000]
    if not me or not text or not q("SELECT 1 FROM users WHERE username=?", (to,), one=True): return
    ts = int(time.time()); q("INSERT INTO messages(sender,recipient,text,ts) VALUES(?,?,?,?)", (me, to, text, ts))
    for room in {me, to}: emit("message", {"from": me, "to": to, "text": text, "ts": ts}, to=room)

if __name__ == "__main__":
    sio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), allow_unsafe_werkzeug=True)
