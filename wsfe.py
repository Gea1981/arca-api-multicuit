from zeep import Client
import datetime
from models import FacturaRequest
from wsaa import get_token_sign  # Este archivo lo armamos luego

def emitir_comprobante(data: FacturaRequest):
    token, sign = get_token_sign(data.cuit_emisor)

    wsdl = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"
    client = Client(wsdl)

    auth = {
        'Token': token,
        'Sign': sign,
        'Cuit': data.cuit_emisor
    }

    # Obtener próximo comprobante
    ultimo = client.service.FECompUltimoAutorizado(auth, data.punto_venta, data.tipo_comprobante)
    prox_nro = ultimo.CbteNro + 1

    hoy = data.fecha_emision.strftime('%Y%m%d')

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

    result = client.service.FECAESolicitar(
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

    det = result.FeDetResp.FECAEDetResponse[0]

    if det.Resultado != 'A':
        raise Exception(f"Comprobante rechazado: {det.Observaciones.Obs[0].Msg}")

    return {
        "cae": det.CAE,
        "cae_vencimiento": datetime.datetime.strptime(det.CAEFchVto, '%Y%m%d').date(),
        "numero_comprobante": prox_nro
    }
