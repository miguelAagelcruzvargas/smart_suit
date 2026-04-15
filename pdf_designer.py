#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_designer.py  v2.0
🎨 Editor Visual de PDFs — PowerSuite Pro
Canvas premium, estilos de texto predefinidos, selector de fuentes.
"""

import sys, os, threading, tempfile, textwrap
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox, colorchooser, font as tkfont
except ImportError:
    print("Falta customtkinter"); sys.exit(1)

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    HAS_RL = True
except ImportError:
    HAS_RL = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def resource_path(relative_path):
    """Obtiene la ruta absoluta para recursos, compatible con PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ─── Constantes de página ─────────────────────────────────────────────────────
A4_W_PT = 595.0
A4_H_PT = 842.0

# ─── Paleta de colores del diseño ─────────────────────────────────────────────
BG_DEEP   = "#050810"
BG_DARK   = "#0D0F1A"
BG_PANEL  = "#111827"
BG_CARD   = "#1C2033"
ACCENT    = "#6C63FF"
ACCENT2   = "#4F46E5"
TEXT_MAIN = "#F1F5F9"
TEXT_GRAY = "#94A3B8"
RED       = "#EF4444"
GREEN     = "#10B981"
GOLD      = "#F59E0B"

# ─── Presets de texto ─────────────────────────────────────────────────────────
TEXT_PRESETS = [
    {"name": "Título Principal",  "size": 32, "bold": True,  "italic": False, "color": "#1E1B4B", "family": "Helvetica"},
    {"name": "Subtítulo",         "size": 20, "bold": False, "italic": True,  "color": "#4338CA", "family": "Helvetica"},
    {"name": "Encabezado 1",      "size": 18, "bold": True,  "italic": False, "color": "#1F2937", "family": "Helvetica"},
    {"name": "Encabezado 2",      "size": 15, "bold": True,  "italic": False, "color": "#374151", "family": "Helvetica"},
    {"name": "Encabezado 3",      "size": 13, "bold": True,  "italic": False, "color": "#4B5563", "family": "Helvetica"},
    {"name": "Cuerpo Normal",     "size": 11, "bold": False, "italic": False, "color": "#111827", "family": "Helvetica"},
    {"name": "Cita / Énfasis",    "size": 11, "bold": False, "italic": True,  "color": "#6B7280", "family": "Helvetica"},
    {"name": "Nota pequeña",      "size": 9,  "bold": False, "italic": False, "color": "#9CA3AF", "family": "Helvetica"},
    {"name": "Etiqueta",          "size": 10, "bold": True,  "italic": False, "color": "#6C63FF", "family": "Helvetica"},
]

FONTS_AVAILABLE = ["Helvetica", "Times New Roman", "Courier", "Arial", "Calibri", "Georgia"]
SIZES_AVAILABLE = ["8","9","10","11","12","14","16","18","20","22","24","28","32","36","42","48","60","72"]

# ─── Tipos de elemento ────────────────────────────────────────────────────────
EL_TEXT  = "text"
EL_IMAGE = "image"
EL_RECT  = "rect"
EL_LINE  = "line"
EL_ZONE  = "photo_zone"

TOOL_LABELS = {
    EL_TEXT:  ("📝", "Texto"),
    EL_IMAGE: ("🖼️", "Imagen"),
    EL_RECT:  ("⬛", "Rectángulo"),
    EL_LINE:  ("➖", "Línea"),
    EL_ZONE:  ("📷", "Zona de Foto"),
}


class Element:
    _cnt = 0
    def __init__(self, et, x, y):
        Element._cnt += 1
        self.uid      = Element._cnt
        self.type     = et
        self.x        = float(x)
        self.y        = float(y)
        self.selected = False
        self.canvas_ids = []

        if et == EL_TEXT:
            self.text    = "Texto de ejemplo"
            self.size    = 16
            self.bold    = False
            self.italic  = False
            self.color   = "#1E1B4B"
            self.family  = "Helvetica"
            self.align   = "left"
        elif et == EL_IMAGE:
            self.path    = ""
            self.width   = 180
            self.height  = 140
            self.pil_img = None
            self.tk_img  = None
        elif et == EL_RECT:
            self.width   = 220
            self.height  = 80
            self.fill    = "#6C63FF"
            self.outline = "#4F46E5"
            self.bw      = 2
        elif et == EL_LINE:
            self.width   = 400
            self.height  = 3
            self.color   = "#6C63FF"
        elif et == EL_ZONE:
            self.width   = 200
            self.height  = 150
            self.label   = "📷 Zona de foto"
            self.fill    = "#EDE9FE"
            self.outline = "#7C3AED"


