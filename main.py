import random
import requests
import re
import logging
import urllib3
from fastapi import FastAPI, Request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

# --- LISTA ULTRA-RÁPIDA (Filtramos solo los de mejor respuesta) ---
PROXIES_LIST = [
    "socks5h://fonnotou:0k9ppmka6543@147.124.198.200:6059", # USA
    "socks5h://fonnotou:0k9ppmka6543@108.165.69.64:6026",  # Países Bajos
    "socks5h://fonnotou:0k9ppmka6543@45.39.5.210:6648",    # Canadá
    "socks5h://fonnotou:0k9ppmka6543@82.22.211.242:6050"   # Reino Unido
]

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Connection': 'close' 
    }

    # Un solo intento con un proxy al azar para responder ANTES que ManyChat corte
    proxy_url = random.choice(PROXIES_LIST)
    proxies = {"http": proxy_url, "https": proxy_url}
    
    try:
        logging.info(f"Conectando rápido vía: {proxy_url}")
        # Timeout estricto de 7 segundos. Si no responde, vamos directo al asesor.
        response = requests.get(url, headers=headers, proxies=proxies, timeout=7, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            periodos = results.get('periodos', [])
            if not periodos: return 1
            
            peor = 1
            for entidad in periodos[0].get('entidades', []):
                sit = int(entidad.get('situacion', 1))
                if sit > peor: peor = sit
            return peor
    except Exception as e:
        logging.error(f"Fallo en proxy: {e}")
            
    return "error_conexion"

@app.post("/webhook-cuil")
async def webhook_manychat(request: Request):
    try:
        data = await request.json()
        cuil = data.get("cuil")
        res = consultar_situacion_bcra(cuil)

        # Usamos los textos de Crédito Denis
        if res == 1:
            texto = "✅ ¡Buenas noticias! Tu perfil califica. Un asesor de Crédito Denis se contactará contigo pronto."
        elif isinstance(res, int) and res > 1:
            texto = f"❌ Lo sentimos, tu situación actual (Nivel {res}) no nos permite avanzar con el préstamo ahora."
        else:
            texto = "⚠️ Estamos teniendo inconvenientes para consultar con el BCRA. Te derivo con un asesor para que te atienda personalmente ahora mismo."

        return {"version": "v2", "content": {"messages": [{"text": texto}]}}
    except:
        return {"version": "v2", "content": {"messages": [{"text": "⏳ Tenemos una demora técnica. Un asesor te atenderá en instantes."}]}}
