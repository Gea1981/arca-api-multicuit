import os
import datetime
import ssl
from lxml import etree
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from xml.etree import ElementTree as ET
from datetime import timezone
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import pkcs7

# ——————————————————————————————————————————————————————————————
# 1) Entorno: 'homo' = homologación / 'prod' = producción
# ——————————————————————————————————————————————————————————————
ENV = os.getenv("ENVIRONMENT", "homo").strip().lower()  # "homo" o "prod"
WSAA_WSDL_HOMO = os.getenv("WSAA_WSDL_HOMO")
WSAA_WSDL_PROD = os.getenv("WSAA_WSDL_PROD")
if not WSAA_WSDL_HOMO or not WSAA_WSDL_PROD:
    raise RuntimeError("Faltan WSAA_WSDL_HOMO o WSAA_WSDL_PROD en el .env")

WSDL = WSAA_WSDL_HOMO if ENV == "homo" else WSAA_WSDL_PROD

# Nombre del servicio AFIP (no cambia)
SERVICE = "wsfe"

# Directorio donde están los certificados .crt / .key
CERTS_DIR = os.getenv("CERTS_DIR", "certs")


# ——————————————————————————————————————————————————————————————
# Adapter para inyectar nuestro SSLContext en urllib3 (requests)
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
def get_afip_ssl_context() -> ssl.SSLContext:
    """
    Crea un SSLContext para la comunicación con AFIP.
    - Deshabilita la verificación de hostname y certificado.
    - Establece el nivel de seguridad de OpenSSL a 1 para
      permitir los ciphers de los servidores de homologación.
    """
    # Creamos un contexto que no verifica el certificado
    # y tampoco el hostname, evitando el error.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    # AFIP (especialmente en homologación) requiere ciphers antiguos.
    context.set_ciphers("DEFAULT@SECLEVEL=1")
    return context


# ——————————————————————————————————————————————————————————————
def create_tra(service: str) -> bytes:
    """
    Crea el XML de loginTicketRequest para WSAA:
      - uniqueId: epoch UTC en segundos
      - generationTime: UTC actual - 1 minuto, timezone-aware
      - expirationTime: UTC actual + 12 horas, timezone-aware
      - service: nombre del servicio (ej. 'wsfe')
    Ambos tiempos en formato ISO-8601 con offset (p.ej. '2025-07-03T14:25:00+00:00').
    """
    # 1) Hora UTC timezone-aware, sin microsegundos
    now_utc = datetime.datetime.now(timezone.utc).replace(microsecond=0)
    # 2) Fechas de generación y expiración
    gen_time = now_utc - datetime.timedelta(minutes=1)
    exp_time = now_utc + datetime.timedelta(hours=12)

    tra = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(tra, "header")
    etree.SubElement(header, "uniqueId").text = str(int(now_utc.timestamp()))
    etree.SubElement(header, "generationTime").text = gen_time.isoformat()
    etree.SubElement(header, "expirationTime").text = exp_time.isoformat()
    etree.SubElement(tra, "service").text = service

    return etree.tostring(
        tra,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )


# ——————————————————————————————————————————————————————————————
def sign_tra_in_memory(tra_xml: bytes, cert_path: str, key_path: str) -> str:
    """
    Firma el TRA en memoria usando la librería cryptography y devuelve
    el CMS en formato PEM (codificado en base64).
    """
    # 1. Cargar el certificado y la clave privada
    with open(cert_path, "rb") as f:
        cert = serialization.load_pem_x509_certificate(f.read())
    with open(key_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)

    # 2. Construir el objeto CMS/PKCS7
    options = [pkcs7.PKCS7Options.Binary]
    builder = pkcs7.PKCS7SignatureBuilder().set_data(tra_xml)
    signed_data = builder.add_signer(
        cert, key, hashes.SHA256()
    ).sign(
        encoding=serialization.Encoding.SMIME, options=options
    )

    # 3. Extraer el contenido del SMIME (esquivando headers)
    # El formato que espera AFIP es el base64 puro.
    return signed_data.split(b"\n\n", 1)[1].replace(b"\n", b"").decode("ascii")


# ——————————————————————————————————————————————————————————————
def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama a WSAA.loginCms. En homologación baja a SECLEVEL=1
    (para DHE-1024); en prod usa el contexto por defecto.
    Devuelve (token, sign).
    """
    # Creamos una sesión de requests y le montamos nuestro adapter
    # con el contexto SSL customizado para AFIP.
    session = Session()
    session.mount("https://", TLSAdapter(get_afip_ssl_context()))
    transport = Transport(session=session)
    client   = Client(wsdl=WSDL, transport=transport)
    response = client.service.loginCms(cms)
    xml      = ET.fromstring(response.encode("utf-8"))
    token    = xml.findtext(".//token")
    sign     = xml.findtext(".//sign")

    if not token or not sign:
        raise RuntimeError("WSAA no devolvió token o sign")

    return token, sign


# ——————————————————————————————————————————————————————————————
def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Para un CUIT dado, busca certs/{cuit}.crt y .key,
    genera el TRA, lo firma y llama a WSAA.
    """
    cert_path = os.path.join(CERTS_DIR, f"{cuit}.crt")
    key_path  = os.path.join(CERTS_DIR, f"{cuit}.key")

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontraron {cert_path} o {key_path}")

    tra = create_tra(SERVICE)
    cms = sign_tra_in_memory(tra, cert_path, key_path)
    return call_wsaa(cms)
