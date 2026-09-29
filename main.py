from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import uvicorn

app = FastAPI(title="Cotizador Logístico Unificado")

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

# MEJORA: Mensaje de bienvenida para que el link corto no tire error
@app.get("/")
def bienvenida():
    return {"mensaje": "¡La API está encendida! Para usarla, agregale al final de la URL: /cotizar?modelo=LH4300i&cp_destino=2000"}

async def cotizar_via_cargo(cp_destino: str, equipo: dict):
    # MEJORA: Atrapamos los errores para que no colapse el servidor
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto("https://viacargo.com.ar/cotizar-envio/", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                await page.fill("input[placeholder*='Origen']", "1264", timeout=5000)
                await page.click("text=BARRACAS (1264) - CAPITAL FEDERAL", timeout=5000)
                
                await page.fill("input[placeholder*='Destino']", cp_destino)
                await page.keyboard.press("Enter")
                
                await page.fill("input[name='bultos']", "1")
                await page.fill("input[name='peso']", str(equipo["peso_kg"]))
                await page.fill("input[name='largo']", str(equipo["largo_cm"]))
                await page.fill("input[name='ancho']", str(equipo["ancho_cm"]))
                await page.fill("input[name='alto']", str(equipo["alto_cm"]))
                await page.fill("input[name='valor']", str(equipo["valor"]))
                
                await page.check("input[name='pago_origen']") 
                await page.click("button:has-text('Cotizar')")
                await page.wait_for_timeout(4000)
                
                # Extracción segura
                precio = await page.evaluate("() => { const match = document.body.innerText.match(/\\$[0-9,.]+/); return match ? match[0] : 'Precio no encontrado en pantalla'; }")
                return {"transporte": "Vía Cargo", "precio": precio}
            except Exception as e:
                return {"transporte": "Vía Cargo", "error": f"Error al navegar: {str(e)}"}
            finally:
                await browser.close()
    except Exception as e:
        return {"transporte": "Vía Cargo", "error": "El navegador invisible no pudo iniciar."}

async def cotizar_andreani(cp_destino: str, equipo: dict):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto("https://www.andreani.com/?tab=cotizar-envio", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                await page.fill("input[placeholder*='Código Postal de origen']", "1264", timeout=5000)
                await page.click("text=1264 - CIUDAD AUTONOMA DE BUENOS AIRES", timeout=5000)
                
                await page.fill("input[placeholder*='Código Postal de destino']", cp_destino)
                await page.keyboard.press("Enter")
                
                peso_gramos = equipo["peso_kg"] * 1000
                await page.fill("input[name='peso']", str(peso_gramos))
                await page.fill("input[name='largo']", str(equipo["largo_cm"]))
                await page.fill("input[name='ancho']", str(equipo["ancho_cm"]))
                await page.fill("input[name='alto']", str(equipo["alto_cm"]))
                
                await page.click("button:has-text('Cotizar')")
                await page.wait_for_timeout(4000)
                
                precio = await page.evaluate("() => { const match = document.body.innerText.match(/\\$[0-9,.]+/); return match ? match[0] : 'Precio no encontrado en pantalla'; }")
                return {"transporte": "Andreani", "precio": precio}
            except Exception as e:
                return {"transporte": "Andreani", "error": f"Error al navegar: {str(e)}"}
            finally:
                await browser.close()
    except Exception as e:
        return {"transporte": "Andreani", "error": "El navegador invisible no pudo iniciar."}

@app.get("/cotizar")
async def obtener_cotizacion(modelo: str, cp_destino: str):
    if modelo not in EQUIPOS:
        raise HTTPException(status_code=404, detail="Modelo no encontrado. Usá LH4300i, GK7000ISE o KPSC2500Pro")
    
    equipo = EQUIPOS[modelo]
    
    # MEJORA: Ejecutamos uno DESPUÉS del otro para no colapsar la memoria del servidor gratuito
    resultado_via_cargo = await cotizar_via_cargo(cp_destino, equipo)
    resultado_andreani = await cotizar_andreani(cp_destino, equipo)
    
    return {
        "modelo": modelo,
        "cp_destino": cp_destino,
        "cotizaciones": [resultado_via_cargo, resultado_andreani]
    }
