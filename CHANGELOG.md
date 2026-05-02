# Changelog

All notable changes documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-05-02

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
  (hotkey, model, language, live_mode, tokenize_thai, window position, auto_update)
- Auto-update check — daemon thread on startup polls GitHub Releases, toasts if newer version available. Opt-out via config (`auto_update: false`).
- PyInstaller single-file build (`build.bat` → `dist\ThaiVoice.exe`)
- Inno Setup installer (`installer.iss` + `build_installer.bat`) for Start Menu / Add-Remove Programs registration
- MIT license

### Engineering
- Multi-module layout (9 files): `main.py`, `log_setup.py`, `constants.py`, `util.py`, `config.py`, `audio.py`, `transcribe.py`, `ui_capsule.py`, `updater.py`. Refactored from a 1210-line monolithic `main.py`.
- 34 pytest unit tests (mocked: no real Tk / audio device / Whisper model). Covers `LiveTranscriber`, `AudioRecorder`, config round-trip, `_resolve_log_dir`, `insert_thai_word_breaks`, hotkey parser, version compare logic.
- `ruff` lint + format configured via `pyproject.toml`. `pre-commit` hook config in `.pre-commit-config.yaml`.
- GitHub Actions CI: `.github/workflows/ci.yml` runs ruff + pytest on Python 3.10 / 3.11 / 3.12 on `windows-latest` for every push/PR.
- GitHub Actions Build: `.github/workflows/build.yml` triggers on tag `v*`, builds `ThaiVoice.exe` via PyInstaller, creates a draft Release with the artifact attached.

### Notes
- CPU-only build by default (CUDA DLLs filtered to keep .exe small)
- First run downloads Whisper model to `%USERPROFILE%\.cache\huggingface\`

[Unreleased]: https://github.com/nrathpluk/VoiceInk/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nrathpluk/VoiceInk/releases/tag/v0.1.0
