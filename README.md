# ThaiVoice

[![CI](https://github.com/nrathpluk/VoiceInk/actions/workflows/ci.yml/badge.svg)](https://github.com/nrathpluk/VoiceInk/actions/workflows/ci.yml)

แอปถอดเสียงไทยเป็นข้อความ สำหรับ Windows ที่ทำอันนี้ออกมาเพราะว่าบางทีผมขี้เกียจพิมพ์แล้วก็เวลาผมทำอะไรผมชอบอธิบายเป็นคำพูดมากกว่า

<!-- TODO: ใส่ GIF / screenshot ที่นี่ -->
![demo](docs/demo.gif)

## ฟีเจอร์

- หน้าต่างแคปซูลลอย always-on-top
- Hotkey ลัด (default `Ctrl+Shift+Space`)
- ใช้ Whisper offline ผ่าน faster-whisper — ไม่ต้องต่อเน็ต ไม่ต้องส่งเสียงขึ้น cloud
- ถอดเสร็จ copy ลง clipboard อัตโนมัติ — กด `Ctrl+V` วางในแอปไหนก็ได้
- ประวัติ 10 ข้อความล่าสุด คลิกเพื่อ copy ซ้ำ
- ลากย้ายตำแหน่งได้
- เลือก model ได้: `tiny` / `base` / `small` / `medium` / `large-v3`
- Live mode — preview ข้อความระหว่างพูด

## สิ่งที่ต้องมี

- Windows 10 / 11
- Python 3.10+
- ไมโครโฟน
- (แนะนำ) GPU NVIDIA + CUDA สำหรับ model ใหญ่

## เริ่มใช้งาน

```bat
git clone https://github.com/nrathpluk/VoiceInk.git
cd VoiceInk
pip install -r requirements.txt
python main.py
```

แคปซูลลอยจะโผล่มุมขวาล่าง

## Build เป็น .exe

```bat
build.bat
```

ได้ไฟล์ `dist\ThaiVoice.exe` — single file, ไม่เปิด console

### Installer (optional)

หลังจาก `build.bat` แล้ว ถ้าอยาก installer (.exe ที่ register Start Menu + Add/Remove Programs):

1. ลง [Inno Setup 6+](https://jrsoftware.org/isinfo.php)
2. รัน `build_installer.bat`
3. ได้ไฟล์ `dist\ThaiVoice-Setup-0.1.0.exe`

## วิธีใช้

1. กด hotkey (`Ctrl+Shift+Space`) → แคปซูลเปลี่ยนเป็นสีแดง = กำลังอัด
2. พูดภาษาไทย
3. กด hotkey อีกครั้ง → ถอดเสียง → copy ลง clipboard อัตโนมัติ
4. กด `Ctrl+V` วางในแอปอื่น
5. คลิกปุ่มไมค์บนแคปซูล = toggle เหมือน hotkey
6. คลิกขวาบนแคปซูล = เมนู (เปลี่ยน model, hotkey, ดู history, เปิด live mode, quit)
7. ลาก body ของแคปซูลเพื่อย้ายตำแหน่ง

## ตั้งค่า

| Config | ค่า default | เปลี่ยนที่ |
|---|---|---|
| Hotkey | `ctrl+shift+space` | คลิกขวา → `Hotkey:...` |
| Model | `base` | คลิกขวา → `Model` |
| ภาษา | `th` | คลิกขวา → `Language` (`auto` / `th` / `en`) |
| Live mode | ปิด | คลิกขวา → `Live mode (streaming)` |
| ตัดคำไทย | เปิด | คลิกขวา → `ตัดคำไทย` |

ค่าทุกตัว + ตำแหน่งหน้าต่าง บันทึกที่ `%APPDATA%\ThaiVoice\config.json` อัตโนมัติ

ครั้งแรกของแต่ละ model จะ download อัตโนมัติ (~75MB ถึง ~3GB) เก็บที่ `%USERPROFILE%\.cache\huggingface\`

## เทคโนโลยีที่ใช้

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper บน CTranslate2 เร็วกว่า openai-whisper ~4 เท่า
- [tkinter](https://docs.python.org/3/library/tkinter.html) — UI แคปซูลลอย
- [sounddevice](https://python-sounddevice.readthedocs.io/) — อัดเสียงจากไมค์
- [keyboard](https://github.com/boppreh/keyboard) — global hotkey
- [pyperclip](https://github.com/asweigart/pyperclip) — copy ลง clipboard
- [winotify](https://github.com/versa-syahptr/winotify) — Windows toast notification

## License

MIT — ดู [`LICENSE`](LICENSE)

