import os
import subprocess
import datetime
from lxml import etree
from zeep import Client
from xml.etree import ElementTree as ET

# ------------------------------------------------------------------
# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
# ------------------------------------------------------------------
ENV = os.getenv("ENVIRONMENT", "homo").upper()  # por defecto HOMO si no existe
WSAA_WSDL_HOMO = os.getenv("WSAA_WSDL_HOMO")
WSAA_WSDL_PROD = os.getenv("WSAA_WSDL_PROD")

if not WSAA_WSDL_HOMO or not WSAA_WSDL_PROD:
    raise RuntimeError("Faltan variables de entorno WSAA_WSDL_HOMO o WSAA_WSDL_PROD")

# elegimos el endpoint según el modo
WSDL = WSAA_WSDL_HOMO if ENV == "HOMO" else WSAA_WSDL_PROD

# servicio (no cambia entre entornos)
SERVICE = "wsfe"

# -----------------------------------------------------------------------------
def create_tra(service: str) -> bytes:
    """
    Crea el XML de LoginTicketRequest con:
      - generationTime = UTC ahora - 1 minuto, sin microsegundos
      - expirationTime = UTC + 12 horas
    Ambos en formato 'YYYY-MM-DDThh:mm:ss'
    """
    now = datetime.datetime.utcnow().replace(microsecond=0) - datetime.timedelta(minutes=1)
    expire = now + datetime.timedelta(hours=12)

    tra = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(tra, "header")
    etree.SubElement(header, "uniqueId").text = str(int(now.timestamp()))
    etree.SubElement(header, "generationTime").text = now.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(header, "expirationTime").text = expire.strftime("%Y-%m-%dT%H:%M:%S")
    etree.SubElement(tra, "service").text = service

    return etree.tostring(
        tra,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )

def sign_tra(tra_xml: bytes, cert_path: str, key_path: str) -> str:
    """
    Firma el TRA con OpenSSL y devuelve el CMS en PEM sin delimitadores.
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

    with open("TRA.cms", "r") as f:
        # filtramos BEGIN/END
        return "".join(line for line in f if not line.startswith("-----")).strip()

def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama al WSAA loginCms y extrae token y sign del XML de respuesta.
    """
    client = Client(WSDL)
    response = client.service.loginCms(cms)
    xml = ET.fromstring(response.encode("utf-8"))
    token = xml.findtext(".//token")
    sign  = xml.findtext(".//sign")
    return token, sign

def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Genera o renueva el token/sign para el CUIT dado,
    esperando encontrar:
       certs/{cuit}.crt  y  certs/{cuit}.key
    """
    cert_path = f"certs/{cuit}.crt"
    key_path  = f"certs/{cuit}.key"

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontró .crt/.key para CUIT {cuit}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
