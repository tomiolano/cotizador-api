from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uuid

app = FastAPI(title="Cotizador Logistico Unificado")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EQUIPOS = {
    "LH4300i": {"peso_kg": 23, "largo_cm": 50, "ancho_cm": 30, "alto_cm": 45, "valor": 650000},
    "GK7000ISE": {"peso_kg": 50, "largo_cm": 60, "ancho_cm": 47, "alto_cm": 50, "valor": 850000},
    "KPSC2500Pro": {"peso_kg": 32, "largo_cm": 30, "ancho_cm": 35, "alto_cm": 40, "valor": 850000},
}

CP_ORIGEN = "1264"
HEADERS_VC = {
    "Content-Type": "application/json",
    "Referer": "https://viacargo.com.ar/cotizar-envio/",
    "Origin": "https://viacargo.com.ar",
}
HEADERS_AN = {
    "Content-Type": "application/json",
    "Referer": "https://www.andreani.com/",
    "Origin": "https://www.andreani.com",
}


@app.get("/")
def bienvenida():
    modelos = list(EQUIPOS.keys())
    return {
        "mensaje": "API Cotizador Logistico - Ultra rapida, sin navegador",
        "uso": "/cotizar?modelo=LH4300i&cp_destino=2000",
        "modelos_disponibles": modelos,
    }


async def cotizar_via_cargo(cp_destino: str, equipo: dict):
    url = "https://ws.busplus.com.ar/alerce/cotizar"
    payload = {
        "IdClienteRemitente": "99999999",
        "IdCentroRemitente": "99",
        "CodigoPostalRemitente": CP_ORIGEN,
        "CodigoPostalDestinatario": cp_destino,
        "ImporteValorDeclarado": str(equipo["valor"]),
        "NumeroBultos": "1",
        "Kilos": str(equipo["peso_kg"]),
        "Largo": str(equipo["largo_cm"]),
        "Alto": str(equipo["alto_cm"]),
        "Ancho": str(equipo["ancho_cm"]),
        "TipoPortes": "P",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers=HEADERS_VC)
            resp.raise_for_status()
            data = resp.json()
            servicios = []
            for prod in data.get("Cotizacion", []):
                if prod.get("PRODUCTO_PERMITIDO") == "S":
                    servicios.append({
                        "servicio": prod["PRODUCTO_DESCRIPCION"],
                        "precio": int(float(prod["TOTAL"])),
                        "precio_formateado": "$" + f"{int(float(prod['TOTAL'])):,}".replace(",", "."),
                        "fecha_entrega": prod.get("TIEMPO_ENTREGA", ""),
                    })
            return {"transporte": "Via Cargo", "servicios": servicios}
    except Exception as e:
        return {"transporte": "Via Cargo", "error": str(e)}


async def cotizar_andreani(cp_destino: str, equipo: dict):
    url = "https://www.andreani.com/api/cotizador/prices"
    payload = {
        "codigoPostalOrigen": CP_ORIGEN,
        "codigoPostalDestino": cp_destino,
        "bultos": [
            {
                "itemId": str(uuid.uuid4()),
                "altoCm": str(equipo["alto_cm"]),
                "anchoCm": str(equipo["ancho_cm"]),
                "largoCm": str(equipo["largo_cm"]),
                "pesoGramos": str(equipo["peso_kg"] * 1000),
            }
        ],
        "tipoDeEnvioId": "9c16612c-a916-48cf-9fbb-dbad2b097e9e",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers=HEADERS_AN)
            resp.raise_for_status()
            data = resp.json()
            servicios = []
            for item in data:
                tipo_nombre = "Envio a sucursal" if item["type"] == "branch" else "Envio a domicilio"
                precio = item["price"]
                servicios.append({
                    "servicio": tipo_nombre,
                    "precio": round(precio),
                    "precio_formateado": "$" + f"{round(precio):,}".replace(",", "."),
                })
            return {"transporte": "Andreani", "servicios": servicios}
    except Exception as e:
        return {"transporte": "Andreani", "error": str(e)}


@app.head("/cotizar")
@app.get("/cotizar")
async def obtener_cotizacion(modelo: str, cp_destino: str):
    if modelo not in EQUIPOS:
        raise HTTPException(
            status_code=404,
            detail="Modelo no encontrado. Usa: LH4300i, GK7000ISE o KPSC2500Pro",
        )
    equipo = EQUIPOS[modelo]

    resultado_vc = await cotizar_via_cargo(cp_destino, equipo)
    resultado_an = await cotizar_andreani(cp_destino, equipo)

    return {
        "modelo": modelo,
        "cp_destino": cp_destino,
        "cotizaciones": [resultado_vc, resultado_an],
    }
