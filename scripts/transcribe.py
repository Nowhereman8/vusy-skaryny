"""
Распознавание выпусков «Вусы Скарыны» через faster-whisper на видеокарте.

Примеры:
  python transcribe.py --model large-v3 --episodes 001 069 110
  python transcribe.py --model bl4dylion/faster-whisper-small-belarusian --episodes 001 069 110
  python transcribe.py --model large-v3 --all          (все файлы из папки audio)

Результат: transcripts/<модель>/<номер>_<id>.txt (с таймкодами) и .json
Уже готовые файлы пропускаются, так что скрипт можно прерывать и перезапускать.
"""
import argparse
import glob
import json
import os
import site
import sys
import time

# --- подключаем CUDA-библиотеки, установленные через pip (nvidia-cublas / nvidia-cudnn) ---
for sp in site.getsitepackages() + [site.getusersitepackages()]:
    for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_runtime/bin"):
        p = os.path.join(sp, sub)
        if os.path.isdir(p):
            os.add_dll_directory(p)
            os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]

from faster_whisper import WhisperModel  # noqa: E402

# Подсказка модели: стиль, язык и типичные имена. Помогает не съезжать в русский.
PROMPT = (
    "Вусы Скарыны. Праграма пра нечаканыя павароты беларускае гісторыі. "
    "Вялікае Княства Літоўскае, Полацк, Рэч Паспалітая, Радзівілы, Каліноўскі, Скарына."
)


def fmt(t):
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--episodes", nargs="*", default=[], help="номера, напр. 001 069 110")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--lang", default="be", help="be / ru / auto (по умолчанию be)")
    ap.add_argument("--audio", default="audio")
    ap.add_argument("--no-prompt", action="store_true")
    a = ap.parse_args()

    if a.all:
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

    out_dir = os.path.join("transcripts", a.model.replace("/", "__") + "_" + a.lang)
    os.makedirs(out_dir, exist_ok=True)

    print(f"Загружаю модель {a.model} на видеокарту...")
    model = WhisperModel(a.model, device="cuda", compute_type="float16")

    for i, f in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(f))[0]
        txt_path = os.path.join(out_dir, base + ".txt")
        if os.path.exists(txt_path):
            print(f"[{i}/{len(files)}] {base} — уже есть, пропускаю")
            continue

        t0 = time.time()
        segments, info = model.transcribe(
            f,
            language=None if a.lang == "auto" else a.lang,
            beam_size=5,
            vad_filter=True,
            initial_prompt=None if a.no_prompt else PROMPT,
        )
        segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]

        with open(txt_path, "w", encoding="utf-8") as fh:
            for s in segs:
                fh.write(f"[{fmt(s['start'])}] {s['text']}\n")
        with open(os.path.join(out_dir, base + ".json"), "w", encoding="utf-8") as fh:
            json.dump(
                {"file": base, "model": a.model, "language": info.language,
                 "language_probability": round(info.language_probability, 3),
                 "duration": round(info.duration, 1), "segments": segs},
                fh, ensure_ascii=False, indent=1,
            )

        dt = time.time() - t0
        print(f"[{i}/{len(files)}] {base}: язык={info.language} ({info.language_probability:.0%}), "
              f"{fmt(info.duration)} аудио за {dt:.0f} с")

    print(f"Готово. Тексты в папке {out_dir}")


if __name__ == "__main__":
    main()
