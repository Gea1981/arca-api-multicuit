import subprocess
import datetime
from lxml import etree
from zeep import Client
from xml.etree import ElementTree as ET
import os

SERVICE = "wsfe"
WSDL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"

def create_tra(service: str) -> bytes:
    """
    Crea el XML de LoginTicketRequest:
    - generationTime: UTC sin micros, -1 min (formato YYYY-MM-DDThh:mm:ss)
    - expirationTime: +12h en el mismo formato
    """
    # UTC actual sin microsegundos, restamos 1 minuto
    now = datetime.datetime.utcnow().replace(microsecond=0) - datetime.timedelta(minutes=1)
    # Expiración en 12 horas
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
    Firma el TRA con OpenSSL y retorna el CMS en formato PEM sin delimitadores.
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

    # Leemos y filtramos las líneas -----BEGIN/END-----  
    with open("TRA.cms", "r") as f:
        return "".join(line for line in f if not line.startswith("-----")).strip()

def call_wsaa(cms: str) -> tuple[str, str]:
    """
    Llama al servicio loginCms de WSAA y extrae token y sign.
    """
    client = Client(WSDL)
    response = client.service.loginCms(cms)
    xml = ET.fromstring(response.encode("utf-8"))
    token = xml.findtext(".//token")
    sign  = xml.findtext(".//sign")
    return token, sign

def get_token_sign(cuit: int) -> tuple[str, str]:
    """
    Genera (o renueva) el Token/Sign para el CUIT dado, buscando
    certs/{cuit}.crt y certs/{cuit}.key.
    """
    cert_path = f"certs/{cuit}.crt"
    key_path  = f"certs/{cuit}.key"

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"No se encontraron {cert_path} o {key_path}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
