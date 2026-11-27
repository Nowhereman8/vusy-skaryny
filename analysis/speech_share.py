"""Хто колькі казаў: вядучы (спікер з найбольшай колькасцю слоў у выпуску), сцэнкі (радкі ўнутры
тайм-кодаў сцэнак з facts/) і астатнія галасы — каты. 023 — віктарына з гасцямі, там «госці»."""
import re, glob, os, json, collections as C
def ts(t):
    p = [int(x) for x in re.findall(r"\d+", str(t))][:3]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p))) if p else None
rows = []
for f in sorted(glob.glob("transcripts/final/*.txt")):
    s = os.path.basename(f)[:-4]; sk = []
    for x in json.load(open(f"facts/{s}.json"))["sketches"]:
        a, b = ts(x["start"]), ts(x["end"])
        if a is not None and b is not None and b > a: sk.append((a, b))
    lines = []
    for line in open(f):
        m = re.match(r"^\[(\d+):(\d+)(?::(\d+))?\]\s*(Спікер\s*\d+)?:?\s*(.*)", line)
        if not m: continue
        t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) if m[3] else int(m[1]) * 60 + int(m[2])
        lines.append((t, m[4] or "?", len(re.findall(r"[^\W\d_]+", re.sub(r"\[[^\]]*\]", "", m[5])))))
    spk = C.Counter()
    for _, sp, n in lines: spk[sp] += n
    host = spk.most_common(1)[0][0]
    c = C.Counter()
    for t, sp, n in lines:
        c["sketch" if any(a <= t < b for a, b in sk) else "host" if sp == host else "cats"] += n
    other = "guests" if s.startswith("023") else "cats"
    rows.append({"id": s[4:], "host": c["host"], "cats": c["cats"] if other == "cats" else 0,
                 "guests": c["cats"] if other == "guests" else 0, "sketch": c["sketch"], "words": sum(c.values())})
json.dump(rows, open("analysis/out/dash/speech.json", "w"), ensure_ascii=False)
t = C.Counter(); [t.update({k: r[k] for k in ("host", "cats", "guests", "sketch", "words")}) for r in rows]
print(t, sum(1 for r in rows if r["cats"] > 0))
