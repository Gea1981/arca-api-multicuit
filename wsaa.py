import subprocess
import datetime
from lxml import etree
from zeep import Client
from xml.etree import ElementTree as ET

CERT = "certs/certificado.crt"
PRIVATE_KEY = "certs/privada.key"
SERVICE = "wsfe"
WSDL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"  # PRODUCCIÓN

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

def sign_tra(tra_xml):
    with open("TRA.xml", "wb") as f:
        f.write(tra_xml)

    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", CERT,
        "-inkey", PRIVATE_KEY,
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

def get_token_sign():
    tra = create_tra(SERVICE)
    cms = sign_tra(tra)
    return call_wsaa(cms)
