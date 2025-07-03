# db.py (actualizado)

import os
import psycopg2
from factura_pdf import generar_qr_base64  
from models import FacturaRequest
import base64

# Cargamos todo desde el .env
DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME"),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "host":     os.getenv("DB_HOST"),
    "port":     os.getenv("DB_PORT", "5432"),
    # ¡IMPORTANTE! deshabilitar SSL si el servidor no lo soporta
    "sslmode":  os.getenv("DB_SSL_MODE", "disable"),
}

def get_connection():
    """Devuelve una conexión psycopg2 usando DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)

def guardar_comprobante(data: FacturaRequest, resultado: dict):
    conn = get_connection()
    cur  = conn.cursor()

    # Genera el QR y lo pasa a base64
    qr_bytes  = generar_qr_base64(
        data.cuit_emisor,
        data.tipo_comprobante,
        data.punto_venta,
        resultado["numero_comprobante"],
        data.total,
        resultado["cae"],
        resultado["cae_vencimiento"]
    )
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
    ) VALUES (
        %(fecha_emision)s,
        %(cuit_emisor)s,
        %(punto_venta)s,
        %(tipo_comprobante)s,
        %(numero_comprobante)s,
        %(doc_tipo)s,
        %(doc_nro)s,
        %(concepto)s,
        %(imp_neto)s,
        %(imp_iva)s,
        %(imp_total)s,
        %(cae)s,
        %(cae_vencimiento)s,
        %(qr_base64)s,
        %(pdf_path)s
    );
    """
    params = {
        "fecha_emision":      data.fecha_emision,
        "cuit_emisor":        data.cuit_emisor,
        "punto_venta":        data.punto_venta,
        "tipo_comprobante":   data.tipo_comprobante,
        "numero_comprobante": resultado["numero_comprobante"],
        "doc_tipo":           data.doc_tipo,
        "doc_nro":            data.doc_nro,
        "concepto":           data.concepto,
        "imp_neto":           data.neto,
        "imp_iva":            data.iva,
        "imp_total":          data.total,
        "cae":                resultado["cae"],
        "cae_vencimiento":    resultado["cae_vencimiento"],
        "qr_base64":          qr_base64,
        "pdf_path":           resultado["pdf_path"],
    }

    cur.execute(insert_sql, params)
    conn.commit()
    cur.close()
    conn.close()
