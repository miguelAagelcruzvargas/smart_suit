#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smart_organizer.py
🗂️ Organizador inteligente de archivos - Sin dependencias externas

Características:
• Clasifica archivos por extensión (imágenes, documentos, videos, etc.)
• Opción de organizar por fecha (AAAA/MM)
• Detecta y maneja duplicados (renombrar/saltar/backup)
• Modo preview (dry-run) para ver cambios sin ejecutar
• Configuración personalizable vía diccionario o JSON
• Logs detallados + resumen final

Uso básico:
    python smart_organizer.py --source ~/Downloads --organize-by type --dry-run
    python smart_organizer.py --source ./Desordenado --config mi_config.json

Autor: Tu nombre | License: MIT
"""

import os
import sys
import shutil
import hashlib
import argparse
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Set


# ─── CONFIGURACIÓN POR DEFECTO ───────────────────────────────────────────────
DEFAULT_CATEGORIES = {
    # 🖼️ Imágenes
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".heic"],
    
    # 🎬 Videos
    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
    
    # 🎵 Audio
    "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    
    # 📄 Documentos
    "documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".txt", ".rtf"],
    
    # 📦 Comprimidos
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    
    # 💻 Ejecutables/Instaladores
    "installers": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"],
    
    # 🌐 Web/Código
    "web": [".html", ".htm", ".css", ".js", ".ts", ".json", ".xml", ".csv"],
    
    # 🗃️ Otros
    "other": []  # Catch-all para lo no clasificado
}

# Extensiones que se ignoran (archivos temporales, sistema, etc.)
IGNORE_EXTENSIONS = {".tmp", ".temp", ".log", ".lock", ".partial", ".crdownload", ".download"}

# Archivos que siempre se ignoran por nombre
IGNORE_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", "._*", "*.tmp"}


# ─── UTILIDADES ──────────────────────────────────────────────────────────────
def get_file_hash(filepath: Path, chunk_size: int = 8192) -> str:
    """Calcula hash MD5 de un archivo para detectar duplicados."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, OSError):
        return ""


def get_file_date_folder(filepath: Path, format_str: str = "%Y/%m") -> str:
    """Obtiene carpeta de fecha basada en modificación del archivo."""
    try:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        return mtime.strftime(format_str)
    except Exception:
        return "unknown/date"


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Limpia nombre de archivo para evitar problemas de SO."""
    # Caracteres inválidos en Windows/Linux
    invalid = '<>:"/\\|?*'
    for char in invalid:
        name = name.replace(char, "_")
    # Recortar si es muy largo
    if len(name) > max_length:
        base, ext = os.path.splitext(name)
        name = base[:max_length-len(ext)] + ext
    return name.strip() or "unnamed_file"


def format_size(bytes_size: int) -> str:
    """Convierte bytes a formato legible."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"


