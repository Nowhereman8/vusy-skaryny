"""
Сбор статистики и комментариев по всем выпускам «Вусы Скарыны» с YouTube.
Использует yt-dlp.exe из этой же папки. ИИ и токены не нужны.

Запуск:  python collect_youtube.py
Результат:
  meta/<id>.json        — полные данные по видео (включая комментарии)
  stats.csv             — таблица: просмотры, лайки, комментарии, дата, длительность
  comments_all.md       — все комментарии по выпускам (сначала самые залайканные)
Уже скачанные видео пропускаются — можно прерывать и перезапускать.
"""
import csv
import json
import os
import subprocess
import sys
import time

YTDLP = os.path.join(".", "yt-dlp.exe") if os.name == "nt" else "yt-dlp"


def read_catalog(path="catalog.txt"):
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 4 or p[1] in ("", "NA"):
                continue
            title = "|".join(p[2:-1])
            if title == "NA":
                continue
            items.append({"n": int(p[0]), "id": p[1], "title": title})
    return items


def fetch(vid, out):
    cmd = [YTDLP, "-J", "--skip-download", "--write-comments", "--no-warnings",
           "--extractor-args", "youtube:comment_sort=top;max_comments=all,all,all,all",
           f"https://www.youtube.com/watch?v={vid}"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 or not r.stdout.strip():
        print("   ошибка:", (r.stderr or "")[-300:])
        return False
    data = json.loads(r.stdout)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return True


def fmt_date(d):
    return f"{d[6:8]}.{d[4:6]}.{d[:4]}" if d and len(d) == 8 else ""


def main():
    items = read_catalog()
    os.makedirs("meta", exist_ok=True)

    for i, it in enumerate(items, 1):
        out = os.path.join("meta", f"{it['id']}.json")
        if os.path.exists(out):
            continue
        t0 = time.time()
        ok = fetch(it["id"], out)
        print(f"[{i}/{len(items)}] {it['n']:03d} {'ok' if ok else 'НЕ УДАЛОСЬ'} ({time.time() - t0:.0f} с)")
        time.sleep(3)

    # --- сводка ---
    rows, md = [], ["# Вусы Скарыны — усе каментары\n"]
    for it in items:
        path = os.path.join("meta", f"{it['id']}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        comments = d.get("comments") or []
        rows.append({
            "n": it["n"], "id": it["id"], "title": d.get("title") or it["title"],
            "upload_date": fmt_date(d.get("upload_date")),
            "duration_min": round((d.get("duration") or 0) / 60, 1),
            "views": d.get("view_count") or 0,
            "likes": d.get("like_count") or 0,
            "comments": d.get("comment_count") or len(comments),
            "comments_downloaded": len(comments),
            "url": f"https://www.youtube.com/watch?v={it['id']}",
        })

        top = [c for c in comments if c.get("parent") in (None, "root")]
        replies = {}
        for c in comments:
            if c.get("parent") not in (None, "root"):
                replies.setdefault(c["parent"], []).append(c)
        top.sort(key=lambda c: c.get("like_count") or 0, reverse=True)

        md.append(f"\n## {it['n']:03d}. {d.get('title') or it['title']}\n")
        md.append(f"{rows[-1]['url']} · {rows[-1]['upload_date']} · "
                  f"{rows[-1]['views']} праглядаў · {rows[-1]['likes']} лайкаў · {len(comments)} каментароў\n")
        for c in top:
            text = " ".join((c.get("text") or "").split())
            md.append(f"- **{c.get('author', '')}** (👍 {c.get('like_count') or 0}): {text}")
            for r in sorted(replies.get(c.get("id"), []), key=lambda x: x.get("timestamp") or 0):
                rt = " ".join((r.get("text") or "").split())
                md.append(f"    - ↳ **{r.get('author', '')}** (👍 {r.get('like_count') or 0}): {rt}")

    with open("stats.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open("comments_all.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    tv = sum(r["views"] for r in rows)
    tl = sum(r["likes"] for r in rows)
    tc = sum(r["comments_downloaded"] for r in rows)
    print(f"\nГотово: {len(rows)} выпускаў, {tv} праглядаў, {tl} лайкаў, {tc} каментароў.")
    print("Файлы: stats.csv, comments_all.md")


if __name__ == "__main__":
    sys.exit(main())
