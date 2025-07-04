import os
import ssl
import urllib3
import logging

# Configuración SSL agresiva para AFIP
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['OPENSSL_CONF'] = '/dev/null'
ssl._create_default_https_context = ssl._create_unverified_context

# Parche global para requests
import requests.adapters
import urllib3.util.ssl_
original_create_urllib3_context = urllib3.util.ssl_.create_urllib3_context

def create_urllib3_context(ciphers=None, cert_reqs=ssl.CERT_REQUIRED, **kwargs):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers('DEFAULT@SECLEVEL=0')
    return ctx

urllib3.util.ssl_.create_urllib3_context = create_urllib3_context
urllib3.disable_warnings()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from models import FacturaRequest, FacturaResponse
from wsfe import emitir_comprobante
from db import guardar_comprobante
from factura_pdf import generar_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Configuración SSL agresiva aplicada para AFIP")

app = FastAPI(
    title="API AFIP Multicuit",
    version="1.0",
    description="Emitir comprobantes electrónicos AFIP y generar PDF con QR"
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
    try:
        # 1) Emitimos el comprobante en AFIP
        resultado = emitir_comprobante(data)
        # 2) Generamos el PDF y obtenemos la ruta
        pdf_path = generar_pdf(data, resultado)
        # 3) Inyectamos esa ruta en el dict para guardarlo en la BD
        resultado["pdf_path"] = pdf_path
        # 4) Guardamos en la base de datos (incluye pdf_path)
        guardar_comprobante(data, resultado)
        # 5) Devolvemos el response model
        return FacturaResponse(
            cae=resultado["cae"],
            vencimiento=resultado["cae_vencimiento"],
            pdf=pdf_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/comprobante/{cuit}/{pto}/{nro}",
    summary="Descarga el PDF de un comprobante existente"
)
def descargar_pdf(cuit: int, pto: int, nro: int):
    """
    Sirve desde disco:
      comprobantes/{cuit}/factura_{pto:04d}_{nro}.pdf
    """
    filename = f"factura_{pto:04d}_{nro}.pdf"
    path = os.path.join("comprobantes", str(cuit), filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(path, media_type="application/pdf", filename=filename)
