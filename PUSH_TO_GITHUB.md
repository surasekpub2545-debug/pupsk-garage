# Push to GitHub → Auto build APK

วิธีนี้ทำครั้งเดียว ครั้งต่อๆ ไปแค่ `git push` แล้วรอ APK ใน 30 นาที

---

## ขั้นที่ 1 — สร้าง GitHub repo

1. ไปที่ <https://github.com/new>
2. Repository name: `pupsk-garage` (หรืออะไรก็ได้)
3. **Public** หรือ **Private** ก็ได้ (Private จำกัด 2000 นาที/เดือน free — พอใช้)
4. ห้ามติ๊ก "Initialize this repository with README" — เราจะ push ของเอง
5. กด Create

GitHub จะแสดง URL เช่น `https://github.com/USERNAME/pupsk-garage.git` — เก็บไว้ใช้ขั้นที่ 3

---

## ขั้นที่ 2 — ติดตั้ง Git (ถ้ายังไม่มี)

PowerShell:
```powershell
winget install Git.Git
```
ปิดเปิด PowerShell ใหม่หลังติดตั้ง

ตั้งค่าครั้งแรก:
```powershell
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

---

## ขั้นที่ 3 — Push โค้ดขึ้น GitHub

PowerShell ใน `C:\Users\Lenovo\Desktop\remap\App\android_app`:

```powershell
cd C:\Users\Lenovo\Desktop\remap\App\android_app
git init
git branch -M main
git add .
git commit -m "Initial PUP-SK GARAGE Android build"
git remote add origin https://github.com/USERNAME/pupsk-garage.git
git push -u origin main
```

แทน `USERNAME` ด้วยชื่อ GitHub ของคุณ — ถ้าเป็น repo private ตอน push GitHub จะถามให้ login (ใช้ Personal Access Token แทน password)

---

## ขั้นที่ 4 — รอ build

1. เปิด repo บน GitHub → tab **Actions**
2. จะเห็น "Build Android APK" กำลังรัน
3. รอ ~25-40 นาที (ครั้งแรกช้าเพราะโหลด Android SDK)
4. ครั้งต่อๆ ไป ~10-15 นาที (cache ช่วย)

---

## ขั้นที่ 5 — ดาวน์โหลด APK

หลัง build สำเร็จ:
1. คลิก workflow run ที่เพิ่งเสร็จ
2. เลื่อนลงล่างสุด ส่วน **Artifacts**
3. คลิก `pupsk-garage-apk` → ดาวน์โหลด zip
4. แตก zip จะได้ไฟล์ `pupskgarage-1.0.0-arm64-v8a_armeabi-v7a-debug.apk`

ส่งไฟล์ไปมือถือผ่าน:
- USB cable
- Google Drive
- Discord/LINE/etc.

มือถือต้องอนุญาต install จาก Unknown sources

---

## ถ้า build fail

1. เปิด workflow run → ดู step ที่ ❌
2. ดู artifact `buildozer-log` (จะมีถ้า fail)
3. ส่ง error log ให้ผม → ผมจะแก้

---

## ครั้งต่อๆ ไป

แก้โค้ดในเครื่อง → push:
```powershell
git add .
git commit -m "อะไรก็ได้ที่แก้"
git push
```
GitHub Actions จะ build ใหม่อัตโนมัติ
