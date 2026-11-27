"""
Распознавание выпусков «Вусы Скарыны» через ElevenLabs Scribe (API).

Ключ берётся из переменной окружения ELEVENLABS_API_KEY
(один раз: setx ELEVENLABS_API_KEY "ключ"  и открыть новое окно PowerShell).

Примеры:
  python scribe.py --episodes 001 069 110
  python scribe.py --all
  python scribe.py --episodes 001 --model scribe_v2

Результат: transcripts/<модель>/<номер>_<id>.txt (реплики по спикерам с таймкодами)
и .json (полный ответ API). Готовые файлы пропускаются — можно прерывать и перезапускать.
"""
import argparse
import glob
import json
import os
import sys
import time

import requests

API_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def fmt(t):
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def to_turns(words):
    """Склеивает слова в реплики: новая реплика при смене спикера
    или после конца предложения, если реплика длиннее ~40 секунд."""
    turns, cur = [], None
    for w in words:
        typ = w.get("type")
        text = w.get("text", "")
        if typ == "audio_event":
            text = f" {text} "
        spk = w.get("speaker_id") or "?"
        if cur is None or (typ == "word" and spk != cur["spk"]):
            if cur and cur["text"].strip():
                turns.append(cur)
            cur = {"spk": spk, "start": w.get("start") or 0, "text": ""}
        cur["text"] += text
        if (typ == "word" and text.rstrip().endswith((".", "?", "!"))
                and (w.get("end") or 0) - cur["start"] > 40):
            turns.append(cur)
            cur = {"spk": spk, "start": w.get("end") or 0, "text": ""}
    if cur and cur["text"].strip():
        turns.append(cur)
    return turns


def speaker_label(spk):
    # speaker_0 -> Спікер 1
    try:
        return f"Спікер {int(str(spk).split('_')[-1]) + 1}"
    except ValueError:
        return f"Спікер {spk}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="scribe_v3")
    ap.add_argument("--episodes", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--range", nargs=2, type=int, metavar=("ОТ", "ДО"), help="диапазон номеров, напр. --range 2 35")
    ap.add_argument("--lang", default="bel", help="код языка ISO-639-3 (bel) или пусто для автоопределения")
    ap.add_argument("--audio", default="audio")
    ap.add_argument("--keyterms", help="файл со списком терминов, по одному на строку (платная опция)")
    a = ap.parse_args()

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("Нет ELEVENLABS_API_KEY. Выполни: setx ELEVENLABS_API_KEY \"ключ\" и открой новое окно PowerShell.")

    if a.range:
        lo, hi = a.range
        files = [f for f in sorted(glob.glob(os.path.join(a.audio, "*.mp3")))
                 if lo <= int(os.path.basename(f)[:3]) <= hi]
    elif a.all:
        files = sorted(glob.glob(os.path.join(a.audio, "*.mp3")))
    else:
        files = []
        for ep in a.episodes:
            found = glob.glob(os.path.join(a.audio, f"{int(ep):03d}_*.mp3"))
            if not found:
                print(f"!! Не найден файл для выпуска {ep}")
            files += found
    if not files:
        sys.exit("Нет файлов для распознавания.")

    keyterms = []
    if a.keyterms:
        with open(a.keyterms, encoding="utf-8") as fh:
            keyterms = [l.strip() for l in fh if l.strip()]

    out_dir = os.path.join("transcripts", a.model)
    os.makedirs(out_dir, exist_ok=True)

    for i, f in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(f))[0]
        txt_path = os.path.join(out_dir, base + ".txt")
        if os.path.exists(txt_path):
            print(f"[{i}/{len(files)}] {base} — уже есть, пропускаю")
            continue

        data = [("model_id", a.model), ("diarize", "true"), ("tag_audio_events", "true")]
        if a.lang:
            data.append(("language_code", a.lang))
        for k in keyterms:
            data.append(("keyterms", k))

        t0 = time.time()
        for attempt in range(3):
            try:
                with open(f, "rb") as audio:
                    r = requests.post(API_URL, headers={"xi-api-key": key}, data=data,
                                      files={"file": (os.path.basename(f), audio, "audio/mpeg")},
                                      timeout=900)
                if r.status_code == 200:
                    break
                print(f"   ошибка {r.status_code}: {r.text[:300]}")
                if r.status_code in (400, 401, 403, 422):
                    sys.exit("Остановлено: проверь ключ / параметры (см. ошибку выше).")
            except requests.RequestException as e:
                print(f"   сетевая ошибка: {e}")
            time.sleep(10 * (attempt + 1))
        else:
            print(f"!! {base}: не удалось после 3 попыток, пропускаю")
            continue

        res = r.json()
        with open(os.path.join(out_dir, base + ".json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)

        turns = to_turns(res.get("words", []))
        with open(txt_path, "w", encoding="utf-8") as fh:
            for t in turns:
                fh.write(f"[{fmt(t['start'])}] {speaker_label(t['spk'])}: {' '.join(t['text'].split())}\n")

        spk_count = len({t["spk"] for t in turns})
        print(f"[{i}/{len(files)}] {base}: язык={res.get('language_code')}, "
              f"спікераў={spk_count}, {time.time() - t0:.0f} с")

    print(f"Готово. Тексты в папке {out_dir}")


if __name__ == "__main__":
    main()
