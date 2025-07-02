import subprocess
import datetime
from lxml import etree
from zeep import Client
from xml.etree import ElementTree as ET
import os

SERVICE = "wsfe"
WSDL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"

def create_tra(service):
    now = datetime.datetime.now()
    expire = now + datetime.timedelta(minutes=600)

    tra = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(tra, "header")
    etree.SubElement(header, "uniqueId").text = str(int(now.timestamp()))
    etree.SubElement(header, "generationTime").text = now.isoformat()
    etree.SubElement(header, "expirationTime").text = expire.isoformat()
    etree.SubElement(tra, "service").text = service

    return etree.tostring(tra, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def sign_tra(tra_xml, cert_path, key_path):
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
        return "".join([line for line in f if "-----" not in line]).strip()

def call_wsaa(cms):
    client = Client(WSDL)
    response = client.service.loginCms(cms)
    xml = ET.fromstring(response.encode("utf-8"))
    token = xml.findtext(".//token")
    sign = xml.findtext(".//sign")
    return token, sign

def get_token_sign(cuit):
    cert_path = f"certs/{cuit}.crt"
    key_path = f"certs/{cuit}.key"

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise Exception(f"No se encontraron archivos .crt/.key para el CUIT {cuit}")

    tra = create_tra(SERVICE)
    cms = sign_tra(tra, cert_path, key_path)
    return call_wsaa(cms)
