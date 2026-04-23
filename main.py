import random
import requests
import re
import logging
import urllib3
from fastapi import FastAPI, Request

# Desactivar advertencias de seguridad
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

# --- LISTA SOCKS5H (Tu lista de fotos) ---
PROXIES_LIST = [
    "socks5h://fonnotou:0k9ppmka6543@82.27.245.223:6546",
    "socks5h://fonnotou:0k9ppmka6543@147.124.198.200:6059",
    "socks5h://fonnotou:0k9ppmka6543@59.152.60.171:6111",
    "socks5h://fonnotou:0k9ppmka6543@108.165.69.64:6026",
    "socks5h://fonnotou:0k9ppmka6543@154.29.25.170:7181",
    "socks5h://fonnotou:0k9ppmka6543@89.40.222.206:6582",
    "socks5h://fonnotou:0k9ppmka6543@45.39.5.210:6648",
    "socks5h://fonnotou:0k9ppmka6543@82.21.249.169:7506",
    "socks5h://fonnotou:0k9ppmka6543@82.22.211.242:6050"
]

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Connection': 'close'
    }

    for intento in range(3):
        proxy_url = random.choice(PROXIES_LIST)
        proxies = {"http": proxy_url, "https": proxy_url}
        
        try:
            logging.info(f"Intento {intento+1}: Conectando vía {proxy_url}")
            # Aumentamos timeout a 25 porque SOCKS5 es más seguro pero a veces más lento
            response = requests.get(url, headers=headers, proxies=proxies, timeout=25, verify=False)
            
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
            
            if response.status_code == 404:
                return 1
                
        except Exception as e:
            logging.error(f"Error técnico en proxy: {e}")
            continue 
            
    return "error_conexion"

@app.post("/webhook-cuil")
async def webhook_manychat(request: Request):
    try:
        data = await request.json()
        cuil = data.get("cuil")
        res = consultar_situacion_bcra(cuil)

        if res == 1:
            texto = "✅ ¡Buenas noticias! Tu perfil califica. Un asesor de Crédito Denis se contactará con vos pronto."
        elif isinstance(res, int) and res > 1:
            texto = f"❌ Lo sentimos, tu situación actual (Nivel {res}) no nos permite avanzar con el préstamo ahora."
        else:
            texto = "⚠️ Estamos teniendo inconvenientes para consultar con el BCRA. Te derivo con un asesor para que te atienda personalmente ahora mismo."

        return {"version": "v2", "content": {"messages": [{"text": texto}]}}
    except:
        return {"version": "v2", "content": {"messages": [{"text": "⏳ Demora técnica. Reintentá en un momento."}]}}
