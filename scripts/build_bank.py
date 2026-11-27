"""Збірае банк пытанняў з quiz/*.json: правярае, перамешвае варыянты, прыбірае дублі."""
import json, glob, random, re, os, csv
random.seed(42)
norm = lambda s: re.sub(r"[^\w]+", " ", s.lower()).strip()
bank, seen, rejected = [], set(), []
for f in sorted(glob.glob("quiz/*.json")):
    stem = os.path.basename(f)[:-5]; ep, yt = stem[:3], stem[4:]
    for i, q in enumerate(json.load(open(f))["questions"]):
        opts, c = q.get("options", []), q.get("correct")
        why = None
        if len(opts) != 4: why = "not 4 options"
        elif not isinstance(c, int) or not 0 <= c < 4: why = "bad correct"
        elif len({norm(o) for o in opts}) < 4: why = "duplicate options"
        elif norm(q["question"]) in seen: why = "duplicate question"
        if why: rejected.append((stem, i, why, q.get("question", ""))); continue
        seen.add(norm(q["question"]))
        order = list(range(4)); random.shuffle(order)
        m = q.get("myth_option")
        bank.append({
            "id": f"{ep}-{i:02d}", "episode": int(ep), "youtube_id": yt,
            "question": q["question"], "options": [opts[k] for k in order],
            "correct": order.index(c),
            "myth_option": order.index(m) if isinstance(m, int) and 0 <= m < 4 and m != c else None,
            "explanation": q.get("explanation", ""), "timecode": q.get("timecode", ""),
            "difficulty": q.get("difficulty", 2), "kids": bool(q.get("kids")), "type": q.get("type", "history"),
        })
os.makedirs("data", exist_ok=True)
json.dump(bank, open("data/question_bank.json", "w"), ensure_ascii=False, indent=1)
with open("data/question_bank_rejected.csv", "w", newline="") as fh:
    csv.writer(fh).writerows([("episode", "idx", "reason", "question")] + rejected)
print(len(bank), "questions,", len(rejected), "rejected")
