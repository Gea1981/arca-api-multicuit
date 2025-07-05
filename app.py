# app.py
from fastapi import FastAPI
from arca_arg.webservice import ArcaWebService
import arca_arg.settings as conf
import os

# Carga configuración como antes
conf.CERT_PATH        = os.getenv('CERT_PATH', '/app/27371046211.crt')
conf.PRIVATE_KEY_PATH = os.getenv('KEY_PATH', '/app/27371046211.key')
conf.TA_FILES_PATH    = os.getenv('TA_PATH', '/app/ta')
conf.CUIT             = os.getenv('CUIT', '27371046211')
conf.PROD             = os.getenv('PROD', 'false').lower() in ('true','1','yes')

app = FastAPI()

@app.get("/ultimo")
def ultimo_cbte():
    # Instanciación corregida:
    ws = ArcaWebService(conf.WSDL_FEV1_HOM, 'wsfe')
    ultimo = ws.FECompUltimoAutorizado(tipo_cbte=1, punto_vta=1, id_cbte=0)
    return {"ultimo_comprobante": ultimo}