[app]
title = PUP-SK GARAGE
package.name = pupskgarage
package.domain = com.surasek.pupsk

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,csv,txt,json,ico,ttf,otf
source.include_patterns = assets/*, assets/logo/*, assets/logo/icons/*, assets/fonts/*

version = 1.0.0
requirements = python3, kivy==2.3.0, pyjnius, android, plyer, pillow, certifi

# App icon + splash
icon.filename = assets/logo/icons/icon_512.png
presplash.filename = assets/logo/logo_splash.png

orientation = landscape
fullscreen = 0

# Bluetooth + storage permissions
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, READ_EXTERNAL_STORAGE

android.api = 34
android.minapi = 26
android.ndk_api = 26
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# Auto-accept all Android SDK licenses (needed for headless CI build)
android.accept_sdk_license = True


# Pin python-for-android to a tagged release that bundles Python 3.11
# (latest p4a defaults to Python 3.14 + NDK r28c, which Kivy 2.3.0 can't
# compile against — glShaderSource signature changed in NDK 27+).
p4a.branch = v2024.01.21

log_level = 2

[buildozer]
log_level = 2
warn_on_root = 0
