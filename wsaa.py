import os
import subprocess
import datetime
import ssl
from lxml import etree
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
from xml.etree import ElementTree as ET

# ------------------------------------------------------------------
# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
# ------------------------------------------------------------------
ENV = os.getenv("ENVIRONMENT", "HOMO").upper()  # por defecto HOMO
WSAA_WSDL_HOMO = os.getenv("WSAA_WSDL_HOMO")
WSAA_WSDL_PROD = os.getenv("WSAA_WSDL_PROD")

if not WSAA_WSDL_HOMO or not WSAA_WSDL_PROD:
    raise RuntimeError("Faltan las variables de entorno WSAA_WSDL_HOMO o WSAA_WSDL_PROD")

# seleccionamos el WSDL según el modo
WSDL = WSAA_WSDL_HOMO if ENV == "HOMO" else WSAA_WSDL_PROD

# servicio (no cambia entre entornos)
SERVICE = "wsfe"

# ------------------------------------------------------------------------
def create_tra(service: str) -> bytes:
    """
    Crea el XML de LoginTicketRequest con:
      - uniqueId: timestamp en segundos (UTC)
      - generationTime: UTC actual menos 2 minutos, sin microsegundos
      - expirationTime: UTC actual + 12 horas, sin microsegundos
      - service: nombre del servicio (e.g. "wsfe")
    Ambos tiempos en formato 'YYYY-MM-DDThh:mm:ss'
    """
    now_utc = datetime.datetime.utcnow().replace(microsecond=0)
    gen_time = now_utc - datetime.timedelta(minutes=2)
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

# ------------------------------------------------------------------------
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

    # Leemos y filtramos las líneas -----BEGIN/END-----
    with open("TRA.cms", "r") as f:
        return "".join(line for line in f if not line.startswith("-----")).strip()

# ------------------------------------------------------------------------
def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama al WSAA loginCms usando un SSLContext con SECLEVEL=1 para
    permitir DHE-1024. Extrae token y sign del XML de respuesta.
    """
    # 1) Creamos un contexto TLS que baje el nivel de seguridad a 1
    ctx = ssl.create_default_context()
    ctx.set_ciphers('DEFAULT@SECLEVEL=1')

    # 2) Montamos un Session de requests con este contexto
    session = Session()
    session.verify = True
    session.mount('https://', HTTPAdapter(ssl_context=ctx))

    # 3) Le pasamos esa sesión a Zeep via Transport
    transport = Transport(session=session)
    client = Client(wsdl=WSDL, transport=transport)

    # 4) Ejecutamos loginCms
    response = client.service.loginCms(cms)
    xml = ET.fromstring(response.encode("utf-8"))
    token = xml.findtext(".//token")
    sign  = xml.findtext(".//sign")
    return token, sign

# ------------------------------------------------------------------------
def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Genera o renueva el token/sign para el CUIT dado,
    esperando encontrar los archivos certs/{cuit}.crt y certs/{cuit}.key.
    """
    cert_path = f"certs/{cuit}.crt"
    key_path  = f"certs/{cuit}.key"

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontró .crt/.key para CUIT {cuit}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
