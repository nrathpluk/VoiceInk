# ThaiVoice — แอพถอดเสียงไทยลง Clipboard

แอพ desktop สำหรับ Windows กด hotkey อัดเสียง → Whisper ถอดเป็นข้อความไทย → copy เข้า clipboard อัตโนมัติ ทำงานอยู่ใน system tray

## ความต้องการ

- Windows 10 / 11
- Python 3.10 ขึ้นไป
- ไมโครโฟน
- (แนะนำ) GPU NVIDIA + CUDA สำหรับ model ใหญ่ ถ้าไม่มีจะใช้ CPU

## ติดตั้ง

```bat
pip install -r requirements.txt
```

## รันจาก source

```bat
python main.py
```

ไอคอนไมค์สีเทาจะปรากฏใน system tray (มุมขวาล่าง)

## Build เป็น .exe

```bat
build.bat
```

ได้ไฟล์ `dist\ThaiVoice.exe` (single file, ไม่เปิด console)

## วิธีใช้

1. กด `Ctrl+Shift+Space` → ไอคอนเปลี่ยนเป็น **สีแดง** = กำลังอัด
2. พูดภาษาไทย
3. กด `Ctrl+Shift+Space` อีกครั้ง → ไอคอน **สีเหลือง** = กำลังถอด
4. เสร็จ → ไอคอนกลับ **สีเทา** + Toast แจ้งว่า copied แล้ว
5. กด `Ctrl+V` วางในแอพอื่นได้เลย

## Tray Menu (คลิกขวาที่ไอคอน)

- **Model** — เลือก `tiny` / `base` / `small` / `medium` / `large-v3`
  - `tiny` เร็วสุด แม่นยำต่ำสุด
  - `base` (default) สมดุลดี
  - `large-v3` แม่นยำสุด แต่ช้าและใช้ RAM/VRAM เยอะ
- **History** — ดู 5 ข้อความล่าสุด คลิกเพื่อ copy ซ้ำ
- **Set hotkey...** — เปลี่ยน hotkey เช่น `ctrl+alt+r`, `f9`
- **Quit** — ออกจากโปรแกรม

## หมายเหตุ

- **ครั้งแรกที่ใช้แต่ละ model จะ download อัตโนมัติ** (~75MB สำหรับ `tiny` ถึง ~3GB สำหรับ `large-v3`) เก็บที่ `%USERPROFILE%\.cache\huggingface\` ระหว่าง download แอพอาจค้างชั่วคราว มี toast แจ้งก่อน
- ใช้ **faster-whisper** (CTranslate2) เร็วกว่า openai-whisper ~4 เท่า
- ถ้ามี NVIDIA GPU + CUDA จะ auto ใช้ ไม่ต้องตั้งค่า

## Troubleshoot

| ปัญหา | แก้ |
|------|-----|
| Hotkey ไม่ทำงาน | รันเป็น Administrator (`keyboard` lib ต้องการสิทธิ์ admin บางเครื่อง) |
| ไม่มีเสียง / mic ไม่เจอ | ตรวจ Settings → System → Sound → Input device |
| Model load fail | เช็ค RAM พอไหม / ลอง model เล็กลง / ลบ cache แล้ว download ใหม่ |
| .exe ใหญ่มาก | ปกติ ~200-500MB เพราะรวม CTranslate2 + dependencies |
| CUDA error | ติดตั้ง cuDNN ให้ตรง version หรือใช้ CPU mode (model จะใช้ int8 อัตโนมัติ) |

## โครงสร้างไฟล์

```
thai-voice-app/
├── main.py            # โค้ดทั้งหมด
├── requirements.txt   # Python packages
├── build.bat          # script build .exe
└── README.md          # ไฟล์นี้
```