# ─── CLASE PRINCIPAL ─────────────────────────────────────────────────────────
class SmartOrganizer:
    """Organizador inteligente de archivos con múltiples estrategias."""
    
    def __init__(
        self,
        source_dir: str,
        categories: Optional[Dict[str, List[str]]] = None,
        organize_by: str = "type",  # "type" | "date" | "custom"
        handle_duplicates: str = "rename",  # "skip" | "rename" | "backup"
        dry_run: bool = False,
        verbose: bool = True,
        config_file: Optional[str] = None
    ):
        self.source = Path(source_dir).expanduser().resolve()
        self.categories = categories or DEFAULT_CATEGORIES
        self.organize_by = organize_by
        self.handle_duplicates = handle_duplicates
        self.dry_run = dry_run
        self.verbose = verbose
        
        # Estadísticas
        self.stats = {
            "processed": 0,
            "moved": 0,
            "skipped": 0,
            "duplicates": 0,
            "errors": 0,
            "total_size": 0,
            "by_category": defaultdict(int)
        }
        
        # Tracking para duplicados
        self.seen_hashes: Dict[str, Path] = {}
        
        # Cargar config desde archivo si se proporciona
        if config_file and Path(config_file).exists():
            self._load_config(config_file)
    
    def _load_config(self, config_file: str):
        """Carga configuración desde JSON."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'categories' in config:
                    self.categories.update(config['categories'])
                if 'ignore_extensions' in config:
                    global IGNORE_EXTENSIONS
                    IGNORE_EXTENSIONS.update(config['ignore_extensions'])
                if 'organize_by' in config:
                    self.organize_by = config['organize_by']
                if 'handle_duplicates' in config:
                    self.handle_duplicates = config['handle_duplicates']
            if self.verbose:
                print(f"✅ Configuración cargada desde: {config_file}")
        except Exception as e:
            print(f"⚠️ Error cargando config: {e}")
    
    def _should_ignore(self, filepath: Path) -> bool:
        """Determina si un archivo debe ignorarse."""
        name = filepath.name.lower()
        ext = filepath.suffix.lower()
        
        # Ignorar por extensión
        if ext in IGNORE_EXTENSIONS:
            return True
        
        # Ignorar por patrón de nombre
        for pattern in IGNORE_NAMES:
            if pattern.startswith("*.") and name.endswith(pattern[1:]):
                return True
            if pattern in name:
                return True
        
        # Ignorar carpetas
        if filepath.is_dir():
            return True
        
        return False
    
    def _get_category(self, filepath: Path) -> str:
        """Determina la categoría de un archivo por su extensión."""
        ext = filepath.suffix.lower()
        
        for category, extensions in self.categories.items():
            if ext in extensions:
                return category
        
        return "other"
    
    def _get_destination(self, filepath: Path) -> Path:
        """Calcula la ruta de destino según la estrategia de organización."""
        if self.organize_by == "date":
            date_folder = get_file_date_folder(filepath)
            return self.source / date_folder
        
        elif self.organize_by == "type":
            category = self._get_category(filepath)
            return self.source / category
            
        elif self.organize_by == "extension":
            ext = filepath.suffix.lower()
            if ext:
                folder_name = ext[1:] # Elimina el punto (ej: .pdf -> pdf)
            else:
                folder_name = "sin_extension"
            return self.source / folder_name
        
        elif self.organize_by == "custom":
            # Aquí podrías agregar lógica personalizada
            return self.source / "organized"
        
        return self.source / "other"
    
    def _handle_duplicate(self, filepath: Path, dest: Path) -> Optional[Path]:
        """
        Maneja archivos duplicados según la estrategia configurada.
        Retorna la ruta final a usar, o None si se debe omitir.
        """
        file_hash = get_file_hash(filepath)
        if not file_hash:
            return dest  # No se pudo calcular hash, proceder normal
        
        # Verificar si ya vimos este hash
        if file_hash in self.seen_hashes:
            original = self.seen_hashes[file_hash]
            self.stats["duplicates"] += 1
            
            if self.handle_duplicates == "skip":
                if self.verbose:
                    print(f"  ⏭️  Duplicado (omitido): {filepath.name}")
                return None
            
            elif self.handle_duplicates == "rename":
                # Agregar timestamp al nombre
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{filepath.stem}_dup_{stamp}{filepath.suffix}"
                new_dest = dest.parent / sanitize_filename(new_name)
                if self.verbose:
                    print(f"  🔄 Duplicado (renombrado): {filepath.name} → {new_name}")
                return new_dest
            
            elif self.handle_duplicates == "backup":
                # Mover a carpeta de duplicados
                backup_dir = self.source / "_duplicates_backup"
                backup_dir.mkdir(exist_ok=True)
                new_dest = backup_dir / filepath.name
                counter = 1
                while new_dest.exists():
                    new_dest = backup_dir / f"{filepath.stem}_{counter}{filepath.suffix}"
                    counter += 1
                if self.verbose:
                    print(f"  💾 Duplicado (backup): {filepath.name}")
                return new_dest
        
        # Registrar hash para futuras comparaciones
        self.seen_hashes[file_hash] = filepath
        return dest
    
    def _move_file(self, src: Path, dest: Path) -> bool:
        """Mueve un archivo manejando conflictos de nombre."""
        if dest.exists():
            # Agregar contador si el nombre ya existe
            counter = 1
            stem, suffix = dest.stem, dest.suffix
            while dest.exists():
                dest = dest.parent / f"{stem}_{counter}{suffix}"
                counter += 1
        
        try:
            if self.dry_run:
                if self.verbose:
                    print(f"  [DRY-RUN] Mover: {src.name} → {dest.relative_to(self.source)}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                if self.verbose:
                    print(f"  ✅ Movido: {src.name} → {dest.relative_to(self.source)}")
            return True
        except Exception as e:
            print(f"  ❌ Error moviendo {src.name}: {e}")
            self.stats["errors"] += 1
            return False
    
    def process(self) -> Dict[str, any]:
        """Ejecuta la organización y retorna estadísticas."""
        if not self.source.exists():
            print(f"❌ Directorio no encontrado: {self.source}")
            return self.stats
        
        if self.verbose:
            mode = "🔍 PREVIEW" if self.dry_run else "🚀 EJECUTANDO"
            print(f"\n{mode} - Organizando: {self.source}")
            print(f"   Estrategia: {self.organize_by} | Duplicados: {self.handle_duplicates}")
            print("-" * 60)
        
        # Obtener todos los archivos directos (no recursivo por defecto)
        items = list(self.source.iterdir())
        files = [f for f in items if f.is_file() and not self._should_ignore(f)]
        
        if not files:
            print("ℹ️  No hay archivos para organizar.")
            return self.stats
        
        for filepath in files:
            self.stats["processed"] += 1
            self.stats["total_size"] += filepath.stat().st_size
            
            # Determinar destino
            dest_dir = self._get_destination(filepath)
            dest_path = dest_dir / filepath.name
            
            # Manejar duplicados
            final_dest = self._handle_duplicate(filepath, dest_path)
            if final_dest is None:
                self.stats["skipped"] += 1
                continue
            
            # Mover archivo
            if self._move_file(filepath, final_dest):
                self.stats["moved"] += 1
                category = final_dest.parent.name
                self.stats["by_category"][category] += 1
        
        return self.stats
    
    def print_summary(self):
        """Imprime resumen final de la operación."""
        print("\n" + "=" * 60)
        print("📊 RESUMEN")
        print("=" * 60)
        print(f"   Archivos procesados: {self.stats['processed']}")
        print(f"   ✅ Movidos:          {self.stats['moved']}")
        print(f"   ⏭️  Omitidos:         {self.stats['skipped']}")
        print(f"   🔄 Duplicados:        {self.stats['duplicates']}")
        print(f"   ❌ Errores:           {self.stats['errors']}")
        print(f"   💾 Total procesado:   {format_size(self.stats['total_size'])}")
        
        if self.stats['by_category']:
            print(f"\n   📁 Por categoría:")
            for cat, count in sorted(self.stats['by_category'].items(), key=lambda x: -x[1]):
                print(f"      • {cat}: {count}")
        
        if self.dry_run:
            print(f"\n   ⚠️  Esto fue un DRY-RUN. Nada fue modificado.")
            print(f"   Para aplicar cambios, ejecuta sin --dry-run")
        print("=" * 60 + "\n")


# ─── INTERFAZ DE LÍNEA DE COMANDOS ───────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="🗂️ Organizador inteligente de archivos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s --source ~/Downloads
  %(prog)s -s ./Desordenado -o date --dry-run
  %(prog)s -s ./Fotos -o type -d rename -v
  %(prog)s --config mi_config.json

Estrategias de organización (--organize-by):
  type  → Clasifica por tipo de archivo (imágenes, docs, etc.)
  date  → Organiza por fecha de modificación (AAAA/MM)
  custom → Usa lógica personalizada (editar código)

Manejo de duplicados (--duplicates):
  skip   → Omite archivos duplicados
  rename → Renombra con timestamp (archivo_dup_20240101_120000.jpg)
  backup → Mueve duplicados a carpeta _duplicates_backup
        """
    )
    
    parser.add_argument(
        "-s", "--source", 
        required=True, 
        help="Directorio a organizar (ej: ~/Downloads)"
    )
    parser.add_argument(
        "-o", "--organize-by",
        choices=["type", "date", "extension", "custom"],
        default="type",
        help="Estrategia de organización (default: type)"
    )
    parser.add_argument(
        "-d", "--duplicates",
        choices=["skip", "rename", "backup"],
        default="rename",
        help="Cómo manejar duplicados (default: rename)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Modo preview: muestra cambios sin ejecutar"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        default=True,
        help="Mostrar detalles durante la ejecución (default: on)"
    )
    parser.add_argument(
        "-q", "--quiet", 
        action="store_false", 
        dest="verbose",
        help="Silenciar salida detallada"
    )
    parser.add_argument(
        "-c", "--config",
        help="Archivo JSON con configuración personalizada"
    )
    
    args = parser.parse_args()
    
    # Validar directorio fuente
    source_path = Path(args.source).expanduser()
    if not source_path.exists():
        print(f"❌ Error: El directorio no existe: {source_path}")
        sys.exit(1)
    
    # Confirmación de seguridad en modo no dry-run
    if not args.dry_run:
        print(f"⚠️  Vas a organizar archivos en: {source_path.resolve()}")
        print(f"   Estrategia: {args.organize_by} | Duplicados: {args.duplicates}")
        try:
            response = input("   ¿Continuar? (s/N): ").strip().lower()
            if response not in ("s", "si", "y", "yes"):
                print("✅ Operación cancelada. Nada fue modificado.")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n✅ Cancelado por usuario.")
            sys.exit(0)
    
    # Ejecutar organizador
    organizer = SmartOrganizer(
        source_dir=args.source,
        organize_by=args.organize_by,
        handle_duplicates=args.duplicates,
        dry_run=args.dry_run,
        verbose=args.verbose,
        config_file=args.config
    )
    
    organizer.process()
    organizer.print_summary()


if __name__ == "__main__":
    main()