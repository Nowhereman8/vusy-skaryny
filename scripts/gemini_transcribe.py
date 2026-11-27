"""
Распознавание выпусков «Вусы Скарыны» через Gemini API.

Ключ: переменная окружения GEMINI_API_KEY
(один раз: setx GEMINI_API_KEY "ключ"  и открыть новое окно PowerShell).
Установка: pip install google-genai

Примеры:
  python gemini_transcribe.py --episodes 001 069 110
  python gemini_transcribe.py --range 36 122
  python gemini_transcribe.py --episodes 001 --model gemini-3.8-flash
"""
import argparse
import glob
import os
import sys
import time

from google import genai
from google.genai import types

PROMPT = """Гэта аўдыя выпуску гістарычнай праграмы «Вусы Скарыны» (Белсат).
Удзельнікі: вядучы, другі ўдзельнік і тры каты, якія перабіваюць вядучага; ёсць камічныя сцэнкі.

Зрабі ПОЎНУЮ даслоўную транскрыпцыю ўсёй размовы ад пачатку да канца, нічога не скарачай і не пераказвай.
Пішы па-беларуску сучасным афіцыйным правапісам; калі нехта гаворыць па-руску (цытаты), пішы па-руску.
Уласныя імёны, назвы і даты пішы дакладна.

Фармат — кожная рэпліка асобным радком:
[мм:сс] Спікер N: тэкст
Новы радок пры змене спікера або прыкладна кожныя 30–40 секунд маналога.
Нумаруй спікераў па голасе (Спікер 1, Спікер 2...). Музыку і гукі пазначай коратка ў квадратных дужках, напр. [музыка].
Без уводзін і каментароў — толькі транскрыпцыя."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--episodes", nargs="*", default=[])
    ap.add_argument("--range", nargs=2, type=int, metavar=("ОТ", "ДО"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--audio", default="audio")
    a = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("Нет GEMINI_API_KEY. Выполни: setx GEMINI_API_KEY \"ключ\" и открой новое окно PowerShell.")
    client = genai.Client(api_key=key)

    allf = sorted(glob.glob(os.path.join(a.audio, "*.mp3")))
    if a.range:
        files = [f for f in allf if a.range[0] <= int(os.path.basename(f)[:3]) <= a.range[1]]
    elif a.all:
        files = allf
    else:
        files = []
        for ep in a.episodes:
            found = glob.glob(os.path.join(a.audio, f"{int(ep):03d}_*.mp3"))
            if not found:
                print(f"!! Не найден файл для выпуска {ep}")
            files += found
    if not files:
        sys.exit("Нет файлов для распознавания.")

    out_dir = os.path.join("transcripts", a.model)
    os.makedirs(out_dir, exist_ok=True)

    for i, f in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(f))[0]
        txt_path = os.path.join(out_dir, base + ".txt")
        if os.path.exists(txt_path):
            print(f"[{i}/{len(files)}] {base} — уже есть, пропускаю")
            continue

        t0 = time.time()
        for attempt in range(3):
            try:
                up = client.files.upload(file=f)
                while up.state and up.state.name == "PROCESSING":
                    time.sleep(3)
                    up = client.files.get(name=up.name)
                resp = client.models.generate_content(
                    model=a.model,
                    contents=[up, PROMPT],
                    config=types.GenerateContentConfig(temperature=0, max_output_tokens=60000),
                )
                text = (resp.text or "").strip()
                try:
                    client.files.delete(name=up.name)
                except Exception:
                    pass
                if text:
                    break
                print("   пустой ответ, повторяю...")
            except Exception as e:
                msg = str(e)
                print(f"   ошибка: {msg[:300]}")
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    print("   лимит запросов — жду 60 с")
                    time.sleep(60)
                elif "404" in msg or "API key" in msg or "PERMISSION" in msg:
                    sys.exit("Остановлено: проверь ключ или название модели (--model).")
                else:
                    time.sleep(10 * (attempt + 1))
        else:
            print(f"!! {base}: не удалось, пропускаю")
            continue

        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        usage = getattr(resp, "usage_metadata", None)
        tok = f", токены вход/выход={usage.prompt_token_count}/{usage.candidates_token_count}" if usage else ""
        print(f"[{i}/{len(files)}] {base}: {len(text.splitlines())} радкоў, {time.time() - t0:.0f} с{tok}")

    print(f"Готово. Тексты в папке {out_dir}")


if __name__ == "__main__":
    main()
