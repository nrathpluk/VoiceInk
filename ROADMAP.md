# ROADMAP — ThaiVoice

สิ่งที่ยังขาด + แนวทางต่อยอด จัดเรียงตามแรงผลัก (impact ÷ effort)

---

## P0 — ต้องมีก่อน release จริง

### 1. Demo GIF / screenshot
README link `docs/demo.gif` แต่ไฟล์ไม่มี — โหลด repo จะเห็น broken image
แก้: อัด ScreenToGif → `docs/demo.gif`

---

## P1 — UX ปรับใหญ่

### 2. เลือก mic device ได้
ตอนนี้ใช้ default mic อย่างเดียว — เครื่องที่มี webcam + headset + virtual mic เลือกไม่ได้
แก้: เพิ่มเมนูคลิกขวา → `Microphone` → list `sd.query_devices(kind="input")`

### 3. Custom vocabulary / initial_prompt
Whisper รับ `initial_prompt` boost คำเฉพาะ (ชื่อคน, ศัพท์เทคนิค, ชื่อบริษัท)
แก้: ช่อง textarea ใน settings → ส่งเข้า `model.transcribe(..., initial_prompt=...)`

### 4. Auto-paste mode (opt-in)
DESIGN_NOTES §16 ตัดทิ้ง เพราะอันตราย — แต่ทำเป็น **off by default + checkbox** ได้
แก้: หลัง `pyperclip.copy(text)` → ถ้า `auto_paste` on → `keyboard.send("ctrl+v")` หลัง delay 50ms

---

## P2 — Distribution / quality

### 5. Signed .exe (ลด SmartScreen warning)
ตอนนี้ exe unsigned — SmartScreen เตือนทุกคนที่ดาวน์โหลด. self-signed cert ลดได้บ้าง, EV cert จริงราคา ~$200/ปี
แก้: ใช้ `signtool sign` ใน `build.yml` + เก็บ cert ใน GitHub Secrets

---

## P3 — ของเล่น / nice-to-have

### 6. History persist + ค้นหา
ตอนนี้ history หาย ทุกครั้งปิด — เก็บ `history.jsonl` ใน `%APPDATA%`
เพิ่ม search box ใน history menu

### 7. Multi-monitor / DPI scaling
หน้าจอ 4K + 100% DPI / 200% DPI capsule เล็ก/ใหญ่ผิด
แก้: `ctypes.windll.shcore.SetProcessDpiAwareness(2)` + scale font ตาม `winfo_fpixels`

### 8. Whisper compute_type ให้ user เลือก
ตอนนี้ auto fallback — power user อาจอยาก force `int8_float16` ลด VRAM
แก้: เมนู `Compute` → `auto` / `float16` / `int8_float16` / `int8`

### 9. Crash reporter (opt-in)
Sentry SDK — ถ้า user opt-in ส่ง stack trace อัตโนมัติ
ตอนนี้ user ต้องเปิด `thai_voice.log` ส่งเอง

### 10. Mic permission pre-check
Windows 11 ปิด mic privacy แอปเงียบไม่อัดอะไรเลย
แก้: ก่อน `audio.start()` เช็ค privacy setting → toast แจ้งไปเปิด

### 11. Keyboard shortcut conflict detection
user set `ctrl+c` เป็น hotkey → break copy ทุกอย่าง
แก้: blacklist common shortcuts (`ctrl+c`, `ctrl+v`, `ctrl+x`, `ctrl+z`, `alt+tab`, etc.)

---

## P4 — เปลี่ยน architecture (ใหญ่)

### 12. แทน faster-whisper ด้วย whisper.cpp
ลดขนาด .exe จาก ~106MB → ~30–50MB
แก้: `pywhispercpp` หรือเรียก binary ตรง ๆ — model format `.bin/gguf`

### 13. Plugin system
post-process pipeline: transcribe → tokenize → punctuation → custom regex → clipboard
ให้ user เขียน plugin Python file วาง `%APPDATA%\ThaiVoice\plugins\`

### 14. Cloud backend option
สำหรับเครื่องอ่อน — ส่งเสียงเข้า OpenAI Whisper API
toggle ใน settings + ช่องใส่ API key (encrypt ด้วย Windows DPAPI)

---

## ของอื่นที่ควรมีในรีโป

- [ ] `CONTRIBUTING.md` (สั้น ๆ — clone, install, run, branch convention)
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] icon source `.svg` หรือ `.afdesign` ใน `docs/`

---

## ลำดับแนะนำ

1. **สัปดาห์นี้** — `git init` + push GitHub + tag `v0.1.0` (ดู `docs/RELEASING.md`), demo.gif
2. **เดือนนี้** — Mic picker, custom vocab, signed .exe
3. **ถ้ามีเวลา** — auto-paste opt-in, history persist, DPI scaling
4. **เก็บไว้คิด** — whisper.cpp, plugin system, cloud backend

---

## Done

- ✅ LICENSE (MIT)
- ✅ Settings persistence — `config.py` + `%APPDATA%\ThaiVoice\config.json` (hotkey, model, language, window_x/y, tokenize_thai, live_mode, auto_update)
- ✅ Window position memory
- ✅ Multi-language support — `auto` / `th` / `en`
- ✅ Thai word tokenization — `pythainlp.word_tokenize` post-process
- ✅ Refactor split `main.py` (2026-05-02) — 1210 → 9 modules. ดู CLAUDE.md §Architecture
- ✅ Auto-update check — `updater.py` toasts when GitHub has newer release. Daemon thread, never blocks UI
- ✅ ruff lint + format — `pyproject.toml` + `.pre-commit-config.yaml`
- ✅ pytest tests — 34 tests in `tests/` (LiveTranscriber, AudioRecorder, config, log_setup, hotkey, updater, util)
- ✅ GitHub Actions CI — `.github/workflows/ci.yml` (lint+test) + `build.yml` (tag → draft Release)
- ✅ Inno Setup installer — `installer.iss` + `build_installer.bat` (manual compile, needs Inno Setup)
- ✅ Release prep — `CHANGELOG.md` + `docs/RELEASING.md` (manual git init/push/tag flow)
