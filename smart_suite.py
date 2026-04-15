#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smart_suite.py
🧰 PowerSuite de Utilidades — Suite Completa Premium

Herramientas incluidas:
1. 🗂️ Organizador Inteligente
2. 🗑️ Trituradora Forense
3. 🗜️ Compresor ZIP
4. 🪄 Quita Fondos IA
5. 📥 Descargador Video/Audio
6. 🔄 Conversor de Imágenes
7. 📄 Suite PDF
8. 🔍 OCR Scanner
9. 🎨 Paleta de Colores Pro
"""

import sys
import subprocess
import threading
import queue
import time
import math
import os
import sqlite3
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque
import re
import socket
import urllib.request
import concurrent.futures

try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import smart_modals as sm
except ImportError:
    print("❌ Falta customtkinter.")
    sys.exit(1)

try:
    from smart_organizer import SmartOrganizer, format_size, sanitize_filename, get_file_hash
    from smart_organizer import DEFAULT_CATEGORIES
    CATEGORY_ICONS = {
        "images": "🖼️", "videos": "🎬", "audio": "🎵", "documents": "📄",
        "archives": "📦", "installers": "💻", "web": "🌐", "other": "🗃️"
    }
except ImportError:
    print("❌ No se encontró smart_organizer.py")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    pass


# ─── 🏛️ CLASES BASE UI ──────────────────────────────────────────────────────

class BaseToolView(ctk.CTkFrame):
    """Clase base para todas las herramientas de la suite."""
    def __init__(self, parent, master_app):
        super().__init__(parent, fg_color="transparent")
        self.master_app = master_app
    def ui_log(self, text, tag="info"): self.master_app._enqueue_log(text, tag)
    def ui_progress(self, val, text): self.master_app._enqueue_progress(val, text)
    def ui_done(self): self.master_app._enqueue_done()

# ─── 📦 CARGA SEGURA DE DEPENDENCIAS ──────────────────────────────────────────
# Intentamos cargar librerías opcionales sin romper el flujo principal.

yt_dlp = None
HAS_YTDLP = False
try:
    import yt_dlp
    HAS_YTDLP = True
except: pass

rembg = None
HAS_REMBG = False
try:
    import rembg
    HAS_REMBG = True
except: pass

PyPDF2 = None
HAS_PYPDF = False
try:
    import PyPDF2
    HAS_PYPDF = True
except: pass

pikepdf = None
HAS_PIKEPDF = False
try:
    import pikepdf
    HAS_PIKEPDF = True
except: pass

reportlab = None
HAS_REPORTLAB = False
try:
    import reportlab
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except: pass

pytesseract = None
HAS_TESSERACT = False
try:
    import pytesseract
    TESS_PATHS = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Tesseract-OCR', 'tesseract.exe'),
    ]
    for p in TESS_PATHS:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
except: pass

def safety_check_dependencies():
    """Mantenemos esta función por compatibilidad con el resto del código."""
    global HAS_REMBG, HAS_YTDLP, HAS_PYPDF, HAS_TESSERACT, HAS_REPORTLAB, HAS_PIKEPDF
    pass

# Llamada única de auditoría
safety_check_dependencies()

# ─── TEMA GLOBAL ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


# ─── UTILIDADES DE DISTRIBUCIÓN ────────────────────────────────────────────────
def resource_path(relative_path):
    """Obtiene la ruta absoluta para recursos, compatible con PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ─── COMPONENTES UI PREMIUM ───────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """Tarjeta de estadística con diseño premium y animaciones."""
    def __init__(self, parent, title: str, value: str = "0", icon: str = "📊", color: str = "#6C63FF", **kwargs):
        super().__init__(parent, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"), **kwargs)
        self._color = color

        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=16, pady=14)

        # Top row: icon
        top = ctk.CTkFrame(pad, fg_color="transparent")
        top.pack(fill="x", anchor="w")
        ctk.CTkLabel(top, text=icon, font=ctk.CTkFont(size=22)).pack(side="left")

        # Value
        self.value_lbl = ctk.CTkLabel(pad, text=value, font=ctk.CTkFont(size=28, weight="bold"), text_color=color)
        self.value_lbl.pack(anchor="w", pady=(8, 0))

        # Title
        ctk.CTkLabel(pad, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w")

    def update_value(self, val):
        self.value_lbl.configure(text=str(val))

    def animate_update(self, target):
        try:
            current = int(self.value_lbl.cget("text"))
            target = int(target)
        except Exception:
            self.update_value(target)
            return
        if current == target: return
        step = max(1, abs(target - current) // 8)
        new = current + step if target > current else current - step
        if abs(new - target) <= step: new = target
        self.value_lbl.configure(text=str(new))
        if new != target:
            self.after(35, lambda: self.animate_update(target))


# ─── GESTIÓN DE BASE DE DATOS (SQLITE) ───────────────────────────────────────

class HistoryManager:
    """Maneja la persistencia del historial y configuraciones SEGURAS en SQLite."""
    def __init__(self):
        self.db_path = Path("powersuite.db")
        # Generar llave de hardware única para cifrado local
        import uuid
        self._hw_key = str(uuid.getnode()) # Clave bloqueada a este PC
        self._init_db()

    def _encrypt(self, text):
        """Cifrado XOR + Base64 bloqueado por hardware."""
        import base64
        from itertools import cycle
        if not text: return ""
        # Proceso: XOR con la llave de hardware -> Base64
        res = ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(text, cycle(self._hw_key)))
        return base64.b64encode(res.encode()).decode()

    def _decrypt(self, encoded):
        """Descifrado inverso usando la llave de hardware."""
        import base64
        from itertools import cycle
        if not encoded: return ""
        try:
            decoded = base64.b64decode(encoded).decode()
            res = ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(decoded, cycle(self._hw_key)))
            return res
        except: return ""

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Historial de acciones
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        action TEXT,
                        details TEXT,
                        icon TEXT
                    )
                """)
                # Configuraciones globales (IA, etc). Nota: Los valores se guardan CIFRADOS.
                conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
                conn.commit()
        except: pass

    def get_setting(self, key, default=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
                res = cursor.fetchone()
                if res:
                    # Descifrar automáticamente al recuperar
                    return self._decrypt(res[0])
                return default
        except: return default

    def set_setting(self, key, value):
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Cifrar automáticamente al guardar
                encrypted_val = self._encrypt(str(value))
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, encrypted_val))
                conn.commit()
        except: pass

    def add_entry(self, action, details, icon="📝"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT INTO history (timestamp, action, details, icon) VALUES (?, ?, ?, ?)",
                            (ts, action, details, icon))
                conn.commit()
        except: pass

    def get_all(self, limit=100):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT timestamp, action, details, icon FROM history ORDER BY id DESC LIMIT ?", (limit,))
                return cursor.fetchall()
        except: return []

    def clear(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM history")
                conn.commit()
        except: pass


# ─── COMPONENTES UI ─────────────────────────────────────────────────────────

class LogPanel(ctk.CTkFrame):
    """Panel de log colapsable con colores y timestamp."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"), **kwargs)
        self._collapsed = True # Colapsado por defecto
        self._setup()
        # Iniciar en estado colapsado visualmente
        self._body.pack_forget()
        self._toggle_lbl.configure(text="▲ Expandir")
        self.configure(height=38)

    def _setup(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(header, text="📋  Registro en Vivo",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#5B5EA6", "#A78BFA")).pack(side="left")

        # Botón colapsar ▲ / ▼
        self._toggle_lbl = ctk.CTkLabel(
            header, text="▼ Contraer",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray", cursor="hand2"
        )
        self._toggle_lbl.pack(side="right", padx=(0, 12))
        self._toggle_lbl.bind("<Button-1>", lambda e: self._toggle())
        self._toggle_lbl.bind("<Enter>", lambda e: self._toggle_lbl.configure(text_color=("#6C63FF", "#A78BFA")))
        self._toggle_lbl.bind("<Leave>", lambda e: self._toggle_lbl.configure(text_color="gray"))

        clear_btn = ctk.CTkLabel(header, text="Limpiar",
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color="gray", cursor="hand2")
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self.clear())
        clear_btn.bind("<Enter>", lambda e: clear_btn.configure(text_color=("#6C63FF", "#A78BFA")))
        clear_btn.bind("<Leave>", lambda e: clear_btn.configure(text_color="gray"))

        # Frame del texto (se oculta al colapsar)
        self._body = tk.Frame(self, bg="#0D0F1A")
        self._body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.text = tk.Text(
            self._body, bg="#0D0F1A", fg="#CBD5E1", font=("Consolas", 10),
            wrap="word", state="disabled", relief="flat", bd=0, padx=12, pady=10,
            insertbackground="#6C63FF", selectbackground="#4F46E5",
        )
        sb = tk.Scrollbar(self._body, command=self.text.yview,
                          bg="#1C2033", troughcolor="#0D0F1A", relief="flat", bd=0)
        self.text.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        for tag, color in [
            ("success", "#10B981"), ("error",   "#EF4444"),
            ("warning", "#F59E0B"), ("info",    "#3B82F6"),
            ("muted",   "#64748B"), ("accent",  "#A78BFA"),
            ("time",    "#334155"),
        ]:
            self.text.tag_config(tag, foreground=color)

    def _toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._body.pack_forget()
            self._toggle_lbl.configure(text="▲ Expandir")
            self.configure(height=38)
        else:
            self._body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
            self._toggle_lbl.configure(text="▼ Contraer")
            self.configure(height=200)

    def log(self, message: str, tag: str = ""):
        self.text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] ", "time")
        self.text.insert("end", message + "\n", tag or "")
        self.text.see("end")
        self.text.config(state="disabled")
        
        # Auto-expandir SOLO si es un ERROR crítico
        if self._collapsed and tag == "error":
            self._toggle()

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


# ─── LÓGICA CORE ──────────────────────────────────────────────────────────────

class PatchedOrganizer(SmartOrganizer):
    def __init__(self, *args, log_cb=None, prog_cb=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_cb = log_cb or (lambda m, t="": None)
        self._prog_cb = prog_cb or (lambda v, l="": None)
        self.verbose = False
        
    def process(self):
        if not self.source.exists():
            self._log_cb(f"❌ Directorio no encontrado", "error")
            return self.stats
        items = list(self.source.iterdir())
        files = [f for f in items if f.is_file() and not self._should_ignore(f)]
        total = len(files)
        if total == 0:
            self._log_cb("ℹ️ No hay archivos válidos.", "info")
            return self.stats
        
        self._log_cb(f"📦 Encontrados {total} archivos", "info")
        for i, filepath in enumerate(files):
            self.stats["processed"] += 1
            self.stats["total_size"] += filepath.stat().st_size
            dest_dir = self._get_destination(filepath)
            dest_path = dest_dir / filepath.name
            
            final_dest = self._handle_duplicate_patched(filepath, dest_path)
            if final_dest is None:
                self.stats["skipped"] += 1
                self._log_cb(f"  ⏭ Omitido: {filepath.name}", "warning")
                continue
                
            if self._move_file_patched(filepath, final_dest):
                self.stats["moved"] += 1
                cat = final_dest.parent.name
                self.stats["by_category"][cat] += 1
                
            pct = ((i + 1) / total) * 100
            self._prog_cb(pct, f"Procesando: {filepath.name}")
        return self.stats

    def _move_file_patched(self, src: Path, dest: Path) -> bool:
        if dest.exists():
            counter = 1
            stem, suffix = dest.stem, dest.suffix
            while dest.exists():
                dest = dest.parent / f"{stem}_{counter}{suffix}"
                counter += 1
        try:
            if self.dry_run:
                try: rel = dest.relative_to(self.source)
                except ValueError: rel = dest.name
                self._log_cb(f"  [PREVIEW] {src.name} → {rel}", "muted")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                icon = CATEGORY_ICONS.get(dest.parent.name.lower(), "📄")
                try: rel = dest.relative_to(self.source)
                except ValueError: rel = dest.name
                self._log_cb(f"  {icon} {src.name} → {rel}", "success")
            return True
        except Exception as e:
            self._log_cb(f"  ❌ Error: {src.name}", "error")
            self.stats["errors"] += 1
            return False

    def _handle_duplicate_patched(self, filepath: Path, dest: Path):
        file_hash = get_file_hash(filepath)
        if not file_hash: return dest
        if file_hash in self.seen_hashes:
            self.stats["duplicates"] += 1
            if self.handle_duplicates == "skip":
                return None
            elif self.handle_duplicates == "rename":
                from datetime import datetime
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{filepath.stem}_dup_{stamp}{filepath.suffix}"
                return dest.parent / sanitize_filename(new_name)
            elif self.handle_duplicates == "backup":
                backup_dir = self.source / "_duplicates_backup"
                backup_dir.mkdir(exist_ok=True)
                new_dest = backup_dir / filepath.name
                counter = 1
                while new_dest.exists():
                    new_dest = backup_dir / f"{filepath.stem}_{counter}{filepath.suffix}"
                    counter += 1
                return new_dest
        self.seen_hashes[file_hash] = filepath
        return dest


class SecureShredder:
    @staticmethod
    def shred_file(filepath: Path, passes: int, prog_cb):
        if not filepath.exists() or not filepath.is_file(): return False
        file_size = filepath.stat().st_size
        chunk_size = 64 * 1024
        try:
            for p in range(passes):
                with open(filepath, "ba+", buffering=0) as f:
                    f.seek(0)
                    written = 0
                    last_update = 0
                    while written < file_size:
                        data = os.urandom(min(chunk_size, file_size - written))
                        f.write(data)
                        written += len(data)
                        
                        # IA: Throttling (Máximo 20 actualizaciones por segundo)
                        now = time.time()
                        if prog_cb and (now - last_update > 0.05):
                            prog_cb(((p * file_size + written) / (passes * file_size)) * 100, f"Destruyendo: Pase {p+1}/{passes}...")
                            last_update = now
                        
                        # Ceder tiempo al sistema para evitar congelamiento
                        time.sleep(0.0001)
            import random, string
            rand_name = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            dest = filepath.parent / rand_name
            os.rename(filepath, dest)
            os.remove(dest)
            return True
        except Exception as e:
            raise Exception(f"Fallo en {filepath.name}: {str(e)}")

class FileCompressor:
    @staticmethod
    def compress_items(source_paths: list[Path], dest_zip: Path, prog_cb):
        total_files = 0
        all_files = []
        for p in source_paths:
            if p.is_file():
                all_files.append((p, p.name))
                total_files += 1
            elif p.is_dir():
                for root, dirs, files in os.walk(p):
                    for f in files:
                        fp = Path(root) / f
                        all_files.append((fp, str(fp.relative_to(p.parent))))
                        total_files += 1
        if total_files == 0: raise Exception("Carpeta vacía.")
        with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, (fp, arcname) in enumerate(all_files):
                zf.write(fp, arcname)
                if prog_cb: prog_cb(((i + 1) / total_files) * 100, f"Zipiando {Path(arcname).name}...")

class BackgroundRemoverTool:
    @staticmethod
    def remove_background(img_path: Path, dest_dir: Path, prog_cb) -> Path:
        if not HAS_REMBG: raise ImportError("Falta rembg")
        dest_img = dest_dir / f"{img_path.stem}_nobg.png"
        if prog_cb: prog_cb(10, "Cargando píxeles...")
        input_image = Image.open(img_path)
        if prog_cb: prog_cb(40, "Calculando fondo con IA...")
        import rembg
        output_image = rembg.remove(input_image)
        if prog_cb: prog_cb(90, "Guardando transparencia...")
        output_image.save(dest_img, "PNG")
        if prog_cb: prog_cb(100, "¡Listo!")
        return dest_img


# ─── VISTAS DE PESTAÑAS ───────────────────────────────────────────────────────


# ─── VISTAS DE PESTAÑAS ───────────────────────────────────────────────────────


class ViewOrganizer(BaseToolView):
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        self.source_var = ctk.StringVar()
        self.org_mode = ctk.StringVar(value="type")
        self.dup_mode = ctk.StringVar(value="rename")
        self.dry_run = ctk.BooleanVar(value=False)

        # ====== 1. ROW DE STAT CARDS (Como te gustaba) ======
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 20))
        stats_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.stat_cards = {}
        for col, (title, icon, color) in enumerate([
            ("Procesados", "📋", "#3B82F6"),
            ("Movidos",    "✅", "#10B981"),
            ("Omitidos",   "⏭",  "#F59E0B"),
            ("Duplicados", "🔄", "#A78BFA"),
            ("Errores",    "❌", "#EF4444")
        ]):
            card = StatCard(stats_frame, title, "0", icon, color)
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col==0 else 10, 0))
            self.stat_cards[title] = card

        # ====== 2. CARD SETTINGS ======
        settings_card = ctk.CTkFrame(self, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        settings_card.pack(fill="x", pady=(0, 20))
        
        # Folder entry
        f_top = ctk.CTkFrame(settings_card, fg_color="transparent")
        f_top.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(f_top, text="Carpeta de Origen:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkEntry(f_top, textvariable=self.source_var, state="readonly", fg_color=("#F3F4F6", "#0D0F1A"), border_width=0, height=36).pack(side="left", fill="x", expand=True, padx=15)
        ctk.CTkButton(f_top, text="📂 Examinar", font=ctk.CTkFont(weight="bold"), height=36, corner_radius=8, command=self._browse).pack(side="left")

        # Configs grid
        f_mid = ctk.CTkFrame(settings_card, fg_color="transparent")
        f_mid.pack(fill="x", padx=20, pady=(10, 20))
        f_mid.grid_columnconfigure((0,1,2), weight=1)

        def make_radio_group(parent, col, title, var, options):
            cf = ctk.CTkFrame(parent, fg_color="transparent")
            cf.grid(row=0, column=col, sticky="nsew", padx=10)
            ctk.CTkLabel(cf, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(anchor="w", pady=(0, 10))
            for lbl, val in options:
                ctk.CTkRadioButton(cf, text=lbl, variable=var, value=val, font=ctk.CTkFont(size=13), radiobutton_width=18, radiobutton_height=18).pack(anchor="w", pady=6)

        make_radio_group(f_mid, 0, "🏷️ Estrategia", self.org_mode, [("Categoría de Archivo", "type"), ("Por Extensión (.pdf)", "extension"), ("Año / Mes", "date")])
        make_radio_group(f_mid, 1, "🔄 Si hay duplicados", self.dup_mode, [("Renombrar con fecha", "rename"), ("Omitir", "skip"), ("Mover a Backup", "backup")])
        
        c3 = ctk.CTkFrame(f_mid, fg_color="transparent")
        c3.grid(row=0, column=2, sticky="nsew", padx=10)
        ctk.CTkLabel(c3, text="⚙️ Opciones extras", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(anchor="w", pady=(0, 10))
        ctk.CTkSwitch(c3, text="Modo Simulación (Sin cambios)", variable=self.dry_run, font=ctk.CTkFont(size=13)).pack(anchor="w", pady=6)

        # ====== 3. ACCIÓN ======
        self.btn = ctk.CTkButton(self, text="▶ Iniciar Organización Automática", height=50, corner_radius=12, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#6C63FF", hover_color="#5B5EA6", command=self._start)
        self.btn.pack(fill="x")

    def _browse(self):
        f = filedialog.askdirectory(title="Seleccionar carpeta")
        if f: self.source_var.set(f)

    def _start(self):
        if not self.source_var.get():
            return messagebox.showerror("Error", "Selecciona una carpeta.")
        self.btn.configure(state="disabled")
        for c in self.stat_cards.values(): c.update_value("0")
        self.master_app._pulse_progress()
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        try:
            self.ui_log(f"🚀 Iniciando ({self.org_mode.get()})", "accent")
            org = PatchedOrganizer(source_dir=self.source_var.get(), organize_by=self.org_mode.get(), handle_duplicates=self.dup_mode.get(), dry_run=self.dry_run.get(), log_cb=self.ui_log, prog_cb=self.ui_progress)
            stats = org.process()
            self.master_app._log_queue.put(("stats", stats))
            self.ui_log(f"✅ ¡Finalizado con éxito!", "success")
            self.master_app.log_history("Organización", f"Carpeta: {Path(self.source_var.get()).name}", "🗂️")
            self.after(0, lambda: sm.show_success(self, "ORGANIZACIÓN COMPLETA", f"Los archivos de '{Path(self.source_var.get()).name}' han sido organizados correctamente."))
        except Exception as e:
            self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self.master_app._enqueue_done()
            self.btn.configure(state="normal")


class ViewShredder(BaseToolView):
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.files = []
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header, text="🗑️ Trituradora Forense", font=ctk.CTkFont(size=26, weight="bold"), text_color="#EF4444").pack(anchor="w")
        ctk.CTkLabel(header, text="Elimina archivos irreversiblemente sobreescribiéndolos. Ni el software del FBI los podrá recuperar.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")
        
        card = ctk.CTkFrame(self, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="both", expand=True, pady=(0, 20))
        
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=20)
        ctk.CTkButton(top, text="➕ Agregar Archivos", font=ctk.CTkFont(weight="bold"), fg_color="#3B82F6", command=self._add).pack(side="left", padx=(0, 10))
        ctk.CTkButton(top, text="Limpiar Lista", fg_color="gray", command=self._clear).pack(side="left")
        
        self.passes_var = ctk.IntVar(value=3)
        ctk.CTkComboBox(top, variable=self.passes_var, values=["1", "3", "7", "35"], width=70).pack(side="right")
        ctk.CTkLabel(top, text="Pases de Seguridad:").pack(side="right", padx=10)
        
        self.listbox = tk.Listbox(card, bg="#0D0F1A", fg="white", bd=0, highlightthickness=0, font=("Segoe UI", 11), selectbackground="#EF4444")
        self.listbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.btn = ctk.CTkButton(self, text="☢️ Triturar Definitivamente", height=50, fg_color="#DC2626", hover_color="#991B1B", font=ctk.CTkFont(size=16, weight="bold"), command=self._start)
        self.btn.pack(fill="x")

    def _add(self):
        for f in filedialog.askopenfilenames():
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", Path(f).name)
    def _clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")
    def _start(self):
        if not self.files: return
        msg = f"¿Eliminar IRREVERSIBLEMENTE {len(self.files)} archivos?\nEsta acción no se puede deshacer incluso con software forense."
        if sm.ask_confirm(self, "PELIGRO DE EXTERMINIO", msg, type="shredder", color="#EF4444"):
            self.btn.configure(state="disabled")
            threading.Thread(target=self._run, daemon=True).start()
    def _run(self):
        try:
            total = len(self.files)
            for i, f in enumerate(self.files):
                self.ui_log(f"☢️ Triturando: {Path(f).name}", "warning")
                SecureShredder.shred_file(Path(f), self.passes_var.get(), self.ui_progress)
                self.ui_progress(((i+1)/total)*100, f"Destruido {i+1}/{total}")
            self.ui_log(f"✅ ¡{total} archivos vaporizados!", "success")
            self.master_app.log_history("Trituradora", f"Vaporizados {total} archivos satisfactoriamente", "🗑️")
            self.after(0, lambda: sm.show_success(self, "DESTRUCCIÓN EXITOSA", f"¡Vaporizados {total} archivos del disco de forma irreversible!"))
        except Exception as e: self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self._clear()
            self.master_app._enqueue_done()
            self.btn.configure(state="normal")


class ViewCompressor(BaseToolView):
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.items = []
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="🗜️ Compresión Rápida", font=ctk.CTkFont(size=26, weight="bold"), text_color="#3B82F6").pack(anchor="w")
        
        card = ctk.CTkFrame(self, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="both", expand=True, pady=(0, 20))
        
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=20)
        ctk.CTkButton(top, text="📄 + Archivos", command=self._add_file).pack(side="left", padx=(0, 10))
        ctk.CTkButton(top, text="📁 + Carpeta", fg_color="#4F46E5", command=self._add_folder).pack(side="left", padx=(0, 10))
        ctk.CTkButton(top, text="Limpiar", fg_color="gray", command=self._clear).pack(side="left")
        
        self.listbox = tk.Listbox(card, bg="#0D0F1A", fg="white", bd=0, highlightthickness=0, font=("Segoe UI", 11), selectbackground="#3B82F6")
        self.listbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.btn = ctk.CTkButton(self, text="📦 Empaquetar en ZIP", height=50, fg_color="#2563EB", hover_color="#1D4ED8", font=ctk.CTkFont(size=16, weight="bold"), command=self._start)
        self.btn.pack(fill="x")

    def _add_file(self):
        for f in filedialog.askopenfilenames():
            if f not in self.items: self.items.append(f); self.listbox.insert("end", f"📄 {Path(f).name}")
    def _add_folder(self):
        f = filedialog.askdirectory()
        if f and f not in self.items: self.items.append(f); self.listbox.insert("end", f"📁 {Path(f).name}/")
    def _clear(self):
        self.items.clear()
        self.listbox.delete(0, "end")
    def _start(self):
        if not self.items: return
        # IA: Nombre inteligente basado en el primer item
        base_name = Path(self.items[0]).stem
        sfx = "-compressed" if len(self.items) == 1 else "-batch-compressed"
        init_f = f"{base_name}{sfx}.zip"
        
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip", 
            filetypes=[("ZIP", "*.zip")],
            initialfile=init_f,
            title="Guardar archivo comprimido como..."
        )
        if dest:
            self.btn.configure(state="disabled")
            threading.Thread(target=self._run, args=(dest,), daemon=True).start()
    def _run(self, dest):
        try:
            self.ui_log(f"🗜️ Empaquetando en {Path(dest).name}...", "accent")
            FileCompressor.compress_items([Path(p) for p in self.items], dest, self.ui_progress)
            self.ui_log(f"✅ ¡ZIP Listo!", "success")
            self.master_app.log_history("Compresión ZIP", f"Archivo: {Path(dest).name}", "🗜️")
            self.after(0, lambda: sm.show_success(self, "COMPRESIÓN LISTA", f"El archivo '{Path(dest).name}' se ha creado correctamente."))
        except Exception as e: self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self.master_app._enqueue_done()
            self.btn.configure(state="normal")


