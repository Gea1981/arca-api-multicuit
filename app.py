# app.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import arca_arg.settings as conf
import arca_arg.auth as auth
from arca_arg.webservice import ArcaWebService

# Carga configuración desde variables de entorno o valores por defecto
conf.CERT_PATH        = os.getenv('CERT_PATH',  '/app/27371046211.crt')
conf.PRIVATE_KEY_PATH = os.getenv('KEY_PATH',   '/app/27371046211.key')
conf.TA_FILES_PATH    = os.getenv('TA_PATH',    '/app/ta')
conf.CUIT             = os.getenv('CUIT',       '27371046211')
conf.PROD             = os.getenv('PROD',       'false').lower() in ('true', '1', 'yes')

# Override en arca_arg.auth para usar las rutas actualizadas
auth.PRIVATE_KEY_PATH = conf.PRIVATE_KEY_PATH
auth.CERT_PATH        = conf.CERT_PATH
auth.TA_FILES_PATH    = conf.TA_FILES_PATH

# Selección dinámica de WSDL según entorno
wsdl_url = conf.WSDL_FEV1_PROD if conf.PROD else conf.WSDL_FEV1_HOM
service_name = 'wsfe'

# Inicializa FastAPI
app = FastAPI(
    title="API ARCA MultiCUIT",
    description="Servicio para obtener último comprobante autorizado vía ARCA/AFIP",
    version="1.0.0"
)

# Configuración de CORS (ajusta orígenes según tu caso)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    try:
        # Instanciar el cliente SOAP una sola vez con auth y rutas parcheadas
        app.state.ws = ArcaWebService(wsdl_url, service_name)
    except Exception as e:
        # Si falla la inicialización, detener la app
        raise RuntimeError(f"Fallo al inicializar ArcaWebService: {e}")

@app.get("/ultimo", summary="Último comprobante autorizado", tags=["Factura Electrónica"])
def ultimo_cbte():
    """
    Retorna el número del último comprobante autorizado para Factura A, punto de venta 1.
    """
    try:
        ultimo = app.state.ws.FECompUltimoAutorizado(tipo_cbte=1, punto_vta=1, id_cbte=0)
        return {"ultimo_comprobante": ultimo}
    except Exception as e:
        # Capturar errores de llamada SOAP y retornar HTTP 500
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", summary="Estado de salud del servicio")
def health_check():
    """Endpoint para verificar que la API está viva."""
    return {"status": "ok", "environment": "production" if conf.PROD else "homologacion"}
