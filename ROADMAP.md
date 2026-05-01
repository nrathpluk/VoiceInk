# ROADMAP — ThaiVoice / VoiceInk

สิ่งที่ยังขาด + แนวทางต่อยอด จัดเรียงตามแรงผลัก (impact ÷ effort)

---

## P0 — ต้องมีก่อน release จริง

### 1. ไฟล์ `LICENSE`
README เขียน "MIT" แต่ยังไม่มีไฟล์ — ตามกฎหมาย default = "all rights reserved"
แก้: `LICENSE` เนื้อหา MIT ใส่ปี + ชื่อ

### 2. Settings persistence
ตอนนี้ทุกครั้งเปิดแอป hotkey + model + live_mode reset เป็น default
แก้: เก็บ `%APPDATA%\ThaiVoice\config.json` keys: `hotkey`, `model`, `live_mode`, `window_x`, `window_y`
เหตุผลที่ DESIGN_NOTES §16 เคยตัด — สเปคแรกไม่ขอ ตอนนี้ใช้จริงเริ่มน่ารำคาญ

### 3. ตำแหน่งหน้าต่างจำได้
ลากย้ายแล้วปิด-เปิดใหม่กลับมุมขวาล่างเสมอ — รวมเข้า settings.json (ข้อ 2)

### 4. Demo GIF / screenshot
README link `docs/demo.gif` แต่ไฟล์ไม่มี — โหลด repo จะเห็น broken image
แก้: อัด ScreenToGif → `docs/demo.gif`

---

## P1 — UX ปรับใหญ่

### 5. เลือก mic device ได้
ตอนนี้ใช้ default mic อย่างเดียว — เครื่องที่มี webcam + headset + virtual mic เลือกไม่ได้
แก้: เพิ่มเมนูคลิกขวา → `Microphone` → list `sd.query_devices(kind="input")`

### 6. Custom vocabulary / initial_prompt
Whisper รับ `initial_prompt` boost คำเฉพาะ (ชื่อคน, ศัพท์เทคนิค, ชื่อบริษัท)
แก้: ช่อง textarea ใน settings → ส่งเข้า `model.transcribe(..., initial_prompt=...)`

### 7. Auto-paste mode (opt-in)
DESIGN_NOTES §16 ตัดทิ้ง เพราะอันตราย — แต่ทำเป็น **off by default + checkbox** ได้
แก้: หลัง `pyperclip.copy(text)` → ถ้า `auto_paste` on → `keyboard.send("ctrl+v")` หลัง delay 50ms

### 8. ภาษาอื่นนอก Thai
hardcode `language="th"` — บางครั้งพิมพ์ผสม EN
แก้: เมนู `Language` → `th` / `en` / `auto` (ยอมรับ +0.5–1s overhead)

