from fastapi import FastAPI, HTTPException
from models import FacturaRequest
from wsfe import emitir_comprobante
from db import guardar_comprobante
from factura_pdf import generar_pdf

app = FastAPI()

@app.get("/")
def root():
    return {"mensaje": "API AFIP funcionando correctamente"}

@app.post("/emitir")
def emitir_factura(data: FacturaRequest):
    try:
        # Emitir con AFIP
        resultado = emitir_comprobante(data)

        # Guardar en DB
        guardar_comprobante(data, resultado)

        # Generar PDF con QR
        pdf_path = generar_pdf(data, resultado)

        return {
            "cae": resultado['cae'],
            "vencimiento": resultado['cae_vencimiento'],
            "pdf": pdf_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