class PDFDesigner(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("✏️  PDF Designer — PowerSuite Pro")
        self.geometry("1380x900")
        self.minsize(1100, 750)
        
        # Icono
        try:
            ico_path = resource_path("powersuite.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except: pass

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1380x900+{(sw-1380)//2}+{(sh-900)//2}")
        self.configure(fg_color=BG_DEEP)

        self.elements   = []
        self.selected   = None
        self._drag_data = {}
        self._tool      = ctk.StringVar(value=EL_TEXT)
        self._scale     = 1.0
        self._page_w    = 0
        self._page_h    = 0
        self._page_ox   = 0   # offset x del page en canvas
        self._page_oy   = 20

        self._build_ui()
        self.attributes("-alpha", 0)
        self._fade(0)

    def _fade(self, a):
        if a < 1.0:
            a = min(1.0, a + 0.07)
            self.attributes("-alpha", a)
            self.after(15, lambda: self._fade(a))

    # ═══════════════════════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._top_menubar()
        self._left_toolbar()
        self._canvas_area()
        self._right_props()

    # ── Barra top ─────────────────────────────────────────────────────────────
    def _top_menubar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=60)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")

        # Logo
        ctk.CTkLabel(bar, text="✏️  PDF Designer", text_color=TEXT_MAIN,
                 font=ctk.CTkFont(size=17, weight="bold")).pack(side="left", padx=18, pady=12)

        # Separador
        tk.Frame(bar, bg="#2D2D4A", width=1).pack(side="left", fill="y", padx=6, pady=8)

        # ── Presets de texto ──
        ctk.CTkLabel(bar, text="Estilo:", text_color=TEXT_GRAY,
                 font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(12, 4))

        self.preset_var = ctk.StringVar(value="Cuerpo Normal")
        preset_names = [p["name"] for p in TEXT_PRESETS]
        preset_cb = ctk.CTkComboBox(bar, variable=self.preset_var,
                                    values=preset_names, width=180, height=30,
                                    command=self._apply_preset,
                                    fg_color=BG_CARD, border_color=ACCENT,
                                    button_color=ACCENT, dropdown_fg_color=BG_PANEL)
        preset_cb.pack(side="left", padx=4)

        tk.Frame(bar, bg="#2D2D4A", width=1).pack(side="left", fill="y", padx=8, pady=8)

        # ── Fuente ──
        ctk.CTkLabel(bar, text="Fuente:", text_color=TEXT_GRAY,
                 font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(4, 4))
        self.font_var = ctk.StringVar(value="Helvetica")
        ctk.CTkComboBox(bar, variable=self.font_var,
                        values=FONTS_AVAILABLE, width=150, height=30,
                        fg_color=BG_CARD, border_color=ACCENT,
                        button_color=ACCENT, dropdown_fg_color=BG_PANEL).pack(side="left", padx=4)

        # ── Tamaño ──
        ctk.CTkLabel(bar, text="Tamaño:", text_color=TEXT_GRAY,
                 font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(8, 4))
        self.size_var = ctk.StringVar(value="16")
        ctk.CTkComboBox(bar, variable=self.size_var,
                        values=SIZES_AVAILABLE, width=72, height=30,
                        fg_color=BG_CARD, border_color=ACCENT,
                        button_color=ACCENT, dropdown_fg_color=BG_PANEL).pack(side="left", padx=4)

        # ── Negrita / Itálica / Color ──
        self.bold_var   = ctk.BooleanVar(value=False)
        self.italic_var = ctk.BooleanVar(value=False)

        tk.Frame(bar, bg="#2D2D4A", width=1).pack(side="left", fill="y", padx=8, pady=8)

        ctk.CTkCheckBox(bar, text="N", variable=self.bold_var,
                        font=ctk.CTkFont(size=13, weight="bold"),
                        fg_color=ACCENT, checkbox_width=22, checkbox_height=22,
                        width=44).pack(side="left", padx=3)
        ctk.CTkCheckBox(bar, text="I", variable=self.italic_var,
                        font=ctk.CTkFont(size=13),
                        fg_color=ACCENT, checkbox_width=22, checkbox_height=22,
                        width=44).pack(side="left", padx=3)

        self._text_color = "#1E1B4B"
        self.color_preview = ctk.CTkFrame(bar, fg_color=self._text_color, width=30, height=30, corner_radius=6)
        self.color_preview.pack(side="left", padx=6, pady=14)
        self.color_preview.bind("<Button-1>", lambda e: self._pick_text_color())
        # Permitir click también en el label de adentro si llegara a tener uno
        ctk.CTkLabel(bar, text="Color", text_color=TEXT_GRAY, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

        # Botones derechos
        rf = tk.Frame(bar, bg=BG_PANEL)
        rf.pack(side="right", padx=14)

        ctk.CTkButton(rf, text="↩ Deshacer", width=100, height=30,
                      fg_color=BG_CARD, hover_color="#1E293B",
                      font=ctk.CTkFont(size=12), command=self._undo).pack(side="left", padx=4)
        ctk.CTkButton(rf, text="🗑 Limpiar", width=90, height=30,
                      fg_color="#1C1315", hover_color="#3B1E1E",
                      text_color=RED, font=ctk.CTkFont(size=12),
                      command=self._clear_all).pack(side="left", padx=4)
                      
        # Botón ultra visible para cargar PDF base
        ctk.CTkButton(rf, text="📂 Abrir PDF (Fondo)", width=160, height=34,
                      fg_color="#F59E0B", hover_color="#D97706", text_color="#1E293B",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._import_bg_pdf).pack(side="left", padx=(12, 6))

        ctk.CTkButton(rf, text="📄 Exportar PDF", width=130, height=34,
                      fg_color=ACCENT, hover_color=ACCENT2,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._export_pdf).pack(side="left", padx=4)

    # ── Panel izquierdo ───────────────────────────────────────────────────────
    def _left_toolbar(self):
        tb = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, width=90)
        tb.grid(row=1, column=0, sticky="nsew")
        tb.grid_propagate(False)

        ctk.CTkLabel(tb, text="HERRAMIENTAS", text_color=TEXT_GRAY,
                 font=ctk.CTkFont(size=10, weight="bold")).pack(pady=(16, 8))

        self._tool_btns = {}
        for key, (icon, label) in TOOL_LABELS.items():
            f = tk.Frame(tb, bg=BG_PANEL, cursor="hand2")
            f.pack(fill="x", pady=3, padx=6)
            ico = tk.Label(f, text=icon, bg=BG_PANEL, fg=TEXT_MAIN,
                           font=("Segoe UI", 20))
            ico.pack()
            lbl = tk.Label(f, text=label, bg=BG_PANEL, fg=TEXT_GRAY,
                           font=("Segoe UI", 8))
            lbl.pack()
            for w in (f, ico, lbl):
                w.bind("<Button-1>", lambda e, k=key: self._select_tool(k))
                w.bind("<Enter>",    lambda e, ff=f: ff.configure(bg=BG_CARD))
                w.bind("<Leave>",    lambda e, ff=f, k=key: ff.configure(
                    bg=ACCENT if self._tool.get() == k else BG_PANEL))
            self._tool_btns[key] = f

        tk.Frame(tb, bg="#2D2D4A", height=1).pack(fill="x", padx=8, pady=12)

        # Herramientas extra
        for icon, tip, cmd in [
            ("🔡", "Presets\nTexto",   self._add_preset_text),
            ("📋", "Plantilla\nBásica", self._insert_template),
        ]:
            f = tk.Frame(tb, bg=BG_PANEL, cursor="hand2")
            f.pack(fill="x", pady=3, padx=6)
            ico = tk.Label(f, text=icon, bg=BG_PANEL, fg=GOLD,
                           font=("Segoe UI", 18))
            ico.pack()
            lbl_t = tk.Label(f, text=tip, bg=BG_PANEL, fg=TEXT_GRAY,
                             font=("Segoe UI", 7), justify="center")
            lbl_t.pack()
            for w in (f, ico, lbl_t):
                w.bind("<Button-1>", lambda e, c=cmd: c())

        self._select_tool(EL_TEXT)

    # ── Canvas central ────────────────────────────────────────────────────────
    def _canvas_area(self):
        wrap = tk.Frame(self, bg=BG_DEEP)
        wrap.grid(row=1, column=1, sticky="nsew")
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        # Regla superior (decorativa)
        ruler = tk.Frame(wrap, bg=BG_PANEL, height=24)
        ruler.grid(row=0, column=0, sticky="ew")
        tk.Label(ruler, text="  A4  ·  210 × 297 mm  ·  Click en la hoja para agregar  ·  Arrastra para mover",
                 bg=BG_PANEL, fg=TEXT_GRAY, font=("Segoe UI", 9)).pack(side="left", padx=12, pady=3)

        canvas_outer = ctk.CTkFrame(wrap, fg_color=BG_DEEP, corner_radius=0)
        canvas_outer.grid(row=1, column=0, sticky="nsew")
        canvas_outer.grid_rowconfigure(0, weight=1)
        canvas_outer.grid_columnconfigure(0, weight=1)

        self.vscroll = ctk.CTkScrollbar(canvas_outer, orientation="vertical", fg_color=BG_DEEP, button_color="#2D2D4A", button_hover_color=ACCENT)
        self.hscroll = ctk.CTkScrollbar(canvas_outer, orientation="horizontal", fg_color=BG_DEEP, button_color="#2D2D4A", button_hover_color=ACCENT)

        self.canvas = tk.Canvas(canvas_outer, bg=BG_DEEP, highlightthickness=0,
                                yscrollcommand=self.vscroll.set,
                                xscrollcommand=self.hscroll.set,
                                cursor="crosshair")

        self.vscroll.configure(command=self.canvas.yview)
        self.hscroll.configure(command=self.canvas.xview)

        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.canvas.bind("<Configure>",      self._on_canvas_resize)
        self.canvas.bind("<Button-1>",       self._on_click)
        self.canvas.bind("<B1-Motion>",      self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",self._on_drop)
        self.canvas.bind("<Double-Button-1>",self._on_double_click)
        self.canvas.bind("<MouseWheel>",     self._on_scroll)

    # ── Panel derecho de propiedades ─────────────────────────────────────────
    def _right_props(self):
        rp = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, width=280)
        rp.grid(row=1, column=2, sticky="nsew")
        rp.grid_propagate(False)

        ctk.CTkLabel(rp, text="⚙  Propiedades", text_color=ACCENT,
                 font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(16, 8))

        sep = ctk.CTkFrame(rp, fg_color="#2D2D4A", height=1)
        sep.pack(fill="x", padx=14, pady=(0, 8))

        self.props_outer = rp
        self.props_frame = ctk.CTkFrame(rp, fg_color="transparent")
        self.props_frame.pack(fill="both", expand=True)
        self._show_empty_props()

    # ═══════════════════════════════════════════════════════════════════════════
    # DIBUJO
    # ═══════════════════════════════════════════════════════════════════════════
    def _on_canvas_resize(self, event):
        cw = event.width
        ch = event.height
        # Escala para que la hoja llene ~85% de la altura visible
        self._scale = (ch * 0.88) / A4_H_PT
        self._page_w = int(A4_W_PT * self._scale)
        self._page_h = int(A4_H_PT * self._scale)
        self._page_ox = (cw - self._page_w) // 2
        self._page_oy = 24
        sr = (0, 0, max(cw, self._page_w + self._page_ox + 40),
              self._page_h + self._page_oy + 40)
        self.canvas.configure(scrollregion=sr)
        self._draw_page()

    def _pt2px(self, v): return v * self._scale
    def _px2pt(self, v): return v / self._scale if self._scale else v

    def _draw_page(self):
        self.canvas.delete("all")
        if self._page_w == 0: return

        ox, oy = self._page_ox, self._page_oy
        pw, ph  = self._page_w, self._page_h

        # Grid de fondo sutil
        grid_step = 30
        for gx in range(0, self.canvas.winfo_width(), grid_step):
            self.canvas.create_line(gx, 0, gx, self.canvas.winfo_height(),
                                    fill="#0F1120", width=1, tags="grid")
        for gy in range(0, self.canvas.winfo_height(), grid_step):
            self.canvas.create_line(0, gy, self.canvas.winfo_width(), gy,
                                    fill="#0F1120", width=1, tags="grid")

        # Sombra página
        for i in range(8, 0, -1):
            alpha = 60 - i * 7
            self.canvas.create_rectangle(ox+i, oy+i, ox+pw+i, oy+ph+i,
                                         fill="#000000", outline="", tags="shadow")
        # Página blanca
        self.canvas.create_rectangle(ox, oy, ox+pw, oy+ph,
                                     fill="white", outline="#B0B8C8", width=1,
                                     tags="page")
                                     
        if hasattr(self, "bg_pdf_img") and self.bg_pdf_img:
            from PIL import ImageTk, Image
            img2 = self.bg_pdf_img.copy()
            img2.thumbnail((pw, ph), Image.LANCZOS)
            self._cached_bg_tk = ImageTk.PhotoImage(img2)
            self.canvas.create_image(ox, oy, anchor="nw", image=self._cached_bg_tk, tags="page")

        # Márgen sutil
        m = int(self._pt2px(30))
        self.canvas.create_rectangle(ox+m, oy+m, ox+pw-m, oy+ph-m,
                                     outline="#E5E7EB", width=1, dash=(3, 4),
                                     tags="margin")

        for el in self.elements:
            self._draw_element(el)

    def _import_bg_pdf(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not f: return
        try:
            import fitz
            from PIL import Image
            doc = fitz.open(f)
            page = doc[0]
            r = page.rect
            global A4_W_PT, A4_H_PT, A4
            A4_W_PT = r.width
            A4_H_PT = r.height
            A4 = (A4_W_PT, A4_H_PT)
            
            self.bg_pdf_path = f
            
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            self.bg_pdf_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Force resize
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            self._scale = (ch * 0.88) / A4_H_PT
            self._page_w = int(A4_W_PT * self._scale)
            self._page_h = int(A4_H_PT * self._scale)
            self._page_ox = (cw - self._page_w) // 2
            sr = (0, 0, max(cw, self._page_w + self._page_ox + 40),
                  self._page_h + self._page_oy + 40)
            self.canvas.configure(scrollregion=sr)
            self._draw_page()
            messagebox.showinfo("Fondo importado", "✅ Fondo PDF cargado.\n\nPuedes dibujar bloques blancos (Rectángulo con relleno blanco y sin borde) para borrar texto, y luego usar la herramienta de Texto para escribir encima.\n\nAl exportar, todo se fusionará matemáticamente conservando la calidad.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar:\n{e}")

    def _draw_element(self, el: Element):
        s = self._scale
        ox, oy = self._page_ox, self._page_oy
        cx = ox + int(el.x * s)
        cy = oy + int(el.y * s)

        ids = []
        tag = f"el_{el.uid}"

        if el.type == EL_TEXT:
            w = "bold" if el.bold else "normal"
            sl = "italic" if el.italic else "roman"
            fam = "TkDefaultFont"
            sz  = max(6, int(el.size * s))
            fnt = tkfont.Font(family="Segoe UI", size=sz, weight=w, slant=sl)
            tid = self.canvas.create_text(
                cx, cy, text=el.text, fill=el.color,
                font=fnt, anchor="nw", tags=(tag, "element"), width=int(self._pt2px(500))
            )
            ids.append(tid)

        elif el.type == EL_IMAGE:
            if el.tk_img:
                iid = self.canvas.create_image(cx, cy, image=el.tk_img, anchor="nw",
                                               tags=(tag, "element"))
                ids.append(iid)
            else:
                pw2 = int(el.width * s); ph2 = int(el.height * s)
                self.canvas.create_rectangle(cx, cy, cx+pw2, cy+ph2,
                                             fill="#EDE9FE", outline=ACCENT, width=2,
                                             dash=(6, 3), tags=(tag, "element"))
                self.canvas.create_text(cx + pw2//2, cy + ph2//2,
                                        text="🖼️\nClic doble para imagen",
                                        fill=ACCENT, justify="center",
                                        font=tkfont.Font(size=10),
                                        tags=(tag, "element"))
                ids = []  # canvas_ids vacío = usa tags

        elif el.type == EL_RECT:
            pw2 = int(el.width * s); ph2 = int(el.height * s)
            rid = self.canvas.create_rectangle(cx, cy, cx+pw2, cy+ph2,
                                               fill=el.fill, outline=el.outline,
                                               width=el.bw, tags=(tag, "element"))
            ids.append(rid)

        elif el.type == EL_LINE:
            pw2 = int(el.width * s); ph2 = max(1, int(el.height * s))
            lid = self.canvas.create_rectangle(cx, cy, cx+pw2, cy+ph2,
                                               fill=el.color, outline="",
                                               tags=(tag, "element"))
            ids.append(lid)

        elif el.type == EL_ZONE:
            pw2 = int(el.width * s); ph2 = int(el.height * s)
            self.canvas.create_rectangle(cx, cy, cx+pw2, cy+ph2,
                                         fill=el.fill, outline=el.outline,
                                         width=2, dash=(7, 4), tags=(tag, "element"))
            self.canvas.create_text(cx + pw2//2, cy + ph2//2,
                                    text=f"{el.label}", fill=el.outline,
                                    justify="center", font=tkfont.Font(size=11),
                                    tags=(tag, "element"))

        el.canvas_ids = ids

        # Resalte de selección
        if el.selected:
            bbox = self.canvas.bbox(tag)
            if bbox:
                x1, y1, x2, y2 = bbox
                self.canvas.create_rectangle(x1-3, y1-3, x2+3, y2+3,
                                             outline=ACCENT, width=2, dash=(5, 3),
                                             tags=("sel", "handle"))
                for hx, hy in [(x1,y1),(x2,y1),(x1,y2),(x2,y2),(x1,(y1+y2)//2),(x2,(y1+y2)//2)]:
                    self.canvas.create_rectangle(hx-5, hy-5, hx+5, hy+5,
                                                 fill=ACCENT, outline="white", width=1,
                                                 tags=("sel", "handle"))

        # Bind drag en items del elemento
        for cid in self.canvas.find_withtag(tag):
            self.canvas.tag_bind(cid, "<Button-1>",
                                 lambda e, el=el: self._select_el(el, e))
            self.canvas.tag_bind(cid, "<B1-Motion>",
                                 lambda e, el=el: self._on_drag(e, el))
            self.canvas.tag_bind(cid, "<ButtonRelease-1>", self._on_drop)

    # ═══════════════════════════════════════════════════════════════════════════
    # EVENTOS
    # ═══════════════════════════════════════════════════════════════════════════
    def _on_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        ox, oy = self._page_ox, self._page_oy
        pw, ph  = self._page_w, self._page_h

        if not (ox <= cx <= ox+pw and oy <= cy <= oy+ph):
            self._deselect_all(); return

        items = self.canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
        for item in reversed(items):
            for tag in self.canvas.gettags(item):
                if tag.startswith("el_"):
                    uid = int(tag.split("_")[1])
                    el  = next((e for e in self.elements if e.uid == uid), None)
                    if el:
                        self._select_el(el, event); return

        ex = self._px2pt(cx - ox)
        ey = self._px2pt(cy - oy)
        self._add_element(self._tool.get(), ex, ey)

    def _add_element(self, etype, x, y):
        if etype == EL_IMAGE:
            p = filedialog.askopenfilename(
                filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp")])
            if not p: return

        el = Element(etype, x, y)

        # Aplicar valores del toolbar al texto nuevo
        if etype == EL_TEXT:
            try: el.size = int(self.size_var.get())
            except: pass
            el.bold     = self.bold_var.get()
            el.italic   = self.italic_var.get()
            el.color    = self._text_color
            el.family   = self.font_var.get()

        if etype == EL_IMAGE:
            el.path = p
            if HAS_PIL:
                try:
                    img = Image.open(p)
                    img.thumbnail((int(el.width * self._scale),
                                   int(el.height * self._scale)))
                    el.pil_img = img
                    el.tk_img  = ImageTk.PhotoImage(img)
                    el.width   = self._px2pt(img.width)
                    el.height  = self._px2pt(img.height)
                except: pass

        self._deselect_all()
        el.selected = True
        self.selected = el
        self.elements.append(el)
        self._draw_page()
        self._show_props(el)

    def _select_el(self, el: Element, event=None):
        self._deselect_all()
        el.selected = True
        self.selected = el
        if event:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            self._drag_data = {"sx": cx, "sy": cy, "ex": el.x, "ey": el.y}
        self._draw_page()
        self._show_props(el)

    def _deselect_all(self):
        for e in self.elements: e.selected = False
        self.selected = None
        self.canvas.delete("sel")
        self._show_empty_props()

    def _on_drag(self, event, el=None):
        if el is None:
            el = self._drag_data.get("el") or self.selected
        if el is None or not self._drag_data: return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if "sx" not in self._drag_data:
            self._drag_data = {"sx": cx, "sy": cy, "ex": el.x, "ey": el.y}
            return

        dx = self._px2pt(cx - self._drag_data["sx"])
        dy = self._px2pt(cy - self._drag_data["sy"])
        el.x = max(0.0, self._drag_data["ex"] + dx)
        el.y = max(0.0, self._drag_data["ey"] + dy)
        self._draw_page()

    def _on_drop(self, event):
        if self.selected and "ex" in self._drag_data:
            self._drag_data = {}

    def _on_double_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        items = self.canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
        for item in reversed(items):
            for tag in self.canvas.gettags(item):
                if tag.startswith("el_"):
                    uid = int(tag.split("_")[1])
                    el  = next((e for e in self.elements if e.uid == uid), None)
                    if el and el.type == EL_TEXT:
                        self._edit_text(el)
                    elif el and el.type == EL_IMAGE:
                        self._change_image(el)
                    return

    def _on_scroll(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ═══════════════════════════════════════════════════════════════════════════
    # HERRAMIENTAS
    # ═══════════════════════════════════════════════════════════════════════════
    def _select_tool(self, key):
        self._tool.set(key)
        for k, frame in self._tool_btns.items():
            frame.configure(bg=ACCENT if k == key else BG_PANEL)
            for w in frame.winfo_children():
                w.configure(bg=ACCENT if k == key else BG_PANEL)

    def _pick_text_color(self):
        c = colorchooser.askcolor(self._text_color, title="Color de texto")[1]
        if c:
            self._text_color = c
            self.color_preview.configure(fg_color=c)

    def _apply_preset(self, name):
        p = next((x for x in TEXT_PRESETS if x["name"] == name), None)
        if not p: return
        self.size_var.set(str(p["size"]))
        self.bold_var.set(p["bold"])
        self.italic_var.set(p["italic"])
        self._text_color = p["color"]
        self.color_preview.configure(fg_color=p["color"])
        self.font_var.set(p["family"])
        self._select_tool(EL_TEXT)
        if self.selected and self.selected.type == EL_TEXT:
            el = self.selected
            el.size   = p["size"]
            el.bold   = p["bold"]
            el.italic = p["italic"]
            el.color  = p["color"]
            el.family = p["family"]
            self._draw_page()
            self._show_props(el)

    def _add_preset_text(self):
        """Abre diálogo para elegir estilo e inserta texto en el centro."""
        center_x = self._px2pt(self._page_w // 2)
        center_y = self._px2pt(self._page_h // 3)
        self._add_element(EL_TEXT, center_x * 0.1, center_y * 0.6)

    def _insert_template(self):
        """Inserta una plantilla básica con título, subtítulo y cuerpo."""
        if self.elements:
            if not messagebox.askyesno("Plantilla", "¿Reemplazar la hoja actual con una plantilla?"):
                return
            self.elements.clear()

        pw_pt = A4_W_PT
        templates = [
            # Barra de color superior
            {"type": EL_RECT,  "x": 0, "y": 0, "w": pw_pt, "h": 55,
             "fill": ACCENT, "outline": ACCENT2, "bw": 0},
            # Título
            {"type": EL_TEXT,  "x": 30, "y": 12, "text": "Título del Documento",
             "size": 26, "bold": True, "italic": False, "color": "#FFFFFF", "family": "Helvetica"},
            # Subtítulo
            {"type": EL_TEXT,  "x": 30, "y": 75, "text": "Subtítulo o descripción breve",
             "size": 14, "bold": False, "italic": True, "color": "#4338CA", "family": "Helvetica"},
            # Línea decorativa
            {"type": EL_LINE,  "x": 30, "y": 98, "w": pw_pt - 60, "h": 2, "color": ACCENT},
            # Cuerpo
            {"type": EL_TEXT,  "x": 30, "y": 115,
             "text": "Escribe aquí el contenido principal. Puedes hacer clic\n"
                     "en cualquier texto para arrastrarlo o doble clic para editarlo.",
             "size": 11, "bold": False, "italic": False, "color": "#1F2937", "family": "Helvetica"},
        ]

        for t in templates:
            el = Element(t["type"], t["x"], t["y"])
            if t["type"] == EL_TEXT:
                el.text   = t["text"]; el.size = t["size"]
                el.bold   = t["bold"]; el.italic = t["italic"]
                el.color  = t["color"]; el.family = t["family"]
            elif t["type"] == EL_RECT:
                el.width  = t["w"]; el.height = t["h"]
                el.fill   = t["fill"]; el.outline = t["outline"]; el.bw = t["bw"]
            elif t["type"] == EL_LINE:
                el.width  = t["w"]; el.height = t["h"]; el.color = t["color"]
            self.elements.append(el)

        self._draw_page()

    def _edit_text(self, el: Element):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Editar texto"); dlg.geometry("480x220")
        dlg.grab_set(); dlg.transient(self)
        ctk.CTkLabel(dlg, text="Contenido del texto:",
                     font=ctk.CTkFont(weight="bold")).pack(pady=(16, 6))
        box = ctk.CTkTextbox(dlg, height=100)
        box.pack(fill="x", padx=20); box.insert("1.0", el.text); box.focus()

        def ok():
            el.text = box.get("1.0", "end").strip() or el.text
            self._draw_page(); dlg.destroy()

        ctk.CTkButton(dlg, text="✅ Aplicar", fg_color=ACCENT, command=ok).pack(pady=10)

    def _change_image(self, el: Element):
        p = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp")])
        if p and HAS_PIL:
            el.path = p
            try:
                img = Image.open(p)
                img.thumbnail((int(el.width * self._scale), int(el.height * self._scale)))
                el.pil_img = img; el.tk_img = ImageTk.PhotoImage(img)
                el.width = self._px2pt(img.width); el.height = self._px2pt(img.height)
            except: pass
            self._draw_page()

    def _undo(self):
        if self.elements:
            self.elements.pop(); self.selected = None
            self._draw_page(); self._show_empty_props()

    def _clear_all(self):
        if self.elements and messagebox.askyesno("Limpiar", "¿Eliminar todo?"):
            self.elements.clear(); self.selected = None
            self._draw_page(); self._show_empty_props()

    # ═══════════════════════════════════════════════════════════════════════════
    # PROPIEDADES
    # ═══════════════════════════════════════════════════════════════════════════
    def _clear_props(self):
        for w in self.props_frame.winfo_children(): w.destroy()

    def _show_empty_props(self):
        self._clear_props()
        ctk.CTkLabel(self.props_frame, text="Selecciona un\nelemento para\neditar.",
                 text_color=TEXT_GRAY, font=ctk.CTkFont(size=13),
                 justify="center").pack(pady=50)

    def _prop_row(self, label, widget_fn):
        f = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(f, text=label, text_color=TEXT_GRAY,
                 font=ctk.CTkFont(size=12), width=70, anchor="w").pack(side="left")
        w = widget_fn(f); w.pack(side="left", fill="x", expand=True)
        return w

    def _prop_label(self, text):
        ctk.CTkLabel(self.props_frame, text=text, fg_color=BG_CARD, text_color=ACCENT, corner_radius=6,
                 font=ctk.CTkFont(size=12, weight="bold"), pady=6).pack(fill="x", padx=4, pady=(12, 4))

    def _show_props(self, el: Element):
        self._clear_props()
        s = self._scale

        # ─ Posición ─
        self._prop_label("📍 Posición")
        xv = ctk.StringVar(value=f"{int(el.x)}")
        yv = ctk.StringVar(value=f"{int(el.y)}")
        self._prop_row("X (pt):", lambda p, v=xv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))
        self._prop_row("Y (pt):", lambda p, v=yv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))

        # ─ Por tipo ─
        if el.type == EL_TEXT:
            self._prop_label("🔤 Texto")

            tv = ctk.StringVar(value=el.text)
            te = ctk.CTkEntry(self.props_frame, textvariable=tv)
            te.pack(fill="x", padx=10, pady=2)

            self._prop_label("🎨 Estilo")

            fsv = ctk.StringVar(value=str(el.size))
            fmv = ctk.StringVar(value=el.family)
            self._prop_row("Fuente:", lambda p, v=fmv: ctk.CTkComboBox(p, variable=v,
                           values=FONTS_AVAILABLE, width=130, height=28))
            self._prop_row("Tamaño:", lambda p, v=fsv: ctk.CTkComboBox(p, variable=v,
                           values=SIZES_AVAILABLE, width=80, height=28))

            bv = ctk.BooleanVar(value=el.bold)
            iv = ctk.BooleanVar(value=el.italic)
            bf = tk.Frame(self.props_frame, bg=BG_PANEL)
            bf.pack(fill="x", padx=10, pady=4)
            ctk.CTkCheckBox(bf, text="Negrita (N)", variable=bv,
                            fg_color=ACCENT).pack(side="left", padx=(0, 8))
            ctk.CTkCheckBox(bf, text="Itálica (I)", variable=iv,
                            fg_color=ACCENT).pack(side="left")

            cv = ctk.StringVar(value=el.color)
            self._cb = None

            def pick_c():
                c = colorchooser.askcolor(el.color, title="Color de texto")[1]
                if c: cv.set(c); self._clr_btn.configure(fg_color=c)

            self._clr_btn = ctk.CTkButton(self.props_frame, text="🎨  Color texto",
                                          fg_color=el.color, hover_color=el.color,
                                          command=pick_c, height=30,
                                          font=ctk.CTkFont(size=11))
            self._clr_btn.pack(fill="x", padx=10, pady=4)

            def apply_text():
                try: el.x = float(xv.get())
                except: pass
                try: el.y = float(yv.get())
                except: pass
                el.text   = tv.get() or el.text
                try: el.size = int(fsv.get())
                except: pass
                el.bold   = bv.get()
                el.italic = iv.get()
                el.color  = cv.get()
                el.family = fmv.get()
                self._draw_page()

            ctk.CTkButton(self.props_frame, text="✅ Aplicar",
                          fg_color=GREEN, hover_color="#047857",
                          command=apply_text, height=36).pack(fill="x", padx=10, pady=6)

            # Atajos de preset rápido
            self._prop_label("⚡ Presets rápidos")
            for p in TEXT_PRESETS[:5]:
                ctk.CTkButton(self.props_frame, text=p["name"], height=26,
                              fg_color=BG_CARD, hover_color="#1E293B",
                              font=ctk.CTkFont(size=11),
                              command=lambda p=p, el=el: self._apply_preset_to_el(p, el)
                              ).pack(fill="x", padx=10, pady=1)

        elif el.type in (EL_RECT, EL_ZONE):
            self._prop_label("📐 Tamaño")
            wv = ctk.StringVar(value=str(int(el.width)))
            hv = ctk.StringVar(value=str(int(el.height)))
            self._prop_row("Ancho:", lambda p, v=wv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))
            self._prop_row("Alto:",  lambda p, v=hv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))

            self._prop_label("🎨 Colores")
            fv = ctk.StringVar(value=el.fill)
            ov = ctk.StringVar(value=el.outline)

            def pk_fill():
                c = colorchooser.askcolor(el.fill, title="Color de fondo")[1]
                if c: fv.set(c); fb_btn.configure(fg_color=c, hover_color=c)
            def pk_out():
                c = colorchooser.askcolor(el.outline, title="Color de borde")[1]
                if c: ov.set(c); ob_btn.configure(fg_color=c, hover_color=c)

            fb_btn = ctk.CTkButton(self.props_frame, text="🎨 Fondo", fg_color=el.fill,
                                   hover_color=el.fill, command=pk_fill, height=30)
            fb_btn.pack(fill="x", padx=10, pady=2)
            ob_btn = ctk.CTkButton(self.props_frame, text="🖊️ Borde", fg_color=el.outline,
                                   hover_color=el.outline, command=pk_out, height=30)
            ob_btn.pack(fill="x", padx=10, pady=2)

            def apply_r():
                try: el.x, el.y = float(xv.get()), float(yv.get())
                except: pass
                try: el.width, el.height = int(wv.get()), int(hv.get())
                except: pass
                el.fill, el.outline = fv.get(), ov.get()
                if el.type == EL_ZONE:
                    pass  # label editado inline
                self._draw_page()

            ctk.CTkButton(self.props_frame, text="✅ Aplicar",
                          fg_color=GREEN, hover_color="#047857",
                          command=apply_r, height=36).pack(fill="x", padx=10, pady=6)

        elif el.type == EL_IMAGE:
            self._prop_label("📐 Tamaño")
            wv = ctk.StringVar(value=str(int(el.width)))
            hv = ctk.StringVar(value=str(int(el.height)))
            self._prop_row("Ancho:", lambda p, v=wv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))
            self._prop_row("Alto:",  lambda p, v=hv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))

            ctk.CTkButton(self.props_frame, text="🖼️ Cambiar imagen",
                          fg_color="#0891B2", command=lambda: self._change_image(el),
                          height=30).pack(fill="x", padx=10, pady=6)

            def apply_i():
                try: el.x, el.y = float(xv.get()), float(yv.get())
                except: pass
                if el.pil_img and HAS_PIL:
                    try:
                        w, h = int(wv.get()), int(hv.get())
                        img2 = el.pil_img.copy()
                        img2.thumbnail((int(w*self._scale), int(h*self._scale)))
                        el.tk_img = ImageTk.PhotoImage(img2)
                        el.width, el.height = self._px2pt(img2.width), self._px2pt(img2.height)
                    except: pass
                self._draw_page()

            ctk.CTkButton(self.props_frame, text="✅ Aplicar",
                          fg_color=GREEN, hover_color="#047857",
                          command=apply_i, height=36).pack(fill="x", padx=10, pady=4)

        elif el.type == EL_LINE:
            self._prop_label("📐 Dimensiones")
            wv = ctk.StringVar(value=str(int(el.width)))
            hv = ctk.StringVar(value=str(int(el.height)))
            self._prop_row("Largo:", lambda p, v=wv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))
            self._prop_row("Grosor:", lambda p, v=hv: ctk.CTkEntry(p, textvariable=v, width=80, height=28))
            cv = ctk.StringVar(value=el.color)

            def pk_line():
                c = colorchooser.askcolor(el.color, title="Color de línea")[1]
                if c: cv.set(c); lb_btn.configure(fg_color=c, hover_color=c)

            lb_btn = ctk.CTkButton(self.props_frame, text="🎨 Color", fg_color=el.color,
                                   hover_color=el.color, command=pk_line, height=30)
            lb_btn.pack(fill="x", padx=10, pady=4)

            def apply_l():
                try: el.x, el.y = float(xv.get()), float(yv.get())
                except: pass
                try: el.width, el.height = int(wv.get()), int(hv.get())
                except: pass
                el.color = cv.get()
                self._draw_page()

            ctk.CTkButton(self.props_frame, text="✅ Aplicar",
                          fg_color=GREEN, hover_color="#047857",
                          command=apply_l, height=36).pack(fill="x", padx=10, pady=4)

        # Botón eliminar (siempre)
        tk.Frame(self.props_frame, bg="#2D2D4A", height=1).pack(fill="x", padx=8, pady=10)
        ctk.CTkButton(self.props_frame, text="🗑️  Eliminar elemento",
                      fg_color="#7F1D1D", hover_color=RED,
                      command=lambda: self._delete_el(el),
                      height=34).pack(fill="x", padx=10)

    def _apply_preset_to_el(self, p, el):
        el.size   = p["size"]
        el.bold   = p["bold"]
        el.italic = p["italic"]
        el.color  = p["color"]
        el.family = p["family"]
        self._draw_page()
        self._show_props(el)

    def _delete_el(self, el: Element):
        if el in self.elements: self.elements.remove(el)
        self.selected = None
        self._draw_page(); self._show_empty_props()

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORTACIÓN
    # ═══════════════════════════════════════════════════════════════════════════
    def _export_pdf(self):
        if not HAS_RL:
            messagebox.showerror("Error", "Falta reportlab:\npip install reportlab"); return
        if not self.elements:
            messagebox.showwarning("Sin contenido", "Agrega elementos antes de exportar."); return
        dest = filedialog.asksaveasfilename(defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf")],
                                            title="Guardar PDF como...")
        if not dest: return
        threading.Thread(target=self._do_export, args=(dest,), daemon=True).start()

    def _do_export(self, dest):
        try:
            temp_ov = str(Path(dest).with_suffix(".tmp.pdf"))
            c = rl_canvas.Canvas(temp_ov, pagesize=A4)
            pw, ph = A4   # Use dynamically updated A4 bounds

            def rl_color(h):
                try: return HexColor(h)
                except:
                    from reportlab.lib.colors import black; return black

            for el in self.elements:
                px = el.x
                py_pdf = ph - el.y   # PDF origin = bottom-left

                if el.type == EL_TEXT:
                    c.setFillColor(rl_color(el.color))
                    style = ""
                    if el.bold and el.italic: style = "-BoldOblique"
                    elif el.bold:             style = "-Bold"
                    elif el.italic:           style = "-Oblique"
                    # reportlab solo tiene Helvetica, Times-Roman, Courier built-in
                    base_map = {
                        "Helvetica": "Helvetica", "Arial": "Helvetica",
                        "Times New Roman": "Times-Roman", "Georgia": "Times-Roman",
                        "Courier": "Courier", "Calibri": "Helvetica"
                    }
                    base = base_map.get(el.family, "Helvetica")
                    fnt  = f"{base}{style}" if style else base
                    c.setFont(fnt, el.size)
                    for i, line in enumerate(el.text.split("\n")):
                        c.drawString(px, py_pdf - el.size - i*(el.size*1.3), line)

                elif el.type == EL_RECT:
                    c.setFillColor(rl_color(el.fill))
                    c.setStrokeColor(rl_color(el.outline))
                    c.setLineWidth(el.bw)
                    c.rect(px, py_pdf - el.height, el.width, el.height, fill=1, stroke=1)

                elif el.type == EL_LINE:
                    c.setFillColor(rl_color(el.color))
                    c.setStrokeColor(rl_color(el.color))
                    c.rect(px, py_pdf - el.height, el.width, el.height, fill=1, stroke=0)

                elif el.type == EL_IMAGE and el.path and Path(el.path).exists():
                    try:
                        c.drawImage(el.path, px, py_pdf - el.height,
                                    width=el.width, height=el.height,
                                    preserveAspectRatio=True, mask="auto")
                    except: pass

                elif el.type == EL_ZONE:
                    c.setFillColor(rl_color(el.fill))
                    c.setStrokeColor(rl_color(el.outline))
                    c.setLineWidth(2)
                    c.rect(px, py_pdf - el.height, el.width, el.height, fill=1, stroke=1)
                    c.setFillColor(rl_color(el.outline))
                    c.setFont("Helvetica-Bold", 9)
                    c.drawCentredString(px + el.width/2, py_pdf - el.height/2, el.label)
                    c.acroForm.textfield(name=f"zona_{el.uid}", tooltip=el.label,
                                        x=px, y=py_pdf - el.height,
                                        width=el.width, height=el.height, fontSize=9)

            # Pie
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.drawString(40, 16,
                         f"Creado con PowerSuite Pro PDF Designer — "
                         f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
            c.save()
            
            if hasattr(self, "bg_pdf_path") and self.bg_pdf_path:
                import PyPDF2
                from pathlib import Path
                reader_bg = PyPDF2.PdfReader(self.bg_pdf_path)
                reader_ov = PyPDF2.PdfReader(temp_ov)
                writer = PyPDF2.PdfWriter()
                for i, page in enumerate(reader_bg.pages):
                    if i == 0:
                        page.merge_page(reader_ov.pages[0])
                    writer.add_page(page)
                with open(dest, "wb") as f_out:
                    writer.write(f_out)
                Path(temp_ov).unlink(missing_ok=True)
            else:
                import shutil
                shutil.move(temp_ov, dest)

            self.after(0, lambda: [
                messagebox.showinfo("✅ Exportado", f"PDF guardado:\n{Path(dest).name}"),
                __import__("os").startfile(dest)
            ])
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))


if __name__ == "__main__":
    app = PDFDesigner()
    app.mainloop()
