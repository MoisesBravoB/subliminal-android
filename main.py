import random
import uuid

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

from android_bridge import (
    has_overlay_permission,
    is_android,
    request_notification_permission,
    request_overlay_permission,
    show_android_overlay,
    start_background_service,
    stop_background_service,
)
from catalog import CATALOG, CUSTOM_CATEGORY_KEY, get_category_messages, get_category_names
from config_store import (
    MAX_DURATION_MS,
    MIN_DURATION_MS,
    PRESET_COLORS,
    RECOMMENDED_FONT_STYLES,
    get_active_session,
    load_config,
    save_config,
)

# Nintendo NES Minimalist Gray + Red Accent Palette
C_BG_MAIN = get_color_from_hex("#E4E3DF")
C_BG_HEADER = get_color_from_hex("#262628")
C_BG_CARD = get_color_from_hex("#F4F3EF")
C_BG_INPUT = get_color_from_hex("#FFFFFF")
C_BG_TRACK = get_color_from_hex("#D5D3CC")
C_BORDER = get_color_from_hex("#C8C6BE")

C_TEXT = get_color_from_hex("#1D1D1F")
C_MUTED = get_color_from_hex("#6E6E73")
C_ON_DARK = get_color_from_hex("#F5F5F7")
C_MUTED_DARK = get_color_from_hex("#A1A1A6")

C_NES_RED = get_color_from_hex("#D62828")
C_BTN_DARK = get_color_from_hex("#363639")
C_BTN_LIGHT = get_color_from_hex("#DFDDD7")
C_LED_GREEN = get_color_from_hex("#22C55E")
C_LED_AMBER = get_color_from_hex("#F59E0B")
C_DANGER = get_color_from_hex("#B91C1C")
C_PREVIEW_BG = get_color_from_hex("#34363A")

POSITION_MAP = {
    "Centro": "center",
    "Aleatoria": "random",
    "Superior": "top",
    "Inferior": "bottom",
}
REV_POSITION_MAP = {v: k for k, v in POSITION_MAP.items()}
DAY_SHORT = ["L", "M", "X", "J", "V", "S", "D"]
MS_PRESETS = [5, 15, 35, 80, 200]


