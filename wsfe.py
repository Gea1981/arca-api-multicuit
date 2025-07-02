import os
from zeep import Client
import datetime
from models import FacturaRequest
from wsaa import get_token_sign

# ------------------------------------------------------------------
# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
# ------------------------------------------------------------------
ENV = os.getenv("ENVIRONMENT", "homo").upper()
WSFE_WSDL_HOMO = os.getenv("WSFE_WSDL_HOMO")
WSFE_WSDL_PROD = os.getenv("WSFE_WSDL_PROD")

if not WSFE_WSDL_HOMO or not WSFE_WSDL_PROD:
    raise RuntimeError("Faltan variables de entorno WSFE_WSDL_HOMO o WSFE_WSDL_PROD")

# Elegimos el endpoint según el modo
WSDL = WSFE_WSDL_HOMO if ENV == "HOMO" else WSFE_WSDL_PROD

def emitir_comprobante(data: FacturaRequest):
    """
    Emite un comprobante AFIP WSFEv1 para el CUIT indicado en data.cuit_emisor,
    guarda el siguiente número de comprobante, solicita el CAE y devuelve:
      - cae
      - cae_vencimiento (date)
      - numero_comprobante
    """
    # 1) Autenticación WSAA según CUIT
    token, sign = get_token_sign(data.cuit_emisor)

    # 2) Creamos el cliente Zeep apuntando al WSDL elegido
    client = Client(WSDL)

    auth = {
        'Token': token,
        'Sign': sign,
        'Cuit': data.cuit_emisor
    }

    # 3) Obtenemos el último comprobante autorizado y calculamos el próximo
    ultimo = client.service.FECompUltimoAutorizado(
        Auth=auth,
        PtoVta=data.punto_venta,
        CbteTipo=data.tipo_comprobante
    )
    prox_nro = ultimo.CbteNro + 1

    # 4) Formateamos la fecha sin separadores
    hoy = data.fecha_emision.strftime('%Y%m%d')

    # 5) Armamos el detalle del comprobante
    detalle = {
        'Concepto': data.concepto,
        'DocTipo': data.doc_tipo,
        'DocNro': data.doc_nro,
        'CbteDesde': prox_nro,
        'CbteHasta': prox_nro,
        'CbteFch': hoy,
        'ImpTotal': data.total,
        'ImpNeto': data.neto,
        'ImpIVA': data.iva,
        'ImpTrib': 0.00,
        'ImpTotConc': 0.00,
        'ImpOpEx': 0.00,
        'MonId': 'PES',
        'MonCotiz': 1.0,
        'Iva': {
            'AlicIva': [
                {'Id': 5, 'BaseImp': data.neto, 'Importe': data.iva}
            ]
        }
    }

    # 6) Llamamos a FECAESolicitar
    respuesta = client.service.FECAESolicitar(
        Auth=auth,
        FeCAEReq={
            'FeCabReq': {
                'CantReg': 1,
                'PtoVta': data.punto_venta,
                'CbteTipo': data.tipo_comprobante,
            },
            'FeDetReq': {'FECAEDetRequest': [detalle]},
        }
    )

    det = respuesta.FeDetResp.FECAEDetResponse[0]

    # 7) Verificamos resultado
    if det.Resultado != 'A':
        msg = det.Observaciones.Obs[0].Msg if det.Observaciones else "Sin detalle"
        raise Exception(f"Comprobante rechazado: {msg}")

    # 8) Devolvemos datos útiles
    return {
        "cae": det.CAE,
        "cae_vencimiento": datetime.datetime.strptime(det.CAEFchVto, '%Y%m%d').date(),
        "numero_comprobante": prox_nro
    }
