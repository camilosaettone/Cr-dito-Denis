from fastapi import FastAPI, Request
import requests
import re
import time
import logging
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuración Inicial ---
app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

# Sesión optimizada con reintentos más agresivos para "Connection Reset"
def get_session():
    session = requests.Session()
    # Agregamos 403 y 429 a la lista de reintentos por si el BCRA nos limita por tasa
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[403, 429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    
    # Headers más "reales" para evitar el reset del peer
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.bcra.gob.ar/',
        'Connection': 'keep-alive' # Ayuda a que no cierren la conexión de golpe
    }
    
    try:
        session = get_session()
        # El timeout de 10 es suficiente; si no responde, es que el BCRA está caído
        response = session.get(url, headers=headers, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            # La API a veces devuelve 'results' o directamente el objeto. Chequeamos ambos.
            results = data.get('results', data) 
            periodos = results.get('periodos', [])
            
            if not periodos: 
                return 1 # Sin deudas = Situación 1
            
            peor = 1
            for entidad in periodos[0].get('entidades', []):
                sit = int(entidad.get('situacion', 1))
                if sit > peor: peor = sit
            return peor
            
        if response.status_code == 404:
            return 1 # No encontrado suele significar que no tiene deudas
            
        return "error_bcra" # Para identificar errores de servidor
    except Exception as e:
        logging.error(f"Error BCRA Crítico: {e}")
        return "error_conexion"

@app.post("/webhook-cuil")
async def webhook_manychat(request: Request):
    try:
        data = await request.json()
        cuil = data.get("cuil")
        
        if not cuil:
            return {"version": "v2", "content": {"messages": [{"text": "⚠️ Por favor, ingresá un CUIL válido para continuar."}]}}

        res = consultar_situacion_bcra(cuil)

        # Lógica de respuesta mejorada
        if res == 1:
            texto = "✅ ¡Buenas noticias! Tu perfil califica para el crédito. Un asesor de Crédito Denis se contactará con vos pronto por este medio."
        elif isinstance(res, int) and res > 1:
            texto = f"❌ Lo sentimos, tu situación en el BCRA (Nivel {res}) no nos permite avanzar en este momento. ¡Gracias por consultar!"
        else:
            # Aquí manejamos el "Connection Reset" o caídas del BCRA
            texto = "⏳ El sistema del Banco Central está saturado en este momento. Por favor, intentá nuevamente en unos minutos para obtener tu aprobación."

        return {
            "version": "v2",
            "content": {
                "messages": [{"text": texto}]
            }
        }
    except Exception as e:
        return {"version": "v2", "content": {"messages": [{"text": "⚠️ Error interno. Por favor intentá más tarde."}]}}
