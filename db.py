import psycopg2
from models import FacturaRequest
from datetime import datetime

# 🔧 Reemplazá estos datos por los reales de tu VM
DB_HOST = "vps-5040092-x.dattaweb.com"
DB_PORT = 5594
DB_NAME = "hss_ventas_vacia"
DB_USER = "root"
DB_PASSWORD = "Mth.99Spwd_1099.Txt"

def guardar_comprobante(data: FacturaRequest, resultado: dict):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    insert = """
        INSERT INTO comprobantes (
            fecha_emision, cuit_emisor, punto_venta, tipo_comprobante,
            numero_comprobante, doc_tipo, doc_nro, concepto,
            imp_neto, imp_iva, imp_total,
            cae, cae_vencimiento, creado_en
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    valores = (
        data.fecha_emision, data.cuit_emisor, data.punto_venta, data.tipo_comprobante,
        resultado['numero_comprobante'], data.doc_tipo, data.doc_nro, data.concepto,
        data.neto, data.iva, data.total,
        resultado['cae'], resultado['cae_vencimiento'], datetime.now()
    )

    cur.execute(insert, valores)
    conn.commit()
    cur.close()
    conn.close()
