from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import qrcode
import base64
import json
from datetime import datetime
import os

def generar_qr_base64(
    cuit_emisor: int,
    tipo_cbte: int,
    pto_vta: int,
    nro_cbte: int,
    importe: float,
    cae: str,
    cae_vto: datetime.date,
    doc_tipo: int,
    doc_nro: int
) -> bytes:
    """
    Genera el QR en base64 para la URL de AFIP.
    """
    payload = {
        "ver": 1,
        "fecha": datetime.today().strftime("%Y-%m-%d"),
        "cuit": cuit_emisor,
        "ptoVta": pto_vta,
        "tipoCmp": tipo_cbte,
        "nroCmp": nro_cbte,
        "importe": float(f"{importe:.2f}"),
        "moneda": "PES",
        "ctz": 1.000,
        "tipoDocRec": doc_tipo,
        "nroDocRec": doc_nro,
        "tipoCodAut": "E",
        "codAut": cae
    }

    qr_url = (
        "https://www.afip.gob.ar/fe/qr/?p="
        + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    )
    img = qrcode.make(qr_url)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

def generar_pdf(data, resultado) -> str:
    """
    Genera un PDF con los datos de la factura y el QR, lo guarda
    en comprobantes/{cuit_emisor}/factura_{tipo}_{pto}_{nro}.pdf
    y devuelve la ruta al archivo.
    """
    nro_cbte = resultado["numero_comprobante"]
    cae      = resultado["cae"]
    cae_vto  = resultado["cae_vencimiento"]

    # Generar bytes del QR
    qr_img = generar_qr_base64(
        data.cuit_emisor,
        data.tipo_comprobante,
        data.punto_venta,
        nro_cbte,
        data.total,
        cae,
        cae_vto,
        data.doc_tipo,
        data.doc_nro
    )

    # Carpeta por CUIT
    pdf_dir = os.path.join("comprobantes", str(data.cuit_emisor))
    os.makedirs(pdf_dir, exist_ok=True)

    # Nombre descriptivo
    pdf_path = os.path.join(
        pdf_dir,
        f"factura_{data.tipo_comprobante}_{data.punto_venta:04d}_{nro_cbte}.pdf"
    )

    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setFont("Helvetica", 12)

    # Datos básicos
    c.drawString(50, 800, f"Factura Tipo {data.tipo_comprobante} - Punto de Venta: {data.punto_venta:04d}")
    c.drawString(50, 780, f"CUIT Emisor: {data.cuit_emisor}")
    c.drawString(50, 760, f"Fecha de Emisión: {data.fecha_emision.strftime('%d/%m/%Y')}")
    c.drawString(50, 740, f"Número: {nro_cbte}")
    c.drawString(50, 720, f"Importe Total: ${data.total:.2f}")
    c.drawString(50, 700, f"CAE: {cae}")
    c.drawString(50, 680, f"Vto. CAE: {cae_vto.strftime('%d/%m/%Y')}")

    # Insertar QR
    c.drawInlineImage(BytesIO(qr_img), 50, 600, width=100, height=100)
    c.save()

    return pdf_path
