import random
from fastapi import FastAPI, Request
import requests
import re
import logging
import urllib3

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

# --- LISTA DE PROXIES ACTUALIZADA (Cargada de tus nuevas fotos) ---
# Formato: "http://usuario:contraseña@ip:puerto/"
PROXIES_LIST = [
    "http://fonnotou:0k9ppmka6543@82.27.245.223:6546/",   # Sudáfrica
    "http://fonnotou:0k9ppmka6543@147.124.198.200:6059/", # USA
    "http://fonnotou:0k9ppmka6543@59.152.60.171:6111/",   # Turquía
    "http://fonnotou:0k9ppmka6543@108.165.69.64:6026/",   # Países Bajos
    "http://fonnotou:0k9ppmka6543@154.29.25.170:7181/",   # Finlandia
    "http://fonnotou:0k9ppmka6543@89.40.222.206:6582/",   # Rumania
    "http://fonnotou:0k9ppmka6543@45.39.5.210:6648/",     # Canadá
    "http://fonnotou:0k9ppmka6543@82.21.249.169:7506/",   # Finlandia (2)
    "http://fonnotou:0k9ppmka6543@82.22.211.242:6050/"    # Reino Unido
]

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    
    # Elegimos un proxy al azar de la lista
    proxy_url = random.choice(PROXIES_LIST)
    proxies = {"http": proxy_url, "https": proxy_url}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.bcra.gob.ar/'
    }
    
    try:
        # Petición a través del proxy seleccionado
        response = requests.get(url, headers=headers, proxies=proxies, timeout=12, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            periodos = results.get('periodos', [])
            if not periodos: return 1 # No tiene deudas
            
            peor = 1
            for entidad in periodos[0].get('entidades', []):
                sit = int(entidad.get('situacion', 1))
                if sit > peor: peor = sit
            return peor
        
        return "error_api"
    except Exception as e:
        logging.error(f"Fallo proxy {proxy_url}: {e}")
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
            # Mensaje de derivación manual según tu pedido
            texto = "⚠️ Estamos teniendo inconvenientes para consultar con el BCRA. Te derivo con un asesor para que te atienda personalmente ahora mismo."

        return {"version": "v2", "content": {"messages": [{"text": texto}]}}
    except:
        return {"version": "v2", "content": {"messages": [{"text": "⏳ Tenemos una demora técnica. Por favor, reintentá en un momento."}]}}
