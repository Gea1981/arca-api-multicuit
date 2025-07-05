import os
import psycopg2
from psycopg2 import sql, pool, Error
from models import FacturaRequest
import base64

# ————————————————————————————————————————————————  
# 1) Cargamos y validamos las variables de entorno
# ————————————————————————————————————————————————  
DB_HOST    = os.getenv("DB_HOST")
DB_USER    = os.getenv("DB_USER")
DB_PASS    = os.getenv("DB_PASS")
DB_NAME    = os.getenv("DB_NAME")
DB_PORT    = os.getenv("DB_PORT", "5432")
DB_SSLMODE = os.getenv("DB_SSLMODE", "disable")

required = [DB_HOST, DB_USER, DB_PASS, DB_NAME]
if not all(required):
    missing = [name for name, val in [
        ("DB_HOST", DB_HOST),
        ("DB_USER", DB_USER),
        ("DB_PASS", DB_PASS),
        ("DB_NAME", DB_NAME)
    ] if not val]
    raise RuntimeError(f"Faltan variables de entorno de BD: {', '.join(missing)}")

# ————————————————————————————————————————————————
# 2) Creamos un pool de conexiones para reutilizarlas
# ————————————————————————————————————————————————
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10, # Ajusta según la carga esperada
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME,
        port=DB_PORT,
        sslmode=DB_SSLMODE
    )
except psycopg2.OperationalError as e:
    raise RuntimeError(f"Error creando el pool de conexiones a la BD: {e}")

# ————————————————————————————————————————————————  
def guardar_comprobante(data: FacturaRequest, resultado: dict, pdf_path: str, qr_bytes: bytes):
    """
    Inserta en la tabla 'comprobantes' todos los datos de la factura,
    el CAE, el QR en base64 y la ruta del PDF generado.
    """
    conn = None
    try:
        # 1) Obtenemos una conexión del pool
        conn = db_pool.getconn()
        with conn: # El bloque 'with conn' maneja commit/rollback automáticamente
            with conn.cursor() as cur:
                # 2) Codificar el QR (ya generado) a base64
                qr_base64 = base64.b64encode(qr_bytes).decode()

                # 3) Sentencia parametrizada
                insert_sql = sql.SQL("""
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
                        %(pto_vta)s,
                        %(tipo_cmp)s,
                        %(nro_cmp)s,
                        %(doc_tipo)s,
                        %(doc_nro)s,
                        %(concepto)s,
                        %(imp_neto)s,
                        %(imp_iva)s,
                        %(imp_total)s,
                        %(cae)s,
                        %(cae_vto)s,
                        %(qr)s,
                        %(pdf_path)s
                    );
                """)

                params = {
                    "fecha_emision": data.fecha_emision,
                    "cuit_emisor":   data.cuit_emisor,
                    "pto_vta":       data.punto_venta,
                    "tipo_cmp":      data.tipo_comprobante,
                    "nro_cmp":       resultado["numero_comprobante"],
                    "doc_tipo":      data.doc_tipo,
                    "doc_nro":       data.doc_nro,
                    "concepto":      data.concepto,
                    "imp_neto":      data.neto,
                    "imp_iva":       data.iva,
                    "imp_total":     data.total,
                    "cae":           resultado["cae"],
                    "cae_vto":       resultado["cae_vencimiento"],
                    "qr":            qr_base64,
                    "pdf_path":      pdf_path,
                }

                cur.execute(insert_sql, params)

    except Error as e:
        raise RuntimeError(f"Error al guardar comprobante en BD: {e}")
    finally:
        # 3) Devolvemos la conexión al pool para que otro la reutilice
        if conn:
            db_pool.putconn(conn)
