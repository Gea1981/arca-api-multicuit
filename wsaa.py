import os
import subprocess
import datetime
import ssl
from lxml import etree
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from xml.etree import ElementTree as ET

# ------------------------------------------------------------------
# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
# ------------------------------------------------------------------
ENV = os.getenv("ENVIRONMENT", "HOMO").upper()
WSAA_WSDL_HOMO = os.getenv("WSAA_WSDL_HOMO")
WSAA_WSDL_PROD = os.getenv("WSAA_WSDL_PROD")
if not WSAA_WSDL_HOMO or not WSAA_WSDL_PROD:
    raise RuntimeError("Faltan WSAA_WSDL_HOMO o WSAA_WSDL_PROD en el .env")

WSDL = WSAA_WSDL_HOMO if ENV == "HOMO" else WSAA_WSDL_PROD
SERVICE = "wsfe"

# ------------------------------------------------------------------
# Adapter que inyecta nuestro SSLContext en urllib3
# ------------------------------------------------------------------
class TLSAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        # Aquí sí aceptamos ssl_context
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=self.ssl_context
        )

# ------------------------------------------------------------------
def create_tra(service: str) -> bytes:
    now_utc = datetime.datetime.utcnow().replace(microsecond=0)
    gen_time = now_utc - datetime.timedelta(minutes=2)
    exp_time = now_utc + datetime.timedelta(hours=12)

    tra = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(tra, "header")
    etree.SubElement(header, "uniqueId").text = str(int(now_utc.timestamp()))
    etree.SubElement(header, "generationTime").text = gen_time.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(header, "expirationTime").text = exp_time.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(tra, "service").text = service

    return etree.tostring(tra, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# ------------------------------------------------------------------
def sign_tra(tra_xml: bytes, cert_path: str, key_path: str) -> str:
    with open("TRA.xml", "wb") as f:
        f.write(tra_xml)

    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", cert_path,
        "-inkey", key_path,
        "-in", "TRA.xml",
        "-out", "TRA.cms",
        "-outform", "PEM",
        "-nodetach"
    ], check=True)

    with open("TRA.cms", "r") as f:
        return "".join(line for line in f if not line.startswith("-----")).strip()

# ------------------------------------------------------------------
def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama a WSAA (loginCms) usando un SSLContext con SECLEVEL=1
    para permitir DHE-1024. Devuelve (token, sign).
    """
    # 1) Contexto TLS con SECLEVEL=1
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")

    # 2) Session de requests con nuestro adapter
    session = Session()
    session.verify = True
    session.mount("https://", TLSAdapter(ctx))

    # 3) Transport de Zeep con esa sesión
    transport = Transport(session=session)
    client = Client(wsdl=WSDL, transport=transport)

    # 4) Llamada real a loginCms
    response = client.service.loginCms(cms)
    xml = ET.fromstring(response.encode("utf-8"))
    token = xml.findtext(".//token")
    sign  = xml.findtext(".//sign")
    return token, sign

# ------------------------------------------------------------------
def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Genera o renueva el Token/Sign para el CUIT dado, usando
    certs/{cuit}.crt y certs/{cuit}.key.
    """
    cert_path = f"certs/{cuit}.crt"
    key_path  = f"certs/{cuit}.key"
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontró .crt/.key para CUIT {cuit}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