class StyledBox(BoxLayout):
    """BoxLayout con fondo redondeado y borde opcional."""

    def __init__(self, bg_color=C_BG_CARD, border_color=None, radius=8, **kwargs):
        super().__init__(**kwargs)
        self._bg_color = bg_color
        self._border_color = border_color
        self._radius = dp(radius)
        with self.canvas.before:
            self._bg_instr = Color(*self._bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
            if self._border_color is not None:
                self._bd_instr = Color(*self._border_color)
                self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius), width=1)
            else:
                self._line = None
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def set_bg_color(self, rgba):
        self._bg_instr.rgba = rgba

    def _sync_bg(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._line is not None:
            self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class FlatButton(Button):
    def __init__(self, bg_color=C_NES_RED, fg_color=C_ON_DARK, radius=6, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = fg_color
        self.bold = True
        self._bg_normal = bg_color
        self._radius = dp(radius)
        with self.canvas.before:
            self._c = Color(*bg_color)
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
        self.bind(pos=self._upd, size=self._upd, state=self._upd_state)

    def set_fill(self, rgba, fg=None):
        self._bg_normal = rgba
        self._c.rgba = rgba
        if fg is not None:
            self.color = fg

    def _upd(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size

    def _upd_state(self, *_):
        r, g, b, a = self._bg_normal
        if self.state == "down":
            self._c.rgba = (max(0, r * 0.85), max(0, g * 0.85), max(0, b * 0.85), a)
        else:
            self._c.rgba = (r, g, b, a)


def make_section_card(title: str) -> StyledBox:
    card = StyledBox(
        orientation="vertical",
        bg_color=C_BG_CARD,
        border_color=C_BORDER,
        radius=8,
        padding=[dp(14), dp(12), dp(14), dp(12)],
        spacing=dp(8),
        size_hint_y=None,
    )
    card.bind(minimum_height=card.setter("height"))

    hdr = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(20), spacing=dp(8))
    bar = StyledBox(bg_color=C_NES_RED, radius=2, size_hint=(None, None), size=(dp(3), dp(14)))
    lbl = Label(
        text=title,
        color=C_MUTED,
        font_size=sp(11),
        bold=True,
        halign="left",
        valign="middle",
    )
    lbl.bind(size=lbl.setter("text_size"))
    hdr.add_widget(bar)
    hdr.add_widget(lbl)
    card.add_widget(hdr)
    return card


class SubliminalAndroidApp(App):
    title = "Subliminal Flash"

    def build(self):
        if not is_android():
            Window.size = (420, 800)
        Window.clearcolor = C_BG_MAIN

        self.cfg = load_config(self.user_data_dir)
        self._seq_index = 0
        self._selected_catalog = get_category_names()[0]
        self._desktop_flash_ev = None
        self._desktop_hide_ev = None
        self._active_tab = 0

        self.root_float = FloatLayout()
        main_col = BoxLayout(orientation="vertical")
        self.root_float.add_widget(main_col)

        # 1. NES Charcoal Header + Red Stripe
        self._build_header(main_col)

        # 2. Android Permission Notice (if needed)
        self.perm_banner = StyledBox(
            orientation="horizontal",
            bg_color=get_color_from_hex("#FEF2F2"),
            border_color=C_NES_RED,
            radius=6,
            padding=[dp(12), dp(8)],
            spacing=dp(8),
            size_hint_y=None,
            height=dp(0),
        )
        self.perm_banner.opacity = 0
        perm_lbl = Label(
            text="Permiso requerido: Mostrar sobre otras apps",
            color=C_DANGER,
            font_size=sp(11),
            bold=True,
            halign="left",
            valign="middle",
        )
        perm_lbl.bind(size=perm_lbl.setter("text_size"))
        perm_btn = FlatButton(
            text="Conceder",
            bg_color=C_NES_RED,
            fg_color=C_ON_DARK,
            font_size=sp(11),
            size_hint=(None, None),
            size=(dp(88), dp(32)),
        )
        perm_btn.bind(on_release=lambda *_: request_overlay_permission())
        self.perm_banner.add_widget(perm_lbl)
        self.perm_banner.add_widget(perm_btn)
        main_col.add_widget(self.perm_banner)

        # 3. Segmented Navigation Bar
        self._build_segmented_nav(main_col)

        # 4. Content Container (Scrollable per tab)
        self.tab_container = BoxLayout(orientation="vertical")
        main_col.add_widget(self.tab_container)

        self.tabs = [
            self._build_home_tab(),
            self._build_catalog_tab(),
            self._build_sessions_tab(),
        ]
        self._select_tab(0)

        # 5. In-app flash overlay (for desktop testing & immediate preview)
        self.flash_holder = StyledBox(
            bg_color=(0.09, 0.09, 0.11, 0.9),
            radius=16,
            padding=[dp(22), dp(12)],
            size_hint=(None, None),
            size=(dp(280), dp(64)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.flash_holder.opacity = 0
        self.flash_label = Label(
            text="",
            color=C_ON_DARK,
            font_size=sp(22),
            bold=True,
            halign="center",
            valign="middle",
        )
        self.flash_label.bind(size=self.flash_label.setter("text_size"))
        self.flash_holder.add_widget(self.flash_label)
        self.root_float.add_widget(self.flash_holder)

        # Sync UI & Start services
        self._refresh_all()
        if is_android():
            request_notification_permission()
            Clock.schedule_interval(lambda dt: self._check_android_permission(), 2.0)
            if self.cfg.get("enabled", True) and has_overlay_permission():
                start_background_service(self.user_data_dir)
        else:
            self._schedule_desktop_flash()

        Clock.schedule_interval(lambda dt: self._update_status_badge(), 10.0)
        return self.root_float

    # =========================================================================
    # HEADER & NAVIGATION
    # =========================================================================
    def _build_header(self, parent: BoxLayout) -> None:
        hdr_wrap = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(78))
        bar = StyledBox(
            orientation="horizontal",
            bg_color=C_BG_HEADER,
            radius=0,
            padding=[dp(14), dp(10), dp(14), dp(10)],
            spacing=dp(8),
            size_hint_y=None,
            height=dp(75),
        )
        left = BoxLayout(orientation="vertical", spacing=dp(2))
        title_lbl = Label(
            text="Subliminal Flash",
            color=C_ON_DARK,
            font_size=sp(17),
            bold=True,
            halign="left",
            valign="bottom",
        )
        title_lbl.bind(size=title_lbl.setter("text_size"))
        self.status_lbl = Label(
            text="● ACTIVO",
            color=C_LED_GREEN,
            font_size=sp(10),
            bold=True,
            halign="left",
            valign="top",
        )
        self.status_lbl.bind(size=self.status_lbl.setter("text_size"))
        left.add_widget(title_lbl)
        left.add_widget(self.status_lbl)

        btns = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_x=None, width=dp(166))
        self.btn_toggle = FlatButton(text="Pausar", bg_color=C_NES_RED, fg_color=C_ON_DARK, font_size=sp(12))
        self.btn_toggle.bind(on_release=lambda *_: self.toggle_enabled())
        btn_test = FlatButton(text="Probar", bg_color=C_BTN_DARK, fg_color=C_ON_DARK, font_size=sp(12))
        btn_test.bind(on_release=lambda *_: self.test_flash())
        btns.add_widget(self.btn_toggle)
        btns.add_widget(btn_test)

        bar.add_widget(left)
        bar.add_widget(btns)

        red_stripe = StyledBox(bg_color=C_NES_RED, radius=0, size_hint_y=None, height=dp(3))
        hdr_wrap.add_widget(bar)
        hdr_wrap.add_widget(red_stripe)
        parent.add_widget(hdr_wrap)

    def _build_segmented_nav(self, parent: BoxLayout) -> None:
        nav_wrap = BoxLayout(padding=[dp(12), dp(10), dp(12), dp(6)], size_hint_y=None, height=dp(56))
        track = StyledBox(
            orientation="horizontal",
            bg_color=C_BG_TRACK,
            border_color=C_BORDER,
            radius=8,
            padding=dp(4),
            spacing=dp(4),
        )
        self.nav_buttons = []
        for idx, text in enumerate(("Inicio", "Catálogo", "Sesiones")):
            b = FlatButton(text=text, bg_color=C_BG_TRACK, fg_color=C_MUTED, font_size=sp(12), radius=6)
            b.bind(on_release=lambda _, i=idx: self._select_tab(i))
            track.add_widget(b)
            self.nav_buttons.append(b)
        nav_wrap.add_widget(track)
        parent.add_widget(nav_wrap)

    def _select_tab(self, index: int) -> None:
        self._active_tab = index
        self.tab_container.clear_widgets()
        self.tab_container.add_widget(self.tabs[index])
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.set_fill(C_BG_INPUT, C_TEXT)
            else:
                btn.set_fill(C_BG_TRACK, C_MUTED)

    # =========================================================================
    # TAB 1: INICIO Y MENSAJES
    # =========================================================================
    def _build_home_tab(self) -> ScrollView:
        sv = ScrollView(do_scroll_x=False)
        col = BoxLayout(
            orientation="vertical",
            padding=[dp(12), dp(6), dp(12), dp(18)],
            spacing=dp(10),
            size_hint_y=None,
        )
        col.bind(minimum_height=col.setter("height"))

        # --- Card 1: Vista previa en vivo ---
        prev_card = make_section_card("VISTA PREVIA EN VIVO")
        self.preview_box = StyledBox(
            bg_color=C_PREVIEW_BG,
            border_color=C_BORDER,
            radius=8,
            padding=dp(12),
            size_hint_y=None,
            height=dp(84),
        )
        self.preview_pill = StyledBox(
            bg_color=(0.09, 0.09, 0.11, 0.9),
            radius=14,
            padding=[dp(16), dp(8)],
        )
        self.preview_lbl = Label(
            text="Estoy enfocado y en calma",
            color=C_ON_DARK,
            font_size=sp(18),
            bold=True,
            halign="center",
            valign="middle",
        )
        self.preview_lbl.bind(size=self.preview_lbl.setter("text_size"))
        self.preview_pill.add_widget(self.preview_lbl)
        self.preview_box.add_widget(self.preview_pill)
        prev_card.add_widget(self.preview_box)
        col.add_widget(prev_card)

        # --- Card 2: Temporización (desde 5 ms) ---
        time_card = make_section_card("TEMPORIZACIÓN")
        dur_row = BoxLayout(size_hint_y=None, height=dp(24))
        self.dur_val_lbl = Label(
            text="Duración: 35 ms",
            color=C_TEXT,
            font_size=sp(13),
            bold=True,
            halign="left",
            valign="middle",
        )
        self.dur_val_lbl.bind(size=self.dur_val_lbl.setter("text_size"))
        self.dur_hint_lbl = Label(
            text="Subliminal",
            color=C_NES_RED,
            font_size=sp(11),
            bold=True,
            halign="right",
            valign="middle",
        )
        self.dur_hint_lbl.bind(size=self.dur_hint_lbl.setter("text_size"))
        dur_row.add_widget(self.dur_val_lbl)
        dur_row.add_widget(self.dur_hint_lbl)
        time_card.add_widget(dur_row)

        self.dur_slider = Slider(
            min=MIN_DURATION_MS,
            max=500,
            value=self.cfg["duration_ms"],
            step=1,
            size_hint_y=None,
            height=dp(34),
        )
        self.dur_slider.bind(value=self._on_dur_slider)
        time_card.add_widget(self.dur_slider)

        presets_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(32))
        for ms in MS_PRESETS:
            b = FlatButton(text=f"{ms} ms", bg_color=C_BTN_LIGHT, fg_color=C_TEXT, font_size=sp(11))
            b.bind(on_release=lambda _, v=ms: self._set_duration_ms(v))
            presets_row.add_widget(b)
        time_card.add_widget(presets_row)

        int_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(36))
        int_row.add_widget(Label(text="Intervalo (seg):", color=C_MUTED, font_size=sp(12), size_hint_x=None, width=dp(96)))
        self.min_s_input = TextInput(
            text=str(self.cfg["interval_min_s"]),
            multiline=False,
            input_filter="float",
            background_color=C_BG_INPUT,
            foreground_color=C_TEXT,
            font_size=sp(13),
        )
        self.min_s_input.bind(on_text_validate=lambda *_: self._save_intervals(), focus=lambda inst, val: None if val else self._save_intervals())
        self.max_s_input = TextInput(
            text=str(self.cfg["interval_max_s"]),
            multiline=False,
            input_filter="float",
            background_color=C_BG_INPUT,
            foreground_color=C_TEXT,
            font_size=sp(13),
        )
        self.max_s_input.bind(on_text_validate=lambda *_: self._save_intervals(), focus=lambda inst, val: None if val else self._save_intervals())
        int_row.add_widget(self.min_s_input)
        int_row.add_widget(Label(text="a", color=C_MUTED, font_size=sp(12), size_hint_x=None, width=dp(16)))
        int_row.add_widget(self.max_s_input)
        time_card.add_widget(int_row)
        col.add_widget(time_card)

        # --- Card 3: Apariencia y Fuentes ---
        app_card = make_section_card("APARIENCIA Y FUENTE")

        row_fp = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(38))
        self.font_spinner = Spinner(
            text=self.cfg["font_style"],
            values=RECOMMENDED_FONT_STYLES,
            background_normal="",
            background_color=C_BTN_LIGHT,
            color=C_TEXT,
            font_size=sp(12),
        )
        self.font_spinner.bind(text=lambda _, v: self._update_cfg("font_style", v))

        self.pos_spinner = Spinner(
            text=REV_POSITION_MAP.get(self.cfg["position"], "Centro"),
            values=list(POSITION_MAP.keys()),
            background_normal="",
            background_color=C_BTN_LIGHT,
            color=C_TEXT,
            font_size=sp(12),
            size_hint_x=0.65,
        )
        self.pos_spinner.bind(text=lambda _, v: self._update_cfg("position", POSITION_MAP.get(v, "center")))
        row_fp.add_widget(self.font_spinner)
        row_fp.add_widget(self.pos_spinner)
        app_card.add_widget(row_fp)

        # Tamaño & Opacidad
        self.size_lbl = Label(
            text=f"Tamaño: {self.cfg['font_size']} sp",
            color=C_MUTED,
            font_size=sp(11),
            size_hint_y=None,
            height=dp(18),
            halign="left",
        )
        self.size_lbl.bind(size=self.size_lbl.setter("text_size"))
        app_card.add_widget(self.size_lbl)
        self.size_slider = Slider(min=14, max=48, value=self.cfg["font_size"], step=1, size_hint_y=None, height=dp(30))
        self.size_slider.bind(value=self._on_size_slider)
        app_card.add_widget(self.size_slider)

        self.op_lbl = Label(
            text=f"Opacidad: {int(self.cfg['opacity'] * 100)}%",
            color=C_MUTED,
            font_size=sp(11),
            size_hint_y=None,
            height=dp(18),
            halign="left",
        )
        self.op_lbl.bind(size=self.op_lbl.setter("text_size"))
        app_card.add_widget(self.op_lbl)
        self.op_slider = Slider(min=10, max=100, value=int(self.cfg["opacity"] * 100), step=5, size_hint_y=None, height=dp(30))
        self.op_slider.bind(value=self._on_op_slider)
        app_card.add_widget(self.op_slider)

        # Color swatches
        color_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(32))
        for hex_c, _ in PRESET_COLORS:
            b = FlatButton(text="", bg_color=get_color_from_hex(hex_c), radius=14)
            b.bind(on_release=lambda _, c=hex_c: self._update_cfg("text_color", c))
            color_row.add_widget(b)
        app_card.add_widget(color_row)

        # Background style
        bg_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(34))
        self.btn_bg_trans = FlatButton(text="Sin fondo", bg_color=C_BTN_LIGHT, fg_color=C_TEXT, font_size=sp(12))
        self.btn_bg_trans.bind(on_release=lambda *_: self._update_cfg("bg_style", "transparent"))
        self.btn_bg_pill = FlatButton(text="Cápsula oscura", bg_color=C_BG_HEADER, fg_color=C_ON_DARK, font_size=sp(12))
        self.btn_bg_pill.bind(on_release=lambda *_: self._update_cfg("bg_style", "pill"))
        bg_row.add_widget(self.btn_bg_trans)
        bg_row.add_widget(self.btn_bg_pill)
        app_card.add_widget(bg_row)
        col.add_widget(app_card)

        # --- Card 4: Mis mensajes ---
        msg_card = make_section_card("MIS MENSAJES")
        add_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(38))
        self.new_msg_input = TextInput(
            hint_text="Escribe un mensaje subliminal...",
            multiline=False,
            background_color=C_BG_INPUT,
            foreground_color=C_TEXT,
            font_size=sp(13),
        )
        self.new_msg_input.bind(on_text_validate=lambda *_: self.add_message())
        add_btn = FlatButton(text="Agregar", bg_color=C_NES_RED, fg_color=C_ON_DARK, font_size=sp(12), size_hint_x=None, width=dp(84))
        add_btn.bind(on_release=lambda *_: self.add_message())
        add_row.add_widget(self.new_msg_input)
        add_row.add_widget(add_btn)
        msg_card.add_widget(add_row)

        order_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(32))
        self.btn_ord_rand = FlatButton(text="Aleatorio", bg_color=C_BG_HEADER, fg_color=C_ON_DARK, font_size=sp(11))
        self.btn_ord_rand.bind(on_release=lambda *_: self._update_cfg("order_mode", "random"))
        self.btn_ord_seq = FlatButton(text="Secuencial", bg_color=C_BTN_LIGHT, fg_color=C_TEXT, font_size=sp(11))
        self.btn_ord_seq.bind(on_release=lambda *_: self._update_cfg("order_mode", "sequential"))
        order_row.add_widget(self.btn_ord_rand)
        order_row.add_widget(self.btn_ord_seq)
        msg_card.add_widget(order_row)

        self.msg_list_col = BoxLayout(orientation="vertical", spacing=dp(5), size_hint_y=None)
        self.msg_list_col.bind(minimum_height=self.msg_list_col.setter("height"))
        msg_card.add_widget(self.msg_list_col)
        col.add_widget(msg_card)

        sv.add_widget(col)
        return sv

    # =========================================================================
    # TAB 2: CATÁLOGO POR CATEGORÍAS
    # =========================================================================
    def _build_catalog_tab(self) -> ScrollView:
        sv = ScrollView(do_scroll_x=False)
        col = BoxLayout(
            orientation="vertical",
            padding=[dp(12), dp(6), dp(12), dp(18)],
            spacing=dp(10),
            size_hint_y=None,
        )
        col.bind(minimum_height=col.setter("height"))

        cat_card = make_section_card("CATEGORÍAS")
        cat_grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        cat_grid.bind(minimum_height=cat_grid.setter("height"))
        self.cat_buttons = {}
        for name in get_category_names():
            b = FlatButton(
                text=name,
                bg_color=C_BTN_LIGHT,
                fg_color=C_TEXT,
                font_size=sp(11),
                size_hint_y=None,
                height=dp(38),
            )
            b.bind(on_release=lambda _, n=name: self._select_catalog(n))
            cat_grid.add_widget(b)
            self.cat_buttons[name] = b
        cat_card.add_widget(cat_grid)
        col.add_widget(cat_card)

        prev_card = make_section_card("MENSAJES DE LA CATEGORÍA")
        self.cat_preview_col = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        self.cat_preview_col.bind(minimum_height=self.cat_preview_col.setter("height"))
        prev_card.add_widget(self.cat_preview_col)

        acts = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(38))
        b_add = FlatButton(text="Agregar todos", bg_color=C_NES_RED, fg_color=C_ON_DARK, font_size=sp(11))
        b_add.bind(on_release=lambda *_: self._add_catalog_all())
        b_rep = FlatButton(text="Reemplazar", bg_color=C_BTN_DARK, fg_color=C_ON_DARK, font_size=sp(11))
        b_rep.bind(on_release=lambda *_: self._replace_with_catalog())
        b_ses = FlatButton(text="Programar →", bg_color=C_BTN_LIGHT, fg_color=C_TEXT, font_size=sp(11))
        b_ses.bind(on_release=lambda *_: self._send_catalog_to_session())
        acts.add_widget(b_add)
        acts.add_widget(b_rep)
        acts.add_widget(b_ses)
        prev_card.add_widget(acts)
        col.add_widget(prev_card)

        sv.add_widget(col)
        return sv

    # =========================================================================
    # TAB 3: SESIONES PROGRAMADAS
    # =========================================================================
    def _build_sessions_tab(self) -> ScrollView:
        sv = ScrollView(do_scroll_x=False)
        col = BoxLayout(
            orientation="vertical",
            padding=[dp(12), dp(6), dp(12), dp(18)],
            spacing=dp(10),
            size_hint_y=None,
        )
        col.bind(minimum_height=col.setter("height"))

        list_card = make_section_card("SESIONES PROGRAMADAS")
        self.btn_sess_only = FlatButton(
            text="Modo: Destellos siempre activos",
            bg_color=C_BTN_LIGHT,
            fg_color=C_TEXT,
            font_size=sp(11),
            size_hint_y=None,
            height=dp(34),
        )
        self.btn_sess_only.bind(on_release=lambda *_: self._toggle_sessions_only())
        list_card.add_widget(self.btn_sess_only)

        self.sessions_col = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        self.sessions_col.bind(minimum_height=self.sessions_col.setter("height"))
        list_card.add_widget(self.sessions_col)
        col.add_widget(list_card)

        # Form card
        form = make_section_card("NUEVA SESIÓN")
        self.sess_name_in = TextInput(
            text="Sesión de enfoque",
            hint_text="Nombre de la sesión",
            multiline=False,
            size_hint_y=None,
            height=dp(38),
            background_color=C_BG_INPUT,
            foreground_color=C_TEXT,
            font_size=sp(13),
        )
        form.add_widget(self.sess_name_in)

        self.sess_cat_spinner = Spinner(
            text=get_category_names()[0],
            values=get_category_names() + [CUSTOM_CATEGORY_KEY],
            background_normal="",
            background_color=C_BTN_LIGHT,
            color=C_TEXT,
            font_size=sp(12),
            size_hint_y=None,
            height=dp(38),
        )
        form.add_widget(self.sess_cat_spinner)

        hours_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(38))
        self.sess_start_in = TextInput(text="09:00", hint_text="Inicio", multiline=False, background_color=C_BG_INPUT, foreground_color=C_TEXT)
        self.sess_end_in = TextInput(text="12:00", hint_text="Fin", multiline=False, background_color=C_BG_INPUT, foreground_color=C_TEXT)
        self.sess_ms_in = TextInput(text="", hint_text="ms (opc)", multiline=False, input_filter="int", background_color=C_BG_INPUT, foreground_color=C_TEXT)
        hours_row.add_widget(self.sess_start_in)
        hours_row.add_widget(self.sess_end_in)
        hours_row.add_widget(self.sess_ms_in)
        form.add_widget(hours_row)

        days_row = BoxLayout(spacing=dp(4), size_hint_y=None, height=dp(34))
        self._sess_days_state = [True] * 7
        self._day_btns = []
        for idx, d in enumerate(DAY_SHORT):
            b = FlatButton(text=d, bg_color=C_BG_HEADER, fg_color=C_ON_DARK, font_size=sp(11))
            b.bind(on_release=lambda _, i=idx: self._toggle_day_btn(i))
            days_row.add_widget(b)
            self._day_btns.append(b)
        form.add_widget(days_row)

        save_btn = FlatButton(
            text="Guardar sesión",
            bg_color=C_NES_RED,
            fg_color=C_ON_DARK,
            font_size=sp(13),
            size_hint_y=None,
            height=dp(40),
        )
        save_btn.bind(on_release=lambda *_: self.add_session())
        form.add_widget(save_btn)
        col.add_widget(form)

        sv.add_widget(col)
        return sv

    # =========================================================================
    # STATE & HANDLERS
    # =========================================================================
    def _save(self) -> None:
        self.cfg = save_config(self.cfg, self.user_data_dir)
        self._update_status_badge()
        self._update_preview()
        if not is_android():
            self._schedule_desktop_flash()

    def _update_cfg(self, key: str, value) -> None:
        self.cfg[key] = value
        self._save()
        self._sync_toggle_buttons()

    def _set_duration_ms(self, ms: int) -> None:
        ms = max(MIN_DURATION_MS, min(MAX_DURATION_MS, int(ms)))
        self.dur_slider.value = min(500, ms)
        self.cfg["duration_ms"] = ms
        self._update_duration_labels(ms)
        self._save()

    def _on_dur_slider(self, _, val: float) -> None:
        ms = max(MIN_DURATION_MS, int(round(val)))
        self.cfg["duration_ms"] = ms
        self._update_duration_labels(ms)
        self._save()

    def _update_duration_labels(self, ms: int) -> None:
        self.dur_val_lbl.text = f"Duración: {ms} ms"
        if ms <= 20:
            self.dur_hint_lbl.text = "Subliminal puro"
            self.dur_hint_lbl.color = C_NES_RED
        elif ms <= 50:
            self.dur_hint_lbl.text = "Subliminal"
            self.dur_hint_lbl.color = get_color_from_hex("#15803D")
        elif ms <= 150:
            self.dur_hint_lbl.text = "Rápido"
            self.dur_hint_lbl.color = get_color_from_hex("#B45309")
        else:
            self.dur_hint_lbl.text = "Visible"
            self.dur_hint_lbl.color = C_MUTED

    def _save_intervals(self) -> None:
        try:
            self.cfg["interval_min_s"] = float(self.min_s_input.text)
        except ValueError:
            pass
        try:
            self.cfg["interval_max_s"] = float(self.max_s_input.text)
        except ValueError:
            pass
        self._save()
        self.min_s_input.text = str(self.cfg["interval_min_s"])
        self.max_s_input.text = str(self.cfg["interval_max_s"])

    def _on_size_slider(self, _, val: float) -> None:
        sz = int(round(val))
        self.size_lbl.text = f"Tamaño: {sz} sp"
        self.cfg["font_size"] = sz
        self._save()

    def _on_op_slider(self, _, val: float) -> None:
        pct = int(round(val))
        self.op_lbl.text = f"Opacidad: {pct}%"
        self.cfg["opacity"] = round(pct / 100.0, 2)
        self._save()

    def _sync_toggle_buttons(self) -> None:
        if self.cfg.get("bg_style") == "pill":
            self.btn_bg_pill.set_fill(C_BG_HEADER, C_ON_DARK)
            self.btn_bg_trans.set_fill(C_BTN_LIGHT, C_TEXT)
        else:
            self.btn_bg_trans.set_fill(C_BG_HEADER, C_ON_DARK)
            self.btn_bg_pill.set_fill(C_BTN_LIGHT, C_TEXT)

        if self.cfg.get("order_mode") == "random":
            self.btn_ord_rand.set_fill(C_BG_HEADER, C_ON_DARK)
            self.btn_ord_seq.set_fill(C_BTN_LIGHT, C_TEXT)
        else:
            self.btn_ord_seq.set_fill(C_BG_HEADER, C_ON_DARK)
            self.btn_ord_rand.set_fill(C_BTN_LIGHT, C_TEXT)

        if self.cfg.get("sessions_only"):
            self.btn_sess_only.text = "Modo: Solo durante sesiones programadas"
            self.btn_sess_only.set_fill(C_BG_HEADER, C_ON_DARK)
        else:
            self.btn_sess_only.text = "Modo: Destellos siempre activos"
            self.btn_sess_only.set_fill(C_BTN_LIGHT, C_TEXT)

    def _update_preview(self) -> None:
        msgs = self.cfg.get("messages", [])
        sample = msgs[0] if msgs else "Estoy enfocado y en calma"
        self.preview_lbl.text = sample
        self.preview_lbl.color = get_color_from_hex(self.cfg.get("text_color", "#FFFFFF"))
        self.preview_lbl.font_size = sp(min(26, max(13, int(self.cfg.get("font_size", 24) * 0.85))))
        self.preview_pill.opacity = float(self.cfg.get("opacity", 0.85))
        if self.cfg.get("bg_style") == "pill":
            self.preview_pill.set_bg_color((0.09, 0.09, 0.11, 0.90))
        else:
            self.preview_pill.set_bg_color((0, 0, 0, 0))

    def _update_status_badge(self) -> None:
        if not self.cfg.get("enabled", True):
            self.status_lbl.text = "● PAUSADO"
            self.status_lbl.color = C_LED_AMBER
            self.btn_toggle.text = "Activar"
            return

        self.btn_toggle.text = "Pausar"
        sess = get_active_session(self.cfg)
        if sess:
            ms_v = sess.get("duration_ms") or self.cfg.get("duration_ms", 35)
            self.status_lbl.text = f"● SESIÓN: {sess['name'].upper()} ({ms_v} ms)"
            self.status_lbl.color = C_NES_RED
        elif self.cfg.get("sessions_only"):
            self.status_lbl.text = "● ESPERANDO SESIÓN"
            self.status_lbl.color = C_MUTED_DARK
        else:
            self.status_lbl.text = "● ACTIVO"
            self.status_lbl.color = C_LED_GREEN

    def _check_android_permission(self) -> None:
        if not is_android():
            return
        if has_overlay_permission():
            self.perm_banner.height = dp(0)
            self.perm_banner.opacity = 0
        else:
            self.perm_banner.height = dp(48)
            self.perm_banner.opacity = 1

    def _refresh_all(self) -> None:
        self._update_duration_labels(self.cfg["duration_ms"])
        self._sync_toggle_buttons()
        self._refresh_messages_ui()
        self._select_catalog(self._selected_catalog)
        self._refresh_sessions_ui()
        self._update_preview()
        self._update_status_badge()

    # --- Messages ---
    def _refresh_messages_ui(self) -> None:
        self.msg_list_col.clear_widgets()
        for idx, msg in enumerate(self.cfg.get("messages", [])):
            row = StyledBox(
                bg_color=C_BG_INPUT,
                border_color=C_BORDER,
                radius=6,
                padding=[dp(10), dp(6)],
                spacing=dp(6),
                size_hint_y=None,
                height=dp(38),
            )
            lbl = Label(text=msg, color=C_TEXT, font_size=sp(12), halign="left", valign="middle")
            lbl.bind(size=lbl.setter("text_size"))
            del_btn = FlatButton(
                text="×",
                bg_color=C_BTN_LIGHT,
                fg_color=C_DANGER,
                font_size=sp(14),
                size_hint=(None, None),
                size=(dp(28), dp(26)),
            )
            del_btn.bind(on_release=lambda _, i=idx: self.delete_message(i))
            row.add_widget(lbl)
            row.add_widget(del_btn)
            self.msg_list_col.add_widget(row)

    def add_message(self) -> None:
        text = self.new_msg_input.text.strip()
        if not text:
            return
        self.cfg.setdefault("messages", []).append(text)
        self.new_msg_input.text = ""
        self._save()
        self._refresh_messages_ui()

    def delete_message(self, idx: int) -> None:
        msgs = self.cfg.get("messages", [])
        if 0 <= idx < len(msgs):
            del msgs[idx]
            self._save()
            self._refresh_messages_ui()

    # --- Catalog ---
    def _select_catalog(self, name: str) -> None:
        self._selected_catalog = name
        for n, b in self.cat_buttons.items():
            if n == name:
                b.set_fill(C_BG_HEADER, C_ON_DARK)
            else:
                b.set_fill(C_BTN_LIGHT, C_TEXT)
        self.cat_preview_col.clear_widgets()
        for msg in get_category_messages(name):
            lbl = Label(
                text=f"• {msg}",
                color=C_TEXT,
                font_size=sp(12),
                size_hint_y=None,
                height=dp(24),
                halign="left",
                valign="middle",
            )
            lbl.bind(size=lbl.setter("text_size"))
            self.cat_preview_col.add_widget(lbl)

    def _add_catalog_all(self) -> None:
        existing = set(self.cfg.get("messages", []))
        for m in get_category_messages(self._selected_catalog):
            if m not in existing:
                self.cfg["messages"].append(m)
                existing.add(m)
        self._save()
        self._refresh_messages_ui()
        self._select_tab(0)

    def _replace_with_catalog(self) -> None:
        self.cfg["messages"] = get_category_messages(self._selected_catalog)
        self._save()
        self._refresh_messages_ui()
        self._select_tab(0)

    def _send_catalog_to_session(self) -> None:
        self.sess_cat_spinner.text = self._selected_catalog
        self.sess_name_in.text = f"Sesión: {self._selected_catalog.split()[0]}"
        self._select_tab(2)

    # --- Sessions ---
    def _toggle_day_btn(self, idx: int) -> None:
        self._sess_days_state[idx] = not self._sess_days_state[idx]
        if self._sess_days_state[idx]:
            self._day_btns[idx].set_fill(C_BG_HEADER, C_ON_DARK)
        else:
            self._day_btns[idx].set_fill(C_BTN_LIGHT, C_MUTED)

    def _toggle_sessions_only(self) -> None:
        self.cfg["sessions_only"] = not self.cfg.get("sessions_only", False)
        self._save()
        self._sync_toggle_buttons()

    def _refresh_sessions_ui(self) -> None:
        self.sessions_col.clear_widgets()
        if not self.cfg.get("sessions"):
            lbl = Label(text="Sin sesiones programadas aún.", color=C_MUTED, font_size=sp(12), size_hint_y=None, height=dp(26))
            self.sessions_col.add_widget(lbl)
            return
        for s in self.cfg["sessions"]:
            row = StyledBox(
                bg_color=C_BG_INPUT,
                border_color=C_BORDER,
                radius=6,
                padding=[dp(10), dp(6)],
                spacing=dp(6),
                size_hint_y=None,
                height=dp(52),
            )
            days_txt = "".join(DAY_SHORT[d] for d in s.get("days", []))
            ms_txt = f"{s['duration_ms']}ms" if s.get("duration_ms") else "global"
            info = Label(
                text=f"[b]{s['name']}[/b] ({s['start_time']}-{s['end_time']})\n{s['category']} • {days_txt} • {ms_txt}",
                markup=True,
                color=C_TEXT if s.get("enabled", True) else C_MUTED,
                font_size=sp(11),
                halign="left",
                valign="middle",
            )
            info.bind(size=info.setter("text_size"))
            tog = FlatButton(
                text="ON" if s.get("enabled", True) else "OFF",
                bg_color=C_LED_GREEN if s.get("enabled", True) else C_BTN_LIGHT,
                fg_color=C_ON_DARK if s.get("enabled", True) else C_MUTED,
                font_size=sp(10),
                size_hint=(None, None),
                size=(dp(44), dp(30)),
            )
            tog.bind(on_release=lambda _, sid=s["id"]: self.toggle_session(sid))
            rm = FlatButton(
                text="×",
                bg_color=C_BTN_LIGHT,
                fg_color=C_DANGER,
                font_size=sp(14),
                size_hint=(None, None),
                size=(dp(30), dp(30)),
            )
            rm.bind(on_release=lambda _, sid=s["id"]: self.delete_session(sid))
            row.add_widget(info)
            row.add_widget(tog)
            row.add_widget(rm)
            self.sessions_col.add_widget(row)

    def add_session(self) -> None:
        days = [i for i, active in enumerate(self._sess_days_state) if active]
        if not days:
            return
        dur_ms = None
        raw_ms = self.sess_ms_in.text.strip()
        if raw_ms.isdigit():
            dur_ms = max(MIN_DURATION_MS, min(MAX_DURATION_MS, int(raw_ms)))
        self.cfg.setdefault("sessions", []).append(
            {
                "id": uuid.uuid4().hex[:8],
                "name": self.sess_name_in.text.strip() or "Sesión",
                "category": self.sess_cat_spinner.text,
                "start_time": self.sess_start_in.text.strip() or "09:00",
                "end_time": self.sess_end_in.text.strip() or "12:00",
                "days": days,
                "duration_ms": dur_ms,
                "enabled": True,
            }
        )
        self._save()
        self._refresh_sessions_ui()

    def toggle_session(self, sid: str) -> None:
        for s in self.cfg.get("sessions", []):
            if s["id"] == sid:
                s["enabled"] = not s.get("enabled", True)
                break
        self._save()
        self._refresh_sessions_ui()

    def delete_session(self, sid: str) -> None:
        self.cfg["sessions"] = [s for s in self.cfg.get("sessions", []) if s["id"] != sid]
        self._save()
        self._refresh_sessions_ui()

    # =========================================================================
    # FLASHING & SERVICE CONTROL
    # =========================================================================
    def toggle_enabled(self) -> None:
        self.cfg["enabled"] = not self.cfg.get("enabled", True)
        self._save()
        if is_android():
            if self.cfg["enabled"]:
                start_background_service(self.user_data_dir)
            else:
                stop_background_service()

    def _get_effective_pool_and_cfg(self):
        sess = get_active_session(self.cfg)
        if sess:
            cat = sess.get("category", CUSTOM_CATEGORY_KEY)
            pool = self.cfg.get("messages", []) if cat == CUSTOM_CATEGORY_KEY else get_category_messages(cat)
            eff = dict(self.cfg)
            if sess.get("duration_ms") is not None:
                eff["duration_ms"] = sess["duration_ms"]
            return pool, eff
        if self.cfg.get("sessions_only"):
            return [], self.cfg
        return self.cfg.get("messages", []), self.cfg

    def _pick_msg(self, pool):
        if not pool:
            return None
        if self.cfg.get("order_mode") == "sequential":
            m = pool[self._seq_index % len(pool)]
            self._seq_index = (self._seq_index + 1) % len(pool)
            return m
        return random.choice(pool)

    def test_flash(self) -> None:
        pool, eff = self._get_effective_pool_and_cfg()
        msg = self._pick_msg(pool) or self._pick_msg(self.cfg.get("messages", [])) or "Mensaje de prueba"
        if is_android() and has_overlay_permission():
            show_android_overlay(msg, eff)
        else:
            self._show_inapp_flash(msg, eff)

    def _show_inapp_flash(self, text: str, cfg: dict) -> None:
        if self._desktop_hide_ev is not None:
            self._desktop_hide_ev.cancel()
        self.flash_label.text = text
        self.flash_label.color = get_color_from_hex(cfg.get("text_color", "#FFFFFF"))
        self.flash_label.font_size = sp(cfg.get("font_size", 24))
        if cfg.get("bg_style") == "pill":
            self.flash_holder.set_bg_color((0.09, 0.09, 0.11, 0.92))
        else:
            self.flash_holder.set_bg_color((0, 0, 0, 0))

        pos = cfg.get("position", "center")
        if pos == "top":
            self.flash_holder.pos_hint = {"center_x": 0.5, "top": 0.86}
        elif pos == "bottom":
            self.flash_holder.pos_hint = {"center_x": 0.5, "y": 0.12}
        elif pos == "random":
            self.flash_holder.pos_hint = {"center_x": random.uniform(0.35, 0.65), "center_y": random.uniform(0.2, 0.8)}
        else:
            self.flash_holder.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        self.flash_holder.opacity = float(cfg.get("opacity", 0.85))
        dur_s = max(0.005, int(cfg.get("duration_ms", 35)) / 1000.0)
        self._desktop_hide_ev = Clock.schedule_once(lambda *_: setattr(self.flash_holder, "opacity", 0), dur_s)

    def _schedule_desktop_flash(self) -> None:
        if self._desktop_flash_ev is not None:
            self._desktop_flash_ev.cancel()
            self._desktop_flash_ev = None
        if not self.cfg.get("enabled", True):
            return
        delay = random.uniform(float(self.cfg["interval_min_s"]), float(self.cfg["interval_max_s"]))
        self._desktop_flash_ev = Clock.schedule_once(self._run_desktop_flash, max(0.5, delay))

    def _run_desktop_flash(self, *_) -> None:
        pool, eff = self._get_effective_pool_and_cfg()
        msg = self._pick_msg(pool)
        if msg:
            self._show_inapp_flash(msg, eff)
        self._schedule_desktop_flash()


if __name__ == "__main__":
    SubliminalAndroidApp().run()
