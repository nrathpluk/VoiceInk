# Shrink ThaiVoice.exe — Options

Current: ~106 MB single-file. Goal: smaller exe.

Where size comes from (estimate):
- `ctranslate2` DLLs (CPU + GPU/CUDA bits) — biggest chunk, often 40–80 MB
- `faster_whisper` package + tokenizer assets
- `numpy`, `sounddevice`, Python stdlib + tkinter
- `--onefile` overhead (compresses, but bootstrap unpacks each run)
- Whisper model itself: NOT bundled — downloaded on first run to `~/.cache/huggingface`. So model size doesn't count here.

---

## Options (ranked: easy → aggressive)

### 1. UPX compression — easiest, biggest single win
- Install UPX, point PyInstaller at it: `--upx-dir "C:\path\to\upx"`
- Typical: 30–50% smaller. 106 MB → ~55–70 MB likely.
- Cost: slower startup (~1–2 s extra). Some AVs flag UPX-packed exes.

### 2. Exclude CUDA / GPU DLLs from ctranslate2
- App always uses CPU fallback fine. CUDA DLLs ride along by default and are huge.
- Add `--exclude-module` for `nvidia.*` and prune large `cu*.dll` / `cudnn*.dll` via PyInstaller `excludes` or post-build script.
- Or pin `ctranslate2` to CPU-only wheel if available.
- Win: 30–60 MB.

### 3. Switch `--onefile` → `--onedir` + zip
- `onefile` adds ~10–15 MB bootstrap and slow first-run unpack.
- `onedir` ships folder. Distribute as zip — usually smaller after zip than `onefile`.
- Cost: not single-file. Folder of DLLs.

### 4. `--exclude-module` deadweight
- Add: `--exclude-module tkinter.test --exclude-module unittest --exclude-module pydoc_data --exclude-module test --exclude-module distutils`
- Win: a few MB. Free.

### 5. Don't ship `faster-whisper` — call Whisper API or cloud
- Replace local STT with OpenAI / Anthropic / Google STT REST.
- Win: drops ctranslate2 + faster-whisper entirely → exe likely ~15–25 MB.
- Cost: needs internet + API key + per-call cost. Privacy gone.

### 6. Replace faster-whisper with whisper.cpp / pywhispercpp
- whisper.cpp is plain C, no ctranslate2/CUDA baggage.
- Win: ctranslate2 gone. Likely ~30–50 MB exe.
- Cost: rewrite transcription path. Different model file format (.bin/gguf).

### 7. Use Vosk (Thai small model) instead of Whisper
- Vosk Thai small ≈ 50 MB model, fast CPU. No ctranslate2.
- Win: smaller deps. But model bundled or downloaded.
- Cost: lower accuracy than Whisper on Thai. Rewrite.

### 8. Switch packager: Nuitka instead of PyInstaller
- Nuitka compiles to C, can produce smaller binaries with `--lto=yes --onefile`.
- Win: variable, sometimes 10–30% smaller, faster startup.
- Cost: longer build, more flags to tune.

### 9. Strip / mklink tricks
- After build, `strip` DLLs (rare gain on Windows).
- 7z SFX wrapping `onedir` — distribute as self-extracting archive.
- Win: marginal.

---

## Recommended combos

- **Quick win, no rewrite:** #1 (UPX) + #2 (drop CUDA) + #4 (exclude deadweight). Target ~40–55 MB.
- **No-CUDA only:** #2 alone if UPX/AV is concern.
- **Big drop, accept rewrite:** #6 (whisper.cpp). Target ~25–35 MB.
- **Smallest possible:** #5 (cloud STT). Target ~15–25 MB. Loses offline.

---

## Tell me which path

Pick a number (or combo) and I'll implement. If `1+2+4`, I'll edit `build.bat` and add an `excludes` spec — no code changes to `main.py`.
