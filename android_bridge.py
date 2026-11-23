"""Puente nativo Android vía pyjnius para overlay flotante y servicio en segundo plano."""

import random
from typing import Any

from kivy.utils import platform

# Mantiene referencias fuertes a los Runnables para que Python no los libere antes de ejecutarse en Java
_ACTIVE_RUNNABLES: set = set()
LAST_OVERLAY_ERROR: str = ""


def is_android() -> bool:
    return platform == "android"


def _get_context():
    from jnius import autoclass

    try:
        PythonService = autoclass("org.kivy.android.PythonService")
        if PythonService.mService is not None:
            return PythonService.mService
    except Exception:
        pass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    return PythonActivity.mActivity


def has_overlay_permission() -> bool:
    if not is_android():
        return True
    try:
        from jnius import autoclass

        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT < 23:
            return True
        Settings = autoclass("android.provider.Settings")
        ctx = _get_context()
        return bool(Settings.canDrawOverlays(ctx))
    except Exception:
        return False


def request_overlay_permission() -> None:
    if not is_android():
        return
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")

        activity = PythonActivity.mActivity
        uri = Uri.parse("package:" + activity.getPackageName())
        intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, uri)
        activity.startActivity(intent)
    except Exception:
        pass


def request_notification_permission() -> None:
    if not is_android():
        return
    try:
        from android.permissions import Permission, request_permissions
        from jnius import autoclass

        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 33:
            request_permissions([Permission.POST_NOTIFICATIONS])
    except Exception:
        pass


def start_background_service(data_dir: str) -> bool:
    if not is_android():
        return False
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        service = autoclass("org.subliminal.subliminalflash.ServiceSubliminal")
        # En python-for-android con :foreground, start() acepta 5 args (notificación persistente)
        try:
            service.start(
                activity,
                "",
                "Subliminal Flash",
                "Activo en segundo plano",
                str(data_dir),
            )
            return True
        except Exception:
            service.start(activity, str(data_dir))
            return True
    except Exception:
        return False


def request_ignore_battery_optimizations() -> None:
    if not is_android():
        return
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")

        activity = PythonActivity.mActivity
        uri = Uri.parse("package:" + activity.getPackageName())
        intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, uri)
        activity.startActivity(intent)
    except Exception:
        pass


def stop_background_service() -> bool:
    if not is_android():
        return False
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        service = autoclass("org.subliminal.subliminalflash.ServiceSubliminal")
        service.stop(activity)
        return True
    except Exception:
        return False


