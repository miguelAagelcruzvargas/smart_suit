import os
import sys
import subprocess
import shutil
from pathlib import Path

def build():
    print("🚀 Iniciando proceso de compilación para PowerSuite Pro...")
    
    # Directorio actual
    cwd = Path(os.getcwd())
    main_script = cwd / "smart_suite.py"
    icon_file = cwd / "powersuite.ico"
    
    if not main_script.exists():
        print(f"❌ Error: No se encontró {main_script}")
        return

    # Comando de PyInstaller
    # --onefile: Un solo archivo EXE
    # --noconsole: Sin ventana de terminal (usamos nuestro router de errores)
    # --icon: Icono del archivo EXE
    # --add-data: Incluir el icono para cargarlo en tiempo de ejecución
    # --collect-all: Asegura que librerías complejas como customtkinter, rembg o fitz se incluyan completas
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--icon={icon_file}",
        f"--add-data={icon_file};.",
        "--name=PowerSuite_Pro",
        # CustomTKinter necesita sus archivos de tema (.json) y assets
        "--collect-all=customtkinter",
        # Estos hidden imports aseguran que el router funcione
        "--hidden-import=pdf_designer",
        "--hidden-import=pdf_form_builder",
        "--hidden-import=smart_organizer",
        # Dependencias críticas de PDF que a veces PyInstaller omite
        "--hidden-import=PyPDF2",
        "--hidden-import=reportlab",
        "--hidden-import=fitz",
        str(main_script)
    ]

    print("\n📦 Ejecutando PyInstaller (esto puede tardar unos minutos)...")
    print(f"Comando: {' '.join(cmd)}")
    
    try:
        # Usamos subprocess.run para ver el progreso en tiempo real si se ejecuta en terminal
        result = subprocess.run(cmd, check=True)
        if result.returncode == 0:
            print("\n✅ ¡Éxito! El archivo EXE se encuentra en la carpeta 'dist/'")
            print(f"Ruta: {cwd / 'dist' / 'PowerSuite_Pro.exe'}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error durante la compilación: {e}")
    except Exception as e:
        print(f"\n❌ Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    build()
