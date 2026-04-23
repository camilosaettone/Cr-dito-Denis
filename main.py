from fastapi import FastAPI, Request
import requests
import re
import time
import logging
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuración de Logs ---
app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

def get_session():
    session = requests.Session()
    # Reintentos automáticos para errores temporales
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[403, 429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.bcra.gob.ar/',
        'Connection': 'keep-alive'
    }
    
    try:
        session = get_session()
        # Timeout corto para no trabar ManyChat
        response = session.get(url, headers=headers, timeout=12, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data) 
            periodos = results.get('periodos', [])
            
            if not periodos: 
                return 1 # Situación 1 (Sin deudas)
            
            peor_situacion = 1
            for entidad in periodos[0].get('entidades', []):
                sit = int(entidad.get('situacion', 1))
                if sit > peor_situacion: peor_situacion = sit
            return peor_situacion
            
        if response.status_code == 404:
            return 1 # No figura en la base = Situación 1
            
        return "error_api"
    except Exception as e:
        logging.error(f"Error Crítico BCRA: {e}")
        return "error_conexion"

@app.post("/webhook-cuil")
async def webhook_manychat(request: Request):
    try:
        data = await request.json()
        cuil = data.get("cuil")
        
        if not cuil:
            return {"version": "v2", "content": {"messages": [{"text": "⚠️ No recibimos un CUIL. Por favor, escribilo de nuevo."}]}}

        res = consultar_situacion_bcra(cuil)

        # Lógica de Respuestas para ManyChat
        if res == 1:
            texto = "✅ ¡Buenas noticias! Tu perfil califica para el crédito. Un asesor de Crédito Denis se contactará con vos pronto para terminar el trámite."
        elif isinstance(res, int) and res > 1:
            texto = f"❌ Lo sentimos, tu situación actual en el Banco Central (Nivel {res}) no nos permite avanzar con el préstamo en este momento."
        else:
            # Esta es la solución al error 104 de Railway
            texto = "⚠️ El sistema del Banco Central está saturado o en mantenimiento. Para agilizar tu trámite, por favor envianos una CAPTURA DE PANTALLA de tu situación crediticia de la web del BCRA y un asesor te atenderá ahora mismo."

        return {
            "version": "v2",
            "content": {
                "messages": [{"text": texto}]
            }
        }
    except Exception as e:
        logging.error(f"Error Webhook: {e}")
        return {"version": "v2", "content": {"messages": [{"text": "⏳ Tenemos una demora técnica. Por favor, intentá de nuevo en unos minutos."}]}}
