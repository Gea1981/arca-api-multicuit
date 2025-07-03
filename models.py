from pydantic import BaseModel
from datetime import date

class FacturaRequest(BaseModel):
    cuit_emisor: int
    punto_venta: int
    tipo_comprobante: int
    concepto: int         # 1=Productos, 2=Servicios, 3=Ambos
    doc_tipo: int         # 80=CUIT, 86=CUIL, etc.
    doc_nro: int
    neto: float
    iva: float
    total: float
    fecha_emision: date
    cae: str
    vencimiento: date
    pdf: str  # ruta al PDF generado
