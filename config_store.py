from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any
import uuid

from catalog import CATALOG, CUSTOM_CATEGORY_KEY

MIN_DURATION_MS = 5
MAX_DURATION_MS = 5000

RECOMMENDED_FONT_STYLES = [
    "Moderna (Sans)",
    "Limpia (Bold)",
    "Monoespaciada",
    "Editorial (Serif)",
]

PRESET_COLORS = [
    ("#FFFFFF", "Blanco"),
    ("#1D1D1F", "Grafito"),
    ("#D62828", "Rojo NES"),
    ("#22C55E", "Verde"),
    ("#38BDF8", "Celeste"),
    ("#FACC15", "Amarillo"),
]

DEFAULT_CONFIG: dict[str, Any] = {
    "messages": [
        "Estoy enfocado y en calma",
        "Confío plenamente en mis capacidades",
        "Cada día avanzo con claridad",
        "Soy disciplinado y constante",
        "Atraigo oportunidades positivas",
    ],
    "duration_ms": 35,
    "interval_min_s": 5.0,
    "interval_max_s": 12.0,
    "order_mode": "random",
    "font_style": "Moderna (Sans)",
    "font_size": 24,
    "text_color": "#FFFFFF",
    "bg_style": "pill",  # "transparent" | "pill"
    "opacity": 0.85,
    "position": "center",  # "center" | "random" | "top" | "bottom"
    "enabled": True,
    "sessions_only": False,
    "sessions": [],
}


def get_config_path(data_dir: str | None = None) -> Path:
    if data_dir:
        base = Path(data_dir)
    elif os.environ.get("ANDROID_PRIVATE"):
        base = Path(os.environ["ANDROID_PRIVATE"]) / "subliminal_data"
    else:
        base = Path(__file__).resolve().parent
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config(data_dir: str | None = None) -> dict[str, Any]:
    path = get_config_path(data_dir)
    cfg = dict(DEFAULT_CONFIG)
    cfg["messages"] = list(DEFAULT_CONFIG["messages"])
    cfg["sessions"] = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            pass
    return sanitize_config(cfg)


def save_config(cfg: dict[str, Any], data_dir: str | None = None) -> dict[str, Any]:
    clean = sanitize_config(cfg)
    path = get_config_path(data_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return clean


def _parse_hhmm(value: str, fallback: str) -> str:
    try:
        parts = str(value).strip().split(":")
        if len(parts) != 2:
            return fallback
        h = int(parts[0])
        m = int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except Exception:
        pass
    return fallback


def _sanitize_session(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip() or "Sesión"
    category = str(raw.get("category", CUSTOM_CATEGORY_KEY)).strip()
    if category != CUSTOM_CATEGORY_KEY and category not in CATALOG:
        category = CUSTOM_CATEGORY_KEY

    start_time = _parse_hhmm(raw.get("start_time", "09:00"), "09:00")
    end_time = _parse_hhmm(raw.get("end_time", "12:00"), "12:00")

    days_raw = raw.get("days", [0, 1, 2, 3, 4, 5, 6])
    if not isinstance(days_raw, list):
        days_raw = [0, 1, 2, 3, 4, 5, 6]
    days = sorted({int(d) for d in days_raw if isinstance(d, (int, float)) and 0 <= int(d) <= 6})
    if not days:
        days = [0, 1, 2, 3, 4, 5, 6]

    dur_raw = raw.get("duration_ms")
    duration_ms = None
    if dur_raw is not None and str(dur_raw).strip() != "":
        try:
            duration_ms = max(MIN_DURATION_MS, min(MAX_DURATION_MS, int(dur_raw)))
        except Exception:
            duration_ms = None

    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:8]),
        "name": name,
        "category": category,
        "start_time": start_time,
        "end_time": end_time,
        "days": days,
        "duration_ms": duration_ms,
        "enabled": bool(raw.get("enabled", True)),
    }


def sanitize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    clean = dict(DEFAULT_CONFIG)
    clean.update(cfg)

    msgs = clean.get("messages")
    if not isinstance(msgs, list):
        msgs = list(DEFAULT_CONFIG["messages"])
    clean["messages"] = [str(m).strip() for m in msgs if str(m).strip()]

    try:
        clean["duration_ms"] = max(MIN_DURATION_MS, min(MAX_DURATION_MS, int(clean["duration_ms"])))
    except Exception:
        clean["duration_ms"] = DEFAULT_CONFIG["duration_ms"]

    try:
        min_s = max(0.5, min(3600.0, float(clean["interval_min_s"])))
    except Exception:
        min_s = DEFAULT_CONFIG["interval_min_s"]

    try:
        max_s = max(min_s, min(3600.0, float(clean["interval_max_s"])))
    except Exception:
        max_s = max(min_s, DEFAULT_CONFIG["interval_max_s"])

    clean["interval_min_s"] = round(min_s, 2)
    clean["interval_max_s"] = round(max_s, 2)

    if clean.get("order_mode") not in ("random", "sequential"):
        clean["order_mode"] = "random"

    if clean.get("font_style") not in RECOMMENDED_FONT_STYLES:
        clean["font_style"] = RECOMMENDED_FONT_STYLES[0]

    try:
        clean["font_size"] = max(14, min(64, int(clean["font_size"])))
    except Exception:
        clean["font_size"] = DEFAULT_CONFIG["font_size"]

    color = str(clean.get("text_color", "#FFFFFF")).strip()
    if not (color.startswith("#") and len(color) == 7):
        color = "#FFFFFF"
    clean["text_color"] = color

    if clean.get("bg_style") not in ("transparent", "pill"):
        clean["bg_style"] = "pill"

    try:
        clean["opacity"] = round(max(0.05, min(1.0, float(clean["opacity"]))), 2)
    except Exception:
        clean["opacity"] = DEFAULT_CONFIG["opacity"]

    if clean.get("position") not in ("center", "random", "top", "bottom"):
        clean["position"] = "center"

    clean["enabled"] = bool(clean.get("enabled", True))
    clean["sessions_only"] = bool(clean.get("sessions_only", False))

    sessions_raw = clean.get("sessions", [])
    sessions: list[dict[str, Any]] = []
    if isinstance(sessions_raw, list):
        for s in sessions_raw:
            parsed = _sanitize_session(s)
            if parsed is not None:
                sessions.append(parsed)
    clean["sessions"] = sessions
    return clean


def _hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def get_active_session(cfg: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    now = now or datetime.now()
    weekday = now.weekday()
    cur_min = now.hour * 60 + now.minute

    for s in cfg.get("sessions", []):
        if not s.get("enabled", True):
            continue
        days = s.get("days", [])
        start_m = _hhmm_to_minutes(s.get("start_time", "09:00"))
        end_m = _hhmm_to_minutes(s.get("end_time", "12:00"))

        if start_m <= end_m:
            if weekday in days and start_m <= cur_min < end_m:
                return s
        else:
            prev_day = (weekday - 1) % 7
            if (weekday in days and cur_min >= start_m) or (prev_day in days and cur_min < end_m):
                return s
    return None
