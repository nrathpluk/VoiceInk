"""Floating capsule HUD window. Custom-drawn pill on Tk Canvas."""

from __future__ import annotations

import math
import os
import tkinter as tk
from typing import TYPE_CHECKING

import pyperclip

from constants import (
    APP_NAME,
    CAPSULE_RADIUS,
    COLORS,
    DEFAULT_HOTKEY,
    LANGUAGE_LABELS,
    LANGUAGES,
    LIVE_PREVIEW_H,
    MIC_CX,
    MIC_CY,
    MIC_R,
    MODELS,
    TRANSPARENT_KEY,
    WAVE_BAR_GAP,
    WAVE_BAR_W,
    WAVE_BARS,
    WIN_H,
    WIN_W,
)
from log_setup import log
from util import State, _resource_path

if TYPE_CHECKING:
    from main import App


class FloatingWindow:
    """Pill-shaped always-on-top mini-HUD."""

    def __init__(self, app: App):
        self.app = app
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            log.warning("transparentcolor unsupported on this platform")
        self.root.configure(bg=TRANSPARENT_KEY)

        try:
            ico = _resource_path("icon.ico")
            if os.path.exists(ico):
                self.root.iconbitmap(default=ico)
        except Exception:
            log.exception("iconbitmap failed")

        # Position: saved coords if on-screen, else bottom-right
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        cfg = getattr(app, "_cfg", {}) or {}
        sx, sy = cfg.get("window_x"), cfg.get("window_y")
        if isinstance(sx, int) and isinstance(sy, int) and -WIN_W < sx < sw and -WIN_H < sy < sh:
            x, y = sx, sy
        else:
            x = sw - WIN_W - 24
            y = sh - WIN_H - 80
        self.root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        # Visual state
        self._state_key = "idle"
        self._copied_active = False
        self._pending_state_key: str | None = None
        self._pulse_phase = 0.0
        self._wave_phase = 0.0
        self._wave_levels = [0.0] * WAVE_BARS
        self._anim_alive = True
        self._model_loading_text: str | None = None
        self._hotkey_label = DEFAULT_HOTKEY

        # Click / drag
        self._press_x = 0
        self._press_y = 0
        self._click_target = "body"
        self._drag_x = 0
        self._drag_y = 0
        self._drag_started = False

        # Capsule canvas
        self.canvas = tk.Canvas(
            self.root,
            width=WIN_W,
            height=WIN_H,
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(side="top", fill="x")
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._show_menu)

        # Live preview (only shown when live_mode on)
        self.preview_frame = tk.Frame(self.root, bg=TRANSPARENT_KEY)
        self.preview_inner = tk.Frame(
            self.preview_frame,
            bg=COLORS["preview_bg"],
            highlightthickness=1,
            highlightbackground="#2a2a40",
        )
        self.preview_inner.pack(padx=8, pady=(0, 6), fill="both", expand=True)
        self.preview_text = tk.Text(
            self.preview_inner,
            height=4,
            bg=COLORS["preview_bg"],
            fg=COLORS["fg"],
            font=("Segoe UI", 8),
            wrap="word",
            relief="flat",
            highlightthickness=0,
            insertbackground=COLORS["fg"],
            padx=6,
            pady=4,
        )
        self.preview_text.pack(fill="both", expand=True)
        self.preview_text.configure(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.app.quit)

        self._draw_all()
        self.root.after(50, self._animate)

    # ---------- Drawing ----------
    def _rounded_rect(self, x0, y0, x1, y1, r, fill="", outline=""):
        c = self.canvas
        # Two overlapping rectangles + four ovals = filled rounded rect
        items = [
            c.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=outline),
            c.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline=outline),
            c.create_oval(x0, y0, x0 + 2 * r, y0 + 2 * r, fill=fill, outline=outline),
            c.create_oval(x1 - 2 * r, y0, x1, y0 + 2 * r, fill=fill, outline=outline),
            c.create_oval(x0, y1 - 2 * r, x0 + 2 * r, y1, fill=fill, outline=outline),
            c.create_oval(x1 - 2 * r, y1 - 2 * r, x1, y1, fill=fill, outline=outline),
        ]
        return items

    def _draw_all(self):
        c = self.canvas
        c.delete("all")

        # Soft glow halo when recording
        if self._state_key == "recording":
            for i, gc in enumerate(("#1f1538", "#241c44", "#291f4e")):
                pad = 3 - i
                self._rounded_rect(
                    -pad,
                    -pad,
                    WIN_W + pad,
                    WIN_H + pad,
                    CAPSULE_RADIUS + pad,
                    fill=gc,
                    outline="",
                )

        # Capsule body
        self._rounded_rect(0, 0, WIN_W, WIN_H, CAPSULE_RADIUS, fill=COLORS["bg"], outline="")

        # Mic button
        if self._state_key == "recording":
            pulse = 1.0 + 0.08 * math.sin(self._pulse_phase)
            r = MIC_R * pulse
            mic_color = COLORS["red"]
            ring = MIC_R * (1.18 + 0.08 * (math.sin(self._pulse_phase) * 0.5 + 0.5))
            c.create_oval(
                MIC_CX - ring,
                MIC_CY - ring,
                MIC_CX + ring,
                MIC_CY + ring,
                fill="",
                outline=COLORS["red"],
                width=1,
            )
        elif self._state_key == "done":
            r = MIC_R
            mic_color = COLORS["green"]
        else:
            r = MIC_R
            mic_color = COLORS["purple"]

        c.create_oval(MIC_CX - r, MIC_CY - r, MIC_CX + r, MIC_CY + r, fill=mic_color, outline="")

        # Inner glyph
        if self._state_key == "done":
            c.create_line(
                MIC_CX - 9,
                MIC_CY + 1,
                MIC_CX - 2,
                MIC_CY + 8,
                MIC_CX + 10,
                MIC_CY - 7,
                fill="#ffffff",
                width=3,
                capstyle="round",
                joinstyle="round",
            )
        else:
            self._draw_mic_glyph(MIC_CX, MIC_CY, "#ffffff")

        # Right side: wave / "Copied!" / model loading text
        right_x = MIC_CX + MIC_R + 18
        right_end = WIN_W - 26
        center_x = (right_x + right_end) // 2
        if self._state_key == "done":
            c.create_text(
                center_x,
                MIC_CY,
                text="Copied!",
                fill=COLORS["green"],
                font=("Segoe UI", 13, "bold"),
                anchor="center",
            )
        elif self._model_loading_text:
            c.create_text(
                center_x,
                MIC_CY,
                text=self._model_loading_text,
                fill=COLORS["wave_active"],
                font=("Segoe UI", 9),
                anchor="center",
            )
        else:
            self._draw_waves(right_x, MIC_CY)

        # Two-dot menu hint
        dot_x = WIN_W - 14
        for off in (-5, 5):
            c.create_oval(
                dot_x - 2,
                MIC_CY + off - 2,
                dot_x + 2,
                MIC_CY + off + 2,
                fill=COLORS["menu_dot"],
                outline="",
            )

    def _draw_mic_glyph(self, cx, cy, color):
        c = self.canvas
        c.create_oval(cx - 6, cy - 12, cx + 6, cy - 1, fill=color, outline="")
        c.create_rectangle(cx - 6, cy - 6, cx + 6, cy + 1, fill=color, outline="")
        c.create_arc(
            cx - 9,
            cy - 2,
            cx + 9,
            cy + 12,
            start=200,
            extent=140,
            style="arc",
            outline=color,
            width=2,
        )
        c.create_line(cx, cy + 11, cx, cy + 16, fill=color, width=2)
        c.create_line(cx - 5, cy + 16, cx + 5, cy + 16, fill=color, width=2)

    def _draw_waves(self, x_start, cy):
        c = self.canvas
        max_h = WIN_H - 24
        idle_heights = [10, 14, 18, 14, 20, 16, 12, 18, 14, 10]
        for i in range(WAVE_BARS):
            x = x_start + i * (WAVE_BAR_W + WAVE_BAR_GAP)
            if self._state_key == "recording":
                lv = self._wave_levels[i]
                h = max(4.0, lv * max_h)
                color = COLORS["wave_active"]
            elif self._state_key == "processing":
                lv = self._wave_levels[i]
                h = max(4.0, lv * max_h)
                color = COLORS["wave_idle"]
            else:
                breathe = 0.85 + 0.15 * math.sin(self._wave_phase * 0.6 + i * 0.7)
                h = idle_heights[i] * breathe
                color = COLORS["wave_idle"]
            y0 = cy - h / 2
            y1 = cy + h / 2
            c.create_rectangle(x, y0, x + WAVE_BAR_W, y1, fill=color, outline="")

    # ---------- Animation tick ----------
    def _animate(self):
        if not self._anim_alive:
            return
        self._pulse_phase += 0.18
        self._wave_phase += 0.12
        # Always redraw to support pulse + wave + idle breathe
        self._draw_all()
        self.root.after(50, self._animate)

    # ---------- Public API ----------
    def render_wave(self, levels: list[float]):
        # Store; redraw happens in _animate
        lv = list(levels) + [0.0] * (WAVE_BARS - len(levels))
        self._wave_levels = lv[:WAVE_BARS]

    def set_state(self, s: State):
        if self._copied_active:
            self._pending_state_key = s.value
            return
        self._state_key = s.value
        self._draw_all()

    def show_copied(self):
        self._copied_active = True
        self._state_key = "done"
        self._draw_all()
        self.root.after(2000, self._clear_copied)

    def _clear_copied(self):
        self._copied_active = False
        nxt = self._pending_state_key or "idle"
        self._pending_state_key = None
        self._state_key = nxt
        self._draw_all()

    def set_hotkey_label(self, hotkey: str):
        self._hotkey_label = hotkey

    def set_model_status(self, text: str, color: str | None = None):
        self._model_loading_text = text or None
        self._draw_all()

    def show_preview(self, on: bool):
        if on:
            if not self.preview_frame.winfo_ismapped():
                self.preview_frame.pack(side="top", fill="x")
            new_h = WIN_H + LIVE_PREVIEW_H
        else:
            if self.preview_frame.winfo_ismapped():
                self.preview_frame.pack_forget()
            new_h = WIN_H
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{WIN_W}x{new_h}+{x}+{y}")

    def set_preview(self, text: str):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self.preview_text.see("end")
        self.preview_text.configure(state="disabled")

    # ---------- Click / drag ----------
    def _inside_capsule(self, x, y):
        r = CAPSULE_RADIUS
        if r <= x <= WIN_W - r:
            return 0 <= y <= WIN_H
        if 0 <= x < r:
            cx, cy = r, WIN_H / 2
            return (x - cx) ** 2 + (y - cy) ** 2 <= cy * cy
        if WIN_W - r < x <= WIN_W:
            cx, cy = WIN_W - r, WIN_H / 2
            return (x - cx) ** 2 + (y - cy) ** 2 <= cy * cy
        return False

    def _hit_test(self, x, y):
        dx = x - MIC_CX
        dy = y - MIC_CY
        if dx * dx + dy * dy <= (MIC_R + 4) ** 2:
            return "mic"
        if x >= WIN_W - 22 and self._inside_capsule(x, y):
            return "menu"
        if self._inside_capsule(x, y):
            return "body"
        return "outside"

    def _on_press(self, e):
        self._press_x = e.x
        self._press_y = e.y
        self._drag_started = False
        self._click_target = self._hit_test(e.x, e.y)
        if self._click_target == "menu":
            self._show_menu(e)
            return
        if self._click_target in ("body", "mic"):
            self._drag_x = e.x_root - self.root.winfo_x()
            self._drag_y = e.y_root - self.root.winfo_y()

    def _on_drag(self, e):
        if self._click_target not in ("body", "mic"):
            return
        if not self._drag_started and abs(e.x - self._press_x) + abs(e.y - self._press_y) < 5:
            return
        self._drag_started = True
        x = e.x_root - self._drag_x
        y = e.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, e):
        if self._click_target == "mic" and not self._drag_started:
            self.app.toggle()

    # ---------- Right-click menu ----------
    def _show_menu(self, e):
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["purple"],
            activeforeground="#ffffff",
            borderwidth=0,
        )

        model_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["purple"],
            activeforeground="#ffffff",
        )
        for m in MODELS:
            mark = "● " if m == self.app.model_name else "   "
            model_menu.add_command(
                label=f"{mark}{m}",
                command=lambda name=m: self.app.change_model(name),
            )
        menu.add_cascade(label="Model", menu=model_menu)

        lang_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["purple"],
            activeforeground="#ffffff",
        )
        for lc in LANGUAGES:
            mark = "● " if lc == self.app.language else "   "
            lang_menu.add_command(
                label=f"{mark}{LANGUAGE_LABELS[lc]}",
                command=lambda c=lc: self.app.change_language(c),
            )
        menu.add_cascade(label="Language", menu=lang_menu)

        hist_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=COLORS["bg"],
            fg=COLORS["fg"],
            activebackground=COLORS["purple"],
            activeforeground="#ffffff",
        )
        if self.app.history:
            for h in self.app.history:
                lbl = h if len(h) <= 40 else h[:37] + "..."
                hist_menu.add_command(label=lbl, command=lambda t=h: pyperclip.copy(t))
        else:
            hist_menu.add_command(label="(empty)", state="disabled")
        menu.add_cascade(label="History", menu=hist_menu)

        menu.add_separator()
        live_mark = "● " if self.app.live_mode else "   "
        menu.add_command(
            label=f"{live_mark}Live mode (streaming)", command=self.app.toggle_live_mode
        )
        tok_mark = "● " if self.app.tokenize_thai else "   "
        menu.add_command(
            label=f"{tok_mark}ตัดคำไทย (Thai word break)", command=self.app.toggle_tokenize
        )
        menu.add_command(label=f"Hotkey: {self._hotkey_label}", command=self.app.prompt_hotkey)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.app.quit)

        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
