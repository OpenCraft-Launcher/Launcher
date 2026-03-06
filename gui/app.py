import json
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

import launcher
from utils.jvm import args_to_string, get_default_jvm_args, get_max_ram_mb, string_to_args
from utils.versions import get_versions

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#1c1c1c"
SURFACE  = "#2a2a2a"
SURFACE2 = "#323232"
SURFACE3 = "#3a3a3a"
BORDER   = "#3a3a3a"
FG       = "#ffffff"
FG2      = "#aaaaaa"
FG3      = "#666666"
ACCENT   = "#0078d4"
ACCENT_H = "#1a8fe0"
ACCENT_P = "#006cbe"
ERR      = "#d13438"

SKINS_DIR = Path(__file__).parent.parent / "skins"
SKINS_DIR.mkdir(exist_ok=True)

# ── Widgets ───────────────────────────────────────────────────────────────────

class FluentButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, width=120, height=36,
                 bg=ACCENT, bg_h=ACCENT_H, bg_p=ACCENT_P, fg=FG,
                 font_size=10, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG, highlightthickness=0, cursor="hand2", **kw)
        self._t, self._cmd = text, command
        self._n, self._h, self._p, self._fg = bg, bg_h, bg_p, fg
        self._font = ("Segoe UI", font_size, "bold")
        self._dis = False
        self._draw(bg)
        self.bind("<Enter>",           lambda e: self._set(self._h))
        self.bind("<Leave>",           lambda e: self._set(self._n))
        self.bind("<Button-1>",        lambda e: self._set(self._p))
        self.bind("<ButtonRelease-1>", self._rel)

    def _rr(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
               x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1, x1+r,y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, col):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        c = SURFACE3 if self._dis else col
        fg = FG3 if self._dis else self._fg
        self._rr(0, 0, w, h, 6, fill=c, outline="")
        self.create_text(w//2, h//2, text=self._t, fill=fg, font=self._font)

    def _set(self, c):
        if not self._dis: self._draw(c)

    def _rel(self, e):
        if not self._dis:
            self._set(self._n)
            if self._cmd: self._cmd()

    def config_state(self, disabled, text=None):
        self._dis = disabled
        if text: self._t = text
        self._draw(self._n)

    def set_bg(self, bg):
        self.configure(bg=bg)


class FluentEntry(tk.Frame):
    def __init__(self, parent, textvariable=None, width=20, **kw):
        super().__init__(parent, bg=SURFACE, **kw)
        self._var = textvariable or tk.StringVar()
        self._e = tk.Entry(self, textvariable=self._var, bg=SURFACE2, fg=FG,
                            insertbackground=FG, relief="flat",
                            font=("Segoe UI", 11), bd=0, width=width)
        self._e.pack(fill="x", ipady=6, padx=6)
        self._bar = tk.Frame(self, bg=BORDER, height=2)
        self._bar.pack(fill="x", side="bottom")
        self._e.bind("<FocusIn>",  lambda e: self._bar.config(bg=ACCENT))
        self._e.bind("<FocusOut>", lambda e: self._bar.config(bg=BORDER))

    def get(self): return self._var.get()


def section(parent, text):
    return tk.Label(parent, text=text, bg=BG, fg=FG2, font=("Segoe UI Semibold", 9))


# ── Top tab bar ───────────────────────────────────────────────────────────────

class TopTabBar(tk.Frame):
    def __init__(self, parent, tabs, on_change=None, **kw):
        super().__init__(parent, bg=SURFACE, **kw)
        self._tabs = tabs
        self._on_change = on_change
        self._selected = tabs[0][0]
        self._btns = {}
        self._changing = False
        self._indicator = tk.Frame(self, bg=ACCENT, height=2)

        for tid, label, emoji in tabs:
            btn = tk.Label(self, text=f"{emoji}  {label}",
                           font=("Segoe UI", 10), padx=20, pady=11,
                           bg=SURFACE, cursor="hand2")
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, t=tid: self._pick(t))
            self._btns[tid] = btn

        self._refresh_colors()
        self.after(20, self._place_indicator)

    def _pick(self, tid):
        if self._changing: return
        self._selected = tid
        self._refresh_colors()
        self.after(10, self._place_indicator)
        if self._on_change:
            self._changing = True
            self._on_change(tid)
            self._changing = False

    def _refresh_colors(self):
        for tid, btn in self._btns.items():
            sel = tid == self._selected
            btn.configure(fg=FG if sel else FG2)

    def _place_indicator(self):
        btn = self._btns.get(self._selected)
        if btn:
            x, w, h = btn.winfo_x(), btn.winfo_width(), self.winfo_height()
            if w > 0 and h > 0:
                self._indicator.place(x=x, y=h-2, width=w, height=2)

    def select(self, tid):
        self._selected = tid
        self._refresh_colors()
        self.after(10, self._place_indicator)


