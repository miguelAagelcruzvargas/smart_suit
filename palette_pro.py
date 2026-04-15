#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
palette_pro.py v1.1
🎨 Extractor de Paleta de Colores Pro — PowerSuite Pro
ADN Visual de imágenes, sugerencia de tipografía y códigos Hex/RGB/Tailwind.
"""

import sys, os
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Falta customtkinter o Pillow"); sys.exit(1)

# ReportLab para exportación PDF
try:
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as r_colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def resource_path(relative_path):
    """Obtiene la ruta absoluta para recursos, compatible con PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PaletteProApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎨 Paleta de Colores Pro — PowerSuite Pro")
        self.geometry("1100x720")
        self.minsize(900, 600)
        
        # Icono
        try:
            ico_path = resource_path("powersuite.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except: pass

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1100x720+{(sw-1100)//2}+{(sh-720)//2}")

        self.file_path = None
        self.extracted_colors = [] # Almacenar (r,g,b,hex)

        # Header
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=15, pady=(15, 10))
        ctk.CTkLabel(h, text="🎨 Paleta de Colores Pro", font=ctk.CTkFont(size=28, weight="bold"), text_color="#EC4899").pack(anchor="w")
        ctk.CTkLabel(h, text="Extrae colores perfectos, sugerencias de tipografía y códigos CSS/Tailwind directos.", font=ctk.CTkFont(size=14), text_color="gray").pack(anchor="w")

        # Main Layout
        self.layout = ctk.CTkFrame(self, fg_color="transparent")
        self.layout.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.layout.grid_columnconfigure(0, weight=1)
        self.layout.grid_columnconfigure(1, weight=2)
        self.layout.grid_rowconfigure(0, weight=1)

        # Left: Image Selection & Actions
        self.left_panel = ctk.CTkFrame(self.layout, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"))
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        
        self.preview_lbl = ctk.CTkLabel(self.left_panel, text="📸 Selecciona una imagen\npara obtener su ADN visual", font=ctk.CTkFont(size=15))
        self.preview_lbl.pack(expand=True, padx=20, pady=20)
        
        ctk.CTkButton(self.left_panel, text="📁 Seleccionar Imagen", height=45, font=ctk.CTkFont(weight="bold"), fg_color="#EC4899", hover_color="#DB2777", command=self._browse).pack(pady=(0, 20), padx=30, fill="x")

        # Export Actions
        self.export_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.export_frame.pack(fill="x", padx=30, pady=(0, 30))
        self.export_frame.pack_forget() # Ocultar hasta procesar
        
        ctk.CTkLabel(self.export_frame, text="⚡ Exportar Resultados:", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(anchor="w", pady=(0, 10))
        
        btn_grid = ctk.CTkFrame(self.export_frame, fg_color="transparent")
        btn_grid.pack(fill="x")
        
        ctk.CTkButton(btn_grid, text="📄 Descargar PDF", height=40, font=ctk.CTkFont(weight="bold"), fg_color="#374151", hover_color="#10B981", command=self._export_pdf).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_grid, text="🖼️ Guardar Imagen", height=40, font=ctk.CTkFont(weight="bold"), fg_color="#374151", hover_color="#6366F1", command=self._export_image).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Right: Results Scroll
        self.right_panel = ctk.CTkScrollableFrame(self.layout, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"), label_text="Paleta Extraída")
        self.right_panel.grid(row=0, column=1, sticky="nsew")

    def _browse(self):
        f = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp")])
        if f:
            self.file_path = f
            try:
                img = Image.open(f)
                img.thumbnail((350, 350))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.preview_lbl.configure(text="", image=ctk_img)
                self.preview_lbl._ctk_image = ctk_img
                self._process_colors()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar la imagen:\n{e}")

    def _process_colors(self):
        if not self.file_path: return
        
        # Clear old results
        for w in self.right_panel.winfo_children(): w.destroy()
        self.extracted_colors = []
        
        try:
            img = Image.open(self.file_path).convert("RGB")
            # Reducir imagen para velocidad y generalizar colores
            img = img.resize((150, 150), Image.NEAREST)
            # Cuantizar a 10 colores para sacar el top 8
            quantized = img.quantize(colors=10, method=Image.Quantize.MEDIANCUT).convert("RGB")
            colors = quantized.getcolors(150*150)
            
            # Ordenar por frecuencia
            colors = sorted(colors, key=lambda x: x[0], reverse=True)
            unique_rgbs = [c[1] for c in colors]
            
            for index, (r, g, b) in enumerate(unique_rgbs[:8]):
                hex_c = f"#{r:02x}{g:02x}{b:02x}".upper()
                self.extracted_colors.append((r,g,b,hex_c))
                self._add_color_card(r, g, b, index)
            
            self.export_frame.pack(fill="x", padx=30, pady=(0, 30))
            
        except Exception as e:
            messagebox.showerror("Error IA", f"Error al procesar paleta:\n{e}")

    def _add_color_card(self, r, g, b, idx):
        hex_code = f"#{r:02x}{g:02x}{b:02x}".upper()
        # Calcular luminancia para contraste
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        text_color = "#FFFFFF" if lum < 0.55 else "#000000"
        
        card = ctk.CTkFrame(self.right_panel, fg_color=("#F3F4F6", "#0D0F1A"), height=140)
        card.pack(fill="x", pady=8, padx=10)
        
        # Color Box & Label
        left_f = ctk.CTkFrame(card, fg_color="transparent")
        left_f.pack(side="left", padx=15, pady=12)
        
        color_box = ctk.CTkFrame(left_f, width=70, height=70, fg_color=hex_code, corner_radius=10)
        color_box.pack()
        ctk.CTkLabel(color_box, text="ABC", font=ctk.CTkFont(size=14, weight="bold"), text_color=text_color).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(left_f, text=hex_code, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(5,0))

        # Snippets Section
        info_f = ctk.CTkFrame(card, fg_color="transparent")
        info_f.pack(side="left", fill="both", expand=True, padx=10, pady=12)
        
        suggest = "Texto blanco ideal" if lum < 0.55 else "Texto negro ideal"
        ctk.CTkLabel(info_f, text=f"💡 {suggest}", font=ctk.CTkFont(size=11), text_color="#A78BFA").pack(anchor="w", pady=(0,5))

        formats = [
            ("CSS", f"background-color: {hex_code};"),
            ("Tailwind", f"bg-[{hex_code}]"),
            ("RGB", f"rgb({r}, {g}, {b})")
        ]

        for label, val in formats:
            row = ctk.CTkFrame(info_f, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"{label}:", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray", width=60, anchor="w").pack(side="left")
            
            entry = ctk.CTkEntry(row, height=22, font=ctk.CTkFont(size=10, family="Consolas"), fg_color=("#E2E8F0", "#1C2033"), border_width=0)
            entry.insert(0, val)
            entry.configure(state="readonly")
            entry.pack(side="left", fill="x", expand=True, padx=5)
            
            ctk.CTkButton(row, text="📋", width=26, height=22, fg_color="#374151", hover_color="#6C63FF", 
                          command=lambda v=val: self._copy(v)).pack(side="right")

    def _copy(self, val):
        self.clipboard_clear()
        self.clipboard_append(val)

    def _export_pdf(self):
        if not self.extracted_colors: return
        if not HAS_REPORTLAB:
            return messagebox.showerror("Error", "No se encontró ReportLab para generar PDFs.")
            
        dest = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile=f"Paleta_{Path(self.file_path).stem}.pdf")
        if not dest: return
        
        try:
            c = pdf_canvas.Canvas(dest, pagesize=A4)
            w, h = A4
            
            # Header PDF
            c.setFillColor(r_colors.HexColor("#1C2033"))
            c.rect(0, h-100, w, 100, fill=True, stroke=False)
            
            c.setFillColor(r_colors.white)
            c.setFont("Helvetica-Bold", 24)
            c.drawString(40, h-50, "PowerSuite Pro — Paleta de Colores")
            c.setFont("Helvetica", 10)
            c.drawString(40, h-75, f"Generado desde: {Path(self.file_path).name} el {datetime.now().strftime('%d/%m/%Y')}")
            
            # Draw original image preview (optional, small)
            try:
                # c.drawImage(...) requiere fitz o similar para paths, o PIL directo
                pass
            except: pass
            
            # Colors
            y = h - 140
            for r, g, b, hex_c in self.extracted_colors:
                # Color swatch
                c.setFillColor(r_colors.HexColor(hex_c))
                c.roundRect(40, y-50, 60, 60, 8, fill=True, stroke=False)
                
                # Luminance for visual "ABC"
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                c.setFillColor(r_colors.white if lum < 0.55 else r_colors.black)
                c.setFont("Helvetica-Bold", 14)
                c.drawCentredString(70, y-25, "ABC")
                
                # Info
                c.setFillColor(r_colors.black)
                c.setFont("Helvetica-Bold", 16)
                c.drawString(120, y-15, f"{hex_c}")
                
                c.setFont("Helvetica", 10)
                c.setFillColor(r_colors.gray)
                c.drawString(120, y-32, f"CSS: background-color: {hex_c};")
                c.drawString(120, y-45, f"Tailwind: bg-[{hex_c}]  |  RGB: rgb({r},{g},{b})")
                
                y -= 85
                if y < 60:
                    c.showPage()
                    y = h - 60

            c.save()
            messagebox.showinfo("Éxito", f"Paleta guardada como PDF:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al exportar PDF: {e}")

    def _export_image(self):
        if not self.extracted_colors: return
        dest = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("Imagen PNG", "*.png"), ("Imagen JPG", ".*jpg")], initialfile=f"Paleta_{Path(self.file_path).stem}.png")
        if not dest: return
        
        try:
            # Crear lienzo (800x1000)
            canvas_w = 800
            canvas_h = 100 * len(self.extracted_colors) + 200
            img = Image.new("RGB", (canvas_w, canvas_h), "#0D0F1A")
            draw = ImageDraw.Draw(img)
            
            # Title
            draw.text((40, 40), "PowerSuite Pro — Paleta Extraída", fill="#EC4899")
            draw.text((40, 70), f"Basado en: {Path(self.file_path).name}", fill="#A78BFA")
            
            y = 130
            for r, g, b, hex_c in self.extracted_colors:
                # Rectángulo de color
                draw.rectangle([40, y, 140, y+80], fill=hex_c)
                # Info texto (simplificado para Pillow básico sin cargar ttf externas complejas)
                draw.text((160, y+5), f"HEX: {hex_c}", fill="white")
                draw.text((160, y+30), f"CSS: background-color: {hex_c};", fill="#94A3B8")
                draw.text((160, y+55), f"Tailwind: bg-[{hex_c}]", fill="#94A3B8")
                y += 100
                
            img.save(dest)
            messagebox.showinfo("Éxito", f"Paleta guardada como imagen:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al exportar imagen: {e}")

if __name__ == "__main__":
    app = PaletteProApp()
    app.mainloop()
