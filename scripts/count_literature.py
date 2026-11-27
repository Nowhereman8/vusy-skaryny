"""Скачвае класіку з be.wikisource і лічыць словы (як для «Вусоў»). Вынік: literature/summary.json."""
import json, os, re, time, urllib.parse, urllib.request
API = "https://be.wikisource.org/w/api.php"
UA = {"User-Agent": "VusySkaryny-stats/1.0 (word count for internal report)"}
WORKS = [("Новая зямля", "Якуб Колас"), ("Сымон-музыка", "Якуб Колас"), ("Паўлінка", "Янка Купала"),
         ("Тутэйшыя", "Янка Купала"), ("Курган", "Янка Купала"), ("Дудка беларуская", "Францішак Багушэвіч"),
         ("Вянок", "Максім Багдановіч"), ("Тарас на Парнасе", ""), ("Пінская шляхта", "Вінцэнт Дунін-Марцінкевіч")]
def get(params):
    params.update(format="json", formatversion="2")
    for i in range(6):
        try:
            req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(1.5); return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(20 * (i + 1))
    raise RuntimeError("429 too long")
import html as H
def rendered(title):
    d = get({"action": "parse", "page": title, "prop": "text|links", "redirects": 1})["parse"]
    t = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", d["text"], flags=re.S)
    t = re.sub(r'<span class="pagenum.*?</span>', " ", t, flags=re.S)
    t = H.unescape(re.sub(r"<[^>]+>", " ", t))
    return t, [l["title"] for l in d.get("links", []) if l.get("ns") == 0 and l.get("exists", True)]
def text_of(title, name, depth=0):
    t, links = rendered(title)
    subs = [p["title"] for p in get({"action": "query", "list": "allpages", "apprefix": title + "/", "aplimit": 500})["query"]["allpages"]]
    if subs:
        return "\n".join(rendered(p)[0] for p in subs), title, len(subs)
    if words(t) < 1500 and depth == 0:
        cand = [l for l in links if name.lower()[:6] in l.lower() and l != title and "Заручыны" not in l]
        if cand: return text_of(cand[0], name, 1)
    return t, title, 0
def raw(title):
    url = "https://be.wikisource.org/w/index.php?" + urllib.parse.urlencode({"title": title, "action": "raw"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: return r.read().decode("utf-8")
def clean(t):
    for _ in range(3): t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", " ", t, flags=re.S); t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t); t = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", t)
    t = re.sub(r"^\s*(Катэгорыя|Category):.*$", "", t, flags=re.M)
    return t.replace("'''", "").replace("''", "")
words = lambda t: 0 if t is None else len(re.findall(r"[^\W\d_]+", t))
os.makedirs("literature", exist_ok=True); out = []
for name, author in WORKS:
    try:
        hits = get({"action": "query", "list": "search", "srsearch": f'intitle:"{name}" {author}', "srnamespace": 0, "srlimit": 5})["query"]["search"]
        hits = [h["title"] for h in hits if name.lower() in h["title"].lower()]
        if not hits: print("NOT FOUND:", name); out.append({"work": name, "author": author, "found": False}); continue
        base = min(hits, key=len).split("/")[0]
        text, base, nsub = text_of(base, name); subs = range(nsub); pages = [base] * max(1, nsub)
        n = words(text)
        open(f"literature/{base.replace('/', '_')}.txt", "w", encoding="utf-8").write(text)
        out.append({"work": name, "author": author, "page": base, "subpages": len(subs), "words": n, "found": True})
        print(f"{name}: {base} | {len(pages)} стар. | {n} слоў")
    except Exception as e:
        print("ERROR", name, e); out.append({"work": name, "author": author, "found": False, "error": str(e)})
json.dump(out, open("literature/summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE")
