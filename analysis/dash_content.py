"""Рыхтуе файлы для старонкі статыстыкі з facts/*.json."""
import json, glob, os, random, re, collections as C
F = {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob("facts/*.json"))}
def tsec(t):
    p = [int(x) for x in re.findall(r"\d+", str(t))][:3]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p))) if p else 0
url = lambda s, t: f"https://www.youtube.com/watch?v={s[4:]}&t={tsec(t)}s"
ROLE = {"селянін": "Сялянін", "сялянін": "Сялянін", "багуслаў радзівіл": "Богуслаў Радзівіл"}
PLACE = {"Менск": "Мінск"}
cnt = {g: C.Counter() for g in ["era", "century", "person", "main", "place", "role", "food", "category"]}
for s, f in F.items():
    cnt["era"][f["era"]] += 1; cnt["category"][f["category"]] += 1
    for c in set(f["centuries"]): cnt["century"][f"{c}"] += 1
    for p in {p["name"] for p in f["persons"]}: cnt["person"][p] += 1
    for p in {p["name"] for p in f["persons"] if p.get("is_main")}: cnt["main"][p] += 1
    for p in {PLACE.get(p["name"], p["name"]) for p in f["places"]}: cnt["place"][p] += 1
    for x in {str(x).lower() for x in f["food"]}: cnt["food"][x] += 1
    for r in f["viktar_roles"]:
        n = r["character"].strip(); cnt["role"][ROLE.get(n.lower(), n)] += 1
rows = []
for g, c in cnt.items():
    items = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
    if g == "century": items = sorted(c.items(), key=lambda kv: int(kv[0]))
    lim = {"person": 40, "main": 30, "place": 30, "food": 20}.get(g)
    if lim: items = items[:lim]
    for label, v in items:
        rows.append({"key": f"{g}:{label}", "group": g, "label": label, "value": v})
sk = [dict(x, _s=s) for s, f in F.items() for x in f["sketches"]]
kp = {"sketches": len(sk), "sketches_top": sum(1 for x in sk if x.get("funny") == 5),
      "myths": sum(len(f["cat_myths"]) for f in F.values()),
      "role_apps": sum(cnt["role"].values()), "roles": len(cnt["role"]),
      "persons": len(cnt["person"]), "places": len(cnt["place"]), "episodes": len(F)}
rows += [{"key": f"kpi:{k}", "group": "kpi", "label": k, "value": v} for k, v in kp.items()]
json.dump(rows, open("analysis/out/dash/content.json", "w"), ensure_ascii=False)
top = sorted([x for x in sk if x.get("funny") == 5], key=lambda x: (x["_s"], tsec(x["start"])))
json.dump([{"n": i + 1, "episode": int(x["_s"][:3]), "topic": F[x["_s"]]["main_topic"], "start": x["start"],
            "title": x["title"], "summary": x["summary"], "characters": "; ".join(x.get("characters") or []),
            "url": url(x["_s"], x["start"])} for i, x in enumerate(top)],
          open("analysis/out/dash/sketches.json", "w"), ensure_ascii=False)
my = [{"episode": int(s[:3]), "topic": f["main_topic"], "myth": m["myth"], "truth": m["truth"], "url": url(s, m["timecode"])}
      for s, f in F.items() for m in f["cat_myths"]]
random.seed(7); pick = [m for m in my if len(m["myth"]) < 110 and len(m["truth"]) < 170]; random.shuffle(pick)
for i, m in enumerate(my): m["featured"] = 0
seen = set(); k = 0
for m in pick:
    if m["episode"] in seen: continue
    seen.add(m["episode"]); m["featured"] = 1; k += 1
    if k == 12: break
json.dump(my, open("analysis/out/dash/myths.json", "w"), ensure_ascii=False)
print(kp); print([ (r['label'],r['value']) for r in rows if r['group']=='role'][:12])
for m in my:
    if m["featured"]: print("-", m["episode"], m["myth"])