# ── Skin preview canvas ───────────────────────────────────────────────────────

class SkinPreview(tk.Canvas):
    """Renders a Minecraft skin PNG as a simple flat front-facing character."""

    # Each region: (u, v, w, h) in the 64x64 skin texture
    # We'll draw head, body, arms, legs as scaled rectangles with color sampling

    SIZE = 64   # skin texture size

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=SURFACE, highlightthickness=0, **kw)
        self._img_data = None   # raw pixel list (r,g,b,a) or None
        self._scale = 4
        self.bind("<Configure>", lambda e: self._redraw())

    def load(self, png_path: str):
        """Load skin PNG and extract pixel data."""
        try:
            # Use tkinter's PhotoImage — works without Pillow
            img = tk.PhotoImage(file=png_path)
            w, h = img.width(), img.height()
            # Get pixel data row by row
            self._img_data = []
            for y in range(h):
                row = []
                for x in range(w):
                    r, g, b = img.get(x, y)
                    row.append((r, g, b))
                self._img_data.append(row)
            self._img_w = w
            self._img_h = h
        except Exception:
            self._img_data = None
        self._redraw()

    def clear(self):
        self._img_data = None
        self._redraw()

    def _get_pixel(self, x, y):
        if self._img_data is None:
            return "#888888"
        if y >= len(self._img_data) or x >= len(self._img_data[0]):
            return "#888888"
        r, g, b = self._img_data[y][x]
        return f"#{r:02x}{g:02x}{b:02x}"

    def _avg_region(self, u, v, w, h):
        """Average color of a skin region."""
        if self._img_data is None:
            return "#888888"
        rs, gs, bs, n = 0, 0, 0, 0
        for dy in range(h):
            for dx in range(w):
                px = self._img_data[v + dy][u + dx] if (v+dy) < len(self._img_data) and (u+dx) < len(self._img_data[0]) else (136,136,136)
                rs += px[0]; gs += px[1]; bs += px[2]; n += 1
        if n == 0: return "#888888"
        return f"#{rs//n:02x}{gs//n:02x}{bs//n:02x}"

    def _sample_region(self, u, v, rw, rh, dest_x, dest_y, dest_w, dest_h):
        """Draw a skin region as a grid of scaled pixels."""
        if self._img_data is None:
            self.create_rectangle(dest_x, dest_y, dest_x+dest_w, dest_y+dest_h,
                                   fill="#888888", outline="")
            return
        px_w = dest_w / rw
        px_h = dest_h / rh
        for dy in range(rh):
            for dx in range(rw):
                sx = u + dx
                sy = v + dy
                col = self._get_pixel(sx, sy)
                x1 = int(dest_x + dx * px_w)
                y1 = int(dest_y + dy * px_h)
                x2 = int(dest_x + (dx+1) * px_w)
                y2 = int(dest_y + (dy+1) * px_h)
                self.create_rectangle(x1, y1, x2, y2, fill=col, outline="")

    def _redraw(self):
        self.delete("all")
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 10 or ch < 10:
            return

        if self._img_data is None:
            # Draw placeholder silhouette
            self._draw_placeholder(cw, ch)
            return

        self._draw_skin(cw, ch)

    def _draw_placeholder(self, cw, ch):
        # Simple Steve-shaped silhouette in grey
        s = min(cw, ch) // 10
        cx = cw // 2

        # head
        hx, hy, hs = cx - s*2, 20, s*4
        self.create_rectangle(hx, hy, hx+hs, hy+hs, fill=SURFACE3, outline=BORDER)
        # body
        bx, by, bw, bh = cx - s*2, hy+hs+2, s*4, s*6
        self.create_rectangle(bx, by, bx+bw, by+bh, fill=SURFACE3, outline=BORDER)
        # left arm
        self.create_rectangle(bx-s*2, by, bx-2, by+bh, fill=SURFACE3, outline=BORDER)
        # right arm
        self.create_rectangle(bx+bw+2, by, bx+bw+s*2, by+bh, fill=SURFACE3, outline=BORDER)
        # left leg
        self.create_rectangle(bx, by+bh+2, bx+bw//2-1, by+bh+s*6, fill=SURFACE3, outline=BORDER)
        # right leg
        self.create_rectangle(bx+bw//2+1, by+bh+2, bx+bw, by+bh+s*6, fill=SURFACE3, outline=BORDER)
        self.create_text(cx, ch-16, text="No skin loaded", fill=FG3,
                         font=("Segoe UI", 9))

    def _draw_skin(self, cw, ch):
        # Minecraft skin UV map (front faces only, no overlay layers)
        # Skin texture is 64x64 (modern) or 64x32 (classic)
        is64 = self._img_h >= 64

        # Scale: fit character in canvas with padding
        total_h = 32  # head(8) + body(12) + leg(12) in skin units
        total_w = 16  # body(8) + arm(4) + arm(4) in skin units
        s = min((cw - 20) // total_w, (ch - 20) // total_h)
        if s < 2: s = 2

        # Pixel dimensions
        head_w, head_h = s*8, s*8
        body_w, body_h = s*8, s*12
        arm_w,  arm_h  = s*4, s*12
        leg_w,  leg_h  = s*4, s*12

        char_total_h = head_h + body_h + leg_h
        char_total_w = arm_w + body_w + arm_w

        # Center in canvas
        cx = cw // 2
        top = (ch - char_total_h) // 2
        if top < 4: top = 4

        # Positions
        hx = cx - head_w // 2
        hy = top

        bx = cx - body_w // 2
        by = hy + head_h

        lax = bx - arm_w   # left arm (right arm in skin = viewer's left)
        rax = bx + body_w  # right arm (left arm in skin = viewer's right)
        ay  = by

        llx = bx            # left leg
        rlx = bx + leg_w    # right leg
        ly  = by + body_h

        # ── Draw each part using correct UV front-face coordinates ──
        # Minecraft UV layout:
        #   Head front:      u=8,  v=8,  w=8, h=8
        #   Body front:      u=20, v=20, w=8, h=12
        #   Right arm front: u=44, v=20, w=4, h=12
        #   Left arm front:  u=36, v=52, w=4, h=12  (64x64 only)
        #   Right leg front: u=4,  v=20, w=4, h=12
        #   Left leg front:  u=20, v=52, w=4, h=12  (64x64 only)

        self._sample_region(8,  8,  8, 8,  hx,  hy, head_w, head_h)
        self._sample_region(20, 20, 8, 12, bx,  by, body_w, body_h)
        self._sample_region(44, 20, 4, 12, lax, ay, arm_w,  arm_h)
        self._sample_region(4,  20, 4, 12, llx, ly, leg_w,  leg_h)

        if is64:
            self._sample_region(36, 52, 4, 12, rax, ay, arm_w, arm_h)
            self._sample_region(20, 52, 4, 12, rlx, ly, leg_w, leg_h)
        else:
            # Classic skin: mirror arms and legs
            self._sample_region(44, 20, 4, 12, rax, ay, arm_w, arm_h)
            self._sample_region(4,  20, 4, 12, rlx, ly, leg_w, leg_h)


# ── Main app ──────────────────────────────────────────────────────────────────

class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenCraft Launcher")
        self.geometry("900x600")
        self.minsize(860, 560)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._versions = {}
        self._ram_max = get_max_ram_mb()
        self._launch_thread = None
        self._skin_path = ""

        # DWM: dark titlebar + black border
        try:
            from ctypes import windll, byref, c_int
            hwnd = windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(c_int(1)), 4)
            windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, byref(c_int(0x00000000)), 4)
        except Exception:
            pass

        self._build()
        threading.Thread(target=self._load_versions, daemon=True).start()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        tbar = tk.Frame(self, bg=SURFACE, height=46)
        tbar.pack(fill="x")
        tbar.pack_propagate(False)
        tk.Label(tbar, text="⛏", bg=SURFACE, fg=ACCENT,
                 font=("Segoe UI Emoji", 17)).pack(side="left", padx=(17, 6), pady=10)
        tk.Label(tbar, text="OpenCraft", bg=SURFACE, fg=FG,
                 font=("Segoe UI Semibold", 15)).pack(side="left", pady=10)

        # Tab bar
        self._tabbar = TopTabBar(
            self,
            tabs=[("play", "Play", "▶"), ("skins", "Skins", "🎨")],
            on_change=self._show_tab,
        )
        self._tabbar.pack(fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Content frames
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True)

        self._play_frame  = tk.Frame(self._content, bg=BG)
        self._skins_frame = tk.Frame(self._content, bg=BG)

        self._build_play(self._play_frame)
        self._build_skins(self._skins_frame)

        self._show_tab("play")

    def _show_tab(self, tab_id):
        self._play_frame.pack_forget()
        self._skins_frame.pack_forget()
        if tab_id == "play":
            self._play_frame.pack(fill="both", expand=True)
        else:
            self._skins_frame.pack(fill="both", expand=True)
            self._refresh_skin_list()
        self._tabbar.select(tab_id)

    # ── Play tab ──────────────────────────────────────────────────────────────

    def _build_play(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # Left column
        left = tk.Frame(body, bg=BG, width=296)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        # Username
        section(left, "USERNAME").pack(anchor="w", pady=(0, 4))
        card = tk.Frame(left, bg=SURFACE, padx=12, pady=10)
        card.pack(fill="x", pady=(0, 12))
        tk.Frame(card, bg=ACCENT, width=3).place(x=0, y=0, relheight=1)
        self._username_var = tk.StringVar(value="Player")
        FluentEntry(card, textvariable=self._username_var, width=22).pack(fill="x")
        self._err = tk.Label(card, text="", bg=SURFACE, fg=ERR, font=("Segoe UI", 8))
        self._err.pack(anchor="w")

        # Version & loader
        section(left, "VERSION & MOD LOADER").pack(anchor="w", pady=(0, 4))
        card2 = tk.Frame(left, bg=SURFACE, padx=12, pady=10)
        card2.pack(fill="x", pady=(0, 12))

        self._loader_var = tk.StringVar(value="vanilla")
        pills = tk.Frame(card2, bg=SURFACE)
        pills.pack(fill="x", pady=(0, 8))
        self._pills = {}
        for val, lbl in [("vanilla","Vanilla"),("fabric","Fabric"),("forge","Forge")]:
            b = tk.Label(pills, text=lbl, bg=SURFACE2, fg=FG2,
                         font=("Segoe UI", 9, "bold"), padx=12, pady=5, cursor="hand2")
            b.pack(side="left", padx=(0,6))
            b.bind("<Button-1>", lambda e, v=val: self._pick_loader(v))
            self._pills[val] = b
        self._pick_loader("vanilla")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Flat.TCombobox", fieldbackground=SURFACE2, background=SURFACE2,
                         foreground=FG, selectbackground=ACCENT, selectforeground=FG,
                         borderwidth=0, arrowcolor=FG2, padding=6)
        style.map("Flat.TCombobox", fieldbackground=[("readonly", SURFACE2)])

        self._version_var = tk.StringVar(value="Loading…")
        self._version_combo = ttk.Combobox(card2, textvariable=self._version_var,
                                            state="readonly", style="Flat.TCombobox", width=24)
        self._version_combo.pack(fill="x")

        # RAM
        section(left, "MEMORY").pack(anchor="w", pady=(0, 4))
        card3 = tk.Frame(left, bg=SURFACE, padx=12, pady=10)
        card3.pack(fill="x", pady=(0, 12))
        ram_row = tk.Frame(card3, bg=SURFACE)
        ram_row.pack(fill="x")
        tk.Label(ram_row, text="RAM Allocation", bg=SURFACE, fg=FG2,
                 font=("Segoe UI", 9)).pack(side="left")
        self._ram_badge = tk.Label(ram_row, text="2048 MB", bg=ACCENT, fg=FG,
                                    font=("Segoe UI", 8, "bold"), padx=8, pady=2)
        self._ram_badge.pack(side="right")
        self._ram_var = tk.IntVar(value=min(2048, self._ram_max))
        ttk.Scale(card3, from_=512, to=self._ram_max, variable=self._ram_var,
                   orient="horizontal", command=self._on_ram).pack(fill="x", pady=(8,0))
        lims = tk.Frame(card3, bg=SURFACE)
        lims.pack(fill="x")
        tk.Label(lims, text="512 MB", bg=SURFACE, fg=FG3, font=("Segoe UI",8)).pack(side="left")
        tk.Label(lims, text=f"{self._ram_max} MB", bg=SURFACE, fg=FG3, font=("Segoe UI",8)).pack(side="right")

        # Active skin indicator
        section(left, "ACTIVE SKIN").pack(anchor="w", pady=(0, 4))
        skin_card = tk.Frame(left, bg=SURFACE, padx=12, pady=8)
        skin_card.pack(fill="x", pady=(0, 12))
        skin_row = tk.Frame(skin_card, bg=SURFACE)
        skin_row.pack(fill="x")
        self._play_skin_lbl = tk.Label(skin_row, text="Default skin", bg=SURFACE,
                                        fg=FG2, font=("Segoe UI", 9))
        self._play_skin_lbl.pack(side="left")
        tk.Label(skin_row, text="→ Skins tab", bg=SURFACE, fg=FG3,
                 font=("Segoe UI", 8), cursor="hand2").pack(side="right")

        # Launch button
        self._launch_btn = FluentButton(left, text="▶   Play", command=self._launch,
                                         width=272, height=44, font_size=12)
        self._launch_btn.pack(pady=(8, 0))

        # Right column
        right = tk.Frame(body, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        jvm_hdr = tk.Frame(right, bg=BG)
        jvm_hdr.pack(fill="x", pady=(0, 4))
        section(jvm_hdr, "JVM ARGUMENTS").pack(side="left")
        tk.Label(jvm_hdr, text="Advanced", bg=BG, fg=FG3,
                 font=("Segoe UI", 8)).pack(side="right", pady=4)

        jvm_card = tk.Frame(right, bg=SURFACE, padx=10, pady=8)
        jvm_card.pack(fill="x", pady=(0, 12))
        self._jvm_text = tk.Text(jvm_card, bg=SURFACE2, fg=FG2, insertbackground=FG,
                                  relief="flat", font=("Consolas", 8), height=5, wrap="word", bd=0)
        self._jvm_text.pack(fill="both")
        self._jvm_text.insert("1.0", args_to_string(get_default_jvm_args(2048)))

        section(right, "CONSOLE").pack(anchor="w", pady=(0, 4))
        log_card = tk.Frame(right, bg=SURFACE, padx=8, pady=8)
        log_card.pack(fill="both", expand=True)
        self._log = tk.Text(log_card, bg="#0d0d0d", fg="#cccccc", insertbackground=FG,
                             relief="flat", font=("Consolas", 9), state="disabled", bd=0)
        sb = ttk.Scrollbar(log_card, command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True)

        self._status = tk.Label(parent, text="Ready", bg=BG, fg=FG3,
                                 font=("Segoe UI", 8), anchor="w")
        self._status.pack(fill="x", padx=16, pady=(0, 6))

    # ── Skins tab ─────────────────────────────────────────────────────────────

    def _build_skins(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # Left: skin list
        left = tk.Frame(body, bg=BG, width=260)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        hdr = tk.Frame(left, bg=BG)
        hdr.pack(fill="x", pady=(0, 8))
        section(hdr, "MY SKINS").pack(side="left")
        add_btn = tk.Label(hdr, text="+ Add", bg=ACCENT, fg=FG,
                           font=("Segoe UI", 9, "bold"), padx=10, pady=4, cursor="hand2")
        add_btn.pack(side="right")
        add_btn.bind("<Button-1>", lambda e: self._add_skin())

        list_frame_outer = tk.Frame(left, bg=SURFACE)
        list_frame_outer.pack(fill="both", expand=True)

        self._skin_canvas = tk.Canvas(list_frame_outer, bg=SURFACE, highlightthickness=0)
        skin_sb = ttk.Scrollbar(list_frame_outer, orient="vertical",
                                 command=self._skin_canvas.yview)
        self._skin_canvas.configure(yscrollcommand=skin_sb.set)
        skin_sb.pack(side="right", fill="y")
        self._skin_canvas.pack(fill="both", expand=True)

        self._skin_list_frame = tk.Frame(self._skin_canvas, bg=SURFACE)
        self._skin_list_win = self._skin_canvas.create_window(
            (0, 0), window=self._skin_list_frame, anchor="nw")
        self._skin_list_frame.bind(
            "<Configure>",
            lambda e: self._skin_canvas.configure(
                scrollregion=self._skin_canvas.bbox("all")))
        self._skin_canvas.bind(
            "<Configure>",
            lambda e: self._skin_canvas.itemconfig(self._skin_list_win, width=e.width))

        # Right: preview
        right = tk.Frame(body, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        section(right, "PREVIEW").pack(anchor="w", pady=(0, 8))

        preview_card = tk.Frame(right, bg=SURFACE, padx=16, pady=16)
        preview_card.pack(fill="both", expand=True)

        self._preview = SkinPreview(preview_card, width=200, height=360)
        self._preview.pack(side="left", fill="both", expand=True)

        # Info panel beside preview
        info_col = tk.Frame(preview_card, bg=SURFACE, padx=12)
        info_col.pack(side="left", fill="y")

        self._skin_name_lbl = tk.Label(info_col, text="No skin selected", bg=SURFACE,
                                        fg=FG, font=("Segoe UI Semibold", 12),
                                        wraplength=180, justify="left")
        self._skin_name_lbl.pack(anchor="w", pady=(0, 6))

        self._skin_path_lbl = tk.Label(info_col, text="", bg=SURFACE, fg=FG3,
                                        font=("Segoe UI", 8), wraplength=180, justify="left")
        self._skin_path_lbl.pack(anchor="w", pady=(0, 16))

        self._use_btn = FluentButton(info_col, text="✓ Use this skin",
                                      command=self._use_selected_skin,
                                      width=160, height=36, font_size=10)
        self._use_btn.pack(anchor="w", pady=(0, 8))

        self._del_btn = FluentButton(info_col, text="🗑 Remove",
                                      command=self._delete_selected_skin,
                                      width=120, height=32,
                                      bg=SURFACE2, bg_h=SURFACE3, bg_p=BORDER, fg=ERR,
                                      font_size=9)
        self._del_btn.pack(anchor="w")

        self._selected_skin = None  # filename in SKINS_DIR

    def _refresh_skin_list(self):
        for w in self._skin_list_frame.winfo_children():
            w.destroy()

        skins = sorted(SKINS_DIR.glob("*.png"))

        if not skins:
            tk.Label(self._skin_list_frame, text="No skins added yet.\nClick '+ Add' to import a PNG.",
                     bg=SURFACE, fg=FG3, font=("Segoe UI", 9),
                     justify="center").pack(pady=30, padx=10)
            return

        for skin_path in skins:
            self._make_skin_row(skin_path)

    def _make_skin_row(self, skin_path: Path):
        name = skin_path.stem
        is_active = self._skin_path == str(skin_path)

        row = tk.Frame(self._skin_list_frame, bg=SURFACE2 if is_active else SURFACE,
                       padx=10, pady=8, cursor="hand2")
        row.pack(fill="x", pady=1)

        if is_active:
            tk.Frame(row, bg=ACCENT, width=3).pack(side="left", fill="y", padx=(0, 8))

        tk.Label(row, text="🎨", bg=row["bg"],
                 font=("Segoe UI Emoji", 13)).pack(side="left", padx=(0, 8))

        name_lbl = tk.Label(row, text=name, bg=row["bg"], fg=FG if is_active else FG2,
                             font=("Segoe UI", 10, "bold" if is_active else "normal"))
        name_lbl.pack(side="left", fill="x", expand=True)

        if is_active:
            tk.Label(row, text="active", bg=row["bg"], fg=ACCENT,
                     font=("Segoe UI", 8)).pack(side="right")

        for w in [row, name_lbl]:
            w.bind("<Button-1>", lambda e, p=skin_path: self._select_skin(p))

    def _select_skin(self, skin_path: Path):
        self._selected_skin = skin_path
        self._skin_name_lbl.config(text=skin_path.stem)
        self._skin_path_lbl.config(text=str(skin_path))
        self._preview.load(str(skin_path))
        self._refresh_skin_list()

    def _add_skin(self):
        paths = filedialog.askopenfilenames(
            title="Select skin PNG(s)",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        for p in paths:
            src = Path(p)
            dest = SKINS_DIR / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
        self._refresh_skin_list()
        if paths:
            self._select_skin(SKINS_DIR / Path(paths[-1]).name)

    def _use_selected_skin(self):
        if not self._selected_skin:
            return
        self._skin_path = str(self._selected_skin)
        self._play_skin_lbl.config(text=self._selected_skin.stem, fg=FG)
        self._refresh_skin_list()

    def _delete_selected_skin(self):
        if not self._selected_skin:
            return
        if self._skin_path == str(self._selected_skin):
            self._skin_path = ""
            self._play_skin_lbl.config(text="Default skin", fg=FG2)
        self._selected_skin.unlink(missing_ok=True)
        self._selected_skin = None
        self._skin_name_lbl.config(text="No skin selected")
        self._skin_path_lbl.config(text="")
        self._preview.clear()
        self._refresh_skin_list()

    # ── Play helpers ──────────────────────────────────────────────────────────

    def _pick_loader(self, val):
        self._loader_var.set(val)
        for v, b in self._pills.items():
            b.config(bg=ACCENT if v == val else SURFACE2,
                     fg=FG if v == val else FG2)
        vers = self._versions.get(val, [])
        if vers:
            self._version_combo["values"] = vers
            self._version_var.set(vers[0])

    def _on_ram(self, _=None):
        val = int(self._ram_var.get())
        self._ram_badge.config(text=f"{val} MB")
        self._jvm_text.delete("1.0", "end")
        self._jvm_text.insert("1.0", args_to_string(get_default_jvm_args(val)))

    def _load_versions(self):
        self._versions = get_versions()
        loader = self._loader_var.get()
        vers = self._versions.get(loader, [])
        self._version_combo["values"] = vers
        if vers:
            self._version_var.set(vers[0])
        self._log_write("✓ Version list loaded.")

    def _log_write(self, msg):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")
        self._status.config(text=msg[:100])

    def _validate(self, name):
        import re
        if not name: return "Username is required."
        if len(name) < 3 or len(name) > 16: return "Must be 3–16 characters."
        if not re.match(r"^[a-zA-Z0-9_]+$", name): return "Letters, numbers, underscores only."
        return None

    def _launch(self):
        username = self._username_var.get().strip()
        err = self._validate(username)
        if err:
            self._err.config(text=err)
            return
        self._err.config(text="")

        version    = self._version_var.get()
        mod_loader = self._loader_var.get()
        jvm_args   = string_to_args(self._jvm_text.get("1.0", "end").strip())

        self._launch_btn.config_state(True, "Launching…")
        self._log_write(f"▶ {version} [{mod_loader}] as '{username}'…")

        def run():
            try:
                launcher.launch(
                    username=username, version=version, mod_loader=mod_loader,
                    jvm_args=jvm_args, skin_path=self._skin_path,
                    progress_cb=lambda m: self.after(0, self._log_write, m),
                    log_cb=lambda m: self.after(0, self._log_write, m),
                )
                self.after(0, self._log_write, "✓ Game closed.")
            except Exception as e:
                self.after(0, self._log_write, f"✗ {e}")
            finally:
                self.after(0, self._launch_btn.config_state, False, "▶   Play")

        threading.Thread(target=run, daemon=True).start()