def _hex_to_argb_int(hex_color: str, alpha_0_255: int = 255) -> int:
    c = hex_color.lstrip("#")
    if len(c) != 6:
        r, g, b = 255, 255, 255
    else:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    val = ((alpha_0_255 & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)
    if val >= 0x80000000:
        val -= 0x100000000
    return val


def show_android_overlay(text: str, cfg: dict[str, Any]) -> bool:
    """Muestra un TextView flotante nativo sobre cualquier app sin bloquear toques."""
    global LAST_OVERLAY_ERROR
    if not is_android() or not text:
        return False
    if not has_overlay_permission():
        LAST_OVERLAY_ERROR = "Sin permiso de superposición"
        return False
    try:
        from jnius import PythonJavaClass, autoclass, cast, java_method

        Context = autoclass("android.content.Context")
        WindowManagerLayoutParams = autoclass("android.view.WindowManager$LayoutParams")
        PixelFormat = autoclass("android.graphics.PixelFormat")
        Gravity = autoclass("android.view.Gravity")
        TextView = autoclass("android.widget.TextView")
        Typeface = autoclass("android.graphics.Typeface")
        GradientDrawable = autoclass("android.graphics.drawable.GradientDrawable")
        TypedValue = autoclass("android.util.TypedValue")
        BuildVersion = autoclass("android.os.Build$VERSION")
        Handler = autoclass("android.os.Handler")
        Looper = autoclass("android.os.Looper")
        JString = autoclass("java.lang.String")

        ctx = _get_context()
        raw_wm = ctx.getSystemService(Context.WINDOW_SERVICE)
        wm = cast("android.view.WindowManager", raw_wm)
        handler = Handler(Looper.getMainLooper())

        duration_ms = max(5, int(cfg.get("duration_ms", 35)))
        font_size = int(cfg.get("font_size", 24))
        opacity = max(0.05, min(1.0, float(cfg.get("opacity", 0.85))))
        text_color = cfg.get("text_color", "#FFFFFF")
        bg_style = cfg.get("bg_style", "pill")
        position = cfg.get("position", "center")
        font_style = cfg.get("font_style", "Moderna (Sans)")

        class RemoveRunnable(PythonJavaClass):
            __javainterfaces__ = ["java/lang/Runnable"]

            def __init__(self, manager, view):
                super().__init__()
                self._wm = manager
                self._view = view

            @java_method("()V")
            def run(self):
                try:
                    self._wm.removeViewImmediate(self._view)
                except Exception:
                    try:
                        self._wm.removeView(self._view)
                    except Exception:
                        pass
                finally:
                    _ACTIVE_RUNNABLES.discard(self)

        class ShowRunnable(PythonJavaClass):
            __javainterfaces__ = ["java/lang/Runnable"]

            @java_method("()V")
            def run(self):
                global LAST_OVERLAY_ERROR
                try:
                    tv = TextView(ctx)
                    tv.setText(cast("java.lang.CharSequence", JString(text)))
                    tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, float(font_size))
                    tv.setTextColor(_hex_to_argb_int(text_color, 255))
                    tv.setGravity(Gravity.CENTER)
                    tv.setAlpha(float(opacity))

                    if font_style == "Monoespaciada":
                        tv.setTypeface(Typeface.MONOSPACE, Typeface.BOLD)
                    elif font_style == "Editorial (Serif)":
                        tv.setTypeface(Typeface.SERIF, Typeface.BOLD)
                    elif font_style == "Limpia (Bold)":
                        tv.setTypeface(Typeface.SANS_SERIF, Typeface.BOLD)
                    else:
                        tv.setTypeface(Typeface.DEFAULT_BOLD)

                    if bg_style == "pill":
                        bg = GradientDrawable()
                        bg.setColor(_hex_to_argb_int("#18181B", 230))
                        bg.setCornerRadius(36.0)
                        tv.setBackground(bg)
                        tv.setPadding(44, 24, 44, 24)
                    else:
                        tv.setPadding(24, 14, 24, 14)

                    overlay_type = (
                        WindowManagerLayoutParams.TYPE_APPLICATION_OVERLAY
                        if BuildVersion.SDK_INT >= 26
                        else WindowManagerLayoutParams.TYPE_PHONE
                    )
                    flags = (
                        WindowManagerLayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManagerLayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManagerLayoutParams.FLAG_LAYOUT_IN_SCREEN
                    )
                    params = WindowManagerLayoutParams(
                        WindowManagerLayoutParams.WRAP_CONTENT,
                        WindowManagerLayoutParams.WRAP_CONTENT,
                        overlay_type,
                        flags,
                        PixelFormat.TRANSLUCENT,
                    )

                    if position == "top":
                        params.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL
                        params.y = 180
                    elif position == "bottom":
                        params.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL
                        params.y = 220
                    elif position == "random":
                        params.gravity = Gravity.CENTER
                        params.x = random.randint(-120, 120)
                        params.y = random.randint(-360, 360)
                    else:
                        params.gravity = Gravity.CENTER

                    wm.addView(tv, params)
                    remover = RemoveRunnable(wm, tv)
                    _ACTIVE_RUNNABLES.add(remover)
                    handler.postDelayed(remover, duration_ms)
                    LAST_OVERLAY_ERROR = ""
                except Exception as exc:
                    LAST_OVERLAY_ERROR = str(exc)
                finally:
                    _ACTIVE_RUNNABLES.discard(self)

        shower = ShowRunnable()
        _ACTIVE_RUNNABLES.add(shower)
        handler.post(shower)
        return True
    except Exception as exc:
        LAST_OVERLAY_ERROR = str(exc)
        return False
