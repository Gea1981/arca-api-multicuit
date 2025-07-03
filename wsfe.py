--- a/wsfe.py
+++ b/wsfe.py
@@ -1,8 +1,10 @@
 import os
-import ssl
+import ssl
 import datetime
 from zeep import Client
 from zeep.transports import Transport
 from requests import Session
 from requests.adapters import HTTPAdapter
 from urllib3.poolmanager import PoolManager
 from models import FacturaRequest
 from wsaa import get_token_sign, TLSAdapter
+
+# ------------------------------------------------------------
+# 1) Modo de la API: 'HOMO' = homologación / 'PROD' = producción
+# ------------------------------------------------------------
 ENV = os.getenv("ENVIRONMENT", "HOMO").upper()
 
 WSFE_WSDL_HOMO = os.getenv("WSFE_WSDL_HOMO")
 WSFE_WSDL_PROD = os.getenv("WSFE_WSDL_PROD")
@@ -15,15 +17,28 @@ if not WSFE_WSDL_HOMO or not WSFE_WSDL_PROD:
 WSDL = WSFE_WSDL_HOMO if ENV == "HOMO" else WSFE_WSDL_PROD
 
-# ------------------------------------------------------------------
-# Contexto TLS con SECLEVEL=1 (permite ECDHE pero acepta DHE-1024)
-# ------------------------------------------------------------------
-_CTX = ssl.create_default_context()
-_CTX.set_ciphers("DEFAULT@SECLEVEL=1")
+def _build_ssl_context() -> ssl.SSLContext:
+    """
+    Crea un SSLContext. En HOMO baja el nivel a SECLEVEL=1
+    para permitir DHE-1024, en PROD deja el valor por defecto.
+    """
+    ctx = ssl.create_default_context()
+    if ENV == "HOMO":
+        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
+    return ctx
+
+# inicializamos el contexto una sola vez
+_CTX = _build_ssl_context()
 
 
 def emitir_comprobante(data: FacturaRequest):
@@ -41,7 +56,7 @@ def emitir_comprobante(data: FacturaRequest):
     token, sign = get_token_sign(data.cuit_emisor)
 
     # 2) Preparamos el cliente Zeep con Transport custom
-    session = Session()
-    session.verify = True
-    session.mount("https://", TLSAdapter(_CTX))
+    session = Session()
+    session.verify = True
+    session.mount("https://", TLSAdapter(_CTX))
     transport = Transport(session=session)
     client = Client(wsdl=WSDL, transport=transport)
 
@@ -90,4 +105,4 @@ def emitir_comprobante(data: FacturaRequest):
         "cae_vencimiento":    datetime.datetime.strptime(det.CAEFchVto, "%Y%m%d").date(),
         "numero_comprobante": prox_nro
     }
