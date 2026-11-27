"""Статыстыка па facts/*.json: асобы, ролі Віктара, месцы, эпохі, сцэнкі, міфы катоў."""
import json, glob, os, csv, collections as C
F = {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob("facts/*.json"))}
out = "analysis/out"; os.makedirs(out, exist_ok=True)
pers, main, places, era, cat, cent, food = (C.Counter() for _ in range(7))
for f in F.values():
    cat[f["category"]] += 1; era[f["era"]] += 1
    for p in f["persons"]:
        pers[p["name"]] += 1
        if p.get("is_main"): main[p["name"]] += 1
    for p in f["places"]: places[p["name"]] += 1
    for c in f["centuries"]: cent[str(c)] += 1
    for x in f["food"]: food[str(x)] += 1
json.dump({"episodes": len(F), "category": cat.most_common(), "era": era.most_common(),
           "centuries": cent.most_common(), "persons_episodes": pers.most_common(60),
           "main_persons": main.most_common(40), "places_episodes": places.most_common(60),
           "food": food.most_common(30)}, open(f"{out}/facts_summary.json", "w"), ensure_ascii=False, indent=1)
def rows(key, cols):
    with open(f"{out}/{key}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["episode", "youtube_id", "topic"] + cols)
        for s, f in F.items():
            for x in f.get(key, []):
                w.writerow([s[:3], s[4:], f["main_topic"]] + [x.get(c, "") if not isinstance(x.get(c), list) else "; ".join(x[c]) for c in cols])
rows("sketches", ["start", "end", "title", "summary", "characters", "funny", "instagram"])
rows("viktar_roles", ["character", "timecode", "note"])
rows("cat_myths", ["myth", "truth", "timecode"])
with open(f"{out}/best_quotes.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["episode", "topic", "speaker", "quote"])
    for s, f in F.items():
        q = f.get("best_quote") or {}; w.writerow([s[:3], f["main_topic"], q.get("speaker", ""), q.get("text", "")])
print("ok", len(F))
