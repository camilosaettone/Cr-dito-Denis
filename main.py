import re
import logging
import requests
from fastapi import FastAPI, Request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BCRA_API_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"

# ---------------------------
# Configuración de sesión HTTP
# ---------------------------
def crear_sesion():
    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)

    return session

# ---------------------------
# Consulta al BCRA
# ---------------------------
def consultar_situacion_bcra(cuit_cuil):
    cuit_clean = re.sub(r'\D', '', str(cuit_cuil))
    url = f"{BCRA_API_URL}{cuit_clean}"

    session = crear_sesion()

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Origin": "https://www.bcra.gob.ar",
        "Referer": "https://www.bcra.gob.ar/"
    }

    try:
        logging.info(f"Consultando BCRA: {cuit_clean}")

        response = session.get(url, headers=headers, timeout=10)

        logging.info(f"Status code: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"Respuesta no válida: {response.text}")
            return "error_conexion"

        data = response.json()

        results = data.get('results', data)
        periodos = results.get('periodos', [])

        if not periodos:
            return 1

        peor = 1

        for entidad in periodos[0].get('entidades', []):
            sit = int(entidad.get('situacion', 1))
            if sit > peor:
                peor = sit

        return peor

    except requests.exceptions.RequestException as e:
        logging.error(f"Error de red: {e}")
        return "error_conexion"
    except Exception as e:
        logging.error(f"Error inesperado: {e}")
        return "error_conexion"

# ---------------------------
# Cache simple (evita bloqueos)
# ---------------------------
@lru_cache(maxsize=1000)
def consultar_cacheado(cuit):
    return consultar_situacion_bcra(cuit)

# ---------------------------
# Endpoint webhook
# ---------------------------
@app.post("/webhook-cuil")
async def webhook_manychat(request: Request):
    try:
        data = await request.json()
        cuil = data.get("cuil")

        if not cuil:
            return {
                "version": "v2",
                "content": {"messages": [{"text": "⚠️ No se recibió un CUIL válido."}]}
            }

        res = consultar_cacheado(cuil)

        if res == 1:
            texto = "✅ ¡Buenas noticias! Tu perfil califica. Un asesor se contactará contigo pronto."
        elif isinstance(res, int) and res > 1:
            texto = f"❌ Tu situación actual (Nivel {res}) no permite avanzar con el préstamo en este momento."
        else:
            texto = "⚠️ No pudimos consultar el BCRA. Te derivamos con un asesor."

        return {
            "version": "v2",
            "content": {
                "messages": [
                    {"text": texto}
                ]
            }
        }

    except Exception as e:
        logging.error(f"Error en webhook: {e}")

        return {
            "version": "v2",
            "content": {
                "messages": [
                    {"text": "⏳ Tenemos una demora técnica. Un asesor te atenderá en instantes."}
                ]
            }
        }
