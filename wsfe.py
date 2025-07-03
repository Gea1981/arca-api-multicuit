import os
import ssl
import datetime
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from models import FacturaRequest
from wsaa import get_token_sign, TLSAdapter

# ------------------------------------------------------------------
# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
# ------------------------------------------------------------------
ENV = os.getenv("ENVIRONMENT", "HOMO").upper()

WSFE_WSDL_HOMO = os.getenv("WSFE_WSDL_HOMO")
WSFE_WSDL_PROD = os.getenv("WSFE_WSDL_PROD")
if not WSFE_WSDL_HOMO or not WSFE_WSDL_PROD:
    raise RuntimeError("Faltan WSFE_WSDL_HOMO o WSFE_WSDL_PROD en el .env")

# Elegimos el endpoint según el modo
WSDL = WSFE_WSDL_HOMO if ENV == "HOMO" else WSFE_WSDL_PROD

# ------------------------------------------------------------------
# Contexto TLS con SECLEVEL=1 (permite ECDHE pero acepta DHE-1024)
# ------------------------------------------------------------------
_CTX = ssl.create_default_context()
_CTX.set_ciphers("DEFAULT@SECLEVEL=1")

def emitir_comprobante(data: FacturaRequest):
    """
    Emite un comprobante AFIP WSFEv1 para el CUIT indicado,
    solicita el CAE y devuelve:
      - cae
      - cae_vencimiento (date)
      - numero_comprobante
    """
    # 1) Autenticación WSAA (multi-CUIT)
    token, sign = get_token_sign(data.cuit_emisor)

    # 2) Preparamos el cliente Zeep con Transport custom
    session = Session()
    session.verify = True
    session.mount("https://", TLSAdapter(_CTX))
    transport = Transport(session=session)
    client = Client(wsdl=WSDL, transport=transport)

    auth = {
        "Token": token,
        "Sign":  sign,
        "Cuit":  data.cuit_emisor
    }

    # 3) Consultamos último número y calculamos el próximo
    ultimo = client.service.FECompUltimoAutorizado(
        Auth=auth,
        PtoVta=data.punto_venta,
        CbteTipo=data.tipo_comprobante
    )
    prox_nro = ultimo.CbteNro + 1

    # 4) Formato de fecha YYYYMMDD
    hoy = data.fecha_emision.strftime("%Y%m%d")

    # 5) Armado del detalle
    detalle = {
        "Concepto":   data.concepto,
        "DocTipo":    data.doc_tipo,
        "DocNro":     data.doc_nro,
        "CbteDesde":  prox_nro,
        "CbteHasta":  prox_nro,
        "CbteFch":    hoy,
        "ImpTotal":   data.total,
        "ImpNeto":    data.neto,
        "ImpIVA":     data.iva,
        "ImpTrib":    0.00,
        "ImpTotConc": 0.00,
        "ImpOpEx":    0.00,
        "MonId":      "PES",
        "MonCotiz":   1.00,
        "Iva": {
            "AlicIva": [
                {"Id": 5, "BaseImp": data.neto, "Importe": data.iva}
            ]
        }
    }

    # 6) Solicitamos el CAE
    respuesta = client.service.FECAESolicitar(
        Auth=auth,
        FeCAEReq={
            "FeCabReq": {
                "CantReg":  1,
                "PtoVta":   data.punto_venta,
                "CbteTipo": data.tipo_comprobante,
            },
            "FeDetReq": {"FECAEDetRequest": [detalle]},
        }
    )
    det = respuesta.FeDetResp.FECAEDetResponse[0]

    # 7) Validamos resultado
    if det.Resultado != "A":
        msg = det.Observaciones.Obs[0].Msg if det.Observaciones else "Sin detalle"
        raise Exception(f"Comprobante rechazado: {msg}")

    # 8) Retornamos datos útiles
    return {
        "cae":                det.CAE,
        "cae_vencimiento":    datetime.datetime.strptime(det.CAEFchVto, "%Y%m%d").date(),
        "numero_comprobante": prox_nro
    }
