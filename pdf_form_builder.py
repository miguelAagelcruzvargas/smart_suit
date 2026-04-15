#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_form_builder.py
📝 Constructor de Formularios PDF Interactivos — PowerSuite Pro
Crea PDFs con campos llenables, menús, checkboxes y zonas de firma.
"""

import sys, os, threading
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox, colorchooser
except ImportError:
    print("Falta customtkinter")
    sys.exit(1)

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib import colors as rl_colors
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

# ─── Tipos de campo ───────────────────────────────────────────────────────────
FIELD_TEXT      = "text"
FIELD_EMAIL     = "email"
FIELD_DATE      = "date"
FIELD_PHONE     = "phone"
FIELD_NUMBER    = "number"
FIELD_TEXTAREA  = "textarea"
FIELD_DROPDOWN  = "dropdown"
FIELD_CHECKBOX  = "checkbox"
FIELD_RADIO     = "radio"
FIELD_SIGNATURE = "signature"
FIELD_PHOTO     = "photo"
FIELD_DIVIDER   = "divider"
FIELD_HEADING   = "heading"

FIELD_ICONS = {
    FIELD_TEXT:      "📝",
    FIELD_EMAIL:     "📧",
    FIELD_DATE:      "📅",
    FIELD_PHONE:     "📞",
    FIELD_NUMBER:    "🔢",
    FIELD_TEXTAREA:  "📄",
    FIELD_DROPDOWN:  "▼",
    FIELD_CHECKBOX:  "☑️",
    FIELD_RADIO:     "🔘",
    FIELD_SIGNATURE: "✍️",
    FIELD_PHOTO:     "📷",
    FIELD_DIVIDER:   "─",
    FIELD_HEADING:   "🔤",
}

FIELD_LABELS = {
    FIELD_TEXT:      "Texto corto",
    FIELD_EMAIL:     "Correo electrónico",
    FIELD_DATE:      "Fecha",
    FIELD_PHONE:     "Teléfono",
    FIELD_NUMBER:    "Número",
    FIELD_TEXTAREA:  "Texto largo",
    FIELD_DROPDOWN:  "Lista desplegable",
    FIELD_CHECKBOX:  "Casillas de verificación",
    FIELD_RADIO:     "Opciones (una sola)",
    FIELD_SIGNATURE: "Zona de firma",
    FIELD_PHOTO:     "Zona de foto",
    FIELD_DIVIDER:   "Separador",
    FIELD_HEADING:   "Título / Encabezado",
}

ACCENT = "#7C3AED"
ACCENT2 = "#5B21B6"


class FieldRow:
    """Representa un campo dentro del formulario."""
    _counter = 0

    def __init__(self, ftype):
        FieldRow._counter += 1
        self.uid       = FieldRow._counter
        self.ftype     = ftype
        self.label     = f"Campo {FieldRow._counter}"
        self.required  = False
        self.options   = "Opción 1,Opción 2,Opción 3"   # para dropdown/radio/checkbox
        self.placeholder = ""
        self.width_pct = 100   # % del ancho de página (100 o 50)
        self.height_lines = 4  # Para textareas


class PDFFormBuilder(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("📝 PDF Form Builder — PowerSuite Pro")
        self.geometry("1420x940")
        self.minsize(1100, 750)
        
        # Icono
        try:
            ico_path = resource_path("powersuite.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except: pass

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1420x940+{(sw-1420)//2}+{(sh-940)//2}")
        self.configure(fg_color=("#F8FAFC", "#0D0F1A"))

        self.fields = []   # list[FieldRow]

        # Vars globales del formulario
        self.form_title   = ctk.StringVar(value="Formulario de Registro")
        self.form_subtitle = ctk.StringVar(value="Complete todos los campos requeridos (*)")
        self.title_color  = "#7C3AED"
        self.accent_color = "#7C3AED"
        self.page_size_var = ctk.StringVar(value="A4")
        self.show_logo    = ctk.BooleanVar(value=False)
        self.logo_path    = None

        self._build_ui()
        self._fade(0)

    def _fade(self, a):
        if a < 1.0:
            a = min(1.0, a + 0.07)
            self.attributes("-alpha", a)
            self.after(15, lambda: self._fade(a))

    # ─── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_field_palette()
        self._build_canvas_area()

    # ── Topbar ────────────────────────────────────────────────────────────────
    def _build_topbar(self):
        top = ctk.CTkFrame(self, height=64, corner_radius=0,
                           fg_color=("#1E1240", "#1E1240"))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Logo / título
        ctk.CTkLabel(top, text="📝  Constructor de Formularios PDF",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color="#A78BFA").pack(side="left", padx=20, pady=16)

        # Controles globales
        rf = ctk.CTkFrame(top, fg_color="transparent")
        rf.pack(side="right", padx=16, pady=10)

        ctk.CTkLabel(rf, text="Título:", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
        ctk.CTkEntry(rf, textvariable=self.form_title, width=220, height=34).pack(side="left", padx=(0, 14))

        ctk.CTkLabel(rf, text="Tamaño:", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
        ctk.CTkComboBox(rf, variable=self.page_size_var,
                        values=["A4", "Letter"], width=90).pack(side="left", padx=(0, 14))

        # Botón exportar
        ctk.CTkButton(rf, text="📄  Exportar PDF", height=36, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT2,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._export).pack(side="left")

    # ── Panel izq: paleta de campos ───────────────────────────────────────────
    def _build_field_palette(self):
        pal = ctk.CTkFrame(self, width=200, corner_radius=0,
                           fg_color=("#0D0F1A", "#0D0F1A"))
        pal.grid(row=1, column=0, sticky="nsew")
        pal.grid_propagate(False)

        ctk.CTkLabel(pal, text="CAMPOS DISPONIBLES",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="gray").pack(anchor="w", padx=14, pady=(18, 8))

        # Grupos
        groups = [
            ("📋 Texto", [FIELD_TEXT, FIELD_EMAIL, FIELD_PHONE, FIELD_DATE, FIELD_NUMBER, FIELD_TEXTAREA]),
            ("☑️ Selección", [FIELD_CHECKBOX, FIELD_RADIO, FIELD_DROPDOWN]),
            ("🖊️ Especiales", [FIELD_SIGNATURE, FIELD_PHOTO]),
            ("🎨 Diseño", [FIELD_HEADING, FIELD_DIVIDER]),
        ]

        for group_name, ftypes in groups:
            ctk.CTkLabel(pal, text=group_name,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=("#A78BFA", "#A78BFA")).pack(anchor="w", padx=14, pady=(10, 3))
            for ftype in ftypes:
                icon  = FIELD_ICONS[ftype]
                label = FIELD_LABELS[ftype]
                btn = ctk.CTkButton(
                    pal, text=f" {icon}  {label}", anchor="w", height=34,
                    corner_radius=6, fg_color="transparent",
                    hover_color=("#1C2033", "#1C2033"),
                    font=ctk.CTkFont(size=12), text_color=("#D1D5DB", "#D1D5DB"),
                    command=lambda t=ftype: self._add_field(t)
                )
                btn.pack(fill="x", padx=10, pady=1)

        sep = ctk.CTkFrame(pal, height=1, fg_color="#2D2D4A")
        sep.pack(fill="x", padx=14, pady=14)

        ctk.CTkButton(pal, text="🗑️  Limpiar todo", anchor="w", height=34,
                      corner_radius=6, fg_color="transparent",
                      hover_color=("#3B1E1E", "#3B1E1E"),
                      font=ctk.CTkFont(size=12), text_color=("#EF4444", "#EF4444"),
                      command=self._clear_all).pack(fill="x", padx=10, pady=1)

    # ── Panel der: builder / preview ─────────────────────────────────────────
    def _build_canvas_area(self):
        outer = ctk.CTkFrame(self, corner_radius=0, fg_color=("#1A1A2E", "#1A1A2E"))
        outer.grid(row=1, column=1, sticky="nsew")
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Mini topbar del canvas
        sub = ctk.CTkFrame(outer, height=42, fg_color=("#0D0F1A", "#0D0F1A"), corner_radius=0)
        sub.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(sub, text="Vista del formulario  ·  Click en ➕ para agregar campos",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", padx=16, pady=10)

        # Zona de scroll con "hoja"
        canvas_wrap = ctk.CTkFrame(outer, fg_color="#1A1A2E", corner_radius=0)
        canvas_wrap.grid(row=1, column=0, sticky="nsew")

        self.vsb = ctk.CTkScrollbar(canvas_wrap, orientation="vertical", fg_color="#1A1A2E", button_color="#2D2D4A", button_hover_color=ACCENT)
        self.vsb.pack(side="right", fill="y")

        self.canvas = tk.Canvas(canvas_wrap, bg="#1A1A2E",
                                yscrollcommand=self.vsb.set, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.vsb.configure(command=self.canvas.yview)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Frame interno en el canvas (simula la hoja)
        self.sheet_frame = ctk.CTkFrame(self.canvas, corner_radius=10,
                                        fg_color=("#FFFFFF", "#1C2033"))
        self.sheet_window = self.canvas.create_window(
            0, 10, anchor="n", window=self.sheet_frame
        )

        # Header del formulario (dentro de la hoja)
        self._build_form_header()

        # Zona donde se insertan los campos
        self.fields_frame = ctk.CTkFrame(self.sheet_frame, fg_color="transparent")
        self.fields_frame.pack(fill="x", padx=30, pady=(0, 30))
        self._current_row_frame = None

        self._refresh_canvas()

    def _on_canvas_configure(self, event):
        # Ajusta el ancho de la hoja al ancho del canvas
        w = max(event.width - 80, 500)
        self.canvas.itemconfig(self.sheet_window, width=w)
        self.canvas.coords(self.sheet_window, event.width // 2, 10)
        self._refresh_canvas()

    def _build_form_header(self):
        """Encabezado editable del formulario (logo, título, subtítulo)."""
        hdr = ctk.CTkFrame(self.sheet_frame, corner_radius=0,
                           fg_color=(self.title_color, self.title_color))
        hdr.pack(fill="x")

        top_row = ctk.CTkFrame(hdr, fg_color="transparent")
        top_row.pack(fill="x", padx=30, pady=(20, 4))

        ctk.CTkLabel(top_row, textvariable=self.form_title,
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="white").pack(side="left")

        # Botones de edición del header
        edit_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        edit_frame.pack(side="right")

        ctk.CTkButton(edit_frame, text="🎨 Color", width=80, height=28,
                      fg_color="#5B21B6", hover_color="#4C1D95",
                      font=ctk.CTkFont(size=11),
                      command=self._pick_title_color).pack(side="left", padx=4)

        ctk.CTkLabel(hdr, textvariable=self.form_subtitle,
                     font=ctk.CTkFont(size=13), text_color="#E2E8F0").pack(
            anchor="w", padx=30, pady=(0, 20))

    def _refresh_canvas(self):
        self.sheet_frame.update_idletasks()
        self.canvas.configure(
            scrollregion=(0, 0, self.canvas.winfo_width(),
                          self.sheet_frame.winfo_reqheight() + 40)
        )

    # ─── GESTIÓN DE CAMPOS ────────────────────────────────────────────────────
    def _add_field(self, ftype):
        field = FieldRow(ftype)
        self.fields.append(field)
        self._render_field(field)
        self._refresh_canvas()
        # Scroll al final
        self.after(100, lambda: self.canvas.yview_moveto(1.0))

    def _render_field(self, field: FieldRow):
        """Dibuja la tarjeta del campo en la hoja."""
        
        # Determinar el contenedor y argumentos de empaquetado para columnas
        if field.width_pct == 100:
            self._current_row_frame = None
            parent_frame = self.fields_frame
            pack_args = {"fill": "x", "pady": 6}
        else:
            if self._current_row_frame is None or len(self._current_row_frame.winfo_children()) >= 2:
                self._current_row_frame = ctk.CTkFrame(self.fields_frame, fg_color="transparent")
                self._current_row_frame.pack(fill="x", pady=6)
            parent_frame = self._current_row_frame
            pad_x = (0, 6) if len(self._current_row_frame.winfo_children()) == 0 else (6, 0)
            pack_args = {"side": "left", "fill": "both", "expand": True, "padx": pad_x}

        card = ctk.CTkFrame(parent_frame, corner_radius=8,
                            fg_color=("#F8FAFC", "#16213E"),
                            border_width=1,
                            border_color=("#E2E8F0", "#2D2D4A"))
        card.pack(**pack_args)

        # Header de la tarjeta
        ch = ctk.CTkFrame(card, fg_color="transparent")
        ch.pack(fill="x", padx=12, pady=(8, 4))

        icon  = FIELD_ICONS.get(field.ftype, "📝")
        label_display = FIELD_LABELS.get(field.ftype, "Campo")
        ctk.CTkLabel(ch, text=f"{icon}  {label_display}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=(ACCENT, "#A78BFA")).pack(side="left")

        # Botones de control
        ctrl = ctk.CTkFrame(ch, fg_color="transparent")
        ctrl.pack(side="right")

        ctk.CTkButton(ctrl, text="▲", width=28, height=24, fg_color="#1E293B",
                      command=lambda: self._move_field(field, -1),
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        ctk.CTkButton(ctrl, text="▼", width=28, height=24, fg_color="#1E293B",
                      command=lambda: self._move_field(field, 1),
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        ctk.CTkButton(ctrl, text="🗑", width=28, height=24,
                      fg_color="#7F1D1D", hover_color="#991B1B",
                      command=lambda: self._delete_field(field, card),
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=2)

        # Cuerpo de la tarjeta según tipo
        cb = ctk.CTkFrame(card, fg_color="transparent")
        cb.pack(fill="x", padx=12, pady=(0, 10))

        if field.ftype in (FIELD_DIVIDER,):
            ctk.CTkFrame(cb, height=2, fg_color=self.accent_color).pack(fill="x", pady=8)
            return

        if field.ftype == FIELD_HEADING:
            lv = ctk.StringVar(value=field.label)
            def upd_heading(v, f=field): f.label = v
            lv.trace_add("write", lambda *a, lv=lv, f=field: upd_heading(lv.get()))
            ctk.CTkEntry(cb, textvariable=lv, font=ctk.CTkFont(size=15, weight="bold"),
                         placeholder_text="Título de sección...",
                         fg_color="transparent", border_width=0).pack(fill="x")
            field.label = lv.get()
            return

        # Etiqueta del campo
        lrow = ctk.CTkFrame(cb, fg_color="transparent")
        lrow.pack(fill="x", pady=(0, 4))

        lv = ctk.StringVar(value=field.label)
        def upd_label(v, f=field): f.label = v
        lv.trace_add("write", lambda *a, lv=lv, f=field: upd_label(lv.get()))

        ctk.CTkEntry(lrow, textvariable=lv, placeholder_text="Etiqueta del campo",
                     width=240, height=30, font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 12))

        rv = ctk.BooleanVar(value=field.required)
        def upd_req(v=None, f=field, rv=rv): f.required = rv.get()
        ctk.CTkCheckBox(lrow, text="Requerido *", variable=rv,
                        command=upd_req, font=ctk.CTkFont(size=11),
                        checkbox_width=16, checkbox_height=16).pack(side="left")

        # Ajustes de disposición (Ancho y alto)
        layout_row = ctk.CTkFrame(cb, fg_color="transparent")
        layout_row.pack(fill="x", pady=(2, 6))
        
        ctk.CTkLabel(layout_row, text="Ancho:", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")
        wv = ctk.StringVar(value="100%" if field.width_pct == 100 else "50%")
        def upd_w(v, f=field): 
            f.width_pct = 100 if "100" in v else 50
            self.after(10, self._rebuild_fields)
        ctk.CTkComboBox(layout_row, values=["100%", "50%"], variable=wv, width=75, height=24, font=ctk.CTkFont(size=11), command=upd_w).pack(side="left", padx=(6, 16))

        if field.ftype == FIELD_TEXTAREA:
            ctk.CTkLabel(layout_row, text="Filas (altura):", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")
            hv = ctk.StringVar(value=str(getattr(field, 'height_lines', 4)))
            def upd_h(v, f=field):
                try: f.height_lines = int(v)
                except: pass
            ctk.CTkComboBox(layout_row, values=["2", "4", "6", "8", "12", "16"], variable=hv, width=65, height=24, font=ctk.CTkFont(size=11), command=upd_h).pack(side="left", padx=(6, 0))

        # Campo de vista previa
        if field.ftype in (FIELD_TEXT, FIELD_EMAIL, FIELD_PHONE, FIELD_DATE, FIELD_NUMBER):
            icons_ph = {FIELD_EMAIL: "usuario@correo.com",
                        FIELD_DATE:  "dd/mm/aaaa",
                        FIELD_PHONE: "+52 (555) 000-0000",
                        FIELD_NUMBER:"0"}
            ph = icons_ph.get(field.ftype, "Escribir aquí...")
            ctk.CTkEntry(cb, placeholder_text=ph, height=34,
                         fg_color=("#F1F5F9", "#0D0F1A"),
                         state="disabled").pack(fill="x", pady=(0, 2))

        elif field.ftype == FIELD_TEXTAREA:
            ctk.CTkTextbox(cb, height=70, fg_color=("#F1F5F9", "#0D0F1A"),
                           state="disabled").pack(fill="x", pady=(0, 2))

        elif field.ftype == FIELD_DROPDOWN:
            ov = ctk.StringVar(value=field.options)
            def upd_opts(v, f=field): f.options = v
            ov.trace_add("write", lambda *a, ov=ov, f=field: upd_opts(ov.get()))
            or_ = ctk.CTkFrame(cb, fg_color="transparent")
            or_.pack(fill="x")
            ctk.CTkLabel(or_, text="Opciones (separadas por coma):",
                         font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
            ctk.CTkEntry(or_, textvariable=ov, height=30).pack(fill="x")
            # Preview
            opts = [o.strip() for o in field.options.split(",")]
            ctk.CTkComboBox(cb, values=opts, state="readonly",
                            fg_color=("#F1F5F9", "#0D0F1A")).pack(anchor="w", pady=(4, 0))

        elif field.ftype in (FIELD_CHECKBOX, FIELD_RADIO):
            ov = ctk.StringVar(value=field.options)
            def upd_opts(v, f=field): f.options = v
            ov.trace_add("write", lambda *a, ov=ov, f=field: upd_opts(ov.get()))
            or_ = ctk.CTkFrame(cb, fg_color="transparent")
            or_.pack(fill="x")
            ctk.CTkLabel(or_, text="Opciones (separadas por coma):",
                         font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
            ctk.CTkEntry(or_, textvariable=ov, height=30).pack(fill="x")
            # Preview
            opts_row = ctk.CTkFrame(cb, fg_color="transparent")
            opts_row.pack(fill="x", pady=(4, 0))
            for opt in [o.strip() for o in field.options.split(",")][:4]:
                if field.ftype == FIELD_CHECKBOX:
                    ctk.CTkCheckBox(opts_row, text=opt, state="disabled",
                                    font=ctk.CTkFont(size=11)).pack(anchor="w", pady=1)
                else:
                    ctk.CTkRadioButton(opts_row, text=opt, state="disabled",
                                       font=ctk.CTkFont(size=11), value=opt,
                                       variable=ctk.StringVar()).pack(anchor="w", pady=1)

        elif field.ftype == FIELD_SIGNATURE:
            zone = ctk.CTkFrame(cb, height=70, corner_radius=6,
                                fg_color=("#F8FAFC", "#0D1117"),
                                border_width=1, border_color=ACCENT)
            zone.pack(fill="x")
            zone.pack_propagate(False)
            ctk.CTkLabel(zone, text="✍️  Zona de firma",
                         text_color=ACCENT,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(expand=True)

        elif field.ftype == FIELD_PHOTO:
            zone = ctk.CTkFrame(cb, height=90, corner_radius=6,
                                fg_color=("#F0F4FF", "#0D1117"),
                                border_width=1, border_color=ACCENT)
            zone.pack(fill="x")
            zone.pack_propagate(False)
            ctk.CTkLabel(zone, text="📷  Zona de foto del participante",
                         text_color=ACCENT,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(expand=True)

        field._card = card  # guardar referencia

    def _move_field(self, field: FieldRow, direction: int):
        idx = self.fields.index(field)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.fields):
            self.fields[idx], self.fields[new_idx] = self.fields[new_idx], self.fields[idx]
            self._rebuild_fields()

    def _delete_field(self, field: FieldRow, card):
        if field in self.fields:
            self.fields.remove(field)
        card.destroy()
        self._refresh_canvas()

    def _rebuild_fields(self):
        """Redibuja todos los campos en el orden correcto."""
        for w in self.fields_frame.winfo_children():
            w.destroy()
        self._current_row_frame = None
        fields_copy = list(self.fields)
        self.fields.clear()
        for f in fields_copy:
            self.fields.append(f)
            self._render_field(f)
        self._refresh_canvas()

    def _clear_all(self):
        if self.fields and messagebox.askyesno("Limpiar", "¿Eliminar todos los campos?"):
            self.fields.clear()
            for w in self.fields_frame.winfo_children():
                w.destroy()
            self._refresh_canvas()

    def _pick_title_color(self):
        c = colorchooser.askcolor(self.title_color, title="Color del encabezado")[1]
        if c:
            self.title_color = c

    # ─── EXPORTACIÓN ─────────────────────────────────────────────────────────
    def _export(self):
        if not HAS_RL:
            messagebox.showerror("Error", "Falta: pip install reportlab")
            return
        if not self.fields:
            messagebox.showwarning("Sin campos", "Agrega al menos un campo al formulario.")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Interactivo", "*.pdf")],
            title="Guardar formulario PDF como..."
        )
        if not dest: return
        threading.Thread(target=self._do_export, args=(dest,), daemon=True).start()

    def _do_export(self, dest):
        try:
            page_size = A4 if self.page_size_var.get() == "A4" else letter
            c = rl_canvas.Canvas(dest, pagesize=page_size)
            pw, ph = page_size
            y = ph - 20

            # ── Encabezado ──────────────────────────────────────────────────
            def hex_to_rgb(h):
                h = h.lstrip("#")
                return tuple(int(h[i:i+2], 16)/255 for i in (0, 2, 4))

            r, g, b = hex_to_rgb(self.title_color)
            c.setFillColorRGB(r, g, b)
            c.rect(0, ph - 100, pw, 100, fill=1, stroke=0)

            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 22)
            c.drawString(40, ph - 50, self.form_title.get())
            c.setFont("Helvetica", 11)
            c.setFillColorRGB(0.9, 0.9, 0.95)
            c.drawString(40, ph - 72, self.form_subtitle.get())

            y = ph - 120

            # ── Campos ──────────────────────────────────────────────────────
            margin_left = 40
            total_content_w = pw - 80
            GAP = 18

            def check_page_break(needed=50):
                nonlocal y, c
                if y - needed < 40:
                    c.setFont("Helvetica", 7)
                    c.setFillColorRGB(0.6, 0.6, 0.6)
                    c.drawString(40, 20, f"Formulario: {self.form_title.get()} — PowerSuite Pro")
                    c.showPage()
                    c.setFillColorRGB(r, g, b)
                    c.rect(0, ph - 36, pw, 36, fill=1, stroke=0)
                    c.setFillColorRGB(1, 1, 1)
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(40, ph - 24, self.form_title.get() + "  (continuación)")
                    y = ph - 56

            current_x = margin_left
            row_max_h = 0
            
            for field in self.fields:
                
                # Resolviendo si el campo cabe en la fila actual o baja
                is_half = (field.width_pct == 50)
                field_w = total_content_w if not is_half else (total_content_w / 2 - 10)
                
                # Calculando altura que ocuparía el campo
                field_h = 22
                if field.ftype == FIELD_TEXTAREA:
                    field_h = getattr(field, 'height_lines', 4) * 14 + 10
                elif field.ftype in (FIELD_SIGNATURE, FIELD_PHOTO):
                    field_h = 70
                elif field.ftype in (FIELD_CHECKBOX, FIELD_RADIO):
                    n_opts = len([o.strip() for o in field.options.split(",") if o.strip()])
                    field_h = n_opts * 18 + 8
                elif field.ftype == FIELD_HEADING:
                    field_h = 30
                elif field.ftype == FIELD_DIVIDER:
                    field_h = 10

                total_h = field_h + 20 # campo + label
                
                # Forzar salto de línea si no es 50%, o si ya hay algo en la derecha
                if not is_half or current_x > margin_left + 10:
                    # Si ya había algo en la línea, bajar `y` con el `row_max_h`
                    if current_x > margin_left:
                        y -= (row_max_h + GAP + 8)
                        current_x = margin_left
                        row_max_h = 0
                        
                check_page_break(total_h + 10)
                
                # Actualizar el máximo de la fila
                row_max_h = max(row_max_h, total_h)

                if field.ftype == FIELD_DIVIDER:
                    y_div = y - 10
                    c.setStrokeColorRGB(r, g, b)
                    c.setLineWidth(1.5)
                    c.line(current_x, y_div, current_x + field_w, y_div)
                    # Al ser un divisor, forzar salto inmediato
                    y -= (field_h + GAP)
                    current_x = margin_left
                    row_max_h = 0
                    continue

                if field.ftype == FIELD_HEADING:
                    c.setFont("Helvetica-Bold", 15)
                    c.setFillColorRGB(r, g, b)
                    # Background para headings
                    c.rect(current_x, y - 24, field_w, 28, fill=1, stroke=0)
                    c.setFillColorRGB(1, 1, 1)
                    c.drawString(current_x + 6, y - 16, field.label)
                    # Forcemos salto de línea tras heading
                    y -= (field_h + GAP)
                    current_x = margin_left
                    row_max_h = 0
                    continue

                # Etiqueta
                label_text = field.label + (" *" if field.required else "")
                c.setFont("Helvetica-Bold", 10)
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.drawString(current_x, y, label_text)
                fy = y - 16

                # Fondo del campo
                c.setFillColorRGB(0.97, 0.97, 1.0)
                c.setStrokeColorRGB(r, g, b)
                c.setLineWidth(0.8)
                c.roundRect(current_x, fy - field_h, field_w, field_h, 4, fill=1, stroke=1)

                field_name = f"{field.ftype}_{field.uid}"

                # AcroForm
                if field.ftype in (FIELD_TEXT, FIELD_EMAIL, FIELD_PHONE, FIELD_DATE, FIELD_NUMBER):
                    c.acroForm.textfield(
                        name=field_name, tooltip=field.label,
                        x=current_x, y=fy - field_h,
                        width=field_w, height=field_h,
                        fontSize=10,
                        borderColor=rl_colors.Color(r, g, b),
                        fillColor=rl_colors.Color(0.97, 0.97, 1.0)
                    )

                elif field.ftype == FIELD_TEXTAREA:
                    c.acroForm.textfield(
                        name=field_name, tooltip=field.label,
                        x=current_x, y=fy - field_h,
                        width=field_w, height=field_h,
                        fontSize=10, isMultiLine=True,
                        borderColor=rl_colors.Color(r, g, b),
                        fillColor=rl_colors.Color(0.97, 0.97, 1.0)
                    )

                elif field.ftype == FIELD_DROPDOWN:
                    opts = [o.strip() for o in field.options.split(",") if o.strip()]
                    c.acroForm.choice(
                        name=field_name, tooltip=field.label,
                        x=current_x, y=fy - field_h,
                        width=field_w, height=field_h,
                        options=opts, value=opts[0] if opts else "",
                        borderColor=rl_colors.Color(r, g, b)
                    )

                elif field.ftype == FIELD_CHECKBOX:
                    opts = [o.strip() for o in field.options.split(",") if o.strip()]
                    cy_inner = fy - 12
                    for opt in opts:
                        c.acroForm.checkbox(
                            name=f"{field_name}_{opt.replace(' ', '_')}",
                            tooltip=opt,
                            x=current_x + 8, y=cy_inner - 10,
                            buttonStyle="check", size=12,
                            fillColor=rl_colors.Color(0.97, 0.97, 1.0),
                            borderColor=rl_colors.Color(r, g, b)
                        )
                        c.setFont("Helvetica", 10)
                        c.setFillColorRGB(0.2, 0.2, 0.2)
                        c.drawString(current_x + 26, cy_inner - 4, opt)
                        cy_inner -= 18

                elif field.ftype == FIELD_RADIO:
                    opts = [o.strip() for o in field.options.split(",") if o.strip()]
                    cy_inner = fy - 12
                    for opt in opts:
                        c.acroForm.radio(
                            name=field_name,
                            tooltip=opt, value=opt,
                            x=current_x + 8, y=cy_inner - 10,
                            buttonStyle="circle", size=12,
                            fillColor=rl_colors.Color(0.97, 0.97, 1.0),
                            borderColor=rl_colors.Color(r, g, b)
                        )
                        c.setFont("Helvetica", 10)
                        c.setFillColorRGB(0.2, 0.2, 0.2)
                        c.drawString(current_x + 26, cy_inner - 4, opt)
                        cy_inner -= 18

                elif field.ftype == FIELD_SIGNATURE:
                    c.setFillColorRGB(r, g, b)
                    c.setFont("Helvetica-Bold", 9)
                    c.drawCentredString(
                        current_x + field_w / 2, fy - field_h / 2,
                        "✍️   Firma aquí"
                    )
                    c.acroForm.textfield(
                        name=field_name, tooltip="Firma",
                        x=current_x, y=fy - field_h,
                        width=field_w, height=field_h, fontSize=8,
                        borderColor=rl_colors.Color(r, g, b),
                        fillColor=rl_colors.Color(0.97, 0.97, 1.0)
                    )

                elif field.ftype == FIELD_PHOTO:
                    c.setFillColorRGB(r, g, b)
                    c.setFont("Helvetica-Bold", 9)
                    c.drawCentredString(
                        current_x + field_w / 2, fy - field_h / 2,
                        "📷   Adjuntar foto aquí"
                    )
                    c.acroForm.textfield(
                        name=field_name, tooltip="Foto",
                        x=current_x, y=fy - field_h,
                        width=field_w, height=field_h, fontSize=8,
                        borderColor=rl_colors.Color(r, g, b),
                        fillColor=rl_colors.Color(0.97, 0.97, 1.0)
                    )

                # Mover el cursor X a la derecha o saltar de línea
                if is_half and current_x == margin_left:
                    # El campo se colocó en la mitad izquierda, movemos X a la derecha
                    current_x = margin_left + field_w + 20
                else:
                    # El campo ocupa toda una línea o la mitad derecha, forzamos salto
                    y -= (row_max_h + GAP + 8)
                    current_x = margin_left
                    row_max_h = 0
                    
            # Si sobró algo en row_max_h y nadie le dio salto
            if current_x > margin_left:
                y -= (row_max_h + GAP + 8)

            # Pie de página
            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.drawString(40, 20,
                         f"Formulario: {self.form_title.get()} "
                         f"— Generado con PowerSuite Pro — {datetime.now().strftime('%d/%m/%Y %H:%M')}")

            c.save()

            self.after(0, lambda: messagebox.showinfo(
                "✅ Formulario exportado",
                f"Archivo guardado:\n{Path(dest).name}\n\n"
                f"Ábrelo en Adobe Reader o Foxit Reader para llenarlo digitalmente."
            ))
            try:
                os.startfile(dest)
            except:
                pass

        except Exception as e:
            import traceback
            self.after(0, lambda: messagebox.showerror("Error de exportación", str(e)))


if __name__ == "__main__":
    app = PDFFormBuilder()
    app.mainloop()
