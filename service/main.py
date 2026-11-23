"""Servicio en primer plano de Android para destellos subliminales en segundo plano."""

import os
from pathlib import Path
import random
import sys
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from android_bridge import show_android_overlay
from catalog import CUSTOM_CATEGORY_KEY, get_category_messages
from config_store import get_active_session, load_config


def _configure_sticky_service() -> None:
    """Configura START_STICKY para que Android mantenga/reinicie el servicio al cerrar la UI."""
    try:
        from jnius import autoclass

        PythonService = autoclass("org.kivy.android.PythonService")
        if PythonService.mService is not None:
            PythonService.mService.setAutoRestartService(True)
    except Exception:
        pass


def _is_screen_on() -> bool:
    try:
        from jnius import autoclass, cast

        Context = autoclass("android.content.Context")
        PythonService = autoclass("org.kivy.android.PythonService")
        svc = PythonService.mService
        if svc is None:
            return True
        pm = cast("android.os.PowerManager", svc.getSystemService(Context.POWER_SERVICE))
        return bool(pm.isInteractive())
    except Exception:
        return True


def run_service() -> None:
    _configure_sticky_service()
    data_dir = os.environ.get("PYTHON_SERVICE_ARGUMENT") or None
    seq_index = 0

    while True:
        cfg = load_config(data_dir)
        if not cfg.get("enabled", True):
            time.sleep(2.0)
            continue

        if not _is_screen_on():
            time.sleep(3.0)
            continue

        active_sess = get_active_session(cfg)
        if active_sess:
            cat = active_sess.get("category", CUSTOM_CATEGORY_KEY)
            pool = (
                cfg.get("messages", [])
                if cat == CUSTOM_CATEGORY_KEY
                else get_category_messages(cat)
            )
            eff_cfg = dict(cfg)
            if active_sess.get("duration_ms") is not None:
                eff_cfg["duration_ms"] = active_sess["duration_ms"]
        elif cfg.get("sessions_only", False):
            pool = []
            eff_cfg = cfg
        else:
            pool = cfg.get("messages", [])
            eff_cfg = cfg

        if pool:
            if cfg.get("order_mode") == "sequential":
                msg = pool[seq_index % len(pool)]
                seq_index = (seq_index + 1) % len(pool)
            else:
                msg = random.choice(pool)
            show_android_overlay(msg, eff_cfg)

        min_s = float(cfg.get("interval_min_s", 5.0))
        max_s = float(cfg.get("interval_max_s", 12.0))
        wait_s = random.uniform(min_s, max(min_s, max_s))
        time.sleep(max(0.5, wait_s))


if __name__ == "__main__":
    run_service()
