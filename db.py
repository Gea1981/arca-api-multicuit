import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS
from models import FacturaRequest

def guardar_comprobante(data: FacturaRequest, resultado: dict):
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO comprobantes (
            cuit_emisor,
            punto_venta,
            tipo_comprobante,
            numero_comprobante,
            doc_tipo,
            doc_nro,
            neto,
            iva,
            total,
            cae,
            cae_vencimiento,
            fecha_emision,
            pdf_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data.cuit_emisor,
        data.punto_venta,
        data.tipo_comprobante,
        resultado["numero_comprobante"],
        data.doc_tipo,
        data.doc_nro,
        data.neto,
        data.iva,
        data.total,
        resultado["cae"],
        resultado["cae_vencimiento"],
        data.fecha_emision,
        resultado.get("pdf_path", "")  # si querés guardar el path del PDF
    ))

    conn.commit()
    cur.close()
    conn.close()
