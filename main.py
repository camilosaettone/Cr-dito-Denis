from fastapi import FastAPI, Request
import requests
import re
import logging
import urllib3

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"
    
    # --- TUS DATOS DE WEBSHARE (Sacados de tu foto) ---
    proxy_user = "fonnotou"
    proxy_pass = "0k9ppmka6543"
    # El host y puerto lo sacas de la pestaña "Servidor proxy" en Webshare
    # Normalmente es p.webshare.io y puerto 80
    proxy_host = "p.webshare.io" 
    proxy_port = "80"
    
    proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.bcra.gob.ar/'
    }
    
    try:
        # Hacemos la consulta a través del proxy residencial
        response = requests.get(url, headers=headers, proxies=proxies, timeout=20, verify=False)
        
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
        
        return "error_api"
    except Exception as e:
        logging.error(f"Error con Proxy Webshare: {e}")
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
            texto = "⚠️ El sistema del Banco Central está saturado. Para agilizar, por favor envianos una CAPTURA DE PANTALLA de tu situación crediticia y un asesor te atenderá."

        return {"version": "v2", "content": {"messages": [{"text": texto}]}}
    except:
        return {"version": "v2", "content": {"messages": [{"text": "⏳ Tenemos una demora. Reintentá en un momento."}]}}
