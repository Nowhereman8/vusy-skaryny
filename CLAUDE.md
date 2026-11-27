# Notes for Claude

Project: archive, quiz and closing report for the Belsat History YouTube series «Вусы Скарыны» (Belarusian history, 2022–2026). The owner (Maksim) worked on the show; talk to him in Russian.

- Episode files are named `NNN_<youtube-id>`; NNN = playlist position (1 = newest), 027 is a hidden video. Match files by YouTube ID, not by number.
- `transcripts/final/` is the canonical text per episode (Scribe where available, otherwise Gemini). Transcripts are in Belarusian with lines `[mm:ss] Спікер N: ...`.
- Show format: a host, a second participant and three cats who interrupt and often voice myths that the host then corrects; plus comic sketches. For quiz questions, the correct answer must be something the host affirms; cats' myths make good wrong options.
- Audio (MP3) lives only on the owner's PC in `C:\WORK\13 quiz\audio`, not in this repo. New Gemini transcripts appear there daily (free quota ~20/day) and are copied here when the PC is connected.
- Never commit API keys; scripts read them from env vars.
- Token budget matters: do not load all transcripts into the chat; process per episode via scripts/APIs and only review samples here.