class ViewBgRemover(BaseToolView):
    """Herramienta de eliminación de fondos con previsualización comparativa."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.file = None
        
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(h, text="🪄 IA Quitafondos", font=ctk.CTkFont(size=26, weight="bold"), text_color="#A78BFA").pack(anchor="w")
        ctk.CTkLabel(h, text="Elimina fondos perfectamente sin subir tus fotos a internet (Procesamiento Local).", text_color="gray").pack(anchor="w")
        
        card = ctk.CTkFrame(self, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="both", expand=True, pady=(10, 10))
        
        # --- ÁREA DE COMPARACIÓN (Antes / Después) ---
        self.comp_f = ctk.CTkFrame(card, fg_color="transparent")
        self.comp_f.pack(fill="both", expand=True, padx=20, pady=20)
        self.comp_f.grid_columnconfigure((0, 1), weight=1)
        self.comp_f.grid_rowconfigure(0, weight=1)
        
        # Panel Original
        self.orig_card = ctk.CTkFrame(self.comp_f, fg_color=("#F1F5F9", "#0D0F1A"), corner_radius=12)
        self.orig_card.grid(row=0, column=0, sticky="nsew", padx=10)
        ctk.CTkLabel(self.orig_card, text="FOTO ORIGINAL", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(pady=10)
        self.lbl_orig = ctk.CTkLabel(self.orig_card, text="Sin selección", font=ctk.CTkFont(size=12))
        self.lbl_orig.pack(expand=True, pady=20)
        
        # Panel Resultado
        self.res_card = ctk.CTkFrame(self.comp_f, fg_color=("#F1F5F9", "#0D0F1A"), corner_radius=12)
        self.res_card.grid(row=0, column=1, sticky="nsew", padx=10)
        ctk.CTkLabel(self.res_card, text="RESULTADO IA (PNG)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#A78BFA").pack(pady=10)
        self.lbl_res = ctk.CTkLabel(self.res_card, text="Esperando...", font=ctk.CTkFont(size=12))
        self.lbl_res.pack(expand=True, pady=20)
        
        # Botón de Selección
        self.sel_btn = ctk.CTkButton(card, text="📸  Cargar Imagen", height=40, font=ctk.CTkFont(weight="bold"), 
                                     fg_color="#6C63FF", hover_color="#5850E1", command=self._browse)
        self.sel_btn.pack(pady=(0, 15))
        
        # --- BOTÓN MÁGICO IA (ANÁLISIS VISUAL) ---
        if self.master_app.ai_active and self.master_app.ai_has_vision:
            self.ai_btn = ctk.CTkButton(card, text="✨ ANALIZAR CON IA", height=32, corner_radius=20,
                                        fg_color=("#F1F5F9", "#1E293B"), text_color=("#6366F1", "#A78BFA"),
                                        font=ctk.CTkFont(size=11, weight="bold"), border_width=1, border_color="#6366F1",
                                        command=self._ai_analyze)
            self.ai_btn.pack(pady=(0, 15))
        
        self.precision_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(card, text="✨ Máxima Calidad (Bordes inteligentes IA)", variable=self.precision_var, 
                      font=ctk.CTkFont(size=12), progress_color="#8B5CF6").pack(pady=(0, 20))

        # Botón de Procesado
        self.btn = ctk.CTkButton(self, text="⚡  INICIAR TRANSFORMACIÓN IA", height=54, corner_radius=12,
                                 fg_color="#8B5CF6", hover_color="#7C3AED", font=ctk.CTkFont(size=16, weight="bold"), 
                                 command=self._start)
        self.btn.pack(fill="x")

    def _browse(self):
        f = filedialog.askopenfilename(filetypes=[("Imágenes", "*.jpg *.png *.jpeg *.webp")])
        if f:
            self.file = f
            self.lbl_res.configure(text="Esperando...", image=None) 
            try:
                img = Image.open(f)
                img.thumbnail((300, 300))
                # Mantener referencia para evitar garbage collection
                self.ctk_img_orig = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.lbl_orig.configure(text="", image=self.ctk_img_orig)
            except:
                self.lbl_orig.configure(text=Path(f).name, image=None)

    def _start(self):
        if not self.file: return
        init_name = f"{Path(self.file).stem}-nobg.png"
        dest = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG con Transparencia", "*.png")],
            initialfile=init_name,
            title="Guardar imagen sin fondo como..."
        )
        if dest:
            self.btn.configure(state="disabled", text="🔮 PROCESANDO...")
            threading.Thread(target=self._run, args=(dest,), daemon=True).start()

    def _run(self, dest_file):
        try:
            self.ui_log(f"🪄 Quitando fondo con IA: {Path(self.file).name}...", "accent")
            input_image = Image.open(self.file)
            self.ui_progress(20, "Preparando motor neuronal...")
            
            use_high_prec = self.precision_var.get()
            self.ui_progress(50, "Calculando transparencia...")
            
            import rembg
            output_image = rembg.remove(
                input_image,  
                alpha_matting=use_high_prec,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )
            
            self.ui_progress(90, "Guardando transparencia...")
            output_image.save(dest_file, "PNG")
            
            # Cargar preview del resultado
            res_thumb = output_image.copy()
            res_thumb.thumbnail((300, 300))
            self.ctk_img_res = ctk.CTkImage(light_image=res_thumb, dark_image=res_thumb, size=(res_thumb.width, res_thumb.height))
            self.lbl_res.configure(text="", image=self.ctk_img_res)
            
            self.ui_log(f"✅ Imagen guardada correctamente", "success")
            self.master_app.log_history("Quitar Fondo", f"Imagen: {Path(dest_file).name}", "🪄")
            
            self.after(0, lambda: sm.show_success(self, "QUITAFONDOS FINALIZADO", 
                        f"¡Fondo eliminado con éxito!\nSe ha guardado en: {Path(dest_file).name}\n\nPuedes ver el resultado a la derecha."))
            
        except Exception as e: 
            err_msg = str(e)
            self.ui_log(f"❌ Error: {err_msg}", "error")
            self.after(0, lambda: messagebox.showerror("Error IA", f"No se pudo procesar la imagen:\n{err_msg}"))
        finally:
            self.master_app._enqueue_done()
            self.btn.configure(state="normal", text="⚡  INICIAR TRANSFORMACIÓN IA")

    def _ai_analyze(self):
        """Lanza el análisis visual de la imagen cargada."""
        if not self.file:
            return messagebox.showwarning("Sin imagen", "Carga una imagen primero para analizarla.")
        
        # --- VALIDACIÓN PREVENTIVA DE VISIÓN ---
        if not self.master_app.ai_has_vision:
            sm.show_success(self, "MODELO SIN VISIÓN", 
                           f"El modelo actual '{self.master_app.ai_model}' no soporta análisis de imágenes.\n\n"
                           "Para usar esta función, ve a Ajustes IA y elige un modelo como:\n"
                           "• llama-3.2-11b-vision-preview\n"
                           "• gpt-4o-mini", color="#F59E0B")
            return

        self.master_app._pulse_progress()
        self.ui_log("✨ El Cerebro IA está inspeccionando la imagen...", "accent")
        threading.Thread(target=self._do_ai_vision, daemon=True).start()

    def _do_ai_vision(self):
        """Procesa la imagen en Base64 y consulta a la API de visión."""
        try:
            import requests, base64, io, json
            
            # Cargar y optimizar imagen para la API
            img = Image.open(self.file).convert("RGB")
            img.thumbnail((800, 800)) # Limitar resolución para velocidad y coste
            
            # Convertir a Base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            key = self.master_app.ai_key
            prov = self.master_app.ai_provider
            model = self.master_app.ai_model
            
            self.ui_log(f"⏳ Analizando imagen con {model}...", "muted")
            
            # API endpoint condicional (Default Groq)
            url = "https://api.groq.com/openai/v1/chat/completions"
            if "deepseek" in prov.lower(): url = "https://api.deepseek.com/v1/chat/completions"
            elif "openrouter" in prov.lower(): url = "https://openrouter.ai/api/v1/chat/completions"
            
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe esta imagen detalladamente en un párrafo corto. Termina con 5 hashtags."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }
                ],
                "max_tokens": 400
            }
            
            res = requests.post(url, headers=headers, json=payload, timeout=35)
            if res.status_code == 200:
                dt = res.json()
                analysis = dt['choices'][0]['message']['content']
                self.after(0, lambda: sm.show_success(self, "ANÁLISIS VISUAL IA (✨)", f"Resultados de la inspección:\n\n{analysis}"))
                self.ui_log("✅ Análisis de visión completado con éxito.", "success")
            else:
                raw_err = res.text
                err_data = {}
                try: err_data = res.json()
                except: pass
                
                # --- DETECTOR DE ERROR DE VISIÓN ESPECÍFICO ---
                # Si el error dice que el contenido debe ser un string, es 100% falta de visión
                msg = str(err_data.get('error', {}).get('message', ''))
                if "content must be a string" in msg.lower() or "not a vision model" in raw_err.lower():
                    self.ui_log("⚠️ Error: El modelo NO tiene visión.", "warning")
                    self.after(0, lambda: sm.show_success(self, "MODELO SIN VISIÓN", 
                        f"¡Oh no! El modelo actual ({model}) parece ser de solo texto.\n\n"
                        "Las APIs requieren que uses un modelo con la palabra 'vision' o similar para analizar imágenes.\n\n"
                        "💡 Prueba con: llama-3.2-11b-vision-preview", color="#F59E0B"))
                else:
                    self.ui_log(f"❌ Error API: {msg[:100]}...", "error")
        except Exception as e:
            self.ui_log(f"❌ Error IA: {e}", "error")
        finally:
            self.master_app._enqueue_done()


# ─── NUEVAS HERRAMIENTAS ─────────────────────────────────────────────────────

class ViewDownloader(BaseToolView):
    """Descargador de video/audio via yt-dlp."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.url_var = ctk.StringVar()
        self.fmt_var = ctk.StringVar(value="mp4")
        self.dest_dir = None

        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(h, text="📥 Descargador de Video / Audio", font=ctk.CTkFont(size=26, weight="bold"), text_color="#F59E0B").pack(anchor="w")
        ctk.CTkLabel(h, text="Descarga cualquier video o extrae el audio en MP3. Pega el enlace y elige el formato.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        card = ctk.CTkFrame(self, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="both", expand=True, pady=(0, 20))

        url_row = ctk.CTkFrame(card, fg_color="transparent")
        url_row.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(url_row, text="🔗 URL:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        ctk.CTkEntry(url_row, textvariable=self.url_var, placeholder_text="Pega aquí el enlace del video...", height=36).pack(side="left", fill="x", expand=True)

        fmt_row = ctk.CTkFrame(card, fg_color="transparent")
        fmt_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(fmt_row, text="Formato:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(fmt_row, text="🎬 Video MP4 (mejor calidad)", variable=self.fmt_var, value="mp4", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(fmt_row, text="🎵 Solo Audio MP3", variable=self.fmt_var, value="mp3", font=ctk.CTkFont(size=13)).pack(side="left")

        dest_row = ctk.CTkFrame(card, fg_color="transparent")
        dest_row.pack(fill="x", padx=20, pady=(0, 20))
        self.dest_lbl = ctk.CTkLabel(dest_row, text="📁 Destino: (no seleccionado)", text_color="gray", font=ctk.CTkFont(size=12))
        self.dest_lbl.pack(side="left")
        ctk.CTkButton(dest_row, text="Elegir carpeta", width=120, command=self._pick_dest).pack(side="right")

        if not HAS_YTDLP:
            ctk.CTkLabel(card, text="⚠️ yt-dlp no disponible. Ejecuta: pip install yt-dlp", text_color="red").pack(pady=20)

        self.btn = ctk.CTkButton(self, text="📥 Descargar", height=50, fg_color="#D97706", hover_color="#B45309", font=ctk.CTkFont(size=16, weight="bold"), command=self._start)
        self.btn.pack(fill="x")
        if not HAS_YTDLP: self.btn.configure(state="disabled")

    def _pick_dest(self):
        d = filedialog.askdirectory(title="Guardar en...")
        if d:
            self.dest_dir = d
            self.dest_lbl.configure(text=f"📁 Destino: {Path(d).name}", text_color="#10B981")

    def _start(self):
        url = self.url_var.get().strip()
        if not url: return messagebox.showerror("Error", "Pega una URL.")
        if not self.dest_dir: return messagebox.showerror("Error", "Selecciona una carpeta de destino.")
        self.btn.configure(state="disabled")
        self.master_app._pulse_progress()
        threading.Thread(target=self._run, args=(url, self.fmt_var.get(), self.dest_dir), daemon=True).start()

    def _run(self, url, fmt, dest):
        try:
            self.ui_log(f"📥 Descargando ({fmt.upper()}): {url[:60]}...", "accent")
            if fmt == "mp3":
                opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(dest, '%(title)s.%(ext)s'),
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                    'quiet': True, 'no_warnings': True,
                    'progress_hooks': [self._prog_hook],
                }
            else:
                opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'outtmpl': os.path.join(dest, '%(title)s.%(ext)s'),
                    'quiet': True, 'no_warnings': True,
                    'progress_hooks': [self._prog_hook],
                    'merge_output_format': 'mp4',
                }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.ui_log(f"✅ ¡Descarga completada en: {Path(dest).name}!", "success")
            self.master_app.log_history("Descargador", f"Link: {url[:40]}...", "📥")
        except Exception as e:
            self.ui_log(f"❌ Error al descargar: {str(e)[:120]}", "error")
        finally:
            self.master_app._enqueue_done()
            self.btn.configure(state="normal")

    def _prog_hook(self, d):
        if d.get('status') == 'downloading':
            pct_str = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                pct = float(pct_str)
                speed = d.get('_speed_str', '').strip()
                self.ui_progress(pct, f"Descargando... {pct:.0f}% — {speed}")
            except Exception:
                pass


class ViewImageConverter(BaseToolView):
    """Conversor universal: JPG, PNG, WEBP, ICO, BMP, TIFF, GIF y más."""

    # Todos los formatos soportados por Pillow en Windows
    FORMATS = [
        ("JPEG",   ".jpg",  "JPEG — Foto comprimida (WhatsApp, correo)"),
        ("PNG",    ".png",  "PNG — Máxima calidad, fondo transparente"),
        ("WEBP",   ".webp", "WEBP — Formato web moderno, ultra ligero"),
        ("ICO",    ".ico",  "ICO — Ícono para Windows / apps"),
        ("BMP",    ".bmp",  "BMP — Bitmap sin compresión"),
        ("TIFF",   ".tiff", "TIFF — Alta precisión (impresión)"),
        ("GIF",    ".gif",  "GIF — Compatible con animaciones básicas"),
    ]
    FMT_NAMES = [f[2] for f in FORMATS]
    FMT_KEYS  = {f[2]: f[0] for f in FORMATS}
    FMT_EXTS  = {f[0]: f[1] for f in FORMATS}

    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.files = []
        self.out_fmt_name = ctk.StringVar(value=self.FMT_NAMES[0])
        self.quality_var  = ctk.IntVar(value=85)
        self.resize_var   = ctk.BooleanVar(value=False)
        self.max_px_var   = ctk.StringVar(value="1920")

        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(h, text="🔄 Conversor Universal de Imágenes", font=ctk.CTkFont(size=24, weight="bold"), text_color="#06B6D4").pack(anchor="w")
        ctk.CTkLabel(h, text="Convierte entre JPG, PNG, WEBP, ICO, BMP, TIFF, GIF — incluso en lote masivo.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        card = ctk.CTkFrame(self, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="both", expand=True, pady=(0, 15))

        # Fila 1 — Añadir / Limpiar
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkButton(row1, text="➕ Agregar Imágenes", fg_color="#0891B2", command=self._add).pack(side="left", padx=(0, 10))
        ctk.CTkButton(row1, text="🧹 Limpiar", fg_color="gray", command=self._clear).pack(side="left")
        self.count_lbl = ctk.CTkLabel(row1, text="", text_color="#06B6D4", font=ctk.CTkFont(weight="bold"))
        self.count_lbl.pack(side="right")

        # Lista de archivos
        self.listbox = tk.Listbox(card, bg="#0D0F1A", fg="white", bd=0, highlightthickness=0,
                                  font=("Segoe UI", 11), selectbackground="#0891B2", height=5)
        self.listbox.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Fila 2 — Formato destino (DropDown)
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(row2, text="Convertir a:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        ctk.CTkComboBox(row2, variable=self.out_fmt_name, values=self.FMT_NAMES,
                        width=360, command=self._on_fmt_change).pack(side="left")

        # Fila 3 — Calidad + Resize
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(row3, text="Calidad:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 8))
        ctk.CTkSlider(row3, from_=10, to=100, variable=self.quality_var, width=160).pack(side="left")
        self.quality_lbl = ctk.CTkLabel(row3, text="85%", font=ctk.CTkFont(weight="bold"), text_color="#06B6D4", width=36)
        self.quality_lbl.pack(side="left", padx=(6, 20))
        self.quality_var.trace_add("write", lambda *a: self.quality_lbl.configure(text=f"{self.quality_var.get()}%"))

        ctk.CTkSwitch(row3, text="Redimensionar (píx máx):", variable=self.resize_var,
                      font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row3, textvariable=self.max_px_var, width=70, height=30).pack(side="left")

        self.btn = ctk.CTkButton(self, text="🔄 Convertir Todo", height=50, fg_color="#0891B2",
                                 hover_color="#0E7490", font=ctk.CTkFont(size=16, weight="bold"),
                                 command=self._start)
        self.btn.pack(fill="x")

    def _on_fmt_change(self, _=None):
        # ICO no soporta compresión de calidad
        fmt_key = self.FMT_KEYS.get(self.out_fmt_name.get(), "JPEG")
        self.quality_lbl.configure(text_color="gray" if fmt_key in ("ICO", "BMP", "GIF", "TIFF", "PNG") else "#06B6D4")

    def _add(self):
        fs = filedialog.askopenfilenames(
            title="Seleccionar imágenes",
            filetypes=[
                ("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp *.ico *.gif *.tiff *.tif *.svg"),
                ("Todos", "*.*")
            ]
        )
        for f in fs:
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", f"{Path(f).suffix.upper()[1:] or '?'}  →  {Path(f).name}")
        self.count_lbl.configure(text=f"{len(self.files)} archivo(s)")

    def _clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")
        self.count_lbl.configure(text="")

    def _start(self):
        if not self.files: return
        dest = filedialog.askdirectory(title="Guardar imágenes convertidas en...")
        if not dest: return
        self.btn.configure(state="disabled")
        self.master_app._pulse_progress()
        threading.Thread(target=self._run, args=(dest,), daemon=True).start()

    def _run(self, dest):
        try:
            fmt     = self.FMT_KEYS.get(self.out_fmt_name.get(), "JPEG")
            ext     = self.FMT_EXTS.get(fmt, ".jpg")
            quality = self.quality_var.get()
            do_resize = self.resize_var.get()
            max_px  = int(self.max_px_var.get()) if do_resize else None
            total   = len(self.files)
            ok, err = 0, 0

            for i, f in enumerate(self.files):
                try:
                    src = Path(f)
                    # IA: Aplicar sufijo de acción en lote
                    out = Path(dest) / (f"{src.stem}-converted{ext}")

                    # Abrir y convertir modo de color según formato destino
                    img = Image.open(src)

                    # Pasar a RGBA si el destino soporta transparencia, si no a RGB
                    if fmt in ("PNG", "ICO", "GIF"):
                        img = img.convert("RGBA")
                    elif fmt in ("JPEG", "BMP"):
                        if img.mode in ("RGBA", "LA", "P"):
                            bg = Image.new("RGB", img.size, (255, 255, 255))
                            if img.mode == "P": img = img.convert("RGBA")
                            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                            img = bg
                        else:
                            img = img.convert("RGB")
                    else:
                        img = img.convert("RGB")

                    # Redimensionar si aplica
                    if max_px:
                        img.thumbnail((max_px, max_px), Image.LANCZOS)

                    # Guardar con opciones por formato
                    if fmt == "ICO":
                        sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
                        img.save(out, format="ICO", sizes=sizes)
                    elif fmt in ("JPEG", "WEBP"):
                        img.save(out, format=fmt, quality=quality, optimize=True)
                    elif fmt == "TIFF":
                        img.save(out, format="TIFF", compression="tiff_lzw")
                    else:
                        img.save(out, format=fmt)

                    ok += 1
                    sz = out.stat().st_size / 1024
                    self.ui_log(f"  ✅ {src.name} → {out.name} ({sz:.0f} KB)", "success")

                except Exception as e:
                    err += 1
                    self.ui_log(f"  ❌ Error en {Path(f).name}: {e}", "error")

                self.ui_progress(((i+1)/total)*100, f"Convirtiendo {i+1}/{total}: {Path(f).name}")

            self.ui_log(f"✅ Listo: {ok} convertidas, {err} errores.", "success" if err == 0 else "warning")
            self.master_app.log_history("Conversión Imág.", f"Procesadas {ok} imágenes", "🔄")

        except Exception as e:
            self.ui_log(f"❌ Error global: {e}", "error")
        finally:
            self.master_app._enqueue_done()
            self.btn.configure(state="normal")


class ViewPDFTools(BaseToolView):
    """
    Suite PDF Completa:
     - Unir varios PDFs
     - Eliminar páginas específicas
     - Agregar páginas en blanco
     - Crear PDF desde cero (texto, imagen, formas)
     - Crear PDF Interactivo (formularios con campos)
     - Proteger con contraseña
    """

    TABS = [
        ("merge",       "🔗 Unir"),
        ("reorder",     "🔄 Organizar"),
        ("delete",      "🖥️ Eliminar Páginas"),
        ("blank",       "📤 Páginas Blancas"),
        ("pdftoword",   "✨ A Word (Editar)"),
        ("create",      "➕ Crear PDF"),
        ("interactive", "📝 Formulario"),
        ("protect",     "🔒 Proteger"),
    ]

    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.pdf_files = []
        self.current_tab = ctk.StringVar(value="merge")
        self.tab_btns = {}

        # Header
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(h, text="📄 Suite PDF Profesional",
                     font=ctk.CTkFont(size=22, weight="bold"), text_color="#EF4444").pack(anchor="w")
        ctk.CTkLabel(h, text="Unir, eliminar páginas, agregar hojas en blanco, crear PDFs con contenido e incluso formularios interactivos.",
                     font=ctk.CTkFont(size=11), text_color="gray", wraplength=750).pack(anchor="w")

        # Contenedor para el selector visual (Grid de Herramientas)
        self.selection_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.selection_panel.pack(fill="both", expand=True)

        self.panels = {}
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        # No lo packeamos todavía, se mostrará al elegir una herramienta
        
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        self.panels["merge"]       = self._build_merge(self.content_container)
        self.panels["reorder"]     = self._build_reorder(self.content_container)
        self.panels["delete"]      = self._build_delete(self.content_container)
        self.panels["blank"]       = self._build_blank(self.content_container)
        self.panels["pdftoword"]   = self._build_pdftoword(self.content_container)
        self.panels["create"]      = self._build_create(self.content_container)
        self.panels["interactive"] = self._build_interactive(self.content_container)
        self.panels["protect"]     = self._build_protect(self.content_container)

        for p in self.panels.values():
            p.grid(row=1, column=0, sticky="nsew")

        self._build_selection_grid()

    def _build_selection_grid(self):
        """Crea una galería de tarjetas visuales para elegir la herramienta."""
        for w in self.selection_panel.winfo_children(): w.destroy()
        
        self.selection_panel.grid_columnconfigure((0,1,2,3), weight=1)
        
        tools_data = [
            ("merge",       "🔗", "Unir PDFs", "Combina múltiples archivos en uno solo."),
            ("reorder",     "🔄", "Organizar", "Cambia el orden de las páginas visualmente."),
            ("delete",      "🖥️", "Eliminar", "Quita páginas seleccionándolas de la vista previa."),
            ("blank",       "📤", "Hojas Blancas", "Inserta hojas en blanco en posiciones exactas."),
            ("pdftoword",   "✨", "A Word", "Convierte PDF a DOCX editable de alta calidad."),
            ("create",      "➕", "Crear PDF", "Diseña documentos desde cero con el Editor Visual."),
            ("interactive", "📝", "Formularios", "Crea campos rellenables y zonas de firma."),
            ("protect",     "🔒", "Proteger", "Añade contraseñas y cifrado de seguridad.")
        ]
        
        for i, (key, icon, title, desc) in enumerate(tools_data):
            row, col = i // 4, i % 4
            
            card = ctk.CTkFrame(self.selection_panel, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"), border_width=1, border_color=("#E2E8F0", "#2D324A"))
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=40)).pack(pady=(20, 5))
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack()
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=11), text_color="gray", wraplength=140).pack(pady=(5, 20), padx=10)
            
            # Botón invisible o overlay para hacer toda la tarjeta clicable
            btn = ctk.CTkButton(card, text="Abrir Herramienta", height=32, corner_radius=8, fg_color=("#F1F5F9", "#2D324A"), text_color=("#475569", "#94A3B8"), hover_color=("#E2E8F0", "#3B3D5A"), command=lambda k=key: self._switch_tab(k))
            btn.pack(pady=(0, 15), padx=20, fill="x")

    def _switch_tab(self, key):
        self.current_tab.set(key)
        
        # Ocultar selección, mostrar contenido
        self.selection_panel.pack_forget()
        self.content_container.pack(fill="both", expand=True)
        
        # Barra superior de navegación "Atrás"
        if hasattr(self, "nav_bar"): self.nav_bar.destroy()
        self.nav_bar = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.nav_bar.grid(row=0, column=0, sticky="new", padx=5, pady=5)
        
        ctk.CTkButton(self.nav_bar, text="← Volver a Selección de Herramientas", width=220, height=28, fg_color="#3B3D5A", text_color="white", hover_color="#6C63FF", corner_radius=6, command=self._back_to_selection).pack(side="left")
        
        # Mostrar el panel
        self.panels[key].tkraise()

    def _back_to_selection(self):
        self.content_container.pack_forget()
        self.selection_panel.pack(fill="both", expand=True)

    # ─── HELPER: card frame ───────────────────────────────────────────────
    def _card(self, parent, expand=True):
        c = ctk.CTkFrame(parent, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        c.pack(fill="both", expand=expand, pady=(0, 10))
        return c

    def _action_btn(self, parent, text, color, cmd):
        btn = ctk.CTkButton(parent, text=text, height=46, fg_color=color,
                            font=ctk.CTkFont(size=15, weight="bold"), command=cmd)
        btn.pack(fill="x")
        return btn

    # ─── 1. UNIR ───────────────────────────────────────────
    def _build_merge(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        card = self._card(f)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkLabel(top, text="Arrastra los PDFs en el orden correcto y únelos en un solo documento.",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")
        
        # --- BOTÓN MÁGICO IA ---
        if self.master_app.ai_active:
            ai_btn = ctk.CTkButton(top, text="✨ RESUMIR CON IA", width=140, height=28, corner_radius=20,
                                   fg_color=("#DCFCE7", "#064E3B"), text_color=("#166534", "#4ADE80"),
                                   font=ctk.CTkFont(size=10, weight="bold"),
                                   command=self._ai_summarize_files)
            ai_btn.pack(side="right")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=15, pady=(0, 5))
        self.merge_files = []
        
        self.btn_merge_add = ctk.CTkButton(btns, text="➕ Agregar", fg_color="#DC2626", width=100,
                      command=self._ui_add_merge_file)
        self.btn_merge_add.pack(side="left", padx=(0, 8))
        self.btn_merge_up = ctk.CTkButton(btns, text="↑ Subir", fg_color="#4F46E5", width=80, state="disabled",
                      command=lambda: self._ui_move_merge_file(-1))
        self.btn_merge_up.pack(side="left", padx=(0, 8))
        self.btn_merge_down = ctk.CTkButton(btns, text="↓ Bajar", fg_color="#4F46E5", width=80, state="disabled",
                      command=lambda: self._ui_move_merge_file(1))
        self.btn_merge_down.pack(side="left", padx=(0, 8))
        self.btn_merge_rem = ctk.CTkButton(btns, text="🗑️ Quitar", fg_color="gray", width=80, state="disabled",
                      command=self._ui_remove_merge_file)
        self.btn_merge_rem.pack(side="left")
                      
        # Split Area: Lista a la Izquierda, Preview a la Derecha
        split_f = ctk.CTkFrame(card, fg_color="transparent")
        split_f.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        split_f.grid_columnconfigure(0, weight=5) # 50%
        split_f.grid_columnconfigure(1, weight=5) # 50%
        split_f.grid_rowconfigure(0, weight=1)

        is_dark = ctk.get_appearance_mode() == "Dark"
        self.merge_lb = tk.Listbox(split_f, bg="#0D0F1A" if is_dark else "#F8FAFC", 
                                   fg="#E2E8F0" if is_dark else "#1E293B", bd=0, highlightthickness=0,
                                   font=("Segoe UI", 11), selectbackground="#DC2626")
        self.merge_lb.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Panel Vista Previa (Galería de todos los PDFs)
        self.merge_prev = ctk.CTkFrame(split_f, corner_radius=10, fg_color=("#F1F5F9", "#12131F"))
        self.merge_prev.grid(row=0, column=1, sticky="nsew")
        self.merge_prev.grid_rowconfigure(1, weight=1)
        self.merge_prev.grid_columnconfigure(0, weight=1)
        
        hdr = ctk.CTkFrame(self.merge_prev, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkLabel(hdr, text="🔍 Galería de Portadas (Orden de Fusión)", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(side="left")
        
        # Envoltorio del Canvas con barras de scroll
        thumb_wrap = tk.Frame(self.merge_prev, bg="#12131F" if is_dark else "#F1F5F9")
        thumb_wrap.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 10))
        
        self.merge_vsb = ctk.CTkScrollbar(thumb_wrap, orientation="vertical", fg_color="transparent")
        self.merge_vsb.pack(side="right", fill="y")
        
        self.merge_hsb = ctk.CTkScrollbar(thumb_wrap, orientation="horizontal", fg_color="transparent")
        self.merge_hsb.pack(side="bottom", fill="x")
        
        self.merge_canvas = tk.Canvas(thumb_wrap, bg="#12131F" if is_dark else "#F1F5F9", highlightthickness=0,
                                      yscrollcommand=self.merge_vsb.set, xscrollcommand=self.merge_hsb.set)
        self.merge_canvas.pack(side="left", fill="both", expand=True)
        self.merge_vsb.configure(command=self.merge_canvas.yview)
        self.merge_hsb.configure(command=self.merge_canvas.xview)
        
        self.merge_inner = tk.Frame(self.merge_canvas, bg="#12131F" if is_dark else "#F1F5F9")
        self.merge_inner_win = self.merge_canvas.create_window((0,0), window=self.merge_inner, anchor="nw")
        
        def _configure_merge_inner(event):
            self.merge_canvas.configure(scrollregion=self.merge_canvas.bbox("all"))
        self.merge_inner.bind("<Configure>", _configure_merge_inner)
        
        self.btn_unir = self._action_btn(f, "🔗 Unir en un solo PDF", "#DC2626", lambda: self._run_merge())
        self.btn_unir.configure(state="disabled")
        return f

    def _ui_add_merge_file(self):
        self._lb_add(self.merge_files, self.merge_lb)
        self._refresh_merge_gallery()
        
    def _ui_move_merge_file(self, direction):
        self._lb_move(self.merge_lb, self.merge_files, direction)
        self._refresh_merge_gallery()
        
    def _ui_remove_merge_file(self):
        self._lb_remove(self.merge_files, self.merge_lb)
        self._refresh_merge_gallery()

    def _refresh_merge_gallery(self):
        # Update button states
        has_files = len(self.merge_files) > 0
        state = "normal" if has_files else "disabled"
        self.btn_unir.configure(state=state)
        self.btn_merge_up.configure(state=state)
        self.btn_merge_down.configure(state=state)
        self.btn_merge_rem.configure(state=state)

        # Descartar hilos anteriores limpiando la galería de forma rápida
        for w in self.merge_inner.winfo_children(): w.destroy()
        
        if not self.merge_files:
            tk.Label(self.merge_inner, text="Agrega PDFs para verlos aquí.", 
                     bg=self.merge_inner.cget("bg"), fg="gray", font=("Segoe UI", 11)).pack(padx=20, pady=20)
            return

        threading.Thread(target=self._render_merge_gallery_bg, args=(list(self.merge_files),), daemon=True).start()
        
    def _render_merge_gallery_bg(self, files):
        try:
            import fitz
            from PIL import ImageTk, Image
        except Exception:
            return

        _images = []
        COLS = 2 # Mostramos dos columnas en el panel derecho
        THUMB_W = 120
        
        for i, path in enumerate(files):
            try:
                doc = fitz.open(path)
                if doc.page_count > 0:
                    page = doc.load_page(0) # Siempre leer la portada
                    mat = fitz.Matrix(0.25, 0.25)
                    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
                    img_data = pix.tobytes("ppm")
                    import io
                    pil_img = Image.open(io.BytesIO(img_data))
                    thumb_h = int(pil_img.height * THUMB_W / pil_img.width)
                    pil_img = pil_img.resize((THUMB_W, thumb_h), Image.LANCZOS)
                    
                    idx = i # bind loop variable
                    col = idx % COLS
                    row_idx = idx // COLS
                    
                    def _add_tile(img=pil_img, bg_c=self.merge_inner.cget("bg"), nm=Path(path).name, num=idx+1, c=col, r=row_idx):
                        try:
                            tk_img = ImageTk.PhotoImage(img)
                            _images.append(tk_img)
                            cell = tk.Frame(self.merge_inner, bg=bg_c, padx=6, pady=6)
                            cell.grid(row=r, column=c, padx=4, pady=4, sticky="n")
                            border = tk.Frame(cell, bg="#3B3D5A", bd=1)
                            border.pack()
                            tk.Label(border, image=tk_img, bg="#3B3D5A").pack()
                            tk.Label(cell, text=f"({num}) {nm[:15]}...", bg=bg_c, fg="#A78BFA", font=("Segoe UI", 8, "bold")).pack(pady=(2, 0))
                        except Exception: pass
                    
                    self.after(0, _add_tile)
                doc.close()
            except Exception: pass
            
        self.after(0, lambda: setattr(self.merge_inner, "_keep_imgs", _images))

    # ─── 1.5. ORGANIZAR ───────────────────────────────────────────
    def _build_reorder(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        # Top card
        card = ctk.CTkFrame(f, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="x", pady=(0, 8))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=15)
        self.reorder_file_lbl = ctk.CTkLabel(row, text="Ningún PDF seleccionado.", text_color="gray")
        self.reorder_file_lbl.pack(side="left")
        self.reorder_file_path = None
        ctk.CTkButton(row, text="📂 Abrir PDF", fg_color="#475569", width=110,
                      command=self._reorder_open).pack(side="right")

        # Preview card
        prev_card = ctk.CTkFrame(f, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        prev_card.pack(fill="both", expand=True, pady=(0, 8))

        prev_hdr = ctk.CTkFrame(prev_card, fg_color="transparent")
        prev_hdr.pack(fill="x", padx=15, pady=(10, 6))
        ctk.CTkLabel(prev_hdr, text="🔍 Galería Dinámica",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#6C63FF", "#A78BFA")).pack(side="left")
        self.reorder_info = ctk.CTkLabel(prev_hdr, text="Usa las flechas ◀ / ▶ bajo cada página para reordenarlas intuitivamente.",
                                          text_color="gray", font=ctk.CTkFont(size=11))
        self.reorder_info.pack(side="left", padx=14)

        # Canvas
        thumb_wrap = tk.Frame(prev_card, bg="#12131F")
        thumb_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        re_vsb = ctk.CTkScrollbar(thumb_wrap, orientation="vertical", fg_color="#12131F", button_color="#3B3D5A", button_hover_color="#6C63FF")
        re_vsb.pack(side="right", fill="y")
        re_hsb = ctk.CTkScrollbar(thumb_wrap, orientation="horizontal", fg_color="#12131F", button_color="#3B3D5A", button_hover_color="#6C63FF")
        re_hsb.pack(side="bottom", fill="x")

        self.reorder_thumb_canvas = tk.Canvas(thumb_wrap, bg="#12131F", highlightthickness=0, yscrollcommand=re_vsb.set, xscrollcommand=re_hsb.set)
        self.reorder_thumb_canvas.pack(side="left", fill="both", expand=True)
        re_vsb.configure(command=self.reorder_thumb_canvas.yview)
        re_hsb.configure(command=self.reorder_thumb_canvas.xview)

        self.reorder_thumb_inner = tk.Frame(self.reorder_thumb_canvas, bg="#12131F")
        self.reorder_thumb_canvas.create_window((0, 0), window=self.reorder_thumb_inner, anchor="nw")
        self.reorder_thumb_inner.bind("<Configure>", lambda e: self.reorder_thumb_canvas.configure(scrollregion=self.reorder_thumb_canvas.bbox("all")))

        self.btn_reorder_run = self._action_btn(f, "💾 Guardar Documento Ordenado", "#10B981", self._run_reorder)
        self.btn_reorder_run.configure(state="disabled")
        return f

    def _reorder_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.reorder_file_path = f
            try:
                import PyPDF2
                r = PyPDF2.PdfReader(f)
                n = len(r.pages)
                self.reorder_file_lbl.configure(text=f"{Path(f).name}  ({n} páginas cargadas)", text_color="#10B981")
                self.btn_reorder_run.configure(state="normal")
                threading.Thread(target=self._render_pdf_thumbnails,
                                 args=(f, self.reorder_thumb_inner, self.reorder_thumb_canvas, None, None, True), daemon=True).start()
            except Exception as e:
                self.reorder_file_lbl.configure(text=f"Error: {e}", text_color="red")

    # ─── 2. ELIMINAR PÁGINAS ─────────────────────────────
    def _build_delete(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        # Top card: file loader + input
        card = ctk.CTkFrame(f, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="x", pady=(0, 8))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(15, 8))
        self.del_file_lbl = ctk.CTkLabel(row, text="Ningún PDF seleccionado.", text_color="gray")
        self.del_file_lbl.pack(side="left")
        self.del_file_path = None
        ctk.CTkButton(row, text="📂 Abrir PDF", fg_color="#475569", width=110,
                      command=self._del_open).pack(side="right")

        info_row = ctk.CTkFrame(card, fg_color="transparent")
        info_row.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkLabel(info_row, text="Páginas a ELIMINAR (Auto-calculado al hacer clic):",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.del_pages_var = ctk.StringVar()
        ctk.CTkEntry(info_row, textvariable=self.del_pages_var, state="readonly",
                     placeholder_text="Haz clic en las miniaturas 👇", width=200).pack(side="left")
                     
        self.btn_del_undo = ctk.CTkButton(info_row, text="↩️ Deshacer", fg_color="#F59E0B", text_color="black", hover_color="#D97706", width=80, state="disabled", command=self._undo_del_last)
        self.btn_del_undo.pack(side="left", padx=(15, 0))

        self.del_info = ctk.CTkLabel(card, text="", text_color="gray", font=ctk.CTkFont(size=11))
        self.del_info.pack(padx=15, anchor="w", pady=(0, 10))

        # Preview card: scrollable thumbnails
        prev_card = ctk.CTkFrame(f, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        prev_card.pack(fill="both", expand=True, pady=(0, 8))

        prev_hdr = ctk.CTkFrame(prev_card, fg_color="transparent")
        prev_hdr.pack(fill="x", padx=15, pady=(10, 6))
        ctk.CTkLabel(prev_hdr, text="🔍 Vista previa del PDF",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#6C63FF", "#A78BFA")).pack(side="left")
        self.del_prev_info = ctk.CTkLabel(prev_hdr, text="Abre un PDF para ver sus páginas.",
                                          text_color="gray", font=ctk.CTkFont(size=11))
        self.del_prev_info.pack(side="left", padx=14)

        # Canvas + scrollbar for thumbnails
        thumb_wrap = tk.Frame(prev_card, bg="#12131F")
        thumb_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Modern CTk Scrollbars
        del_vsb = ctk.CTkScrollbar(thumb_wrap, orientation="vertical", 
                                   fg_color="#12131F", button_color="#3B3D5A", 
                                   button_hover_color="#6C63FF")
        del_vsb.pack(side="right", fill="y")
        
        del_hsb = ctk.CTkScrollbar(thumb_wrap, orientation="horizontal",
                                   fg_color="#12131F", button_color="#3B3D5A", 
                                   button_hover_color="#6C63FF")
        del_hsb.pack(side="bottom", fill="x")

        self.del_thumb_canvas = tk.Canvas(thumb_wrap, bg="#12131F", highlightthickness=0,
                                          yscrollcommand=del_vsb.set, xscrollcommand=del_hsb.set)
        self.del_thumb_canvas.pack(side="left", fill="both", expand=True)
        del_vsb.configure(command=self.del_thumb_canvas.yview)
        del_hsb.configure(command=self.del_thumb_canvas.xview)

        self.del_thumb_inner = tk.Frame(self.del_thumb_canvas, bg="#12131F")
        self.del_thumb_canvas.create_window((0, 0), window=self.del_thumb_inner, anchor="nw")
        self.del_thumb_inner.bind("<Configure>",
            lambda e: self.del_thumb_canvas.configure(scrollregion=self.del_thumb_canvas.bbox("all")))

        self.del_interactive_set = set()
        self.del_history_list = []
        self.del_widget_dict = {}

        self.btn_eliminar = self._action_btn(f, "🖥️ Eliminar y guardar nuevo PDF", "#B45309", self._run_delete)
        self.btn_eliminar.configure(state="disabled")
        return f

    def _on_del_thumb_click(self, page_num, widget):
        if page_num in self.del_interactive_set:
            self.del_history_list.remove(page_num)
            self.del_interactive_set.remove(page_num)
            widget.configure(bg="#3B3D5A") 
        else:
            if messagebox.askyesno("Eliminar Página", f"¿Estás seguro de MARCAR PARA ELIMINAR la página {page_num}?"):
                self.del_history_list.append(page_num)
                self.del_interactive_set.add(page_num)
                widget.configure(bg="#DC2626") 
        
        sorted_pages = sorted(list(self.del_interactive_set))
        self.del_pages_var.set(",".join(map(str, sorted_pages)))
        self._eval_del_state()

    def _undo_del_last(self):
        if not self.del_history_list:
            return messagebox.showinfo("Deshacer", "No hay acciones para deshacer.")
        p = self.del_history_list.pop()
        self.del_interactive_set.remove(p)
        if p in self.del_widget_dict:
            self.del_widget_dict[p].configure(bg="#3B3D5A")
        sorted_pages = sorted(list(self.del_interactive_set))
        self.del_pages_var.set(",".join(map(str, sorted_pages)))
        self._eval_del_state()
        
    def _eval_del_state(self):
        has_sels = len(self.del_interactive_set) > 0
        self.btn_eliminar.configure(state="normal" if has_sels else "disabled")
        self.btn_del_undo.configure(state="normal" if len(self.del_history_list) > 0 else "disabled")

    # ─── 3. PÁGINAS EN BLANCO ───────────────────────────
    def _build_blank(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(f, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        card.pack(fill="x", pady=(0, 8))

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(15, 8))
        self.blank_file_lbl = ctk.CTkLabel(row1, text="Ningún PDF seleccionado.", text_color="gray")
        self.blank_file_lbl.pack(side="left")
        self.blank_file_path = None
        ctk.CTkButton(row1, text="📂 Abrir PDF", fg_color="#475569", width=110,
                      command=self._blank_open).pack(side="right")

        opts = ctk.CTkFrame(card, fg_color="transparent")
        opts.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(opts, text="Insertar después de página #:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.blank_pos_var = ctk.StringVar(value="0")
        ctk.CTkEntry(opts, textvariable=self.blank_pos_var, width=80).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(opts, text="Cantidad:").pack(side="left", padx=(0, 8))
        self.blank_qty_var = ctk.StringVar(value="1")
        ctk.CTkEntry(opts, textvariable=self.blank_qty_var, width=60).pack(side="left")
        ctk.CTkLabel(opts, text="(0 = al inicio)", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(12, 0))

        # Preview card for Blank Pages
        prev_card = ctk.CTkFrame(f, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        prev_card.pack(fill="both", expand=True, pady=(0, 8))

        prev_hdr = ctk.CTkFrame(prev_card, fg_color="transparent")
        prev_hdr.pack(fill="x", padx=15, pady=(10, 6))
        ctk.CTkLabel(prev_hdr, text="🔍 Vista previa del PDF",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#6C63FF", "#A78BFA")).pack(side="left")
        self.blank_prev_info = ctk.CTkLabel(prev_hdr, text="Abre un PDF para ver sus páginas.",
                                            text_color="gray", font=ctk.CTkFont(size=11))
        self.blank_prev_info.pack(side="left", padx=14)

        thumb_wrap = tk.Frame(prev_card, bg="#12131F")
        thumb_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        bl_vsb = ctk.CTkScrollbar(thumb_wrap, orientation="vertical", 
                                  fg_color="#12131F", button_color="#3B3D5A", 
                                  button_hover_color="#6C63FF")
        bl_vsb.pack(side="right", fill="y")
        bl_hsb = ctk.CTkScrollbar(thumb_wrap, orientation="horizontal",
                                  fg_color="#12131F", button_color="#3B3D5A", 
                                  button_hover_color="#6C63FF")
        bl_hsb.pack(side="bottom", fill="x")

        self.blank_thumb_canvas = tk.Canvas(thumb_wrap, bg="#12131F", highlightthickness=0,
                                            yscrollcommand=bl_vsb.set, xscrollcommand=bl_hsb.set)
        self.blank_thumb_canvas.pack(side="left", fill="both", expand=True)
        bl_vsb.configure(command=self.blank_thumb_canvas.yview)
        bl_hsb.configure(command=self.blank_thumb_canvas.xview)

        self.blank_thumb_inner = tk.Frame(self.blank_thumb_canvas, bg="#12131F")
        self.blank_thumb_canvas.create_window((0, 0), window=self.blank_thumb_inner, anchor="nw")
        self.blank_thumb_inner.bind("<Configure>",
            lambda e: self.blank_thumb_canvas.configure(scrollregion=self.blank_thumb_canvas.bbox("all")))

        self.btn_blanco = self._action_btn(f, "📤 Insertar Páginas en Blanco", "#0891B2", self._run_blank)
        self.btn_blanco.configure(state="disabled")
        return f

    # ─── 4. PDF TO WORD (EDITAR NATIVO) ──────────────────────────────────
    def _build_pdftoword(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        
        c = self._card(f, expand=False)
        self.pdftw_lbl = ctk.CTkLabel(c, text="Ningún PDF seleccionado.", text_color="gray")
        self.pdftw_lbl.pack(pady=(15,0))
        self.pdftw_path = None
        
        def _sel():
            p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
            if p:
                self.pdftw_path = p
                self.pdftw_lbl.configure(text=f"📂 {Path(p).name}", text_color="#10B981")
                self.btn_pdftoword.configure(state="normal")
                
        ctk.CTkButton(c, text="Buscar PDF a Editar", fg_color="#3B3D5A", hover_color="#6C63FF", width=180, height=36, command=_sel).pack(pady=15)
        
        prev_card = self._card(f, expand=True)
        ctk.CTkLabel(prev_card, text="📝 Conversor Inverso Inteligente", font=ctk.CTkFont(size=18, weight="bold"), text_color="#F59E0B").pack(pady=(30, 10))
        info = "Para poder modificar textos libremente, cambiar el interlineado o borrar\npárrafos largos de un archivo PDF, es matemáticamente necesario desencapsularlo.\n\n1) Carga tu PDF aquí.\n2) Dale clic a Guardar. El sistema convertirá el diseño en un archivo .DOCX puro.\n3) Te lo abriremos en Microsoft Word instantáneamente.\n4) Puedes tachar, editar o cambiar y simplemente usar \"Guardar como PDF\" desde Word.\n\n¡Es la forma más profesional y libre de fallos de reescribir contenido!"
        ctk.CTkLabel(prev_card, text=info, text_color="gray", justify="center", font=ctk.CTkFont(size=13)).pack(pady=10)
        
        self.btn_pdftoword = self._action_btn(f, "✨ Convertir y Abrir en Word Nativamente", "#10B981", self._run_pdftoword)
        self.btn_pdftoword.configure(state="disabled")
        return f

    def _run_pdftoword(self):
        if not getattr(self, "pdftw_path", None): return
        dest = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word", "*.docx")], initialfile=f"{Path(self.pdftw_path).stem}-editable.docx")
        if not dest: return
        self.master_app._pulse_progress()
        threading.Thread(target=self._do_pdftoword, args=(self.pdftw_path, dest), daemon=True).start()
        
    def _do_pdftoword(self, src, dest):
        try:
            self.ui_log("✨ Extrayendo vectores, layouts y textos (AI Converter)...", "accent")
            self.ui_progress(30, "Mapeando elementos del PDF...")
            try:
                from pdf2docx import Converter
            except ImportError:
                self.ui_log("❌ Error fatal: falta librería pdf2docx", "error")
                self.master_app._enqueue_done()
                return

            cv = Converter(src)
            self.ui_progress(60, "Construyendo documento Word de MS Office...")
            cv.convert(dest, start=0, end=None)
            cv.close()
            
            self.ui_progress(100, "¡Finalizado!")
            self.ui_log(f"✅ PDF convertido a Word con éxito.", "success")
            self.master_app.log_history("PDF -> Word", f"Documento desbloqueado", "✨")
            self.after(0, lambda: [
                sm.show_success(self, "LISTO PARA EDITAR", f"Tu documento es editable ahora.\nAbriendo Microsoft Word:\n{Path(dest).name}"),
                __import__("os").startfile(dest)
            ])
        except Exception as e:
            self.ui_log(f"❌ Error convirtiendo a Word: {e}", "error")
        finally:
            self.master_app._enqueue_done()

    # ─── 4. CREAR PDF — Editor Visual ──────────────────────────────────────
    def _build_create(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        card = self._card(f)

        # === LANZADOR DEL EDITOR VISUAL ===
        banner = ctk.CTkFrame(card, corner_radius=12,
                              fg_color=("#EDE9FE", "#1A1040"))
        banner.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(banner, text="🎨 Editor Visual de PDF",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=("#6C63FF", "#A78BFA")).pack(pady=(18, 4))

        ctk.CTkLabel(banner,
                     text="Vista previa en tiempo real  ·  Arrastra texto, imágenes y formas\n"
                          "Cambia colores y fuentes  ·  Agrega zonas interactivas de foto",
                     font=ctk.CTkFont(size=12), text_color="gray", justify="center").pack(pady=(0, 14))

        ctk.CTkButton(banner,
                      text="🚀  Abrir Editor Visual",
                      height=50, corner_radius=12,
                      fg_color="#6C63FF", hover_color="#5B5EA6",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._open_designer).pack(padx=20, pady=(0, 18), fill="x")

        return f

    def _open_designer(self):
        """Lanza el Editor Visual de PDF como proceso independiente."""
        import subprocess
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--designer"]
        else:
            designer_path = Path(__file__).parent / "pdf_designer.py"
            if not designer_path.exists():
                messagebox.showerror("Error", f"No se encontró pdf_designer.py")
                return
            cmd = [sys.executable, str(designer_path)]

        try:
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el editor:\n{e}")




    # ─── 5. PDF INTERACTIVO — Constructor dedicado ──────────────────────────
    def _build_interactive(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        card = self._card(f)

        banner = ctk.CTkFrame(card, corner_radius=12,
                              fg_color=("#F5F3FF", "#180D30"))
        banner.pack(fill="x", padx=15, pady=(12, 10))

        ctk.CTkLabel(banner, text="📝",
                     font=ctk.CTkFont(size=40)).pack(pady=(18, 4))

        ctk.CTkLabel(banner, text="Constructor de Formularios PDF",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=("#7C3AED", "#A78BFA")).pack(pady=(0, 6))

        desc = (
            "Texto, Email, Fecha, Teléfono, Checkboxes, Radio,\n"
            "Desplegable, Zona de Firma, Zona de Foto y más.\n"
            "Vista previa en tiempo real · Compatible con Adobe Reader."
        )
        ctk.CTkLabel(banner, text=desc,
                     font=ctk.CTkFont(size=11), text_color="gray",
                     justify="center").pack(pady=(0, 14))

        ctk.CTkButton(banner,
                      text="🚀  Abrir Constructor de Formularios",
                      height=46, corner_radius=10,
                      fg_color="#7C3AED", hover_color="#5B21B6",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._open_form_builder).pack(padx=20, pady=(0, 18), fill="x")

        return f

    def _open_form_builder(self):
        """Lanza el Constructor de Formularios como proceso independiente."""
        import subprocess
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--form-builder"]
        else:
            builder_path = Path(__file__).parent / "pdf_form_builder.py"
            if not builder_path.exists():
                messagebox.showerror("Error", f"No se encontró pdf_form_builder.py")
                return
            cmd = [sys.executable, str(builder_path)]

        try:
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el constructor:\n{e}")



    # ─── 6. PROTEGER ───────────────────────────────────────────
    def _build_protect(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        card = self._card(f)
        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=15, pady=15)
        self.prot_file_lbl = ctk.CTkLabel(r1, text="Ningún PDF seleccionado.", text_color="gray")
        self.prot_file_lbl.pack(side="left")
        self.prot_file_path = None
        
        self.prot_view_btn = ctk.CTkButton(r1, text="👁️ Ver PDF", fg_color="#3B82F6", width=80,
                                           state="disabled", command=lambda: self._view_pdf(self.prot_file_path))
        self.prot_view_btn.pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(r1, text="📂 Abrir PDF", fg_color="#475569", width=110,
                      command=self._prot_open).pack(side="right")

        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(r2, text="🔑 Contraseña:", font=ctk.CTkFont(weight="bold"), width=130).pack(side="left")
        self.prot_pw = ctk.StringVar()
        ctk.CTkEntry(r2, textvariable=self.prot_pw, show="*",
                     placeholder_text="Mínimo 4 caracteres...").pack(side="left", fill="x", expand=True)

        self.btn_proteger = self._action_btn(f, "🔒 Proteger PDF con Contraseña", "#1D4ED8", self._run_protect)
        self.btn_proteger.configure(state="disabled")
        return f

    # ─── HELPERS LISTBOX ──────────────────────────────────────
    def _lb_add(self, lst, lb):
        for f in filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")]):
            if f not in lst: lst.append(f); lb.insert("end", Path(f).name)

    def _lb_remove(self, lst, lb):
        sel = lb.curselection()
        if sel:
            lb.delete(sel[0]); lst.pop(sel[0])

    def _lb_move(self, lb, lst, direction):
        sel = lb.curselection()
        if not sel: return
        i = sel[0]; new_i = i + direction
        if 0 <= new_i < lb.size():
            txt = lb.get(i); lb.delete(i); lb.insert(new_i, txt); lb.selection_set(new_i)
            lst[i], lst[new_i] = lst[new_i], lst[i]

    def _del_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.del_file_path = f
            try:
                import PyPDF2
                r = PyPDF2.PdfReader(f)
                n = len(r.pages)
                self.del_interactive_set.clear()
                self.del_history_list.clear()
                self.del_widget_dict.clear()
                self.del_pages_var.set("")
                self._eval_del_state()
                self.del_file_lbl.configure(text=f"{Path(f).name}  ({n} páginas)", text_color="#10B981")
                self.del_info.configure(text=f"Total: {n} páginas. Haz clic en las miniaturas para marcarlas.")
                self.del_prev_info.configure(text=f"{n} página(s)  —  haz scroll para ver todas")
                threading.Thread(target=self._render_pdf_thumbnails,
                                 args=(f, self.del_thumb_inner, self.del_thumb_canvas, self._on_del_thumb_click, self.del_widget_dict), daemon=True).start()
            except Exception as e:
                self.del_file_lbl.configure(text=f"Error: {e}", text_color="red")

    def _blank_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.blank_file_path = f
            try:
                import PyPDF2
                r = PyPDF2.PdfReader(f)
                n = len(r.pages)
                self.btn_blanco.configure(state="normal")
                self.blank_file_lbl.configure(text=f"{Path(f).name}  ({n} págs)", text_color="#10B981")
                self.blank_prev_info.configure(text=f"{n} página(s)  —  haz scroll para ver todas")
                threading.Thread(target=self._render_pdf_thumbnails,
                                 args=(f, self.blank_thumb_inner, self.blank_thumb_canvas), daemon=True).start()
            except Exception as e:
                self.blank_file_lbl.configure(text=f"Error: {e}", text_color="red")

    def _render_pdf_thumbnails(self, pdf_path, container, canvas_widget, click_cb=None, widget_dict=None, reorder_mode=False):
        """Renders PDF page thumbnails into container using PyMuPDF (fitz)."""
        try:
            import fitz
            from PIL import ImageTk

            # Clear old thumbnails
            def _clear():
                for w in container.winfo_children():
                    w.destroy()
            container.after(0, _clear)
            import time; time.sleep(0.05)
            
            if reorder_mode:
                container._cells = []

            doc = fitz.open(pdf_path)
            THUMB_W = 140  # px width per thumbnail
            COLS = 4
            _images = []  # keep refs to prevent GC

            for i, page in enumerate(doc):
                # Render page to image
                mat = fitz.Matrix(0.35, 0.35)  # scale factor ~35%
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
                img_data = pix.tobytes("ppm")

                from io import BytesIO
                from PIL import Image
                pil_img = Image.open(BytesIO(img_data))
                # Fixed thumbnail height to keep consistent grid
                thumb_h = int(pil_img.height * THUMB_W / pil_img.width)
                pil_img = pil_img.resize((THUMB_W, thumb_h), Image.LANCZOS)

                page_num = i + 1
                col = i % COLS
                row_idx = i // COLS

                def _add_tile(img=pil_img, pn=page_num, c=col, r=row_idx):
                    tk_img = ImageTk.PhotoImage(img)
                    _images.append(tk_img)

                    cell = tk.Frame(container, bg="#12131F", padx=6, pady=6)
                    cell.grid(row=r, column=c, padx=4, pady=4)
                    
                    if reorder_mode:
                        container._cells.append(cell)
                        cell._orig_pn = pn

                    # Border frame to simulate card
                    border = tk.Frame(cell, bg="#3B3D5A", bd=2)
                    border.pack()
                    if widget_dict is not None:
                        widget_dict[pn] = border

                    lbl_img = tk.Label(border, image=tk_img, bg="#3B3D5A", cursor="hand2" if click_cb else "")
                    lbl_img.pack(padx=1, pady=1)

                    # Page number badge
                    num_lbl = tk.Label(cell, text=f"Pág. {pn}",
                                       bg="#12131F", fg="#A78BFA",
                                       font=("Segoe UI", 9, "bold"), cursor="hand2" if click_cb else "")
                    num_lbl.pack(pady=(2, 0))

                    if click_cb:
                        def on_click(e, p=pn, w=border): click_cb(p, w)
                        lbl_img.bind("<Button-1>", on_click)
                        num_lbl.bind("<Button-1>", on_click)

                    if reorder_mode:
                        btns_f = tk.Frame(cell, bg="#12131F")
                        btns_f.pack(pady=(2, 0))
                        
                        def _move_cell(direction, current_cell=cell):
                            idx = container._cells.index(current_cell)
                            new_idx = idx + direction
                            if 0 <= new_idx < len(container._cells):
                                container._cells[idx], container._cells[new_idx] = container._cells[new_idx], container._cells[idx]
                                for i, cc in enumerate(container._cells):
                                    cc.grid(row=i//COLS, column=i%COLS)
                                container.update_idletasks()
                                canvas_widget.configure(scrollregion=canvas_widget.bbox("all"))

                        btn_l = ctk.CTkButton(btns_f, text="‹", width=22, height=22, corner_radius=4, fg_color="transparent", hover_color="#3B3D5A", text_color="gray", font=ctk.CTkFont(size=16, weight="bold"), command=lambda: _move_cell(-1))
                        btn_l.pack(side="left", padx=2)
                        btn_r = ctk.CTkButton(btns_f, text="›", width=22, height=22, corner_radius=4, fg_color="transparent", hover_color="#3B3D5A", text_color="gray", font=ctk.CTkFont(size=16, weight="bold"), command=lambda: _move_cell(1))
                        btn_r.pack(side="left", padx=2)

                        lbl_img.configure(cursor="fleur")
                        num_lbl.configure(cursor="fleur")
                        
                        def on_drag_start(e, c=cell, tk_i=tk_img):
                            c._ghost = tk.Toplevel(container)
                            c._ghost.wm_overrideredirect(True)
                            c._ghost.attributes("-alpha", 0.7)
                            tk.Label(c._ghost, image=tk_i, bg="#6C63FF", bd=4, relief="solid").pack()
                            c._ghost.geometry(f"+{e.x_root + 15}+{e.y_root + 15}")

                        def on_drag_motion(e, c=cell):
                            if hasattr(c, "_ghost") and c._ghost:
                                c._ghost.geometry(f"+{e.x_root + 15}+{e.y_root + 15}")

                        def on_drag_release(e, c=cell):
                            if hasattr(c, "_ghost") and c._ghost:
                                c._ghost.destroy()
                                c._ghost = None
                                
                            mx, my = e.x_root, e.y_root
                            target_cell = None
                            min_dist = float('inf')
                            
                            for cc in container._cells:
                                try:
                                    cx = cc.winfo_rootx() + (cc.winfo_width() / 2)
                                    cy = cc.winfo_rooty() + (cc.winfo_height() / 2)
                                    dist = (cx - mx)**2 + (cy - my)**2
                                    if dist < min_dist:
                                        min_dist = dist
                                        target_cell = cc
                                except Exception:
                                    pass
                                
                            if target_cell and target_cell != c:
                                idx1 = container._cells.index(c)
                                idx2 = container._cells.index(target_cell)
                                
                                val = container._cells.pop(idx1)
                                container._cells.insert(idx2, val)
                                
                                for i, cc in enumerate(container._cells):
                                    cc.grid(row=i//COLS, column=i%COLS)
                                container.update_idletasks()
                                canvas_widget.configure(scrollregion=canvas_widget.bbox("all"))

                        lbl_img.bind("<ButtonPress-1>", on_drag_start)
                        lbl_img.bind("<B1-Motion>", on_drag_motion)
                        lbl_img.bind("<ButtonRelease-1>", on_drag_release)
                        num_lbl.bind("<ButtonPress-1>", on_drag_start)
                        num_lbl.bind("<B1-Motion>", on_drag_motion)
                        num_lbl.bind("<ButtonRelease-1>", on_drag_release)

                container.after(0, _add_tile)

            doc.close()
            # Keep image refs alive on the container
            container._thumb_images = _images

        except Exception as e:
            def _err():
                tk.Label(container, text=f"⚠️ No se pudo renderizar: {e}",
                         bg="#12131F", fg="#EF4444",
                         font=("Segoe UI", 11)).pack(padx=20, pady=20)
            container.after(0, _err)

    def _prot_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.prot_file_path = f
            self.prot_file_lbl.configure(text=Path(f).name, text_color="#10B981")
            self.prot_view_btn.configure(state="normal")
            self.btn_proteger.configure(state="normal")
            
    def _view_pdf(self, path):
        if path and Path(path).exists():
            try:
                import os
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{e}")


    # ─── WORKERS ──────────────────────────────────────────
    def _run_merge(self):
        if not self.merge_files:
            return messagebox.showwarning("Sin archivos", "Agrega PDFs primero.")
            
        # IA: Detectar discrepancias en los tamaños de página
        different_sizes = False
        try:
            import fitz
            first_size = None
            for pth in self.merge_files:
                doc = fitz.open(pth)
                for page in doc:
                    r = page.rect
                    # Ordenamos para agrupar ej. A4 apaisado y vertical como "mismo tamaño de papel"
                    sz = tuple(sorted([round(r.width, 1), round(r.height, 1)]))
                    if first_size is None:
                        first_size = sz
                    elif abs(sz[0] - first_size[0]) > 2 or abs(sz[1] - first_size[1]) > 2:
                        different_sizes = True
                        break
                doc.close()
                if different_sizes: break
        except Exception:
            pass
            
        normalize_flag = False
        if different_sizes:
            ans = messagebox.askyesno("📏 Tamaños Diferentes Detectados",
                "PowerSuite ha detectado que has cargado PDFs con hojas de diferentes tamaños.\n\n"
                "¿Deseas que estandaricemos automáticamente todas las páginas al formato uniforme A4 para evitar que queden asimétricas al unir?")
            normalize_flag = ans

        # IA: Sugerir nombre basado en el primer archivo
        init_f = f"{Path(self.merge_files[0]).stem}-merged.pdf"
        dest = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF", "*.pdf")],
            initialfile=init_f,
            title="Guardar PDF unido como..."
        )
        if not dest: return
        self.master_app._pulse_progress()
        threading.Thread(target=self._do_merge, args=(dest, normalize_flag), daemon=True).start()

    def _do_merge(self, dest, normalize=False):
        try:
            self.ui_log(f"🔗 Uniendo {len(self.merge_files)} PDFs...", "accent")
            
            if normalize:
                import fitz
                doc_out = fitz.open()
                for i, f in enumerate(self.merge_files):
                    doc_in = fitz.open(f)
                    for p_num in range(len(doc_in)):
                        orig_page = doc_in[p_num]
                        r = orig_page.rect
                        # A4 standard sizes in points: Portrait vs Landscape
                        w, h = (841.89, 595.27) if r.width > r.height else (595.27, 841.89)
                        new_page = doc_out.new_page(width=w, height=h)
                        new_page.show_pdf_page(new_page.rect, doc_in, p_num)
                    doc_in.close()
                    self.ui_progress(((i+1) / len(self.merge_files)) * 90, f"Ajustando y uniendo: {Path(f).name}")
                doc_out.save(dest)
                doc_out.close()
            else:
                import PyPDF2
                merger = PyPDF2.PdfMerger()
                for i, f in enumerate(self.merge_files):
                    merger.append(f)
                    self.ui_progress(((i+1) / len(self.merge_files)) * 90, f"Agregando: {Path(f).name}")
                merger.write(dest)
                merger.close()
                
            self.ui_log(f"✅ PDF unido guardado: {Path(dest).name}", "success")
            self.master_app.log_history("PDF Union", f"Unidos {len(self.merge_files)} archivos", "🔗")
            
            msg = f"Se han fusionado {len(self.merge_files)} archivos en uno solo."
            if normalize:
                msg += "\n\n📏 Además, se redimensionaron TODAS las páginas al tamaño uniforme A4 predecible, conservando su orientación original para que nada quede asimétrico."
            self.after(0, lambda: sm.show_success(self, "PDF UNIDO", msg))
        except Exception as e:
            self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self.master_app._enqueue_done()
    def _run_reorder(self):
        if not getattr(self, "reorder_file_path", None): return
        init_f = f"{Path(self.reorder_file_path).stem}-org.pdf"
        dest = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile=init_f, title="Guardar PDF organizado como...")
        if not dest: return
        
        # Extraer orden real desde el estado del grid visual
        seq = [c._orig_pn for c in self.reorder_thumb_inner._cells]
        
        self.master_app._pulse_progress()
        threading.Thread(target=self._do_reorder, args=(self.reorder_file_path, dest, seq), daemon=True).start()

    def _do_reorder(self, src, dest, seq):
        try:
            import PyPDF2
            self.ui_log(f"🔄 Reorganizando páginas internamente...", "accent")
            reader = PyPDF2.PdfReader(src)
            writer = PyPDF2.PdfWriter()
            
            for idx, page_num in enumerate(seq):
                writer.add_page(reader.pages[page_num - 1])
                self.ui_progress(((idx+1)/len(seq))*90, f"Copiando página {page_num} en nueva posición {idx+1}...")
                
            with open(dest, "wb") as f_out:
                writer.write(f_out)
                
            self.ui_log(f"✅ PDF organizado correctamente: {Path(dest).name}", "success")
            self.master_app.log_history("Organizar PDF", f"Páginas redispuestas: {len(seq)}", "🔄")
            self.after(0, lambda: sm.show_success(self, "NUEVO ORDEN APLICADO", f"El nuevo orden de páginas se ha guardado en:\n{Path(dest).name}"))
        except Exception as e:
            err_msg = str(e)
            self.ui_log(f"❌ Error rotando: {err_msg}", "error")
        finally:
            self.master_app._enqueue_done()

    def _run_delete(self):
        if not self.del_file_path:
            return messagebox.showwarning("Sin archivo", "Abre un PDF primero.")
        raw = self.del_pages_var.get().strip()
        if not raw:
            return messagebox.showwarning("Sin páginas", "Especifica qué páginas eliminar.")
        
        # IA: Sugerir nombre con sufijo
        init_f = f"{Path(self.del_file_path).stem}-remove-page.pdf"
        dest = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF", "*.pdf")],
            initialfile=init_f,
            title="Guardar nuevo PDF como..."
        )
        if not dest: return
        self.master_app._pulse_progress()
        threading.Thread(target=self._do_delete, args=(raw, dest), daemon=True).start()

    def _do_delete(self, raw_pages, dest):
        try:
            import PyPDF2
            # Parsear rangos como "1,3,5-8"
            to_delete = set()
            for part in raw_pages.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-")
                    to_delete.update(range(int(a), int(b)+1))
                elif part:
                    to_delete.add(int(part))

            reader = PyPDF2.PdfReader(self.del_file_path)
            writer = PyPDF2.PdfWriter()
            total = len(reader.pages)
            kept = 0
            for i, page in enumerate(reader.pages, start=1):
                if i not in to_delete:
                    writer.add_page(page)
                    kept += 1
                self.ui_progress((i / total) * 90, f"Procesando página {i}/{total}")

            with open(dest, "wb") as f:
                writer.write(f)
            self.ui_log(f"✅ PDF guardado: {kept} páginas conservadas, {len(to_delete)} eliminadas.", "success")
            self.master_app.log_history("PDF Delete", f"Páginas borradas en {Path(self.del_file_path).name}", "🖥️")
            self.after(0, lambda: sm.show_success(self, "PDF GUARDADO", f"Se ha(n) eliminado {len(to_delete)} página(s) con éxito.\nMantuviste {kept} página(s)."))
        except Exception as e:
            self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self.master_app._enqueue_done()

    def _run_blank(self):
        if not self.blank_file_path:
            return messagebox.showwarning("Sin archivo", "Abre un PDF primero.")
        
        # IA: Sugerir nombre con sufijo
        init_f = f"{Path(self.blank_file_path).stem}-insert.pdf"
        dest = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF", "*.pdf")],
            initialfile=init_f,
            title="Guardar PDF con páginas en blanco como..."
        )
        if not dest: return
        self.master_app._pulse_progress()
        threading.Thread(target=self._do_blank, args=(dest,), daemon=True).start()

    def _do_blank(self, dest):
        try:
            import PyPDF2
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            pos = int(self.blank_pos_var.get())
            qty = int(self.blank_qty_var.get())
            reader = PyPDF2.PdfReader(self.blank_file_path)
            total = len(reader.pages)

            # Crear una página en blanco con reportlab
            import io
            blank_buf = io.BytesIO()
            c = canvas.Canvas(blank_buf, pagesize=A4)
            c.showPage()
            c.save()
            blank_buf.seek(0)
            blank_reader = PyPDF2.PdfReader(blank_buf)
            blank_page = blank_reader.pages[0]

            writer = PyPDF2.PdfWriter()
            for i, page in enumerate(reader.pages):
                writer.add_page(page)
                if i + 1 == pos:
                    for _ in range(qty):
                        writer.add_page(blank_page)
                self.ui_progress(((i+1) / total) * 90, f"Procesando pág {i+1}/{total}")

            # Si pos=0, insertar al inicio
            if pos == 0:
                # rewrite: blank pages first
                writer2 = PyPDF2.PdfWriter()
                for _ in range(qty):
                    writer2.add_page(blank_page)
                for page in reader.pages:
                    writer2.add_page(page)
                writer = writer2

            with open(dest, "wb") as f:
                writer.write(f)
            self.ui_log(f"✅ {qty} página(s) en blanco insertadas después de pág. {pos}.", "success")
            self.master_app.log_history("PDF Blanco", f"Insertadas en {Path(self.blank_file_path).name}", "📤")
            self.after(0, lambda: sm.show_success(self, "PÁGINAS INSERTADAS", f"Se insertaron {qty} página(s) en blanco\nposterior a la página {pos}."))
        except Exception as e:
            self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self.master_app._enqueue_done()



    def _run_protect(self):
        if not self.prot_file_path:
            return messagebox.showwarning("Sin archivo", "Abre un PDF primero.")
        pw = self.prot_pw.get().strip()
        if len(pw) < 4:
            return messagebox.showwarning("Contraseña", "Mínimo 4 caracteres.")
        
        # IA: Sugerir nombre con sufijo
        init_f = f"{Path(self.prot_file_path).stem}-protected.pdf"
        dest = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF", "*.pdf")],
            initialfile=init_f,
            title="Guardar PDF protegido como..."
        )
        if not dest: return
        self.master_app._pulse_progress()
        threading.Thread(target=self._do_protect, args=(pw, dest), daemon=True).start()

    def _do_protect(self, pw, dest):
        try:
            import PyPDF2
            self.ui_log(f"🔒 Protegiendo PDF con contraseña...", "accent")
            reader = PyPDF2.PdfReader(self.prot_file_path)
            writer = PyPDF2.PdfWriter()
            for i, page in enumerate(reader.pages):
                writer.add_page(page)
                self.ui_progress(((i+1) / len(reader.pages)) * 90, f"Página {i+1}...")
            writer.encrypt(pw)
            with open(dest, "wb") as f:
                writer.write(f)
            self.ui_log(f"✅ PDF protegido guardado: {Path(dest).name}", "success")
            self.master_app.log_history("PDF Protect", f"Protegido: {Path(dest).name}", "🔒")
        except Exception as e:
            self.ui_log(f"❌ Error: {e}", "error")
        finally:
            self.master_app._enqueue_done()


    def _ai_summarize_files(self):
        if not self.merge_files:
            return messagebox.showwarning("Sin archivos", "Selecciona al menos un PDF para resumir.")
        
        self.master_app._pulse_progress()
        self.ui_log("✨ El Cerebro IA está leyendo tus PDFs...", "accent")
        threading.Thread(target=self._do_ai_summary, daemon=True).start()

    def _do_ai_summary(self):
        if not HAS_PYPDF or PyPDF2 is None:
            return self.ui_log("❌ Error: PyPDF2 no está instalado. Ejecuta: pip install PyPDF2", "error")
        try:
            import requests, json
            # Leer texto del primer PDF (como muestra)
            reader = PyPDF2.PdfReader(self.merge_files[0])
            text_sample = ""
            for i in range(min(3, len(reader.pages))):
                text_sample += reader.pages[i].extract_text() + "\n"
            
            if not text_sample.strip():
                return self.after(0, lambda: messagebox.showerror("Error IA", "No se pudo extraer texto del PDF."))

            self.ui_log(f"⏳ Procesando con {self.master_app.ai_model}...", "muted")
            
            key = self.master_app.ai_key
            prov = self.master_app.ai_provider
            model = self.master_app.ai_model
            
            # API endpoint condicional (Default Groq)
            url = "https://api.groq.com/openai/v1/chat/completions"
            
            if "deepseek" in prov.lower():
                url = "https://api.deepseek.com/v1/chat/completions"
            elif "openrouter" in prov.lower():
                url = "https://openrouter.ai/api/v1/chat/completions"
            elif "cerebras" in prov.lower():
                url = "https://api.cerebras.ai/v1/chat/completions"

            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Eres un asistente experto en análisis de documentos. Resume el siguiente contenido en 5 puntos clave muy concisos. Usa un tono profesional y directo."},
                    {"role": "user", "content": f"Resume este fragmento de PDF:\n\n{text_sample[:4000]}"}
                ],
                "temperature": 0.5
            }
            
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                summary = res.json()['choices'][0]['message']['content']
                self.after(0, lambda: sm.show_success(self, "RESUMEN IA (✨)", f"Aquí tienes lo más importante de tus archivos:\n\n{summary}"))
                self.ui_log("✅ Resumen IA generado con éxito.", "success")
            else:
                self.ui_log(f"❌ Error API: {res.text}", "error")
        except Exception as e:
            self.ui_log(f"❌ Error IA: {e}", "error")
        finally:
            self.master_app._enqueue_done()

class ViewOCR(BaseToolView):
    """Lanzador para la herramienta externa OCR Scanner Pro."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)
        f.pack(fill="both", expand=True)

        card = ctk.CTkFrame(f, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"))
        card.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Banner Superior
        banner = ctk.CTkFrame(card, height=220, corner_radius=15, fg_color=("#8B5CF6", "#4C1D95"))
        banner.pack(fill="x", padx=15, pady=15)
        banner.pack_propagate(False)

        ctk.CTkLabel(banner, text="🔍", font=ctk.CTkFont(size=70)).pack(pady=(35, 10))
        ctk.CTkLabel(banner, text="OCR SCANNER PRO v2.0", 
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="white").pack()
        
        # Info
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="both", expand=True, padx=40, pady=20)
        
        desc = "Extracción de texto de grado profesional (v2.0).\n\n" \
               "• Motor Neuronal LSTM mejorado para máxima precisión.\n" \
               "• Nueva Binarización Adaptativa Otsu (Filtro Anti-Ruido).\n" \
               "• Corrección automática de errores comunes (Post-Procesamiento).\n" \
               "• Segmentación de página completa y detección de columnas.\n" \
               "• Digitaliza facturas, menús y notas complejas con un clic."
        
        ctk.CTkLabel(info, text=desc, font=ctk.CTkFont(size=14), justify="left", 
                     text_color=("#475569", "#94A3B8")).pack(anchor="w")

        # Botón de Lanzamiento
        ctk.CTkButton(card, text="🚀  Abrir OCR Scanner Pro", 
                      height=54, corner_radius=12,
                      fg_color="#8B5CF6", hover_color="#7C3AED",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._open_ocr).pack(pady=(0, 20), padx=40, fill="x")

    def _open_ocr(self):
        import subprocess
        # IA: Pasar credenciales de IA si están activas para OCR de Alta Precisión
        ai_args = []
        if self.master_app.ai_active and self.master_app.ai_has_vision:
            ai_args = [
                "--key", str(self.master_app.ai_key), 
                "--provider", str(self.master_app.ai_provider), 
                "--model", str(self.master_app.ai_model)
            ]

        if getattr(sys, 'frozen', False):
            exe = sys.executable
            cmd = [exe, "--ocr"] + ai_args
        else:
            cmd = [sys.executable, "ocr_pro.py"] + ai_args

        try:
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.master_app.log_history("OCR Pro", "Herramienta externa iniciada con motor IA" if ai_args else "Herramienta externa iniciada", "🔍")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir ocr_pro.py:\n{e}")


# ─── 🎨 PALETA DE COLORES PRO (LANZADOR) ─────────────────────────

class ViewPalette(BaseToolView):
    """Lanzador para la herramienta externa Paleta de Colores Pro."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)
        f.pack(fill="both", expand=True)

        card = ctk.CTkFrame(f, corner_radius=15, fg_color=("#FFFFFF", "#1C2033"))
        card.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Banner Superior
        banner = ctk.CTkFrame(card, height=220, corner_radius=15, fg_color=("#EC4899", "#831843"))
        banner.pack(fill="x", padx=15, pady=15)
        banner.pack_propagate(False)

        ctk.CTkLabel(banner, text="🎨", font=ctk.CTkFont(size=70)).pack(pady=(35, 10))
        ctk.CTkLabel(banner, text="PALETA DE COLORES PRO", 
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="white").pack()
        
        # Info
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="both", expand=True, padx=40, pady=20)
        
        desc = "Extrae el ADN visual de cualquier imagen.\n\n" \
               "• Obtén paletas de colores representativas automáticamente.\n" \
               "• Sugerencias inteligentes de contraste para tipografía.\n" \
               "• Exporta a HEX, RGB y Tailwind CSS instantáneamente.\n" \
               "• Ideal para diseñadores, desarrolladores y creadores de contenido."
        
        ctk.CTkLabel(info, text=desc, font=ctk.CTkFont(size=14), justify="left", 
                     text_color=("#475569", "#94A3B8")).pack(anchor="w")

        # Botón de Lanzamiento
        ctk.CTkButton(card, text="🚀  Abrir Extractor de Paletas", 
                      height=54, corner_radius=12,
                      fg_color="#EC4899", hover_color="#DB2777",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._open_palette).pack(padx=60, pady=(0, 40), fill="x")

    def _open_palette(self):
        """Lanza la paleta pro como proceso independiente."""
        import subprocess
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--palette"]
        else:
            p_path = Path(__file__).parent / "palette_pro.py"
            if not p_path.exists():
                messagebox.showerror("Error", "No se encontró palette_pro.py")
                return
            cmd = [sys.executable, str(p_path)]

        try:
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.master_app.log_history("Paleta Pro", "Herramienta externa iniciada", "🎨")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir:\n{e}")


# ─── 🌐 DIAGNÓSTICO DE RED PRO (LANZADOR) ─────────────────────────

class ViewNetworkDiagnostic(BaseToolView):
    """Lanzador para la herramienta externa WiFi Monitor Pro."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)
        f.pack(fill="both", expand=True)

        card = ctk.CTkFrame(f, corner_radius=15, fg_color=("#FFFFFF", "#121420"))
        card.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Banner Superior
        banner = ctk.CTkFrame(card, height=220, corner_radius=15, fg_color=("#3B82F6", "#1D4ED8"))
        banner.pack(fill="x", padx=15, pady=15)
        banner.pack_propagate(False)

        ctk.CTkLabel(banner, text="🌐", font=ctk.CTkFont(size=70)).pack(pady=(35, 10))
        ctk.CTkLabel(banner, text="WIFI MONITOR PRO v3.0", 
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="white").pack()
        
        # Info
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="both", expand=True, padx=40, pady=20)
        
        desc = "Diagnóstico profundo de red y monitoreo inalámbrico de grado profesional.\n\n" \
               "• Análisis de latencia en tiempo real (Salto local y Salto WAN).\n" \
               "• Escáner avanzado de redes cercanas con análisis de congestión de canales.\n" \
               "• Detección dinámica de adaptadores WiFi y Ethernet.\n" \
               "• Registro histórico de caídas, jitter y pérdida de paquetes.\n" \
               "• Auditoría de errores en controladores de red a nivel de Eventos de Windows.\n" \
               "• Herramientas de auto-reparación: Flush DNS, Reset Stack e IP Renew."
        
        ctk.CTkLabel(info, text=desc, font=ctk.CTkFont(size=14), justify="left", 
                     text_color=("#475569", "#94A3B8")).pack(anchor="w")

        # Botón de Lanzamiento
        ctk.CTkButton(card, text="🚀  Abrir Diagnóstico de Red Pro", 
                      height=54, corner_radius=12,
                      fg_color="#3B82F6", hover_color="#2563EB",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._open_network).pack(pady=(0, 20), padx=40, fill="x")

    def _open_network(self):
        """Lanza el monitor de red como proceso independiente."""
        import subprocess, sys, os
        from pathlib import Path
        
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wifi_monitor_gui.py")
        
        if not os.path.exists(script_path):
            messagebox.showerror("Error", f"No se encontró el archivo:\n{script_path}")
            return

        try:
            subprocess.Popen([sys.executable, script_path], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.master_app.log_history("Red Pro", "Herramienta externa iniciada", "🌐")
            self.ui_log("Lanzando Diagnóstico de Red Independiente...", "info")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el monitor de red:\n{e}")

# ─── 🕒 HISTORIAL DE ACTIVIDAD ───────────────────────────────────────


class ViewHistory(BaseToolView):
    """Muestra los registros guardados en la base de datos SQLite."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(h, text="🕒 Historial de Actividad", font=ctk.CTkFont(size=26, weight="bold"), text_color="#34D399").pack(anchor="w")
        ctk.CTkLabel(h, text="Registro permanente de todas las operaciones realizadas en la Suite.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        # Botón para refrescar y limpiar
        btn_f = ctk.CTkFrame(h, fg_color="transparent")
        btn_f.pack(side="right")
        ctk.CTkButton(btn_f, text="🔄 Refrescar", width=100, height=32, command=self.load_data).pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="🗑️ Borrar Todo", width=100, height=32, fg_color="#EF4444", hover_color="#B91C1C", command=self._clear_db).pack(side="left")

        # Table-like container
        self.scroll = ctk.CTkScrollableFrame(self, corner_radius=12, fg_color=("#FFFFFF", "#1C2033"))
        self.scroll.pack(fill="both", expand=True)

    def load_data(self):
        # Limpiar anterior
        for w in self.scroll.winfo_children(): w.destroy()
        
        data = self.master_app.db.get_all()
        if not data:
            ctk.CTkLabel(self.scroll, text="No hay registros aún. Comienza a usar las herramientas para verlo aquí.", 
                         text_color="gray", pady=40).pack()
            return

        for ts, act, det, ico in data:
            row = ctk.CTkFrame(self.scroll, fg_color=("#F3F4F6", "#0D0F1A"), height=60, corner_radius=10)
            row.pack(fill="x", pady=4, padx=10)
            
            ctk.CTkLabel(row, text=ico, font=ctk.CTkFont(size=20), width=50).pack(side="left", padx=10)
            
            c_info = ctk.CTkFrame(row, fg_color="transparent")
            c_info.pack(side="left", fill="both", expand=True, pady=8)
            
            ctk.CTkLabel(c_info, text=act, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(c_info, text=det, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
            ctk.CTkLabel(row, text=ts, font=ctk.CTkFont(size=10), text_color="gray").pack(side="right", padx=15)

    def _clear_db(self):
        if sm.ask_confirm(self, "Limpiar Historial", "¿Seguro que quieres borrar todo el registro? Esta acción no se puede deshacer.", type="warning", color="#EF4444"):
            self.master_app.db.clear()
            self.load_data()

class ViewAppRemover(BaseToolView):
    """Módulo integrado de eliminación de bloatware (Windows App Remover)."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.apps_vars = {}
        
        # --- HEADER ---
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(h, text="🛡️ Bloatware Remover Pro", font=ctk.CTkFont(size=26, weight="bold"), text_color="#A78BFA").pack(anchor="w")
        ctk.CTkLabel(h, text="Optimización profunda: Desinstala aplicaciones de fábrica de Windows de forma segura.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        # Admin Warning (Inline)
        self._check_admin()

        # --- MAIN CONTAINER (Abarca todo el espacio) ---
        self.content_card = ctk.CTkFrame(self, corner_radius=16, fg_color=("#FFFFFF", "#121420"))
        self.content_card.pack(fill="both", expand=True, pady=(0, 15))
        
        # Scrollable area for apps
        self.scroll = ctk.CTkScrollableFrame(self.content_card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Bottom Actions
        self.action_f = ctk.CTkFrame(self, fg_color="transparent")
        self.action_f.pack(fill="x")

        self.btn = ctk.CTkButton(self.action_f, text="🔍  Escanear Sistema", height=50, corner_radius=12, 
                                 fg_color="#7C3AED", hover_color="#6D28D9", font=ctk.CTkFont(size=16, weight="bold"),
                                 command=self._start_scan)
        self.btn.pack(fill="x")
        
        # Estado inicial
        self.status_lbl = ctk.CTkLabel(self.scroll, text="Haz clic en 'Escanear Sistema' para buscar aplicaciones instaladas.", 
                                      font=ctk.CTkFont(size=13), text_color="gray")
        self.status_lbl.pack(pady=100)

    def _check_admin(self):
        import ctypes
        is_admin = False
        try: is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except: pass
        if not is_admin:
            msg_f = ctk.CTkFrame(self, fg_color=("#FEE2E2", "#450A0A"), corner_radius=8, height=30)
            msg_f.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(msg_f, text="⚠️ ACCESO LIMITADO: Ejecuta PowerSuite como Administrador para poder desinstalar.", 
                         font=ctk.CTkFont(size=11, weight="bold"), text_color=("#991B1B", "#FCA5A5")).pack(pady=4)

    def _start_scan(self):
        self.btn.configure(state="disabled", text="🔍  Escaneando Sistema...")
        for w in self.scroll.winfo_children(): w.destroy()
        
        self.status_lbl = ctk.CTkLabel(self.scroll, text="Analizando paquetes instalados en Windows...", 
                                      font=ctk.CTkFont(size=14))
        self.status_lbl.pack(pady=100)
        
        self.master_app._pulse_progress()
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        """Escanea el sistema usando PowerShell para obtener paquetes reales."""
        try:
            # Comando para obtener solo el nombre y el package full name
            cmd = "Get-AppxPackage | Select-Object Name, PackageFullName | ConvertTo-Json"
            result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, shell=True)
            
            import json
            packages = []
            if result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict): data = [data] # Si solo hay uno
                packages = data
            
            # Lista de patrones conocidos de bloatware
            bloat_patterns = [
                "Xbox", "Zune", "BingWeather", "Solitaire", "GetHelp", "Getstarted", 
                "OneNote", "Skype", "Maps", "communicationsapps", "YourPhone", 
                "People", "3D", "549981C3F5F10", "PowerAutomate", "StickyNotes",
                "FeedbackHub", "SoundRecorder", "Wallet", "MixedReality", "BingNews",
                "BingSports", "BingFinance", "OfficeHub", "Paint3D", "Print3D",
                "Corton", "Disney", "Spotify", "Netflix", "TikTok"
            ]
            
            found_apps = []
            for pkg in packages:
                name = pkg.get("Name", "")
                full_name = pkg.get("PackageFullName", "")
                
                # Clasificar como bloatware si coincide con patrones
                is_bloat = any(p.lower() in name.lower() for p in bloat_patterns)
                
                # Solo mostrar apps de Microsoft o apps sospechosas (evitar drivers/componentes críticos)
                if ("Microsoft." in name or is_bloat) and ".Framework" not in name and ".Runtime" not in name:
                    clean_name = name.replace("Microsoft.", "").replace("Windows.", "")
                    found_apps.append({
                        "display_name": clean_name,
                        "pkg_name": name,
                        "full_name": full_name,
                        "is_known_bloat": is_bloat
                    })
            
            # Ordenar: primero los bloatware conocidos
            found_apps.sort(key=lambda x: x["is_known_bloat"], reverse=True)
            
            self.after(0, lambda: self._show_apps(found_apps))
            
        except Exception as e:
            self.ui_log(f"❌ Error al escanear: {e}", "error")
            self.after(0, lambda: self.btn.configure(state="normal", text="🔍  Reintentar Escaneo"))

    def _show_apps(self, apps):
        if hasattr(self, 'status_lbl'): self.status_lbl.destroy()
        self.apps_vars = {}
        self.master_app._enqueue_done()
        
        if not apps:
            self.status_lbl = ctk.CTkLabel(self.scroll, text="No se encontraron aplicaciones eliminables.", font=ctk.CTkFont(size=14))
            self.status_lbl.pack(pady=100)
            self.btn.configure(state="normal", text="🔍  Escanear de Nuevo")
            return

        self.ui_log(f"🛡️ Escaneo finalizado. {len(apps)} aplicaciones detectadas.", "info")
        
        # --- TOOLBAR SUPERIOR ---
        toolbar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(0, 15))
        
        ctk.CTkButton(toolbar, text="✨ Seleccionar Todo el Bloatware", height=32, corner_radius=20,
                      fg_color=("#F1F5F9", "#1E293B"), text_color=("#6366F1", "#A78BFA"),
                      font=ctk.CTkFont(size=11, weight="bold"), border_width=1, border_color="#6366F1",
                      command=lambda: self._select_all_bloat(apps)).pack(side="left")
        
        ctk.CTkButton(toolbar, text="Desmarcar Todo", height=28, fg_color="transparent", 
                      text_color="gray", font=ctk.CTkFont(size=11),
                      command=self._deselect_all).pack(side="right", padx=10)

        # Header de la tabla
        th = ctk.CTkFrame(self.scroll, fg_color="transparent")
        th.pack(fill="x", padx=15, pady=(0, 5))
        ctk.CTkLabel(th, text="Aplicación / Paquete", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(side="left")
        ctk.CTkLabel(th, text="Estado Recomendado", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(side="right")

        for app in apps:
            var = ctk.BooleanVar(value=False)
            pkg_id = app["pkg_name"]
            self.apps_vars[pkg_id] = var
            
            row = ctk.CTkFrame(self.scroll, fg_color=("#F3F4F6", "#0D0F1A"), corner_radius=10)
            row.pack(fill="x", pady=3, padx=10)
            
            # Indicador de Bloatware
            if app["is_known_bloat"]:
                badge = ctk.CTkLabel(row, text=" BLOATWARE ", font=ctk.CTkFont(size=9, weight="bold"),
                                    fg_color="#450A0A", text_color="#FCA5A5", corner_radius=4)
                badge.pack(side="right", padx=15)
            else:
                badge = ctk.CTkLabel(row, text=" SISTEMA ", font=ctk.CTkFont(size=9, weight="bold"),
                                    fg_color="#064E3B", text_color="#4ADE80", corner_radius=4)
                badge.pack(side="right", padx=15)

            cb = ctk.CTkCheckBox(row, text=app["display_name"], variable=var, font=ctk.CTkFont(size=13, weight="bold"),
                                 checkbox_width=20, checkbox_height=20, border_width=2)
            cb.pack(side="left", padx=15, pady=12)
            
            ctk.CTkLabel(row, text=app["pkg_name"], font=ctk.CTkFont(size=10), text_color="#64748B").pack(side="left")

        self.btn.configure(state="normal", text="🗑️  Eliminar Seleccionados", command=self._confirm_cleanup, 
                           fg_color="#DC2626", hover_color="#B91C1C")

    def _select_all_bloat(self, apps):
        for app in apps:
            if app["is_known_bloat"]:
                self.apps_vars[app["pkg_name"]].set(True)
        self.ui_log("✨ Bloatware recomendado seleccionado automáticamente.", "accent")

    def _deselect_all(self):
        for var in self.apps_vars.values(): var.set(False)

    def _confirm_cleanup(self):
        to_remove = [p for p, v in self.apps_vars.items() if v.get()]
        if not to_remove:
            return messagebox.showwarning("Selección vacía", "Elige al menos una aplicación para eliminar.")
        
        msg = f"¿Deseas desinstalar permanentemente {len(to_remove)} aplicaciones?\n\nEsta acción no se puede deshacer de forma sencilla sin la Microsoft Store."
        if sm.ask_confirm(self, "AUTORIZAR LIMPIEZA PROFUNDA", msg, type="warning", color="#DC2626"):
            self.btn.configure(state="disabled", text="🛡️  Procesando Limpieza...")
            threading.Thread(target=self._run_cleanup, args=(to_remove,), daemon=True).start()

    def _run_cleanup(self, apps):
        total = len(apps)
        self.ui_log(f"🚜 Iniciando desinstalación de {total} aplicaciones...", "accent")
        
        for i, pkg in enumerate(apps):
            self.ui_progress(((i+1)/total)*100, f"Eliminando: {pkg}")
            self.ui_log(f"  🗑️ Borrando: {pkg}", "muted")
            
            # Comando PowerShell para eliminar el paquete del usuario actual y provisionado
            # Usamos -ErrorAction SilentlyContinue para evitar que errores menores detengan el proceso
            cmd = f"Get-AppxPackage -Name '*{pkg}*' | Remove-AppxPackage -ErrorAction SilentlyContinue"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, shell=True)
            
            # También intentar quitar el paquete provisionado (para que no vuelva al crear nuevos usuarios)
            cmd_prov = f"Get-AppxProvisionedPackage -Online | Where-Object {{$_.PackageName -like '*{pkg}*'}} | Remove-AppxProvisionedPackage -Online"
            subprocess.run(["powershell", "-Command", cmd_prov], capture_output=True, shell=True)
            
        self.master_app.log_history("Debloat Pro", f"Eliminadas {total} aplicaciones de fábrica", "🛡️")
        self.ui_log(f"✅ ¡Limpieza completada! {total} paquetes procesados.", "success")
        
        self.after(0, lambda: sm.show_success(self, "LIMPIEZA COMPLETADA", 
                    f"Se han eliminado {total} aplicaciones satisfactoriamente.\nTu sistema es ahora más ligero y privado."))
        
        # Pequeña demora para que Windows actualice su base de datos antes de re-escanear
        time.sleep(2)
        self.after(0, self._start_scan) 
        self.master_app._enqueue_done()


class ViewSystemHealth(BaseToolView):
    """Verifica la salud del sistema y ayuda a instalar dependencias faltantes."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(h, text="🩺 Diagnóstico de Salud", font=ctk.CTkFont(size=26, weight="bold"), text_color="#3B82F6").pack(anchor="w")
        ctk.CTkLabel(h, text="Verifica si tu sistema tiene todo lo necesario para funcionar al 100%.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        # Container for dependency cards
        self.scroll = ctk.CTkScrollableFrame(self, corner_radius=15, fg_color=("#F8FAFC", "#121420"))
        self.scroll.pack(fill="both", expand=True, pady=(0, 20))
        
        self.btn_refresh = ctk.CTkButton(self, text="🔄  Analizar de Nuevo", height=45, corner_radius=10, 
                                        fg_color="#3B82F6", hover_color="#2563EB", font=ctk.CTkFont(weight="bold"),
                                        command=self._run_audit)
        self.btn_refresh.pack(fill="x")
        
        self._run_audit()

    def _run_audit(self):
        for w in self.scroll.winfo_children(): w.destroy()
        self.ui_log("🔍 Iniciando auditoría de dependencias...", "info")
        
        # 1. Verificar FFmpeg (Crítico para descargas)
        self._check_ffmpeg()
        # 2. Verificar Tesseract (Crítico para OCR)
        self._check_tesseract()
        # 3. Verificar yt-dlp (Descargador)
        self._check_python_lib("yt-dlp", "yt_dlp", "Descargador de Video", "https://github.com/yt-dlp/yt-dlp")
        # 4. Verificar rembg (Quita Fondos)
        self._check_python_lib("rembg", "rembg", "Eliminador de Fondos IA", "https://github.com/danielgatis/rembg")
        # 5. Verificar Librerías PDF
        self._check_python_lib("PyPDF2", "PyPDF2", "Unión y División de PDF", "https://pypi.org/project/PyPDF2/")
        self._check_python_lib("Pikepdf", "pikepdf", "Edición Avanzada de PDF", "https://pypi.org/project/pikepdf/")
        self._check_python_lib("ReportLab", "reportlab", "Creación de PDFs", "https://pypi.org/project/reportlab/")

    def _add_dep_card(self, name, status, desc, action_text=None, action_cmd=None, color=None):
        card = ctk.CTkFrame(self.scroll, fg_color=("#FFFFFF", "#0D0F1A"), corner_radius=10)
        card.pack(fill="x", pady=4, padx=10)
        
        # Status Ball
        ball_color = "#10B981" if status else "#EF4444"
        if color: ball_color = color
        
        status_f = ctk.CTkFrame(card, width=12, height=12, corner_radius=6, fg_color=ball_color)
        status_f.pack(side="left", padx=(15, 10))
        
        # Text info
        info_f = ctk.CTkFrame(card, fg_color="transparent")
        info_f.pack(side="left", fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(info_f, text=name, font=ctk.CTkFont(size=14, weight="bold"), 
                     text_color=("#1E293B", "#F1F5F9")).pack(anchor="w")
        ctk.CTkLabel(info_f, text=desc, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
        
        # Action button
        if action_text and action_cmd:
            btn = ctk.CTkButton(card, text=action_text, width=100, height=28, corner_radius=6, 
                                fg_color=("#E2E8F0", "#1E293B"), text_color=("#2563EB", "#60A5FA"),
                                font=ctk.CTkFont(size=11, weight="bold"), command=action_cmd)
            btn.pack(side="right", padx=15)
        elif not status:
            ctk.CTkLabel(card, text="FALTA", text_color="#EF4444", font=ctk.CTkFont(size=10, weight="bold")).pack(side="right", padx=15)
        else:
            ctk.CTkLabel(card, text="INSTALADO", text_color="#10B981", font=ctk.CTkFont(size=10, weight="bold")).pack(side="right", padx=15)

    def _check_ffmpeg(self):
        has_ffmpeg = False
        try:
            res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, shell=True)
            has_ffmpeg = "ffmpeg version" in res.stdout
        except: has_ffmpeg = False
        
        desc = "Necesario para unir audio y video en descargas de alta calidad." if has_ffmpeg else \
               "Crítico: Sin esto, las descargas solo serán de baja calidad o solo audio."
        
        def download_ffmpeg():
            import webbrowser
            webbrowser.open("https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z")
            messagebox.showinfo("Instalación FFmpeg", "1. Descarga el archivoy descomprímelo.\n2. Pon la carpeta 'bin' en tu PATH de Windows.\n3. Reinicia PowerSuite.")

        self._add_dep_card("FFmpeg (Motor Multimedia)", has_ffmpeg, desc, 
                          "🌐 Descargar" if not has_ffmpeg else None, download_ffmpeg if not has_ffmpeg else None)

    def _check_tesseract(self):
        exists = HAS_TESSERACT
        desc = "Motor de reconocimiento visual de texto (OCR)." if exists else \
               "Falta: Instala Tesseract para poder escanear texto de imágenes."
        
        def download_tess():
            import webbrowser
            webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")
        
        self._add_dep_card("Tesseract OCR", exists, desc,
                          "🌐 Web Oficial" if not exists else None, download_tess if not exists else None)

    def _check_python_lib(self, name, import_name, description, url):
        exists = False
        try:
            __import__(import_name)
            exists = True
        except ImportError: exists = False
        
        def install_lib():
            self.ui_log(f"🛠️ Intentando instalar {name}...", "accent")
            self.master_app._pulse_progress()
            threading.Thread(target=self._do_install, args=(name, import_name, url), daemon=True).start()

        self._add_dep_card(f"{name} (Python Lib)", exists, description,
                          "⚡ Instalar" if not exists else None, install_lib if not exists else None)

    def _do_install(self, name, import_name, url):
        import sys
        try:
            # Intentar instalar vía pip
            subprocess.run([sys.executable, "-m", "pip", "install", name], capture_output=True, check=True)
            self.ui_log(f"✅ {name} instalado correctamente.", "success")
            self.after(0, lambda: sm.show_success(self, "LIBRERÍA INSTALADA", f"Se ha instalado {name} con éxito.\nYa puedes usar las funciones relacionadas."))
            self._run_audit()
        except:
            self.ui_log(f"❌ Falló la instalación automática de {name}.", "error")
            import webbrowser
            self.after(0, lambda: [
                messagebox.showerror("Error de Instalación", f"No se pudo instalar {name} automáticamente.\nPor favor, instálalo manualmente con:\npip install {name}"),
                webbrowser.open(url)
            ])
        finally:
            self.master_app._enqueue_done()




class ViewAIConfig(BaseToolView):
    """Configuración centralizada de servicios de IA (Groq, DeepSeek, etc)."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        
        # --- HEADER ---
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(h, text="⚙️  Configuración de IA", font=ctk.CTkFont(size=26, weight="bold"), text_color="#A78BFA").pack(anchor="w")
        ctk.CTkLabel(h, text="Control total sobre tus modelos de lenguaje preferidos.", font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")

        # --- CARD PRINCIPAL ---
        card = ctk.CTkFrame(self, corner_radius=16, fg_color=("#F8FAFC", "#121420"))
        card.pack(fill="both", expand=True, pady=(0, 20))
        
        container = ctk.CTkFrame(card, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        
        # Grid para inputs
        row1 = ctk.CTkFrame(container, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 20))
        
        # Proveedor
        p_sub = ctk.CTkFrame(row1, fg_color="transparent")
        p_sub.pack(side="left", fill="x", expand=True, padx=(0, 20))
        ctk.CTkLabel(p_sub, text="PROVEEDOR", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w")
        self.provider_var = ctk.StringVar(value=self.master_app.db.get_setting("ai_provider", "Groq"))
        self.provider_menu = ctk.CTkOptionMenu(p_sub, values=["Groq", "DeepSeek", "OpenRouter", "Cerebras"], 
                                             variable=self.provider_var, height=45, corner_radius=10, fg_color="#1E293B", button_color="#334155")
        self.provider_menu.pack(fill="x", pady=(8, 0))
        
        # Modelo ID
        m_sub = ctk.CTkFrame(row1, fg_color="transparent")
        m_sub.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(m_sub, text="ID DE MODELO (MODEL ID)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w")
        self.model_entry = ctk.CTkEntry(m_sub, height=45, corner_radius=10, fg_color="#0F172A", border_width=1,
                                     placeholder_text="llama-3.3-70b-versatile")
        self.model_entry.pack(fill="x", pady=(8, 0))
        self.model_entry.insert(0, self.master_app.db.get_setting("ai_model", "llama-3.3-70b-versatile"))

        # API Key
        ctk.CTkLabel(container, text="CLAVE DE API (API KEY)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w")
        self.key_entry = ctk.CTkEntry(container, height=45, corner_radius=10, fg_color="#0F172A", border_width=1, 
                                     placeholder_text="sk-....", show="•")
        self.key_entry.pack(fill="x", pady=(8, 10))
        self.key_entry.insert(0, self.master_app.db.get_setting("ai_key", ""))
        
        ctk.CTkLabel(container, text="* Los ajustes se guardan cifrados localmente en powersuite.db. Solo es necesario configurar una vez.", 
                     font=ctk.CTkFont(size=10), text_color="#475569").pack(anchor="w")

        # Botón Guardar
        self.save_btn = ctk.CTkButton(container, text="🔌  GUARDAR Y ACTIVAR CEREBRO IA", height=54, corner_radius=15, 
                                      fg_color="#6366F1", hover_color="#4F46E5", font=ctk.CTkFont(size=15, weight="bold"),
                                      command=self._save)
        self.save_btn.pack(fill="x", pady=(40, 0))

    def _save(self):
        key = self.key_entry.get().strip()
        mod = self.model_entry.get().strip()
        provider = self.provider_var.get()
        
        if not key or not mod:
            return messagebox.showwarning("Faltan Datos", "Por favor ingresa la API Key y el Model ID para continuar.")
        
        self.master_app.db.set_setting("ai_key", key)
        self.master_app.db.set_setting("ai_provider", provider)
        self.master_app.db.set_setting("ai_model", mod)
        self.master_app.ai_active = True
        self.master_app.ai_key = key
        self.master_app.ai_model = mod
        # Re-evaluar capacidad visual
        self.master_app.ai_has_vision = self.master_app.is_vision_capable(mod)
        
        vis_msg = "👁️ Soporta Visión (Imágenes)" if self.master_app.ai_has_vision else "📝 Modo Texto (Sin Visión)"
        sm.show_success(self, "CONFIGURACIÓN EXITOSA", f"IA activada.\n\nModelo: {mod}\nProveedor: {provider}\n{vis_msg}")
        self.master_app.log_history("Sistema", f"IA Configurada ({mod})", "⚙️")

# ─── 🚀 MONITOR DE RECURSOS (CPU & RAM) ──────────────────────────────

class ResourceGauge(ctk.CTkFrame):
    """Componente de métrica premium con gráfico de tendencia en tiempo real."""
    def __init__(self, parent, title, icon, color, unit="%", **kwargs):
        super().__init__(parent, corner_radius=20, fg_color=("#FFFFFF", "#121420"), border_width=1, border_color=("#E2E8F0", "#1C2033"), **kwargs)
        self.color = color
        self.unit = unit
        self.history = deque([0]*40, maxlen=40)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 2))
        ctk.CTkLabel(h, text=icon, font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(h, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(side="left")
        
        self.val_lbl = ctk.CTkLabel(self, text=f"0{unit}", font=ctk.CTkFont(size=32, weight="bold"), text_color=color)
        self.val_lbl.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 5))
        
        self.canvas_f = ctk.CTkFrame(self, fg_color=("#F8FAFC", "#0D0F1A"), corner_radius=12)
        self.canvas_f.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self.canvas = tk.Canvas(self.canvas_f, bg="#0D0F1A" if ctk.get_appearance_mode() == "Dark" else "#F8FAFC", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)
        
    def update_value(self, val):
        self.val_lbl.configure(text=f"{val:.1f}{self.unit}")
        self.history.append(val)
        self._draw_chart()

    def _draw_chart(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10 or h < 10: return
        self.canvas.delete("all")
        pts = list(self.history)
        step = w / (len(pts)-1)
        mx = max(pts) if max(pts) > 100 else 100
        if mx == 0: mx = 1
        coords = [(i*step, h-(p/mx*(h-6))-3) for i,p in enumerate(pts)]
        if len(coords) < 2: return
        self.canvas.create_polygon([(0,h)]+coords+[(w,h)], fill=self._get_fade(self.color), outline="")
        self.canvas.create_line(coords, fill=self.color, width=2, smooth=True)
        
    def _get_fade(self, hex_c):
        if not hex_c.startswith("#"): return hex_c
        r, g, b = int(hex_c[1:3],16), int(hex_c[3:5],16), int(hex_c[5:7],16)
        return f'#{r//8:02x}{g//8:02x}{b//8:02x}'

class ViewResourceMonitor(BaseToolView):
    """Monitor avanzado de Sistema con telemetría de 4 métricas y optimización."""
    def __init__(self, parent, master_app):
        super().__init__(parent, master_app)
        self.is_running = False
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", pady=(0, 15))
        tf = ctk.CTkFrame(h, fg_color="transparent")
        tf.pack(side="left")
        ctk.CTkLabel(tf, text="🚀 Monitor de Sistema Pro", font=ctk.CTkFont(size=28, weight="bold"), text_color="#F59E0B").pack(anchor="w")
        ctk.CTkLabel(tf, text="Telemetría en tiempo real y purga de recursos.", font=ctk.CTkFont(size=14), text_color="gray").pack(anchor="w")
        self._build_ui()
        
    def _build_ui(self):
        g = ctk.CTkFrame(self, fg_color="transparent")
        g.pack(fill="x", pady=(0, 20))
        g.grid_columnconfigure((0,1,2,3), weight=1)
        self.cpu_card = ResourceGauge(g, "CPU", "⚡", "#3B82F6")
        self.cpu_card.grid(row=0, column=0, sticky="nsew", padx=(0,4))
        self.ram_card = ResourceGauge(g, "RAM", "🧠", "#10B981")
        self.ram_card.grid(row=0, column=1, sticky="nsew", padx=4)
        self.disk_card = ResourceGauge(g, "DISK", "💾", "#8B5CF6")
        self.disk_card.grid(row=0, column=2, sticky="nsew", padx=4)
        self.net_card = ResourceGauge(g, "NET", "🌐", "#EC4899", unit=" KB/s")
        self.net_card.grid(row=0, column=3, sticky="nsew", padx=(4,0))

        self.ins = ctk.CTkFrame(self, corner_radius=18, fg_color=("#FFFFFF", "#121420"), border_width=1, border_color=("#E2E8F0", "#1C2033"))
        self.ins.pack(fill="x", pady=(0, 20))
        inr = ctk.CTkFrame(self.ins, fg_color="transparent")
        inr.pack(padx=20, pady=15, fill="x")
        ctk.CTkLabel(inr, text="🧠 DIAGNÓSTICO IA", font=ctk.CTkFont(size=11, weight="bold"), text_color="#6366F1").pack(anchor="w")
        self.tips = ctk.CTkLabel(inr, text="Esperando telemetría...", font=ctk.CTkFont(size=14), text_color="gray", wraplength=800, justify="left")
        self.tips.pack(pady=(5, 0), anchor="w")

        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.pack(fill="x", pady=(0, 15))
        self.btn_toggle = ctk.CTkButton(tb, text="▶ INICIAR", height=45, fg_color="#F59E0B", command=self._toggle)
        self.btn_toggle.pack(side="left")
        self.btn_opt = ctk.CTkButton(tb, text="🚀 Optimizar", height=45, fg_color="#8B5CF6", command=self._quick_optimize)
        self.btn_opt.pack(side="left", padx=15)
        
        lc = ctk.CTkFrame(self, corner_radius=20, fg_color=("#FFFFFF", "#121420"), border_width=1, border_color=("#E2E8F0", "#1C2033"))
        lc.pack(fill="both", expand=True)
        th = ctk.CTkFrame(lc, fg_color="transparent")
        th.pack(fill="x", padx=25, pady=10)
        ctk.CTkLabel(th, text="PROCESO", width=250, anchor="w").pack(side="left")
        ctk.CTkLabel(th, text="CPU").pack(side="right", padx=60)
        ctk.CTkLabel(th, text="RAM").pack(side="right", padx=10)

        self.cont = ctk.CTkScrollableFrame(lc, fg_color="transparent")
        self.cont.pack(fill="both", expand=True, padx=5, pady=5)
        self.proc_rows = []
        for _ in range(15):
            r = ctk.CTkFrame(self.cont, fg_color="transparent", height=40)
            n = ctk.CTkLabel(r, text="", width=250, anchor="w")
            n.pack(side="left", padx=10)
            b = ctk.CTkButton(r, text="×", width=30, height=25, fg_color="#EF4444")
            b.pack(side="right", padx=10)
            m = ctk.CTkLabel(r, text="", width=80)
            m.pack(side="right", padx=10)
            c = ctk.CTkLabel(r, text="", width=60)
            c.pack(side="right", padx=10)
            pid = ctk.CTkLabel(r, text="", width=50, text_color="gray")
            pid.pack(side="right", padx=10)
            self.proc_rows.append({'frame': r, 'name': n, 'pid': pid, 'cpu': c, 'mem': m, 'btn': b})

    def _toggle(self):
        if self.is_running:
            self.is_running = False
            self.btn_toggle.configure(text="▶ INICIAR", fg_color="#F59E0B")
        else:
            self.is_running = True
            self.btn_toggle.configure(text="⏹ DETENER", fg_color="#EF4444")
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        import psutil, time
        while self.is_running:
            try:
                cpu_p = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory()
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
                    try:
                        mem = p.info['memory_info'].rss / 1048576
                        if mem > 50: procs.append({'pid': p.info['pid'], 'name': p.info['name'], 'mem': mem, 'cpu': p.info['cpu_percent'] or 0})
                    except: pass
                procs = sorted(procs, key=lambda x: (x['mem'], x['cpu']), reverse=True)[:15]
                self.after(0, lambda cpu=cpu_p, rmem=ram.percent, p_list=procs: self._update_ui(cpu, rmem, p_list))
            except: time.sleep(2)

    def _update_ui(self, cpu_val, ram_val, procs):
        if not self.is_running: return
        self.cpu_card.update_value(cpu_val)
        self.ram_card.update_value(ram_val)
        
        # Update tips
        if cpu_val > 80 or ram_val > 80:
            self.tips.configure(text=f"⚠️ Sistema bajo carga. '{procs[0]['name']}' es el principal consumidor.", text_color="#EF4444")
        else:
            self.tips.configure(text="✨ Sistema estable y optimizado.", text_color="#10B981")

        for i, row in enumerate(self.proc_rows):
            if i < len(procs):
                p = procs[i]
                row['frame'].pack(fill="x", pady=2)
                row['name'].configure(text=p['name'][:30])
                row['pid'].configure(text=str(p['pid']))
                row['cpu'].configure(text=f"{p['cpu']:.1f}%")
                row['mem'].configure(text=f"{p['mem']:.0f} MB")
                row['btn'].configure(command=lambda pid=p['pid'], name=p['name']: self._kill_proc(pid, name))
            else:
                row['frame'].pack_forget()

    def _kill_proc(self, pid, name):
        if not sm.ask_confirm(self, "Forzar Cierre", f"¿Cerrar '{name}'?", type="warning", color="#DC2626"): return
        import psutil
        try:
            psutil.Process(pid).kill()
            self.ui_log(f"💥 Terminado PID {pid}", "success")
        except: pass

    def _quick_optimize(self):
        self.btn_opt.configure(state="disabled", text="...")
        def run():
            import ctypes, os, psutil
            if os.name == 'nt':
                try:
                    p = ctypes.WinDLL('psapi')
                    k = ctypes.WinDLL('kernel32')
                    for pr in psutil.process_iter():
                        try:
                            h = k.OpenProcess(0x0100|0x0400, False, pr.pid)
                            if h: p.EmptyWorkingSet(h); k.CloseHandle(h)
                        except: pass
                except: pass
            self.after(0, lambda: self.btn_opt.configure(state="normal", text="🚀 Purga Exitosa"))
            self.after(3000, lambda: self.btn_opt.configure(text="🚀 Optimización Profunda"))
            self.after(0, lambda: sm.show_success(self, "OK", "RAM purgada."))
        threading.Thread(target=run, daemon=True).start()






# ─── MASTER WINDOW ────────────────────────────────────────────────────────────
class SmartSuiteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart PowerSuite Pro")
        self.geometry("1100x820")
        self.minsize(950, 750)
        
        # Cargar Icono si existe
        try:
            ico_path = resource_path("powersuite.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except: pass

        # Centrar
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1100x820+{(sw-1100)//2}+{(sh-820)//2}")

        self.db = HistoryManager()
        self._log_queue = queue.Queue()
        
        # Estado de IA (Persistencia Cifrada)
        self.ai_key = self.db.get_setting("ai_key", "")
        self.ai_provider = self.db.get_setting("ai_provider", "Groq")
        self.ai_model = self.db.get_setting("ai_model", "llama-3.3-70b-versatile")
        self.ai_active = bool(self.ai_key)
        self.ai_has_vision = self.is_vision_capable(self.ai_model)

        # Configuración de Grid
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._show_view("organizador")
        self._poll_queue()
        
        self.attributes("-alpha", 0.0)
        self._fade_in(0.0)

        # Confirmación de salida premium
        self.protocol("WM_DELETE_WINDOW", self._on_exit)

    def is_vision_capable(self, model_id: str) -> bool:
        """Determina de forma inteligente si el modelo ID soporta entrada de imágenes."""
        m = model_id.lower()
        vision_keywords = ["vision", "gpt-4o", "pixtral", "claude-3-5", "claude-3-opus", "gemini-1.5"]
        return any(k in m for k in vision_keywords)

    def _show_about(self):
        """Muestra la ventana de información del proyecto."""
        win = ctk.CTkToplevel(self)
        win.title("Acerca de PowerSuite")
        win.geometry("450x380")
        win.resizable(False, False)
        win.after(100, lambda: win.focus())
        win.grab_set() # Modal
        
        # Centrar relativo a principal
        x = self.winfo_x() + (self.winfo_width()//2) - 225
        y = self.winfo_y() + (self.winfo_height()//2) - 190
        win.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(win, text="💎", font=ctk.CTkFont(size=50)).pack(pady=(30, 10))
        ctk.CTkLabel(win, text="PowerSuite Pro v2.0", font=ctk.CTkFont(size=20, weight="bold"), text_color=("#6366F1", "#A78BFA")).pack()
        ctk.CTkLabel(win, text="Project Excellence Framework", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack()
        
        info = (
            "Esta herramienta ha sido diseñada con fines personales para\n"
            "la gestión eficiente de archivos y optimización de flujos de trabajo.\n\n"
            "Es software de uso libre, gratuito y sin fines de lucro.\n"
            "Desarrollado y diseñado por Miguel Angel.\n\n"
            "✨ Se aceptan sugerencias y contribuciones para seguir\n"
            "mejorando esta herramienta técnica."
        )
        
        ctk.CTkLabel(win, text=info, font=ctk.CTkFont(size=13), justify="center", pady=20).pack(padx=30)
        
        ctk.CTkButton(win, text="Entendido", width=120, height=36, corner_radius=18, 
                       fg_color="#6366F1", hover_color="#4F46E5", command=win.destroy).pack(pady=(10, 20))

    def _on_exit(self):
        if sm.ask_confirm(self, "Cerrar PowerSuite", "¿Estás seguro de que quieres salir? Se perderán las tareas en curso.", type="diamond", color="#6C63FF"):
            self.destroy()

    def _fade_in(self, a):
        if a < 1.0:
            self.attributes("-alpha", min(1.0, a+0.05))
            self.after(20, lambda: self._fade_in(a+0.05))

    def _build_sidebar(self):
        # Sidebar con fondo profundo y diseño minimalista
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=("#F8FAFC", "#0D0F1A"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        
        # --- HEADER (Diseño más compacto para ganar espacio) ---
        header_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_f.grid(row=0, column=0, pady=(30, 15), padx=20, sticky="ew")
        
        self.logo_lbl = ctk.CTkLabel(header_f, text="💎", font=ctk.CTkFont(size=38))
        self.logo_lbl.pack()
        
        
        title_lbl = ctk.CTkLabel(header_f, text="PowerSuite", 
                                font=ctk.CTkFont(size=22, weight="bold"), 
                                text_color=("#6366F1", "#A78BFA"))
        title_lbl.pack(pady=(2, 0))
        
        ver_lbl = ctk.CTkLabel(header_f, text="PRO EDITION • V2.0", 
                               font=ctk.CTkFont(size=10, weight="bold"), 
                               text_color="gray")
        ver_lbl.pack()

        # --- CONTENEDOR DE NAVEGACIÓN CON SCROLL ---
        # Usamos ScrollableFrame para asegurar que NUNCA se corten las opciones
        self.nav_container = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", 
                                                   scrollbar_button_color=("#CBD5E1", "#1E293B"),
                                                   scrollbar_button_hover_color=("#94A3B8", "#334155"),
                                                   height=500)
        self.nav_container.grid(row=1, column=0, sticky="nsew", padx=5)
        self.sidebar.grid_rowconfigure(1, weight=1)
        
        # Indicadores dinámicos
        self.nav_indicator_bg = ctk.CTkFrame(self.sidebar, width=256, height=44, corner_radius=12, 
                                            fg_color=("#E2E8F0", "#1C2033"), border_width=0)
        self.nav_indicator = ctk.CTkFrame(self.sidebar, width=4, height=24, corner_radius=10, 
                                         fg_color=("#6366F1", "#A78BFA"))

        self.nav_btns = {}
        
        menu_data = [
            ("GESTIÓN", [
                ("organizador", "🗂️", "Organizador"),
                ("trituradora", "🗑️", "Trituradora"),
            ]),
            ("PROCESAMIENTO", [
                ("rembg",       "🪄", "Quitar Fondos"),
                ("ocr",         "🔍", "OCR Scanner"),
                ("pdftools",    "📄", "Suite PDF"),
            ]),
            ("HERRAMIENTAS", [
                ("descargador", "📥", "Descargador"),
                ("conversor",   "🔄", "Conversor"),
                ("compresor",   "🗜️", "Comprimir ZIP"),
            ]),
            ("SISTEMA", [
                ("appremover",  "🛡️", "Debloat Pro"),
                ("monitor",     "🚀", "Monitor de RAM/CPU"),
                ("red",         "🌐", "Diagnóstico de Red"),
                ("salud",       "🩺", "Estado del Sistema"),
                ("history",     "🕒", "Historial"),
                ("ai_config",   "⚙️", "Ajustes IA"),
                ("about",       "ⓘ", "Acerca de"),
            ])
        ]

        row_idx = 0
        for group_name, tools in menu_data:
            group_lbl = ctk.CTkLabel(self.nav_container, text=group_name, 
                                     font=ctk.CTkFont(size=10, weight="bold"), 
                                     text_color=("#94A3B8", "#64748B"))
            group_lbl.grid(row=row_idx, column=0, sticky="w", padx=15, pady=(8, 2))
            row_idx += 1
            
            for key, icon, name in tools:
                btn = ctk.CTkButton(
                    self.nav_container, text=f"  {icon}   {name}", anchor="w",
                    font=ctk.CTkFont(size=13), height=40, border_width=0, corner_radius=10,
                    fg_color="transparent", hover_color=("#CBD5E1", "#1E293B"),
                    text_color=("#475569", "#94A3B8"),
                    command=lambda k=key: self._show_view(k)
                )
                btn.grid(row=row_idx, column=0, sticky="ew", pady=1)
                self.nav_btns[key] = btn
                row_idx += 1

        # --- FOOTER COMPACTADO ---
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=2, column=0, pady=15)
        
        status_f = ctk.CTkFrame(footer, fg_color=("#DCFCE7", "#064E3B"), corner_radius=20)
        status_f.pack(padx=20, pady=0)
        ctk.CTkLabel(status_f, text="● PREMIUM ACTIVE", font=ctk.CTkFont(size=9, weight="bold"), 
                     text_color=("#166534", "#4ADE80"), padx=12, pady=2).pack()
    def _build_main(self):
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=5, pady=(15, 10))
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1) # El content frame es dinámico
        
        self.content_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        self.views = {
            "organizador": ViewOrganizer(self.content_frame, self),
            "trituradora": ViewShredder(self.content_frame, self),
            "compresor":   ViewCompressor(self.content_frame, self),
            "rembg":       ViewBgRemover(self.content_frame, self),
            "descargador": ViewDownloader(self.content_frame, self),
            "conversor":   ViewImageConverter(self.content_frame, self),
            "appremover":  ViewAppRemover(self.content_frame, self),
            "monitor":     ViewResourceMonitor(self.content_frame, self),
            "salud":       ViewSystemHealth(self.content_frame, self),
            "pdftools":    ViewPDFTools(self.content_frame, self),
            "ocr":         ViewOCR(self.content_frame, self),
            "palette":     ViewPalette(self.content_frame, self),
            "red":         ViewNetworkDiagnostic(self.content_frame, self),
            "history":     ViewHistory(self.content_frame, self),
            "ai_config":   ViewAIConfig(self.content_frame, self),
        }
        for v in self.views.values(): v.grid(row=0, column=0, sticky="nsew")
        
        self.bottom_panel = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.bottom_panel.grid(row=1, column=0, sticky="ew", pady=(10,0))
        self.bottom_panel.grid_columnconfigure(0, weight=1)
        
        prog_header = ctk.CTkFrame(self.bottom_panel, fg_color="transparent")
        prog_header.pack(fill="x", pady=(0, 5))
        self.prog_label = ctk.CTkLabel(prog_header, text="Esperando instrucciones...", text_color="gray", font=ctk.CTkFont(size=12, weight="bold"))
        self.prog_label.pack(side="left")
        self.prog_pct = ctk.CTkLabel(prog_header, text="0%", font=ctk.CTkFont(size=12, weight="bold"), text_color="#A78BFA")
        self.prog_pct.pack(side="right")
        
        self.progress = ctk.CTkProgressBar(self.bottom_panel, height=12, corner_radius=6)
        self.progress.pack(fill="x", pady=(0, 15))
        self.progress.set(0)
        
        self.log_panel = LogPanel(self.bottom_panel, height=200)
        self.log_panel.pack(fill="x")
        self.log_panel.pack_propagate(False)

    def _show_view(self, view_name):
        if view_name == "about":
            self._show_about()
            return
            
        self._current_view = view_name
        
        # Resetear estilos de todos los botones
        for key, btn in self.nav_btns.items():
            if key == view_name:
                btn.configure(text_color=("#4F46E5", "#A78BFA"), 
                              font=ctk.CTkFont(size=13, weight="bold"))
            else:
                btn.configure(text_color=("#475569", "#94A3B8"), 
                              font=ctk.CTkFont(size=13, weight="normal"))
        
        # Animación del indicador
        self.after(10, lambda: self._animate_indicator(view_name))
        
        # Cambio de vista
        self.views[view_name].tkraise()
        if view_name == "history":
            self.views["history"].load_data()
        if view_name == "salud":
            self.views["salud"]._run_audit()

    def _animate_indicator(self, view_name):
        try:
            btn = self.nav_btns[view_name]
            self.update_idletasks()
            
            # Calcular Y relativa al contenedor de navegación
            # Sumamos el desplazamiento vertical del contenedor respecto al sidebar
            container_y = self.nav_container.winfo_y()
            btn_y = btn.winfo_y()
            
            target_y = container_y + btn_y
            
            # Movimiento fluido del fondo y el acento lateral
            self.nav_indicator_bg.place(x=12, y=target_y, width=256)
            self.nav_indicator.place(x=8, y=target_y + 9)
            self.nav_indicator.tkraise()
        except:
            pass

    def _enqueue_log(self, text, tag="info"): self._log_queue.put(("log", text, tag))
    def _enqueue_progress(self, val, text): self._log_queue.put(("progress", val, text))
    def _pulse_progress(self): self._pulsing = True; self._do_pulse()
    def _do_pulse(self):
        if hasattr(self, '_pulsing') and self._pulsing:
            if not hasattr(self, '_pval'): self._pval = 0
            self._pval += 0.04
            self.progress.set(0.5 + 0.4*math.sin(self._pval))
            self.after(40, self._do_pulse)
    def _enqueue_done(self): self._log_queue.put(("done",))
    def log_history(self, act, det, ico="📝"): self.db.add_entry(act, det, ico)

    def _poll_queue(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg[0] == "log":
                    self.log_panel.log(msg[1], msg[2])
                elif msg[0] == "progress":
                    self._pulsing = False
                    self.progress.set(msg[1] / 100.0)
                    self.prog_label.configure(text=msg[2])
                    self.prog_pct.configure(text=f"{int(msg[1])}%")
                elif msg[0] == "stats":
                    mapping = {"Procesados": msg[1].get("processed",0), "Movidos": msg[1].get("moved",0), "Omitidos": msg[1].get("skipped",0), "Duplicados": msg[1].get("duplicates",0), "Errores": msg[1].get("errors",0)}
                    for t, v in mapping.items(): self.views["organizador"].stat_cards[t].animate_update(v)
                elif msg[0] == "done":
                    self._pulsing = False
                    self.progress.set(1.0)
                    self.prog_pct.configure(text="100%")
                    self.prog_label.configure(text="Completado ✓", text_color="#10B981")
                    self.after(3500, lambda: [self.progress.set(0), self.prog_pct.configure(text="0%"), self.prog_label.configure(text="Esperando instrucciones...", text_color="gray")])
        except queue.Empty: pass
        self.after(50, self._poll_queue)

if __name__ == "__main__":
    # --- ROUTER PARA EXE ---
    if len(sys.argv) > 1:
        if sys.argv[1] == "--designer":
            from pdf_designer import PDFDesigner
            app = PDFDesigner()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--form-builder":
            from pdf_form_builder import PDFFormBuilder
            app = PDFFormBuilder()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--palette":
            from palette_pro import PaletteProApp
            app = PaletteProApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--ocr":
            from ocr_pro import OCRProApp
            app = OCRProApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--wifi":
            from wifi_monitor_gui import WifiMonitorApp
            app = WifiMonitorApp()
            app.mainloop()
            sys.exit(0)

    # --- APP PRINCIPAL ---
    try:
        app = SmartSuiteApp()
        app.mainloop()
    except Exception as e:
        import traceback
        err_log = Path(__file__).parent / "crash_error.log"
        with open(err_log, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        
        # Mostrar error visual si falla al arrancar
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("PowerSuite Fatal Error", 
                                 f"La aplicación se cerró inesperadamente.\n\nError: {e}\n\nSe guardó un registro en crash_error.log")
            root.destroy()
        except: pass
