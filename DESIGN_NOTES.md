# Design Notes — ThaiVoice

บันทึกเหตุผลทางเทคนิคของแต่ละการตัดสินใจ

---

## 1. ทำไมใช้ faster-whisper ไม่ใช้ openai-whisper

| | openai-whisper | faster-whisper |
|---|---|---|
| Backend | PyTorch | CTranslate2 (C++) |
| Speed | 1x | ~4x |
| RAM | สูง | ต่ำกว่า ~50% |
| int8 quantization | ไม่มี native | มี (CPU เร็วขึ้นอีก) |

**เหตุผล:** App นี้ user รอผลแบบ realtime หลังหยุดอัด ความเร็วสำคัญสุด CTranslate2 บีบ inference ลงเหลือ < 2 วินาที สำหรับ audio 5 วินาที (model `base`, CPU) — ทันใช้

---

## 2. ทำไมใช้ pystray ไม่ใช้ Tkinter window / Qt

- **Tkinter window** — ต้องเปิดหน้าต่างกินที่ dock พื้นที่ user ตลอด ไม่เหมาะ workflow แบบ "อัดแล้ววาง"
- **PyQt/PySide** — install ใหญ่ (>100MB) license ซับซ้อน overkill สำหรับ tray icon
- **pystray** — เบา ~50KB pure Python integrate กับ Pillow ได้ตรงๆ build .exe ขนาดเล็กลง

**ราคาที่จ่าย:** menu pystray static-ish ต้อง `update_menu()` หลัง mutate state — รับได้

---

## 3. ทำไม icon สร้างด้วย Pillow ไม่โหลดไฟล์ .ico

- **ไม่ต้องจัดการ asset path** — ตอน PyInstaller `--onefile` แตกไฟล์ใน temp dir path เปลี่ยน ต้องใช้ `sys._MEIPASS` ยุ่ง
- **3 สีต้องการ runtime swap** — gray/red/yellow ถ้าทำเป็น .ico ต้อง 3 ไฟล์ generate ใน code ครั้งเดียวจบ
- **ขนาด .exe เล็กลง** — ไม่ต้อง bundle ไฟล์เพิ่ม

**Trade-off:** icon ไม่สวยเท่าออกแบบมือ แต่ functional ครบ

---

## 4. ทำไม hotkey ใช้ `keyboard` lib ไม่ใช้ `pynput` / `keyboard_listener` ของ pystray

- **`pynput`** — global hotkey ทำงานไม่เสถียรบน Windows เวลามีหลาย modifier
- **pystray hotkey** — รับเฉพาะตอน focus tray ใช้ไม่ได้
- **`keyboard`** — hook ระดับ low-level Windows API ทำงานทุก context แม้ fullscreen game

**ข้อเสีย:** ต้องการ admin บางเครื่อง — แจ้งใน README

---

## 5. ทำไมแยก threading 3 ส่วน

```
Main thread       → pystray event loop (blocking)
keyboard thread   → hotkey listener (lib จัดการเอง)
worker thread     → record + transcribe (per-toggle, daemon)
```

**เหตุผล:**
- pystray `icon.run()` blocking ต้องอยู่ main thread
- ถ้า transcribe ใน hotkey callback → block keyboard hook → hotkey ค้าง 2-5 วินาที กดไม่ได้ระหว่างนั้น
- ใช้ `threading.Lock` ใน `toggle()` กัน race เวลา user กด hotkey รัวๆ

**ทางเลือกอื่น:** `asyncio` — overkill มี blocking call (sounddevice, whisper) ต้อง thread อยู่ดี

---

## 6. ทำไม model lazy load (ไม่ load ตอน startup)

- **Startup เร็ว** — tray icon ขึ้นทันที ไม่รอ 30 วินาที
- **เปลี่ยน model แล้วยังไม่โหลดทันที** — รอจนกด hotkey ครั้งแรก ถ้า user เปลี่ยนหลายครั้งก่อนใช้ ไม่เสียเวลา
- **First-use มี toast "Loading..."** — user รู้ว่ากำลังทำงาน

**ราคา:** กดครั้งแรกช้ากว่าครั้งหลัง — ยอมรับได้

---

## 7. ทำไม `compute_type="auto"` แล้ว fallback `int8`

```python
try:
    WhisperModel(name, device="auto", compute_type="auto")
except Exception:
    WhisperModel(name, device="cpu", compute_type="int8")
```

- `auto` — ถ้ามี GPU ใช้ float16 (เร็ว) ถ้า CPU ใช้ float32
- **GPU OOM เกิดบ่อย** กับ `large-v3` บนการ์ด 4-6GB → fallback `int8` ใช้ RAM น้อยลงครึ่งหนึ่ง
- **CUDA dll missing** บางเครื่อง → fallback CPU ทำงานได้ ไม่ crash

---

## 8. ทำไม `language="th"` hardcode (ไม่ auto-detect)

