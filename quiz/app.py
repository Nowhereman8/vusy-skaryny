"""Квіз «Вусы Скарыны» — фаза 1: уваход, гульцы, сола-гульня, ачкі, статыстыка.

Запуск:  uvicorn app:app --host 127.0.0.1 --port 8041
Першы ўліковы запіс:  python app.py adduser ІМЯ [--admin]
"""
import base64, hashlib, hmac, json, os, random, secrets, sqlite3, sys, time
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent
CONF = Path(os.environ.get("QUIZ_CONFIG", BASE / "config"))
DB_PATH = Path(os.environ.get("QUIZ_DB", BASE / "config" / "quiz.db"))
BANK_PATH = Path(os.environ.get("QUIZ_BANK", BASE.parent / "data" / "question_bank.json"))
SECURE_COOKIE = os.environ.get("QUIZ_SECURE_COOKIE", "1") == "1"
QUESTION_TIME = 20          # секунд на адказ
COOKIE_AGE = 365 * 24 * 3600

# ---------- банк пытанняў ----------
BANK = {q["id"]: q for q in json.loads(BANK_PATH.read_text(encoding="utf-8"))}
ERAS = sorted({q["era"] for q in BANK.values() if q.get("era")})

# ---------- база ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (name TEXT PRIMARY KEY, pw TEXT NOT NULL, admin INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY, name TEXT UNIQUE COLLATE NOCASE NOT NULL,
  avatar TEXT DEFAULT '🐱', show_seen INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS seen (player_id INTEGER, qid TEXT, ts REAL, correct INTEGER, PRIMARY KEY (player_id, qid));
CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, player_id INTEGER, started REAL, finished REAL,
  score INTEGER DEFAULT 0, correct INTEGER DEFAULT 0, total INTEGER, streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, filters TEXT);
