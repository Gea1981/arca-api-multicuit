# app.py
from arca_arg.webservice import ArcaWebService
import arca_arg.settings as conf
import os

def main():
    # Configuración de rutas y credenciales
    conf.CERT_PATH        = os.getenv('CERT_PATH', '/app/27371046211.crt')  # Archivo .crt
    conf.PRIVATE_KEY_PATH = os.getenv('KEY_PATH', '/app/27371046211.key')    # Archivo .key
    conf.TA_FILES_PATH    = os.getenv('TA_PATH', '/app/ta')                   # Carpeta para tokens
    conf.CUIT             = os.getenv('CUIT', '27371046211')                 # CUIT
    conf.PROD             = os.getenv('PROD', 'true').lower() in ('true', '1', 'yes')

    # Inicializar el servicio WSFE (Factura Electrónica)
    ws = ArcaWebService(wsdl=conf.WSDL_FEV1_HOM)

    # Obtener y mostrar último comprobante autorizado
    ultimo = ws.FECompUltimoAutorizado(tipo_cbte=1, punto_vta=1, id_cbte=0)
    print(f"Último comprobante autorizado: {ultimo}")

if __name__ == '__main__':
    main()
