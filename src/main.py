import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from .models import FacturaRequest, FacturaResponse
from .wsfe import emitir_comprobante
from .db import guardar_comprobante, connect_to_db, close_db_connection
from .factura_pdf import generar_pdf, generar_qr_base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta al iniciar la aplicación
    logger.info("Iniciando aplicación y conectando a la base de datos...")
    connect_to_db()
    yield
    # Se ejecuta al apagar la aplicación
    logger.info("Cerrando conexiones a la base de datos...")
    close_db_connection()

app = FastAPI(
    title="API AFIP Multicuit",
    version="1.0",
    description="Emitir comprobantes electrónicos AFIP y generar PDF con QR",
    lifespan=lifespan
)

@app.get("/", summary="Estado del servicio")
def root():
    return {"mensaje": "API AFIP funcionando correctamente"}

@app.post(
    "/emitir",
    response_model=FacturaResponse,
    summary="Emite un comprobante, lo guarda en BD y genera el PDF"
)
def emitir_factura(data: FacturaRequest):
    resultado_afip = None
    try:
        # 1) Emitimos el comprobante en AFIP
        resultado_afip = emitir_comprobante(data)

        # 2) Generamos el QR una sola vez
        qr_bytes = generar_qr_base64(
            cuit_emisor=data.cuit_emisor,
            tipo_cbte=data.tipo_comprobante,
            pto_vta=data.punto_venta,
            nro_cbte=resultado_afip["numero_comprobante"],
            importe=data.total,
            cae=resultado_afip["cae"],
            cae_vto=resultado_afip["cae_vencimiento"],
            doc_tipo=data.doc_tipo,
            doc_nro=data.doc_nro
        )

        # 3) Generamos el PDF, pasándole el QR ya generado
        pdf_path = generar_pdf(data, resultado_afip, qr_bytes)

        # 4) Guardamos en la base de datos, pasando todos los argumentos
        guardar_comprobante(
            data=data, resultado=resultado_afip, pdf_path=pdf_path, qr_bytes=qr_bytes
        )

        # 5) Devolvemos el response model
        return FacturaResponse(
            cae=resultado_afip["cae"],
            vencimiento=resultado_afip["cae_vencimiento"],
            pdf=pdf_path
        )
    except Exception as e:
        # Si la emisión fue exitosa pero algo más falló, lo registramos
        # para no perder el CAE.
        if resultado_afip:
            logger.critical(
                "¡FALLO CRÍTICO! Se emitió el CAE pero no se pudo guardar en BD o generar el PDF. "
                f"Datos: {data.model_dump_json()}, Resultado AFIP: {resultado_afip}. Error: {e}"
            )
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/comprobante/{cuit}/{pto}/{nro}",
    summary="Descarga el PDF de un comprobante existente"
)
def descargar_pdf(cuit: int, pto: int, nro: int):
    """
    Sirve desde disco:
      comprobantes/{cuit}/factura_{pto:04d}_{nro}.pdf
    
    Se implementa una validación de seguridad para prevenir Path Traversal.
    """
    # Directorio base seguro
    base_dir = os.path.abspath("comprobantes")
    
    # Construcción del path solicitado
    filename = f"factura_{pto:04d}_{nro}.pdf"
    user_path = os.path.join(base_dir, str(cuit), filename)
    
    # Verificación de seguridad: el path resuelto debe estar dentro del directorio base
    if not os.path.abspath(user_path).startswith(base_dir):
        raise HTTPException(status_code=400, detail="Ruta de archivo inválida.")
        
    if not os.path.isfile(user_path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(user_path, media_type="application/pdf", filename=filename)