### 9. ตัดคำ + เติมจุด/วรรค
Whisper Thai output ไม่ค่อยมีเว้นวรรค — copy ออกไปอ่านยาก
แก้: post-process ผ่าน [`pythainlp.tokenize.word_tokenize`](https://pythainlp.github.io/) + insert space ตามรูป

---

## P2 — Distribution / quality

### 10. GitHub Actions CI
- Lint: `ruff check`
- Build .exe ทุก push tag `v*` → upload เข้า Release
- ทดสอบ smoke (import main.py, ไม่ crash)
ไฟล์: `.github/workflows/build.yml`

### 11. GitHub Release + signed .exe
ตอนนี้ user ต้อง clone + build เอง
แก้: Tag `v0.1.0` → upload `ThaiVoice.exe` เข้า Release
Signing: ใช้ self-signed cert ก็ลด SmartScreen warning ได้บ้าง

### 12. Installer (optional)
Raw .exe ใช้ได้ แต่ไม่ register Start Menu / Add-Remove Programs
แก้: [Inno Setup](https://jrsoftware.org/isinfo.php) script → MSI/setup.exe

### 13. Tests
ตอนนี้ 0 tests
ขั้นต่ำ:
- `LiveTranscriber` — feed sine wave → check `committed_samples` advance
- `_resolve_log_dir` — mock filesystem
- Hotkey parser — invalid string ไม่ crash
- Audio buffer concat — empty → return zero-len array
Framework: pytest

### 14. Refactor split `main.py`
1043 บรรทัดไฟล์เดียว — แก้ส่วน UI กระทบ logic
แนะนำ:
```
main.py          # entry + wiring
ui_capsule.py    # FloatingWindow
audio.py         # record + RMS + sd stream
transcribe.py    # WhisperModel wrapper + LiveTranscriber
config.py        # settings persistence (P0 #2)
log_setup.py    # stream guard + logging
```

### 15. Linter / formatter
- `ruff` config ใน `pyproject.toml`
- `pre-commit` hook
ป้องกัน drift บน contributor

---

## P3 — ของเล่น / nice-to-have

### 16. ตัวเลือก auto-update
ดึง `https://api.github.com/repos/nrathpluk/VoiceInk/releases/latest` → toast ถ้ามี version ใหม่

### 17. History persist + ค้นหา
ตอนนี้ history หาย ทุกครั้งปิด — เก็บ `history.jsonl` ใน `%APPDATA%`
เพิ่ม search box ใน history menu

### 18. Multi-monitor / DPI scaling
หน้าจอ 4K + 100% DPI / 200% DPI capsule เล็ก/ใหญ่ผิด
แก้: `ctypes.windll.shcore.SetProcessDpiAwareness(2)` + scale font ตาม `winfo_fpixels`

### 19. Whisper compute_type ให้ user เลือก
ตอนนี้ auto fallback — power user อาจอยาก force `int8_float16` ลด VRAM
แก้: เมนู `Compute` → `auto` / `float16` / `int8_float16` / `int8`

### 20. Crash reporter (opt-in)
Sentry SDK — ถ้า user opt-in ส่ง stack trace อัตโนมัติ
ตอนนี้ user ต้องเปิด `thai_voice.log` ส่งเอง

### 21. Mic permission pre-check
Windows 11 ปิด mic privacy แอปเงียบไม่อัดอะไรเลย
แก้: ก่อน `start_record` เช็ค `Get-WinUserLanguageList` หรือ COM API → toast แจ้งไปเปิด

### 22. Keyboard shortcut conflict detection
user set `ctrl+c` เป็น hotkey → break copy ทุกอย่าง
แก้: blacklist common shortcuts (`ctrl+c`, `ctrl+v`, `ctrl+x`, `ctrl+z`, `alt+tab`, etc.)

---

## P4 — เปลี่ยน architecture (ใหญ่)

### 23. แทน faster-whisper ด้วย whisper.cpp
ลดขนาด .exe จาก ~106MB → ~30–50MB (อ้างอิง SHRINK_NOTES.md ที่ลบไปแล้ว)
แก้: `pywhispercpp` หรือเรียก binary ตรงๆ — model format `.bin/gguf`

### 24. Plugin system
post-process pipeline: transcribe → tokenize → punctuation → custom regex → clipboard
ให้ user เขียน plugin Python file วาง `%APPDATA%\ThaiVoice\plugins\`

### 25. Cloud backend option
สำหรับเครื่องอ่อน — ส่งเสียงเข้า OpenAI Whisper API
toggle ใน settings + ช่องใส่ API key (encrypt ด้วย Windows DPAPI)

---

## ของอื่นที่ควรมีในรีโป

- [ ] `LICENSE`
- [ ] `CHANGELOG.md` (เริ่มจาก v0.1.0)
- [ ] `CONTRIBUTING.md` (สั้นๆ — clone, install, run, branch convention)
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `pyproject.toml` (แทน `requirements.txt` + ruff config)
- [ ] `docs/demo.gif`
- [ ] icon source `.svg` หรือ `.afdesign` ใน `docs/`

---

## ลำดับแนะนำ

1. **สัปดาห์นี้** — LICENSE, settings.json (hotkey/model จำได้), demo.gif, GitHub Release v0.1.0
2. **เดือนนี้** — Mic picker, custom vocab, refactor split files, ruff + ci
3. **ถ้ามีเวลา** — auto-paste opt-in, ภาษาอื่น, tests
4. **เก็บไว้คิด** — whisper.cpp, plugin system, cloud backend
