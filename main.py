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

# Sesión optimizada para BCRA
session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.bcra.gob.ar/BCRAyVos/Situacion_Crediticia.asp'
    }
    try:
        time.sleep(1) # Delay mínimo para no ser bloqueado
        response = session.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            data = response.json()
            periodos = data.get('results', {}).get('periodos', [])
            if not periodos: return 1
            
            peor = 1
            for entidad in periodos[0].get('entidades', []):
                sit = int(entidad.get('situacion', 1))
                if sit > peor: peor = sit
            return peor
        return 1 if response.status_code == 404 else None
    except Exception as e:
        logging.error(f"Error BCRA: {e}")
        return None

# --- RUTA PARA MANYCHAT ---
@app.post("/webhook-cuil")
async def webhook_manychat(request: Request):
    data = await request.json()
    cuil = data.get("cuil")
    
    if not cuil:
        return {"version": "v2", "content": {"messages": [{"text": "⚠️ No se recibió un CUIL válido."}]}}

    res = consultar_situacion_bcra(cuil)

    # Lógica de respuesta formateada para ManyChat (Dynamic Content)
    if res == 1:
        texto_respuesta = "✅ ¡Buenas noticias! Tu perfil califica para el crédito. Un asesor de Crédito Denis se contactará con vos pronto."
    elif res and res > 1:
        texto_respuesta = f"❌ Lo sentimos, tu situación crediticia actual (Nivel {res}) no nos permite avanzar con el préstamo en este momento."
    else:
        texto_respuesta = "⚠️ Hubo un problema al consultar tu perfil. Por favor, intentalo más tarde o hablá con un asesor."

    return {
        "version": "v2",
        "content": {
            "messages": [
                {"text": texto_respuesta}
            ]
        }
    }
