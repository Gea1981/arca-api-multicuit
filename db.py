--- a/db.py
+++ b/db.py
@@ def guardar_comprobante(data: FacturaRequest, resultado: dict):
-                # 2) Generar QR en base64
-                qr_bytes  = generar_qr_base64(
-                    data.cuit_emisor,
-                    data.tipo_comprobante,
-                    data.punto_venta,
-                    resultado["numero_comprobante"],
-                    data.total,
-                    resultado["cae"],
-                    resultado["cae_vencimiento"],
-                    data.doc_tipo,
-                    data.doc_nro
-                )
+                # 2) Generar QR en base64 (la función acepta 7 args)
+                qr_bytes  = generar_qr_base64(
+                    data.cuit_emisor,
+                    data.tipo_comprobante,
+                    data.punto_venta,
+                    resultado["numero_comprobante"],
+                    data.total,
+                    resultado["cae"],
+                    resultado["cae_vencimiento"]
+                )
                 qr_base64 = base64.b64encode(qr_bytes).decode()