CREATE TABLE IF NOT EXISTS game_q (game_id TEXT, idx INTEGER, qid TEXT, served REAL, answered REAL, choice INTEGER,
  points INTEGER, PRIMARY KEY (game_id, idx));
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, qid TEXT, player_id INTEGER, text TEXT, ts REAL, done INTEGER DEFAULT 0);
"""

def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    CONF.mkdir(parents=True, exist_ok=True)
    with closing(db()) as con:
        con.executescript(SCHEMA); con.commit()

# ---------- паролі і cookie (як у качалцы) ----------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2${salt}${h}"

def check_pw(pw, stored):
    try:
        _, salt, _h = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_pw(pw, salt), stored)

def secret():
    p = CONF / "secret.key"
    if not p.exists():
        CONF.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(32)); os.chmod(p, 0o600)
    return p.read_text().strip().encode()

def sign(data: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    mac = hmac.new(secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{mac}"

def unsign(token):
    try:
        raw, mac = token.rsplit(".", 1)
        if not hmac.compare_digest(hmac.new(secret(), raw.encode(), hashlib.sha256).hexdigest(), mac):
            return None
        return json.loads(base64.urlsafe_b64decode(raw))
    except Exception:
        return None

def pw_tag(stored):  # змена пароля выкідвае з усіх браўзераў
    return hashlib.sha256(stored.encode()).hexdigest()[:16]

def set_cookie(resp, name, value):
    resp.set_cookie(name, value, max_age=COOKIE_AGE, httponly=True, secure=SECURE_COOKIE, samesite="lax")

def account(req: Request):
    s = unsign(req.cookies.get("vq_session", ""))
    if not s:
        raise HTTPException(401, "login")
    with closing(db()) as con:
        row = con.execute("SELECT * FROM accounts WHERE name=?", (s.get("a"),)).fetchone()
    if not row or pw_tag(row["pw"]) != s.get("t"):
        raise HTTPException(401, "login")
    return row

def player(req: Request, required=True):
    account(req)
    s = unsign(req.cookies.get("vq_player", ""))
    row = None
    if s:
        with closing(db()) as con:
            row = con.execute("SELECT * FROM players WHERE id=?", (s.get("p"),)).fetchone()
    if not row and required:
        raise HTTPException(409, "player")
    return row

def pub_player(r):
    return {"id": r["id"], "name": r["name"], "avatar": r["avatar"], "show_seen": bool(r["show_seen"])} if r else None

# ---------- праграма ----------
app = FastAPI(docs_url=None, redoc_url=None)
init_db()

class Login(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(body: Login):
    with closing(db()) as con:
        row = con.execute("SELECT * FROM accounts WHERE name=?", (body.username.strip(),)).fetchone()
    if not row or not check_pw(body.password, row["pw"]):
        time.sleep(1)
        raise HTTPException(401, "bad")
    resp = JSONResponse({"ok": True})
    set_cookie(resp, "vq_session", sign({"a": row["name"], "t": pw_tag(row["pw"])}))
    return resp

@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("vq_session"); resp.delete_cookie("vq_player")
    return resp

@app.get("/api/me")
def me(req: Request):
    acc = account(req)
    return {"account": acc["name"], "admin": bool(acc["admin"]), "player": pub_player(player(req, False)),
            "eras": ERAS, "question_time": QUESTION_TIME, "bank": len(BANK)}

@app.get("/api/players")
def players(req: Request):
    account(req)
    with closing(db()) as con:
        rows = con.execute("""SELECT p.*, COALESCE(MAX(g.score),0) best, COUNT(g.id) games FROM players p
            LEFT JOIN games g ON g.player_id=p.id AND g.finished IS NOT NULL GROUP BY p.id ORDER BY p.name""").fetchall()
    return [{**pub_player(r), "best": r["best"], "games": r["games"]} for r in rows]

class NewPlayer(BaseModel):
    name: str
    avatar: str = "🐱"

@app.post("/api/players")
def new_player(body: NewPlayer, req: Request):
    account(req)
    name = " ".join(body.name.split())[:24]
    if len(name) < 2:
        raise HTTPException(400, "short")
    with closing(db()) as con:   # COLLATE NOCASE не ведае кірыліцы
        if any(r[0].casefold() == name.casefold() for r in con.execute("SELECT name FROM players")):
            raise HTTPException(409, "taken")
    try:
        with closing(db()) as con:
            cur = con.execute("INSERT INTO players(name, avatar, created) VALUES(?,?,?)", (name, body.avatar[:4] or "🐱", time.time()))
            con.commit(); pid = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "taken")
    return select_player(SelectPlayer(id=pid), req)

class SelectPlayer(BaseModel):
    id: int

@app.post("/api/player/select")
def select_player(body: SelectPlayer, req: Request):
    account(req)
    with closing(db()) as con:
        row = con.execute("SELECT * FROM players WHERE id=?", (body.id,)).fetchone()
    if not row:
        raise HTTPException(404, "no player")
    resp = JSONResponse({"player": pub_player(row)})
    set_cookie(resp, "vq_player", sign({"p": row["id"]}))
    return resp

@app.post("/api/player/leave")
def leave_player(req: Request):
    """«Гэта не я»: вярнуцца да выбару імя. Незавершаная гульня нікому не залічваецца."""
    p = player(req, False)
    if p:
        with closing(db()) as con:
            con.execute("DELETE FROM game_q WHERE game_id IN (SELECT id FROM games WHERE player_id=? AND finished IS NULL)", (p["id"],))
            con.execute("DELETE FROM games WHERE player_id=? AND finished IS NULL", (p["id"],)); con.commit()
    resp = JSONResponse({"ok": True}); resp.delete_cookie("vq_player")
    return resp

class Settings(BaseModel):
    show_seen: bool | None = None
    avatar: str | None = None

@app.put("/api/settings")
def settings(body: Settings, req: Request):
    p = player(req)
    with closing(db()) as con:
        if body.show_seen is not None:
            con.execute("UPDATE players SET show_seen=? WHERE id=?", (int(body.show_seen), p["id"]))
        if body.avatar:
            con.execute("UPDATE players SET avatar=? WHERE id=?", (body.avatar[:4], p["id"]))
        con.commit()
        return {"player": pub_player(con.execute("SELECT * FROM players WHERE id=?", (p["id"],)).fetchone())}

# ---------- гульня ----------
class Start(BaseModel):
    count: int = 10
    era: str | None = None
    difficulty: int | None = None

def public_q(q, idx, total):
    return {"idx": idx, "total": total, "id": q["id"], "question": q["question"], "options": q["options"],
            "difficulty": q["difficulty"], "era": q.get("era", ""), "time": QUESTION_TIME}

@app.post("/api/game/start")
def start(body: Start, req: Request):
    p = player(req)
    pool = [q for q in BANK.values() if (not body.era or q.get("era") == body.era)
            and (not body.difficulty or q["difficulty"] == body.difficulty)]
    with closing(db()) as con:
        seen = {r[0] for r in con.execute("SELECT qid FROM seen WHERE player_id=?", (p["id"],))}
        fresh = [q for q in pool if q["id"] not in seen]
        random.shuffle(fresh)
        exhausted = False
        if p["show_seen"]:
            old = [q for q in pool if q["id"] in seen]; random.shuffle(old)
            picked = (fresh + old)[: body.count] if len(fresh) < body.count else fresh[: body.count]
        else:
            picked = fresh[: body.count]
            exhausted = len(picked) < body.count
        if not picked:
            return {"exhausted": True, "game": None}
        # не больш за 2 пытанні з аднаго выпуску ў гульні
        by_ep, final = {}, []
        for q in picked + [q for q in fresh if q not in picked]:
            if by_ep.get(q["episode"], 0) < 2 and len(final) < len(picked):
                final.append(q); by_ep[q["episode"]] = by_ep.get(q["episode"], 0) + 1
        gid = secrets.token_urlsafe(9); now = time.time()
        con.execute("INSERT INTO games(id, player_id, started, total, filters) VALUES(?,?,?,?,?)",
                    (gid, p["id"], now, len(final), json.dumps(body.model_dump(), ensure_ascii=False)))
        con.executemany("INSERT INTO game_q(game_id, idx, qid) VALUES(?,?,?)", [(gid, i, q["id"]) for i, q in enumerate(final)])
        con.execute("UPDATE game_q SET served=? WHERE game_id=? AND idx=0", (now, gid)); con.commit()
    return {"game": gid, "exhausted": exhausted, "question": public_q(final[0], 0, len(final))}

class Answer(BaseModel):
    idx: int
    choice: int  # -1 = скончыўся час

@app.post("/api/game/{gid}/answer")
def answer(gid: str, body: Answer, req: Request):
    p = player(req)
    now = time.time()
    with closing(db()) as con:
        g = con.execute("SELECT * FROM games WHERE id=? AND player_id=?", (gid, p["id"])).fetchone()
        gq = con.execute("SELECT * FROM game_q WHERE game_id=? AND idx=?", (gid, body.idx)).fetchone()
        if not g or not gq or g["finished"]:
            raise HTTPException(404, "game")
        if gq["answered"]:
            raise HTTPException(409, "answered")
        q = BANK[gq["qid"]]
        elapsed = now - (gq["served"] or now)
        ok = body.choice == q["correct"] and elapsed <= QUESTION_TIME + 2   # 2 с на сетку
        streak = g["streak"] + 1 if ok else 0
        speed = max(0.0, 1 - elapsed / QUESTION_TIME)
        points = (500 + round(500 * speed) + 100 * min(streak - 1, 5)) if ok else 0
        con.execute("UPDATE game_q SET answered=?, choice=?, points=? WHERE game_id=? AND idx=?", (now, body.choice, points, gid, body.idx))
        con.execute("UPDATE games SET score=score+?, correct=correct+?, streak=?, best_streak=MAX(best_streak, ?) WHERE id=?",
                    (points, int(ok), streak, streak, gid))
        con.execute("INSERT OR REPLACE INTO seen(player_id, qid, ts, correct) VALUES(?,?,?,?)", (p["id"], q["id"], now, int(ok)))
        nxt = None
        if body.idx + 1 < g["total"]:
            n = con.execute("SELECT qid FROM game_q WHERE game_id=? AND idx=?", (gid, body.idx + 1)).fetchone()
            nxt = public_q(BANK[n["qid"]], body.idx + 1, g["total"])
        else:
            con.execute("UPDATE games SET finished=? WHERE id=?", (now, gid))
        con.commit()
        g = con.execute("SELECT score, correct, best_streak, total FROM games WHERE id=?", (gid,)).fetchone()
    return {"correct": q["correct"], "ok": ok, "points": points, "streak": streak, "myth": q.get("myth_option"),
            "explanation": q["explanation"], "episode_title": q.get("episode_title", ""),
            "link": f"https://www.youtube.com/watch?v={q['youtube_id']}&t={tc(q.get('timecode'))}s",
            "score": g["score"], "right": g["correct"], "best_streak": g["best_streak"], "total": g["total"], "next": nxt}

@app.post("/api/game/{gid}/next")
def serve_next(gid: str, req: Request):
    """Кліент паказаў наступнае пытанне — з гэтага моманту ідзе час."""
    p = player(req)
    with closing(db()) as con:
        row = con.execute("SELECT idx FROM game_q WHERE game_id=? AND answered IS NULL AND game_id IN (SELECT id FROM games WHERE player_id=?) ORDER BY idx LIMIT 1", (gid, p["id"])).fetchone()
        if row:
            con.execute("UPDATE game_q SET served=? WHERE game_id=? AND idx=? AND served IS NULL", (time.time(), gid, row["idx"])); con.commit()
    return {"ok": True}

def tc(t):
    parts = [int(x) for x in str(t or "0").replace(".", ":").split(":") if x.strip().isdigit()][:3]
    s = 0
    for x in parts: s = s * 60 + x
    return s

# ---------- статыстыка ----------
@app.get("/api/stats")
def stats(req: Request):
    p = player(req)
    with closing(db()) as con:
        g = con.execute("""SELECT COUNT(*) games, COALESCE(SUM(score),0) points, COALESCE(MAX(score),0) best,
            COALESCE(SUM(correct),0) "right", COALESCE(SUM(total),0) asked, COALESCE(MAX(best_streak),0) streak
            FROM games WHERE player_id=? AND finished IS NOT NULL""", (p["id"],)).fetchone()
        seen = con.execute("SELECT qid, correct FROM seen WHERE player_id=?", (p["id"],)).fetchall()
        recent = con.execute("SELECT score, correct, total, finished FROM games WHERE player_id=? AND finished IS NOT NULL ORDER BY finished DESC LIMIT 10", (p["id"],)).fetchall()
    eras = {}
    for r in seen:
        e = BANK.get(r["qid"], {}).get("era", "")
        d = eras.setdefault(e, [0, 0]); d[0] += 1; d[1] += r["correct"]
    return {**dict(g), "seen": len(seen), "bank": len(BANK), "episodes": len({BANK[r['qid']]['episode'] for r in seen if r['qid'] in BANK}),
            "eras": [{"era": e, "asked": a, "right": c} for e, (a, c) in sorted(eras.items(), key=lambda x: -x[1][0])],
            "recent": [dict(r) for r in recent]}

@app.get("/api/leaderboard")
def leaderboard(req: Request, period: str = "all"):
    account(req)
    since = time.time() - 7 * 86400 if period == "week" else 0
    with closing(db()) as con:
        rows = con.execute("""SELECT p.name, p.avatar, MAX(g.score) best, SUM(g.score) total, COUNT(*) games,
            SUM(g.correct)*100/MAX(SUM(g.total),1) pct FROM games g JOIN players p ON p.id=g.player_id
            WHERE g.finished IS NOT NULL AND g.finished>=? GROUP BY p.id ORDER BY best DESC LIMIT 30""", (since,)).fetchall()
    return [dict(r) for r in rows]

class Report(BaseModel):
    qid: str
    text: str = ""

@app.post("/api/report")
def report(body: Report, req: Request):
    p = player(req)
    if body.qid not in BANK:
        raise HTTPException(404, "q")
    with closing(db()) as con:
        con.execute("INSERT INTO reports(qid, player_id, text, ts) VALUES(?,?,?,?)", (body.qid, p["id"], body.text[:500], time.time())); con.commit()
    return {"ok": True}

@app.get("/api/reports")
def reports(req: Request):
    if not account(req)["admin"]:
        raise HTTPException(403, "admin")
    with closing(db()) as con:
        rows = con.execute("SELECT r.*, p.name FROM reports r LEFT JOIN players p ON p.id=r.player_id ORDER BY ts DESC").fetchall()
    return [{**dict(r), "question": BANK.get(r["qid"], {}).get("question", "")} for r in rows]

# ---------- старонка ----------
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html", headers={"Cache-Control": "no-cache"})

# ---------- кансоль ----------
if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "adduser":
        import getpass
        name = sys.argv[2]; pw = getpass.getpass(f"Пароль для {name}: ")
        with closing(db()) as con:
            con.execute("INSERT OR REPLACE INTO accounts(name, pw, admin) VALUES(?,?,?)", (name, hash_pw(pw), int("--admin" in sys.argv))); con.commit()
        print("гатова")
    else:
        print(__doc__)
