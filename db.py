import psycopg2
from factura_pdf import generar_qr_base64  # Asegurate que devuelva bytes
from models import FacturaRequest

# 🔧 Reemplazá con tus datos reales
DB_CONFIG = {
    "dbname": "tu_db",
    "user": "tu_usuario",
    "password": "tu_password",
    "host": "localhost",  # O el host de tu contenedor / servidor
    "port": "5432"
}

def guardar_comprobante(data: FacturaRequest, resultado: dict):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Generamos el QR en base64
    qr_bytes = generar_qr_base64(
        data.cuit_emisor,
        data.tipo_comprobante,
        data.punto_venta,
        resultado["numero_comprobante"],
        data.total,
        resultado["cae"],
        resultado["cae_vencimiento"]
    )
    import base64
    qr_base64 = base64.b64encode(qr_bytes).decode()

    insert_sql = """
        INSERT INTO comprobantes (
            fecha_emision,
            cuit_emisor,
            punto_venta,
            tipo_comprobante,
            numero_comprobante,
            doc_tipo,
            doc_nro,
            concepto,
            imp_neto,
            imp_iva,
            imp_total,
            cae,
            cae_vencimiento,
            qr_base64,
            pdf_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    cur.execute(insert_sql, (
        data.fecha_emision,
        data.cuit_emisor,
        data.punto_venta,
        data.tipo_comprobante,
        resultado["numero_comprobante"],
        data.doc_tipo,
        data.doc_nro,
        data.concepto,
        data.neto,
        data.iva,
        data.total,
        resultado["cae"],
        resultado["cae_vencimiento"],
        qr_base64,
        resultado["pdf_path"]
    ))

    conn.commit()
    cur.close()
    conn.close()
