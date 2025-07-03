import os
import subprocess
import datetime
import ssl
from zoneinfo import ZoneInfo
from lxml import etree
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from xml.etree import ElementTree as ET

# ------------------------------------------------------------
# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
# ------------------------------------------------------------
ENV = os.getenv("ENVIRONMENT", "HOMO").upper()

WSAA_WSDL_HOMO = os.getenv("WSAA_WSDL_HOMO")
WSAA_WSDL_PROD = os.getenv("WSAA_WSDL_PROD")
if not WSAA_WSDL_HOMO or not WSAA_WSDL_PROD:
    raise RuntimeError("Faltan WSAA_WSDL_HOMO o WSAA_WSDL_PROD en el .env")

WSDL = WSAA_WSDL_HOMO if ENV == "HOMO" else WSAA_WSDL_PROD
SERVICE = "wsfe"

# ------------------------------------------------------------
# Adapter custom para inyectar nuestro SSLContext en urllib3
# ------------------------------------------------------------
class TLSAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        # Creamos el PoolManager con nuestro contexto TLS
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=self.ssl_context
        )

# ------------------------------------------------------------
def create_tra(service: str) -> bytes:
    """
    Crea el XML de LoginTicketRequest con:
      - uniqueId: timestamp en segundos (ARG local)
      - generationTime: local ARG actual - 1 minuto, con offset '-03:00'
      - expirationTime: local ARG actual + 12 horas, con offset '-03:00'
      - service: nombre del servicio (ej. 'wsfe')
    """
    # zona horaria Argentina
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = datetime.datetime.now(tz).replace(microsecond=0)
    gen_time = now - datetime.timedelta(minutes=1)
    exp_time = now + datetime.timedelta(hours=12)

    tra = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(tra, "header")
    # uniqueId como segundos desde epoch UTC:
    unique_id = str(int(now.timestamp()))
    etree.SubElement(header, "uniqueId").text = unique_id
    # isoformat() ya incluye '-03:00'
    etree.SubElement(header, "generationTime").text = gen_time.isoformat()
    etree.SubElement(header, "expirationTime").text = exp_time.isoformat()
    etree.SubElement(tra, "service").text = service

    return etree.tostring(
        tra,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )

# ------------------------------------------------------------
def sign_tra(tra_xml: bytes, cert_path: str, key_path: str) -> str:
    """
    Firma el TRA con OpenSSL y devuelve el CMS en PEM sin
    encabezados BEGIN/END.
    """
    with open("TRA.xml", "wb") as f:
        f.write(tra_xml)

    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", cert_path,
        "-inkey",   key_path,
        "-in",      "TRA.xml",
        "-out",     "TRA.cms",
        "-outform", "PEM",
        "-nodetach"
    ], check=True)

    # Leemos y filtramos líneas '-----BEGIN/END-----'
    with open("TRA.cms", "r") as f:
        return "".join(line for line in f if not line.startswith("-----")).strip()

# ------------------------------------------------------------
def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama a WSAA.loginCms usando un SSLContext SECLEVEL=1
    para permitir DHE-1024. Retorna (token, sign).
    """
    # 1) Contexto OpenSSL con SECLEVEL=1
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")

    # 2) Session de requests con nuestro adapter
    session = Session()
    session.verify = True
    session.mount("https://", TLSAdapter(ctx))

    # 3) Transport de Zeep con esa session
    transport = Transport(session=session)
    client = Client(wsdl=WSDL, transport=transport)

    # 4) Invocamos loginCms y parseamos la respuesta
    response = client.service.loginCms(cms)
    xml      = ET.fromstring(response.encode("utf-8"))
    token    = xml.findtext(".//token")
    sign     = xml.findtext(".//sign")
    return token, sign

# ------------------------------------------------------------
def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Genera o renueva el token/sign para el CUIT dado,
    buscando certs/{cuit}.crt y certs/{cuit}.key.
    """
    cert_path = f"certs/{cuit}.crt"
    key_path  = f"certs/{cuit}.key"
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontró .crt/.key para CUIT {cuit}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
