import traceback, os
results = {}

# Test reportlab
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    # Quick test: create a PDF in memory
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 700, "Test OK")
    c.save()
    results["reportlab"] = f"✅ OK - reportlab disponible"
except Exception as e:
    results["reportlab"] = f"❌ FALLO: {traceback.format_exc()}"

# Test pikepdf
try:
    import pikepdf
    # Quick test: create blank PDF
    pdf = pikepdf.Pdf.new()
    page = pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page,
        MediaBox=[0, 0, 612, 792],
        Resources=pikepdf.Dictionary(),
        Contents=pikepdf.Stream(pdf, b"")
    ))
    pdf.pages.append(page)
    results["pikepdf"] = f"✅ OK - pikepdf {pikepdf.__version__} disponible"
except Exception as e:
    results["pikepdf"] = f"❌ FALLO: {traceback.format_exc()}"

# Test PyPDF2 (already confirmed)
try:
    import PyPDF2
    results["pypdf2"] = "✅ OK - PyPDF2 disponible"
except Exception as e:
    results["pypdf2"] = f"❌ {e}"

with open("test_pdf_libs.txt", "w", encoding="utf-8") as f:
    for k, v in results.items():
        f.write(f"[{k}]\n  {v}\n\n")
print("Test completado.")
