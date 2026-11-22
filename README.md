# Subliminal Flash — Android (Python + Kivy)

Versión móvil para Android construida en **Python + Kivy** con el mismo diseño minimalista estilo Nintendo NES, catálogo por categorías, sesiones programadas, mínimo de **5 ms** y vista previa en vivo.

## Probar la interfaz en tu PC (Windows)
```powershell
.\.venv\Scripts\python.exe main.py
```

## Cómo generar el archivo `.apk` para Android (sin instalar Linux)
Buildozer solo compila en Linux, así que este proyecto ya incluye un flujo automático en `.github/workflows/build-apk.yml`:

1. Sube esta carpeta como un nuevo repositorio en GitHub (por ejemplo `subliminal-android`).
2. En GitHub entra a la pestaña **Actions**.
3. Verás ejecutándose **Build Android APK (Kivy / Buildozer)** (la primera vez tarda ~12–15 min; las siguientes son más rápidas gracias al caché).
4. Al terminar, entra a la ejecución y descarga el archivo **`SubliminalFlash-Android-APK`** en la sección **Artifacts**.
5. Pasa el `.apk` a tu celular Android e instálalo.

## Permiso en Android
Al abrir la app por primera vez en tu celular, pulsa **Conceder** en el aviso superior para habilitar **"Mostrar sobre otras aplicaciones"** (`SYSTEM_ALERT_WINDOW`). Así los mensajes subliminales aparecerán mientras usas cualquier otra app sin bloquear tus toques.
