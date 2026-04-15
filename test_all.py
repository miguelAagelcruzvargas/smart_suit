"""
Test de las 4 nuevas herramientas de la Suite.
Escribe resultados en test_results.txt
"""
results = {}

# TEST 1: yt-dlp (Descargador)
try:
    import yt_dlp
    # Solo verificamos que el módulo cargue y el extractor base exista
    ydl = yt_dlp.YoutubeDL({'quiet': True})
    results["yt_dlp"] = "✅ OK - yt-dlp v" + yt_dlp.version.__version__
except Exception as e:
    results["yt_dlp"] = f"❌ FALLO: {e}"

# TEST 2: pypdf2 (PDFs)
try:
    import pypdf
    results["pypdf"] = "✅ OK - pypdf disponible"
except ImportError:
    try:
        import PyPDF2
        results["pypdf"] = "✅ OK - PyPDF2 disponible"
    except Exception as e:
        results["pypdf"] = f"❌ FALLO: {e}"

# TEST 3: fpdf2 (Crear PDFs con contraseña - nota: la contraseña real la da pypdf/pikepdf)
try:
    from fpdf import FPDF
    results["fpdf2"] = "✅ OK - fpdf2 disponible"
except Exception as e:
    results["fpdf2"] = f"❌ FALLO: {e}"

# TEST 4: Pillow (Conversor de imágenes)
try:
    from PIL import Image
    import io
    # Test convirtiendo un pequeño bitmap en memoria
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    results["pillow_convert"] = "✅ OK - Pillow conversión de imágenes funciona"
except Exception as e:
    results["pillow_convert"] = f"❌ FALLO: {e}"

# TEST 5: pytesseract (OCR)
try:
    import pytesseract
    # Nota: necesita Tesseract-OCR instalado como programa en Windows
    version = pytesseract.get_tesseract_version()
    results["tesseract"] = f"✅ OK - Tesseract {version} detectado"
except Exception as e:
    results["tesseract"] = f"❌ FALLO (normal sin instalación de Tesseract): {e}"

# Escribir resultados
with open("test_results.txt", "w", encoding="utf-8") as f:
    f.write("=== RESULTADOS TEST SUITE ===\n\n")
    for tool, result in results.items():
        f.write(f"[{tool}]\n  {result}\n\n")
    f.write("=== FIN ===\n")

print("Tests completados. Ver test_results.txt")
