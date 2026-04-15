#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smart_modals.py v4.1
💎 Minimalist Flat UI Modals — PowerSuite Pro
Uso del icono oficial powersuite.ico para la identidad del sistema.
Layout optimizado para evitar recortes y centrado perfecto.
"""

import sys, os
try:
    import customtkinter as ctk
    import tkinter as tk
    from PIL import Image, ImageDraw
except ImportError:
    print("Falta customtkinter o Pillow."); sys.exit(1)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SmartModal(ctk.CTkToplevel):
    """Ventana modal minimalista con estética Pro y bordes ultra-finos."""
    def __init__(self, parent, title, message, icon_type="info", color="#6366F1", show_cancel=True, callback=None):
        super().__init__(parent)
        self.title("")
        self.width = 500
        self.height = 430 
        self.geometry(f"{self.width}x{self.height}")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # --- TRUCO DE TRANSPARENCIA PARA ESQUINAS REDONDEADAS ---
        # Definimos un color "mágico" que el sistema hará invisible.
        self.bg_color = "#000001" 
        self.configure(fg_color=self.bg_color)
        self.wm_attributes("-transparentcolor", self.bg_color)
        
        self.callback = callback
        self.result = False
        
        # Mapeo de iconos
        icon_map = {
            "warning": "flat_warning.png",
            "shredder": "flat_shredder.png",
            "success": "flat_success.png",
            "diamond": "powersuite.ico",
            "info": "powersuite.ico"
        }
        
        img_file = icon_map.get(icon_type, "powersuite.ico")
        img_path = resource_path(img_file)
        
        # Centrado perfecto en pantalla
        self.update_idletasks()
        try:
            parent.update_idletasks()
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.width // 2)
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.height // 2)
        except:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            px, py = (sw-self.width)//2, (sh-self.height)//2
        self.geometry(f"{self.width}x{self.height}+{px}+{py}")

        # --- CONTENEDOR PRINCIPAL REDONDEADO ---
        self.main_f = ctk.CTkFrame(self, corner_radius=28, fg_color="#0F172A", 
                                   border_width=1, border_color=color)
        self.main_f.pack(fill="both", expand=True)

        # Icon Container (Glow suave)
        icon_bg = ctk.CTkFrame(self.main_f, width=120, height=120, corner_radius=60, 
                               fg_color=("#F8FAFC", "#1E293B"), border_width=0)
        icon_bg.pack(pady=(45, 15))
        icon_bg.pack_propagate(False)

        # --- PROCESAMIENTO DE ICONO PREMIUM (Recorte Circular) ---
        if os.path.exists(img_path):
            try:
                pil_img = Image.open(img_path).convert("RGBA")
                # Crear máscara circular para eliminar "picos" blancos o fondos cuadrados
                size = (200, 200) # Alta res para el proceso
                pil_img = pil_img.resize(size, Image.LANCZOS)
                
                mask = Image.new('L', size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0], size[1]), fill=255)
                
                # Aplicar máscara
                output = Image.new('RGBA', size, (0,0,0,0))
                output.paste(pil_img, (0,0), mask)
                
                # Convertir a CTkImage
                ctk_img = ctk.CTkImage(light_image=output, dark_image=output, size=(90, 90))
                ctk.CTkLabel(icon_bg, text="", image=ctk_img, fg_color="transparent").pack(expand=True)
            except Exception as e:
                print(f"Error procesando icono: {e}")
                ctk.CTkLabel(icon_bg, text="💎", font=ctk.CTkFont(size=50), fg_color="transparent").pack(expand=True)
        else:
            ctk.CTkLabel(icon_bg, text="⚡", font=ctk.CTkFont(size=50), fg_color="transparent").pack(expand=True)

        # Título y Mensaje con jerarquía clara
        ctk.CTkLabel(self.main_f, text=title.upper(), font=ctk.CTkFont(size=22, weight="bold"), text_color="white").pack()
        
        msg_f = ctk.CTkFrame(self.main_f, fg_color="transparent")
        msg_f.pack(fill="both", expand=True, padx=40, pady=(10, 20))
        
        self.msg_lbl = ctk.CTkLabel(msg_f, text=message, font=ctk.CTkFont(size=14), 
                                   text_color="#94A3B8", wraplength=420, justify="center")
        self.msg_lbl.pack(expand=True)

        # Barra de Acciones (Diseño limpio inferior)
        action_bar = ctk.CTkFrame(self.main_f, fg_color="transparent")
        action_bar.pack(fill="x", side="bottom", pady=(0, 40), padx=40)

        if show_cancel:
            self.no_btn = ctk.CTkButton(action_bar, text="CANCELAR", height=50, corner_radius=14, 
                                        fg_color="#1E293B", hover_color="#334155", font=ctk.CTkFont(size=13, weight="bold"),
                                        command=self._on_no)
            self.no_btn.pack(side="left", fill="x", expand=True, padx=(0, 15))

        self.confirm_btn = ctk.CTkButton(action_bar, text="ENTENDIDO", height=50, corner_radius=14,
                                         fg_color=color, hover_color=color, font=ctk.CTkFont(size=13, weight="bold"),
                                         command=self._on_yes)
        self.confirm_btn.pack(side="left", fill="x", expand=True)

        # Asegurar foco
        self.grab_set()

    def _on_yes(self): self.result = True; self._close()
    def _on_no(self): self.result = False; self._close()
    def _close(self):
        self.grab_release()
        self.destroy()
        if self.callback: 
            self.callback(self.result)

# Funciones globales mejoradas
def ask_confirm(parent, title, message, type="info", color="#6366F1"):
    m = SmartModal(parent, title, message, icon_type=type, color=color, show_cancel=True)
    parent.wait_window(m)
    return m.result

def show_success(parent, title, message):
    m = SmartModal(parent, title, message, icon_type="success", color="#10B981", show_cancel=False)
    parent.wait_window(m)

def show_error(parent, title, message):
    m = SmartModal(parent, title, message, icon_type="warning", color="#EF4444", show_cancel=False)
    parent.wait_window(m)
