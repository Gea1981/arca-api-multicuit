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

# ——————————————————————————————————————————————————————————————
# 1) Entorno: homologación vs producción
# ——————————————————————————————————————————————————————————————
ENV = os.getenv("ENVIRONMENT", "HOMO").upper()  # "HOMO" o "PROD"
WSAA_WSDL_HOMO = os.getenv("WSAA_WSDL_HOMO")
WSAA_WSDL_PROD = os.getenv("WSAA_WSDL_PROD")
if not WSAA_WSDL_HOMO or not WSAA_WSDL_PROD:
    raise RuntimeError("Faltan WSAA_WSDL_HOMO o WSAA_WSDL_PROD en el .env")

WSDL = WSAA_WSDL_HOMO if ENV == "HOMO" else WSAA_WSDL_PROD

# Nombre del servicio AFIP (no cambia)
SERVICE = "wsfe"

# Directorio de certificados (.crt y .key)
CERTS_DIR = os.getenv("CERTS_DIR", "certs")

# ——————————————————————————————————————————————————————————————
# 2) Adapter para inyectar nuestro SSLContext en urllib3 (requests)
# ——————————————————————————————————————————————————————————————
class TLSAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=self.ssl_context
        )

# ——————————————————————————————————————————————————————————————
def create_tra(service: str) -> bytes:
    """
    Crea el XML de LoginTicketRequest para WSAA:
      - uniqueId: epoch UTC en segundos
      - generationTime: UTC actual - 1 minuto (sin microsegundos)
      - expirationTime: UTC actual + 12 horas
    Ambos tiempos formateados como 'YYYY-MM-DDThh:mm:ss'
    """
    now_utc = datetime.datetime.utcnow().replace(microsecond=0)
    gen_time = now_utc - datetime.timedelta(minutes=1)
    exp_time = now_utc + datetime.timedelta(hours=12)

    tra = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(tra, "header")
    etree.SubElement(header, "uniqueId").text = str(int(now_utc.timestamp()))
    etree.SubElement(header, "generationTime").text = gen_time.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(header, "expirationTime").text = exp_time.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(tra, "service").text = service

    return etree.tostring(
        tra,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )

# ——————————————————————————————————————————————————————————————
def sign_tra(tra_xml: bytes, cert_path: str, key_path: str) -> str:
    """
    Firma el TRA (LoginTicketRequest) usando OpenSSL y devuelve
    el CMS en PEM SIN las líneas -----BEGIN/END-----.
    """
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
        # Filtramos las líneas -----BEGIN/END-----
        return "".join(line for line in f if not line.startswith("-----")).strip()

# ——————————————————————————————————————————————————————————————
def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama al método loginCms de WSAA usando un SSLContext
    con SECLEVEL=1 (para permitir DHE-1024). Retorna (token, sign).
    """
    # 1) Preparamos SSLContext con nivel de seguridad 1
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")

    # 2) Montamos una sesión de requests con nuestro TLSAdapter
    session = Session()
    session.verify = True
    session.mount("https://", TLSAdapter(ctx))

    # 3) Creamos el transporte de Zeep y el cliente
    transport = Transport(session=session)
    client = Client(wsdl=WSDL, transport=transport)

    # 4) Invocamos loginCms
    response = client.service.loginCms(cms)
    xml = ET.fromstring(response.encode("utf-8"))
    token = xml.findtext(".//token")
    sign  = xml.findtext(".//sign")

    if not token or not sign:
        raise RuntimeError("No se obtuvo token/sign de WSAA")

    return token, sign

# ——————————————————————————————————————————————————————————————
def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Punto de entrada: para un CUIT dado, busca certs/{cuit}.crt y .key,
    genera (o renueva) el TRA, firma y llama a WSAA.
    """
    cert_path = os.path.join(CERTS_DIR, f"{cuit}.crt")
    key_path  = os.path.join(CERTS_DIR, f"{cuit}.key")

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontraron {cert_path} o {key_path}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
