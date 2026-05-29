# Honda ECU Cockpit (Android / Kivy)

แอปอ่านค่า Honda ECU ผ่าน BLE box (Super Connext) บน Android และ desktop.

## โครงสร้าง

```
android_app/
├─ main.py                       Kivy app entry
├─ requirements.txt              desktop dev deps
├─ buildozer.spec                APK build config
├─ assets/
│  └─ honda_dtc_codes.csv        47 Honda DTC codes
└─ src/
   ├─ ble_client.py              bleak-based BLE (desktop)
   ├─ ble_android.py             pyjnius BLE stub (Android — TODO)
   ├─ protocol/
   │  ├─ super_connext.py        ASCII parser ($RDTC, &M..., &RDTC...)
   │  └─ honda_dtc.py            DTC lookup table loader
   ├─ widgets/
   │  ├─ theme.py                color palette
   │  ├─ tachometer.py           Kivy circular RPM gauge
   │  └─ gauge.py                Kivy bar gauge
   └─ screens/
      ├─ connect_screen.py       BLE scan + pair
      └─ cockpit_screen.py       realtime dashboard
```

## รัน desktop (development)

```cmd
cd C:\Users\Lenovo\Desktop\remap\App\android_app
pip install -r requirements.txt
python main.py
```

ต้องมี BLE adapter ในเครื่อง (Windows 10+ พอ)

## Build APK

ต้องใช้ Linux/WSL/macOS (Buildozer ไม่รองรับ Windows native):

```bash
pip install buildozer cython
cd android_app
buildozer android debug
# → bin/hondaecucockpit-1.0.0-arm64-v8a-debug.apk
```

หรือใช้ Docker:
```bash
docker run -v $(pwd):/home/user/hostcwd kivy/buildozer android debug
```

## Sprint Status

- ✅ Sprint 1: Protocol parser + BLE scan + Connect screen + basic Cockpit
- ⬜ Sprint 2: Tachometer/Gauge widgets polish, Trends, AFR Map, Dyno
- ⬜ Sprint 3: Compare runs, save/load, DTC screen, settings, theme

## Protocol cheat sheet (Super Connext)

**Commands (write to FFE1 or FFF2):**
- `$RDTC\r\n` — read DTC
- `$CDTC\r\n` — clear DTC
- `$RELAYON{pw}\r\n` — antitheft unlock

**Responses (notify on FFE1 or FFF1, LF-terminated):**
- `&M[17 × 4-hex fields][4-hex checksum]\n` — live data (76 chars)
- `&RDTC[count][CD1][CD2][CD3]\n` — DTC codes
- `&CDTCDONE` — clear success
- `&INFO...`, `&ID...` — device info

Live data fields (Honda):
1. RPM   2. SPD   3. TPS°   4. TPS_V   5. ECT°C   6. ECT_V
7. IAT°C   8. IAT_V   9. MAP_kPa   10. MAP_V   11. ISC
12. INJ_ms   13. IG°BTDC   14. BARO   15. AFR   16. TRIM   17. STATUS
