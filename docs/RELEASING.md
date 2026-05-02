# Releasing ThaiVoice

ขั้นตอน manual ครั้งแรก (v0.1.0). ครั้งถัดไปอาจ automate มากขึ้น.

## Pre-flight

ตรวจ local ก่อน push ใด ๆ:

```bat
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import main"
build.bat
dist\ThaiVoice.exe          :: smoke test ด้วยมือ — hotkey + record + clipboard
```

ถ้าทุกอย่าง pass → continue.

## 1. ครั้งแรก: init git repo + push GitHub

```bat
:: ตอนนี้โปรเจกต์ยังไม่ใช่ git repo
cd C:\Users\JAY\Desktop\spaek_andcopy\thai-voice-app
git init
git branch -M main
git add .
git status                  :: ดูให้แน่ใจว่าไม่มีไฟล์เผลอ commit (.log, dist/, ฯลฯ)
git commit -m "v0.1.0 initial release"
```

สร้าง repo บน GitHub (GUI หรือ gh CLI):

```bat
gh repo create nrathpluk/VoiceInk --public --source=. --remote=origin --push
```

หรือถ้าทำผ่าน web — สร้าง repo เปล่า ๆ ที่ `https://github.com/nrathpluk/VoiceInk` แล้ว:

```bat
git remote add origin https://github.com/nrathpluk/VoiceInk.git
git push -u origin main
```

## 2. รอ CI สีเขียว

ดู `https://github.com/nrathpluk/VoiceInk/actions` — workflow `CI` ต้อง pass บน Python 3.10/3.11/3.12.

ถ้าแดง — แก้ไข, push fix, รอใหม่. **อย่า tag release จนกว่า CI ผ่าน.**

## 3. Tag + push → trigger build workflow

```bat
git tag -a v0.1.0 -m "v0.1.0 — first public release"
git push origin v0.1.0
```

`.github/workflows/build.yml` จะรันอัตโนมัติ:
- Setup Python 3.11 + ลง deps
- รัน `python make_icon.py`
- รัน `pyinstaller ThaiVoice.spec --noconfirm`
- Upload artifact `ThaiVoice-v0.1.0`
- สร้าง **draft** Release พร้อมแนบ `ThaiVoice.exe`

## 4. Review draft Release

ไปที่ `https://github.com/nrathpluk/VoiceInk/releases` → จะเห็น draft `v0.1.0`.

แก้ release notes ตาม `CHANGELOG.md`:

```markdown
## v0.1.0 — first public release

[paste content from CHANGELOG.md ## [0.1.0]]

### Install

ดาวน์โหลด `ThaiVoice.exe` แล้ว double-click. ครั้งแรก SmartScreen อาจ warn — กด More info → Run anyway.

### หรือใช้ installer

- ลง Inno Setup 6+
- ใน repo → run `build_installer.bat`
- ได้ `dist\ThaiVoice-Setup-0.1.0.exe`
```

(installer.exe ตอนนี้ยัง build manual; ครั้งหน้าเพิ่มเข้า build.yml ได้)

## 5. กด Publish release

Draft → Publish. ตอนนี้ public ติด search Google ได้.

## 6. Post-release

- Update README badge ถ้าจำเป็น (badge ปัจจุบันชี้ `ci.yml` workflow ✓)
- Add `[Unreleased]` section ใน `CHANGELOG.md` ถ้ายังไม่มี (มีแล้ว — อันถัดไปลงใต้นั้น)
- Bump version ใน `constants.py` (`VERSION`) + `pyproject.toml` ตอนเริ่ม dev cycle ถัดไป

## ปัญหาที่อาจเจอ

| ปัญหา | สาเหตุ | แก้ |
|---|---|---|
| `softprops/action-gh-release` 403 | `GITHUB_TOKEN` no `contents: write` | เพิ่ม `permissions: contents: write` ที่ job level (มีแล้วใน `build.yml`) |
| CI fail บน 3.10 แต่ pass บน 3.12 | type-hint syntax `X | None` | ลด matrix หรือใส่ `from __future__ import annotations` |
| PyInstaller missing module | local module หาย | เพิ่ม `hiddenimports=['module_name']` ใน `ThaiVoice.spec` |
| .exe ขนาดใหญ่ไป | CUDA DLLs ผ่าน filter | ตรวจ `_is_cuda_blob` ใน `ThaiVoice.spec` |
| SmartScreen warn ทุกคนที่ download | unsigned exe | ใช้ self-signed cert หรือซื้อ EV cert (ROADMAP #6 mentions) |

## Bumping version (next release)

1. Edit `constants.py` → `VERSION = "0.2.0"`
2. Edit `pyproject.toml` → `version = "0.2.0"`
3. Edit `installer.iss` → `#define AppVersion "0.2.0"`
4. Edit `build_installer.bat` → final echo path `dist\ThaiVoice-Setup-0.2.0.exe`
5. Add `## [0.2.0] — YYYY-MM-DD` section to `CHANGELOG.md`, move `[Unreleased]` items into it
6. Repeat steps 1-5 of this doc with `v0.2.0`
