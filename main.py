import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from models import FacturaRequest, FacturaResponse
from wsfe import emitir_comprobante
from db import guardar_comprobante
from factura_pdf import generar_pdf
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API AFIP Multicuit",
    version="1.0",
    description="Emitir comprobantes electrónicos AFIP y generar PDF con QR"
)

@app.get("/", summary="Estado del servicio")
def root():
    return {"mensaje": "API AFIP funcionando correctamente"}

@app.post(
    "/emitir",
    response_model=FacturaResponse,
    summary="Emite un comprobante, lo guarda en BD y genera el PDF"
)
def emitir_factura(data: FacturaRequest):
    resultado_afip = None
    try:
        # 1) Emitimos el comprobante en AFIP
        resultado_afip = emitir_comprobante(data)

        # 2) Generamos el PDF y obtenemos la ruta
        pdf_path = generar_pdf(data, resultado_afip)

        # 3) Inyectamos esa ruta en el dict para guardarlo en la BD
        resultado_afip["pdf_path"] = pdf_path

        # 4) Guardamos en la base de datos (incluye pdf_path)
        guardar_comprobante(data, resultado_afip)

        # 5) Devolvemos el response model
        return FacturaResponse(
            cae=resultado_afip["cae"],
            vencimiento=resultado_afip["cae_vencimiento"],
            pdf=pdf_path
        )
    except Exception as e:
        # Si la emisión fue exitosa pero algo más falló, lo registramos
        # para no perder el CAE.
        if resultado_afip:
            logger.critical(
                "¡FALLO CRÍTICO! Se emitió el CAE pero no se pudo guardar en BD o generar el PDF. "
                f"Datos: {data.model_dump_json()}, Resultado AFIP: {resultado_afip}. Error: {e}"
            )
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/comprobante/{cuit}/{pto}/{nro}",
    summary="Descarga el PDF de un comprobante existente"
)
def descargar_pdf(cuit: int, pto: int, nro: int):
    """
    Sirve desde disco:
      comprobantes/{cuit}/factura_{pto:04d}_{nro}.pdf
    """
    filename = f"factura_{pto:04d}_{nro}.pdf"
    path = os.path.join("comprobantes", str(cuit), filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(path, media_type="application/pdf", filename=filename)
