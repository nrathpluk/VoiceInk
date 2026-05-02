# Changelog

## v0.1.0 — 2026-05-02

First public release.

### Added
- Floating capsule HUD (always-on-top, draggable, transparent corners)
- Global hotkey toggle (default `Ctrl+Shift+Space`)
- Offline Thai transcription via faster-whisper
- Auto-copy result to clipboard
- Live mode (sliding-window streaming preview)
- Multi-language picker: `auto` / `th` / `en`
- Thai word break post-process (pythainlp `newmm`)
- 10-item history menu, click-to-recopy
- Right-click menu: model / language / hotkey / live / history / quit
- Settings persist to `%APPDATA%\ThaiVoice\config.json`
  (hotkey, model, language, live_mode, tokenize_thai, window position)
- PyInstaller single-file build (`build.bat` → `dist\ThaiVoice.exe`)
- MIT license

### Notes
- CPU-only build by default (CUDA DLLs filtered to keep .exe small)
- First run downloads Whisper model to `%USERPROFILE%\.cache\huggingface\`
