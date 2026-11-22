[app]
title = Subliminal Flash
package.name = subliminalflash
package.domain = org.subliminal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = .venv,venv,.git,.github,bin,.buildozer,__pycache__
version = 1.2.0

requirements = python3,kivy==2.3.1,pyjnius

icon.filename = %(source.dir)s/assets/icon.png
orientation = portrait
fullscreen = 0

# Servicio en primer plano para destellos en segundo plano sobre otras apps
services = Subliminal:service/main.py:foreground

# Permisos Android
android.permissions = SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
