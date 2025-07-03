from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from models import FacturaRequest, FacturaResponse
from wsfe import emitir_comprobante
from db import guardar_comprobante
from factura_pdf import generar_pdf
import os

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
    try:
        # 1) Emitir en AFIP
        resultado = emitir_comprobante(data)

        # 2) Generar PDF y obtener ruta
        pdf_path = generar_pdf(data, resultado)

        # 3) Inyectar la ruta en el dict que guardaremos en BD
        resultado["pdf_path"] = pdf_path

        # 4) Guardar en la base de datos
        guardar_comprobante(data, resultado)

        # 5) Devolver al cliente
        return {
            "cae": resultado["cae"],
            "vencimiento": resultado["cae_vencimiento"],
            "pdf": pdf_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/comprobante/{cuit}/{pto}/{nro}",
    summary="Descarga el PDF de un comprobante existente"
)
def descargar_pdf(cuit: int, pto: int, nro: int):
    """
    Devuelve el PDF generado para:
      comprobantes/{cuit}/factura_{pto:04d}_{nro}.pdf
    """
    filename = f"factura_{pto:04d}_{nro}.pdf"
    path = os.path.join("comprobantes", str(cuit), filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(path, media_type="application/pdf", filename=filename)
