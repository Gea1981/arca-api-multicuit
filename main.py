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
        # 1) Emitir con AFIP (devuelve dict con 'cae', 'cae_vencimiento' y 'numero_comprobante')
        resultado = emitir_comprobante(data)

        # 2) Generar PDF con QR y obtener la ruta
        pdf_path = generar_pdf(data, resultado)

        # 3) Inyectar el pdf_path dentro del dict para que luego lo guarde la función DB
        resultado['pdf_path'] = pdf_path

        # 4) Guardar todo en la base de datos (ahora 'resultado' incluye pdf_path)
        guardar_comprobante(data, resultado)

        # 5) Devolver al cliente la info
        return {
            "cae": resultado['cae'],
            "vencimiento": resultado['cae_vencimiento'],
            "pdf": pdf_path
        }

    except Exception as e:
        # En caso de error devolvemos 500 con detalle
        raise HTTPException(status_code=500, detail=str(e))
