from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import qrcode
import base64
from datetime import datetime
import os

def generar_qr_base64(cuit_emisor, tipo_cbte, pto_vta, nro_cbte, importe, cae, cae_vto):
    data = {
        "ver": 1,
        "fecha": datetime.today().strftime('%Y-%m-%d'),
        "cuit": cuit_emisor,
        "ptoVta": pto_vta,
        "tipoCmp": tipo_cbte,
        "nroCmp": nro_cbte,
        "importe": float(f"{importe:.2f}"),
        "moneda": "PES",
        "ctz": 1.000,
        "tipoDocRec": 80,
        "nroDocRec": 20304111112,
        "tipoCodAut": "E",
        "codAut": cae
    }

    import json
    qr_url = f"https://www.afip.gob.ar/fe/qr/?p={base64.urlsafe_b64encode(json.dumps(data).encode()).decode()}"
    img = qrcode.make(qr_url)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

def generar_pdf(data, resultado):
    nro_cbte = resultado["numero_comprobante"]
    cae = resultado["cae"]
    cae_vto = resultado["cae_vencimiento"]

    qr_img_bytes = generar_qr_base64(
        data.cuit_emisor,
        data.tipo_comprobante,
        data.punto_venta,
        nro_cbte,
        data.total,
        cae,
        cae_vto
    )

    # Ruta de salida
    pdf_dir = "comprobantes"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"factura_{data.punto_venta}_{nro_cbte}.pdf")

    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setFont("Helvetica", 12)

    # Cabecera simple
    c.drawString(50, 800, f"Factura Tipo {data.tipo_comprobante} - Punto de Venta: {data.punto_venta:04d}")
    c.drawString(50, 780, f"CUIT Emisor: {data.cuit_emisor}")
    c.drawString(50, 760, f"Fecha de Emisión: {data.fecha_emision.strftime('%d/%m/%Y')}")
    c.drawString(50, 740, f"Número: {nro_cbte}")
    c.drawString(50, 720, f"Importe Total: ${data.total:.2f}")

    # CAE
    c.drawString(50, 700, f"CAE: {cae}")
    c.drawString(50, 680, f"Vto. CAE: {cae_vto.strftime('%d/%m/%Y')}")

    # Código QR
    c.drawInlineImage(BytesIO(qr_img_bytes), 50, 600, width=100, height=100)

    c.save()

    return pdf_path
