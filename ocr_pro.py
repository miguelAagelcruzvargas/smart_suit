#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr_pro.py v3.0
🔍 OCR Scanner Pro — PowerSuite Pro
Extractor de texto con doble motor: 
1. ✨ IA Vision (GPT-4o / Llama-3-Vision) para precisión del 99%.
2. 🤖 Tesseract OCR (Offline) para escaneos rápidos y locales.
"""

import sys, os
import threading
import argparse
from pathlib import Path

try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    import pytesseract
    import numpy as np
except ImportError:
    print("Faltan dependencias (customtkinter, Pillow, pytesseract, numpy)"); sys.exit(1)

# Configuración de Tesseract
TESS_PATHS = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Tesseract-OCR', 'tesseract.exe'),
]

HAS_TESSERACT = False
for p in TESS_PATHS:
    if os.path.exists(p):
        pytesseract.pytesseract.tesseract_cmd = p
        break

try:
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
except:
    HAS_TESSERACT = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class OCRProApp(ctk.CTk):
    def __init__(self, ai_key="", ai_provider="", ai_model=""):
        super().__init__()
        self.title("🔍 OCR Scanner Pro — PowerSuite Pro v3.0")
        self.geometry("1000x750")
        
        self.ai_key = ai_key
        self.ai_provider = ai_provider
        self.ai_model = ai_model
        
        # Icono
        try:
            ico_path = resource_path("powersuite.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except: pass

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1000x750+{(sw-1000)//2}+{(sh-750)//2}")

        self.file_path = None

        # Header
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=20, pady=(20, 15))
        ctk.CTkLabel(h, text="🔍 OCR Scanner Pro v3.0", font=ctk.CTkFont(size=28, weight="bold"), text_color="#A78BFA").pack(anchor="w")
        
        sub_text = "Extracción de texto con DOBLE MOTOR (IA + Tesseract)."
        if self.ai_key:
            sub_text += f" ✨ IA ACTIVADA ({self.ai_provider})"
        
        ctk.CTkLabel(h, text=sub_text, font=ctk.CTkFont(size=14), text_color="gray").pack(anchor="w")

        # Layout
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_columnconfigure(1, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Left: Preview
        self.left = ctk.CTkFrame(self.main, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"))
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        self.preview_lbl = ctk.CTkLabel(self.left, text="Selecciona una imagen\npara escanear texto", font=ctk.CTkFont(size=14))
        self.preview_lbl.pack(expand=True, padx=20, pady=20)
        
        self.btn_browse = ctk.CTkButton(self.left, text="📸 Seleccionar Imagen", height=45, font=ctk.CTkFont(weight="bold"), fg_color="#8B5CF6", hover_color="#7C3AED", command=self._browse)
        self.btn_browse.pack(fill="x", padx=30, pady=(0, 20))

        # Right: Result
        self.right = ctk.CTkFrame(self.main, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"))
        self.right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        ctk.CTkLabel(self.right, text="📝 Texto Extraído:", font=ctk.CTkFont(weight="bold"), text_color="gray").pack(anchor="w", padx=20, pady=(15, 5))
        
        txt_f = ctk.CTkFrame(self.right, fg_color=("#F8FAFC", "#0D0F1A"), corner_radius=12)
        txt_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        is_dark = ctk.get_appearance_mode() == "Dark"
        self.result_text = tk.Text(txt_f, bg="#0D0F1A" if is_dark else "#F8FAFC",
                                   fg="#E2E8F0" if is_dark else "#1E293B",
                                   font=("Segoe UI", 14), wrap="word", relief="flat", bd=0, padx=15, pady=15,
                                   insertbackground="#A78BFA")
        
        sb = ctk.CTkScrollbar(txt_f, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=3, pady=3)
        self.result_text.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=3)

        # Bottom Actions
        self.bottom = ctk.CTkFrame(self, height=80, fg_color="transparent")
        self.bottom.pack(fill="x", padx=20, pady=(0, 20))
        
        btn_text = "✨ ESCANEAR CON IA (VISIÓN)" if self.ai_key else "🔍 ESCANEAR CON TESSERACT"
        self.btn_ocr = ctk.CTkButton(self.bottom, text=btn_text, height=55, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#7C3AED", hover_color="#6D28D9", command=self._start)
        self.btn_ocr.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(self.bottom, text="📋 Copiar al Portapapeles", width=220, height=55, font=ctk.CTkFont(size=14, weight="bold"), fg_color="#4F46E5", command=self._copy).pack(side="right")

    def _browse(self):
        f = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if f:
            self.file_path = f
            try:
                img = Image.open(f)
                img_prev = img.copy()
                img_prev.thumbnail((450, 450))
                ctk_img = ctk.CTkImage(light_image=img_prev, dark_image=img_prev, size=(img_prev.width, img_prev.height))
                self.preview_lbl.configure(text="", image=ctk_img)
                self.preview_lbl._ctk_img = ctk_img
            except: pass

    def _copy(self):
        text = self.result_text.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copiado", "Texto copiado al portapapeles.")

    def _start(self):
        if not self.file_path: return
        if self.ai_key:
            self._run_ai_vision()
        else:
            self.btn_ocr.configure(state="disabled", text="Escanenado...")
            threading.Thread(target=self._run_tesseract, daemon=True).start()

    def _run_ai_vision(self):
        self.btn_ocr.configure(state="disabled", text="✨ Procesando con IA...")
        threading.Thread(target=self._do_ai_vision, daemon=True).start()

    def _do_ai_vision(self):
        try:
            import base64, requests, json
            with open(self.file_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            url = "https://api.groq.com/openai/v1/chat/completions"
            if "deepseek" in self.ai_provider.lower(): url = "https://api.deepseek.com/v1/chat/completions"
            elif "openrouter" in self.ai_provider.lower(): url = "https://openrouter.ai/api/v1/chat/completions"
            
            prompt = "Extrae TODO el texto de la imagen exactamente como aparece, pero DALE FORMATO. " \
                     "Usa Markdown estructurado: emplea # y ## para Títulos, **negritas** para textos importantes, " \
                     "y respeta los párrafos. El idioma es ESPAÑOL. Devuelve SOLO el contenido formateado y nada más."
            
            headers = {"Authorization": f"Bearer {self.ai_key}", "Content-Type": "application/json"}
            
            # IA: Elegir modelo con Vision
            model = self.ai_model
            if "vision" not in model.lower() and "gpt-4o" not in model.lower():
                model = "llama-3.2-11b-vision-preview" # Fallback a vision de groq
                
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }],
                "temperature": 0.1
            }
            res = requests.post(url, headers=headers, json=payload, timeout=45)
            if res.status_code == 200:
                result = res.json()['choices'][0]['message']['content']
                self._update_result(result)
            else:
                self._update_result(f"Error API IA: {res.text}\n\nReintentando con motor local...")
                self._run_tesseract()
        except Exception as e:
            self._update_result(f"Error IA: {e}\n\nUsando motor local...")
            self._run_tesseract()
        finally:
            self.after(0, lambda: self.btn_ocr.configure(state="normal", text="✨ ESCANEAR CON IA (VISIÓN)"))

    def _run_tesseract(self):
        if not HAS_TESSERACT:
            self._update_result("❌ ERROR CRÍTICO:\n\nTu modelo de IA actual NO soporta imágenes (Visión) y Tesseract OCR local no está instalado en este equipo.\n\nPara solucionarlo:\n1. Ve a Configuración de IA y usa un modelo como `gpt-4o`, `gemini-1.5-flash` o `llama-3.2-11b-vision-preview`.\n2. O instala Tesseract localmente desde el Diagnóstico de Salud.")
            self.after(0, lambda: self.btn_ocr.configure(state="normal", text="🔍 ESCRIBE MODELO IA CON VISIÓN"))
            return
            
        try:
            img = Image.open(self.file_path)
            img = ImageOps.grayscale(img)
            img = ImageEnhance.Contrast(img).enhance(1.8)
            
            try:
                text = pytesseract.image_to_string(img, lang="spa+eng", config='--oem 1 --psm 3')
            except:
                text = pytesseract.image_to_string(img)
                
            if not text.strip():
                text = "⚠️ Tesseract no pudo encontrar ningún texto en la imagen."
            self._update_result(text)
        except Exception as e:
            self._update_result(f"❌ Error interno de OCR Local:\n{str(e)}")
        finally:
            self.after(0, lambda: self.btn_ocr.configure(state="normal", text="🔍 ESCANEAR CON TESSERACT"))

    def _update_result(self, text):
        self.after(0, lambda: self._do_update(text))

    def _do_update(self, text):
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        
        # Tema de colores
        is_dark = ctk.get_appearance_mode() == "Dark"
        h1_color = "#A78BFA" if is_dark else "#6D28D9"
        h2_color = "#8B5CF6" if is_dark else "#5B21B6"
        err_color = "#EF4444" if is_dark else "#DC2626"
        fg_color = "#E2E8F0" if is_dark else "#1E293B"

        self.result_text.tag_config("h1", font=("Segoe UI", 22, "bold"), foreground=h1_color, spacing3=10)
        self.result_text.tag_config("h2", font=("Segoe UI", 18, "bold"), foreground=h2_color, spacing3=8)
        self.result_text.tag_config("bold", font=("Segoe UI", 14, "bold"), foreground=fg_color)
        self.result_text.tag_config("normal", font=("Segoe UI", 14), foreground=fg_color)
        self.result_text.tag_config("error", font=("Segoe UI", 15, "bold"), foreground=err_color)
        
        has_error = text.startswith("❌ ERROR") or text.startswith("⚠️")
        
        if has_error:
            self.result_text.insert("end", text, "error")
        else:
            lines = text.split('\n')
            for line in lines:
                if line.startswith('# '):
                    self.result_text.insert("end", line[2:] + "\n", "h1")
                elif line.startswith('## '):
                    self.result_text.insert("end", line[3:] + "\n", "h2")
                elif line.startswith('### '):
                    self.result_text.insert("end", line[4:] + "\n", "h2")
                else:
                    parts = line.split('**')
                    for i, part in enumerate(parts):
                        if i % 2 == 1:
                            self.result_text.insert("end", part, "bold")
                        else:
                            self.result_text.insert("end", part, "normal")
                    self.result_text.insert("end", "\n")
                    
        self.result_text.configure(state="disabled")
        
        # Popups
        if not has_error and text.strip():
            messagebox.showinfo("Extracción Exitosa", "🎉 El texto ha sido extraído correctamente y formateado.")
        elif has_error:
            messagebox.showwarning("Aviso de Extracción", "No se pudo extraer el texto o hubo un error con el motor.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    
    app = OCRProApp(ai_key=args.key, ai_provider=args.provider, ai_model=args.model)
    app.mainloop()