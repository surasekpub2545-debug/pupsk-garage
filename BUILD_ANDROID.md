# Build APK — PUP-SK GARAGE

Buildozer ไม่รัน native บน Windows — ต้องผ่าน **WSL2 (Ubuntu)** หรือ Docker

---

## ทางที่แนะนำ: WSL2

### 1. ติดตั้ง WSL2 + Ubuntu 22.04 (ครั้งเดียว)

PowerShell แบบ admin:
```powershell
wsl --install -d Ubuntu-22.04
```
รีสตาร์ทเครื่อง, เปิด Ubuntu, ตั้ง user/password

### 2. ติดตั้งของที่ buildozer ต้องการ (ใน Ubuntu)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv build-essential git \
    zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev \
    libncurses-dev libncurses5 libtinfo5 cmake libffi-dev libssl-dev

pip install --user --upgrade buildozer cython==0.29.36
```

### 3. คัดลอกโปรเจกต์เข้า WSL (ครั้งแรกเท่านั้น)

ห้ามใช้ `/mnt/c/...` ตรงๆ — ช้ามาก แนะนำ copy เข้า home:
```bash
mkdir -p ~/projects
cp -r /mnt/c/Users/Lenovo/Desktop/remap/App/android_app ~/projects/pupsk
cd ~/projects/pupsk
```

### 4. Build APK ครั้งแรก

```bash
buildozer android debug
```

- ครั้งแรกใช้เวลา ~30-60 นาที (โหลด Android SDK/NDK ~5GB)
- ครั้งต่อๆ ไป ~3-5 นาที
- APK อยู่ใน `bin/pupskgarage-1.0.0-arm64-v8a_armeabi-v7a-debug.apk`

### 5. ติดตั้งบนมือถือ

วิธีง่ายสุด — `adb`:
```bash
sudo apt install -y adb
# เสียบมือถือ + เปิด USB debugging (Developer options)
adb devices
adb install bin/pupskgarage-*-debug.apk
```

หรือ copy APK ไป Windows แล้วโอนเข้ามือถือผ่าน USB / Google Drive

---

## ทางเลือก: Docker

ถ้าไม่อยาก setup WSL:
```bash
docker run --rm -v ${PWD}:/home/user/hostcwd kivy/buildozer android debug
```
(Docker Desktop for Windows ต้อง enable WSL2 backend อยู่ดี)

---

## ปัญหาที่ต้องเจอแน่ๆ

### A. Android 12+ permission popup
แอปต้องขอ `BLUETOOTH_SCAN` + `BLUETOOTH_CONNECT` ตอนรันครั้งแรก  
โค้ดขอแล้วใน `main.py:_request_android_permissions()` แต่ user ต้องกด Allow

### B. BLE ไม่ทำงาน → เช็ค:
- Location services เปิด (Android 6-11 ต้องใช้คู่กับ BLE scan)
- Bluetooth เปิด
- มือถือใกล้กล่อง Super Connext < 5m
- Android log ผ่าน adb:
  ```bash
  adb logcat | grep -E 'python|ble-android'
  ```

### C. tkinter dialogs (save / load run, pick image) ใช้ไม่ได้บน Android
ตอนนี้ทุกที่ที่เรียก tkinter wrap try/except — กดแล้วไม่มีอะไรเกิดขึ้น  
**TODO ต่อ:** เปลี่ยนเป็น Kivy-native file picker หรือ plyer.filechooser

### D. plyer.gps ต้องการ Google Play Services
บนมือถือบางรุ่นที่ไม่มี GPS API จะ fallback ไม่ได้ — cockpit จะใช้ ECU speed แทน (มี fallback อยู่แล้ว)

### E. Build crash บน Cython
ถ้า error `cython.parser.parser` → ลดเวอร์ชัน:
```bash
pip install cython==0.29.36
```

---

## เร็วๆ — Cheat sheet

```bash
# WSL Ubuntu
cd ~/projects/pupsk

# Clean build (ถ้าติดปัญหา)
buildozer android clean

# Debug build + install + log
buildozer android debug deploy run logcat | grep python
```