- **Auto-detect ใช้เวลาเพิ่ม** ~0.5-1 วินาที ทุกครั้ง
- **App นี้ออกแบบเฉพาะภาษาไทย** ตามสเปค
- **Auto-detect บางครั้งผิด** เช่น "OK" → en, ทำให้ผลลัพธ์เพี้ยน
- **`beam_size=5`** — accuracy ดีขึ้นเล็กน้อย เสียเวลาเพิ่ม ~10% รับได้

ถ้าอยาก multi-language ภายหลัง: เพิ่ม dropdown ใน menu

---

## 9. ทำไม sample rate 16000

- **Whisper train ที่ 16kHz** — ส่ง rate อื่นต้อง resample ภายใน เสียเวลา
- **เสียงพูดอยู่ใน band < 8kHz** (Nyquist) — 16kHz เหลือพอ
- **File size เล็ก** — buffer RAM น้อย

---

## 10. ทำไม audio buffer เป็น list ของ chunk แล้ว `np.concatenate` ตอนหยุด

- **Pre-allocate buffer ไม่ได้** — ไม่รู้ความยาวล่วงหน้า
- **Resize np.array ทุก callback ช้า** — O(n²) เพราะ copy ทั้ง array ทุกครั้ง
- **List append O(1)** — concat ครั้งเดียวตอนจบ O(n)

Pattern มาตรฐานของ sounddevice

---

## 11. ทำไม history ใช้ `deque(maxlen=5)`

- **Auto-evict** — ไม่ต้องเขียน logic ตัด list เอง
- **`appendleft` O(1)** — ใหม่สุดอยู่บน
- **Thread-safe สำหรับ append/pop** ที่ปลายทั้งสอง

ไม่ persist ลง disk — ตามสเปค "5 อันล่าสุด" ไม่ใช่ history ยาว

---

## 12. ทำไม build ใช้ `--onefile --noconsole` + `--collect-all`

| Flag | เหตุผล |
|---|---|
| `--onefile` | user double-click .exe เดียวจบ ไม่ต้อง folder _internal/ |
| `--noconsole` | ไม่เปิด terminal ดำๆ ระหว่าง user ใช้งาน |
| `--collect-all faster_whisper` | lib มี data files (tokenizer JSON) ที่ PyInstaller auto-detect ไม่เจอ |
| `--collect-all ctranslate2` | มี .dll/.so PyInstaller plug-in ไม่เห็น runtime crash "DLL not found" |
| `--hidden-import=winotify` | บางครั้ง dynamic import → PyInstaller มองไม่เห็น |

**ราคาที่จ่าย:** .exe ขนาด ~200-500MB และ startup ช้ากว่า run script ~2-3 วินาที (extract temp) — รับได้สำหรับ desktop tool

---

## 13. ทำไม winotify ไม่ใช้ plyer / win10toast

- **`win10toast`** — deprecated maintain หยุด crash บน Windows 11 บางเวอร์ชัน
- **`plyer`** — cross-platform abstraction layer เพิ่ม dependency เยอะ app นี้ Windows-only ไม่จำเป็น
- **`winotify`** — เรียก Windows Toast API ตรงๆ เบา ทำงานเสถียร Win10/11

---

## 14. ทำไมเลือก pyperclip ไม่ใช้ `win32clipboard`

- **pyperclip cross-platform** — ถ้าต้อง port macOS/Linux ภายหลัง ไม่ต้องเขียนใหม่
- **`win32clipboard`** ต้อง `pywin32` หนัก install ยุ่งบน Python ใหม่
- **Unicode ไทย** — pyperclip handle UTF-16 ถูกต้องบน Windows

---

## 15. Error handling philosophy

ทุก operation ที่อาจ fail หุ้มด้วย try/except + toast แจ้ง user ไม่ให้ crash ทั้ง app:

- mic หาย → toast "No mic" → กลับ IDLE
- model download fail → toast → revert state
- transcribe error → toast → log traceback
- toast ตัวเองพังเอง → silent (ไม่ recursive crash)

**หลัก:** tray app ต้อง resilient — ถ้า crash user เห็นแค่ icon หาย หาสาเหตุไม่เจอ

---

## 16. สิ่งที่ตัดทิ้ง (และทำไม)

| ตัด | เหตุผล |
|---|---|
| Settings persist (JSON config) | สเปคไม่ขอ — เพิ่ม `model.json` `hotkey.json` เป็น scope creep |
| VAD (voice activity detection) | สเปคบอก "กดอีกที" toggle ชัด VAD ทำให้ unpredictable |
| Auto-paste (Ctrl+V หลัง copy) | บาง app ไม่ accept paste ทันที + อันตราย user อาจอยู่ password field |
| Streaming transcription | faster-whisper ไม่ support native ดี ทำเองยุ่ง offline mode พอแล้ว |
| Multi-language toggle | สเปคระบุ "Thai" ชัด ทำเพิ่ม = scope creep |
