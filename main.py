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

@app.get("/")
def bienvenida():
    return {"mensaje": "API Online"}

# Bloqueamos absolutamente todo lo visual para ahorrar RAM
async def optimizar_pagina(page):
    await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())

# Dieta extrema para Chromium (Evita que Render lo apague por exceso de RAM)
CHROMIUM_ARGS = [
    "--disable-dev-shm-usage", 
    "--no-sandbox", 
    "--disable-setuid-sandbox", 
    "--disable-gpu", 
    "--no-zygote", 
    "--single-process",
    "--disable-extensions",
    "--js-flags=--max-old-space-size=256"
]

async def cotizar_via_cargo(cp_destino: str, equipo: dict):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
            context = await browser.new_context()
            page = await context.new_page()
            await optimizar_pagina(page)
            
            try:
                await page.goto("https://viacargo.com.ar/cotizar-envio/", timeout=60000)
                await page.wait_for_timeout(4000)
                origen_input = page.locator("input[placeholder*='rigen'], input[placeholder*='ORIGEN'], input[id*='origen']").first
                await origen_input.fill("1264", timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                destino_input = page.locator("input[placeholder*='estino'], input[placeholder*='DESTINO'], input[id*='destino']").first
                await destino_input.fill(cp_destino, timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                await page.locator("input[name='bultos'], input[id*='bulto']").first.fill("1", timeout=10000)
                await page.locator("input[name='peso'], input[id*='peso']").first.fill(str(equipo["peso_kg"]))
                await page.locator("input[name='largo'], input[id*='largo']").first.fill(str(equipo["largo_cm"]))
                await page.locator("input[name='ancho'], input[id*='ancho']").first.fill(str(equipo["ancho_cm"]))
                await page.locator("input[name='alto'], input[id*='alto']").first.fill(str(equipo["alto_cm"]))
                await page.locator("input[name='valor'], input[id*='valor']").first.fill(str(equipo["valor"]))
                await page.locator("button:has-text('Cotizar'), button:has-text('COTIZAR')").first.click()
                await page.wait_for_timeout(5000)
                precio = await page.evaluate("() => { const match = document.body.innerText.match(/\\$[0-9,.]+/); return match ? match[0] : 'Precio no encontrado en pantalla'; }")
                return {"transporte": "Vía Cargo", "precio": precio}
            except Exception as e:
                return {"transporte": "Vía Cargo", "error": f"Error al navegar: {str(e)}"}
            finally:
                await browser.close()
    except Exception as e:
        return {"transporte": "Vía Cargo", "error": f"Fallo motor Docker: {str(e)}"}

async def cotizar_andreani(cp_destino: str, equipo: dict):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
            context = await browser.new_context()
            page = await context.new_page()
            await optimizar_pagina(page)
            
            try:
                await page.goto("https://www.andreani.com/?tab=cotizar-envio", timeout=60000)
                await page.wait_for_timeout(4000)
                origen_input = page.locator("input[placeholder*='Postal'], input[placeholder*='origen'], input[id*='origen']").first
                await origen_input.fill("1264", timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                destino_input = page.locator("input[placeholder*='Postal'], input[placeholder*='destino'], input[id*='destino']").nth(1)
                await destino_input.fill(cp_destino, timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                peso_gramos = equipo["peso_kg"] * 1000
                await page.locator("input[name='peso'], input[placeholder*='Peso']").first.fill(str(peso_gramos), timeout=10000)
                await page.locator("input[name='largo'], input[placeholder*='Largo']").first.fill(str(equipo["largo_cm"]))
                await page.locator("input[name='ancho'], input[placeholder*='Ancho']").first.fill(str(equipo["ancho_cm"]))
                await page.locator("input[name='alto'], input[placeholder*='Alto']").first.fill(str(equipo["alto_cm"]))
                await page.locator("button:has-text('Cotizar'), button:has-text('COTIZAR')").first.click()
                await page.wait_for_timeout(5000)
                precio = await page.evaluate("() => { const match = document.body.innerText.match(/\\$[0-9,.]+/); return match ? match[0] : 'Precio no encontrado en pantalla'; }")
                return {"transporte": "Andreani", "precio": precio}
            except Exception as e:
                return {"transporte": "Andreani", "error": f"Error al navegar: {str(e)}"}
            finally:
                await browser.close()
    except Exception as e:
        return {"transporte": "Andreani", "error": f"Fallo motor Docker: {str(e)}"}

@app.head("/cotizar")
@app.get("/cotizar")
async def obtener_cotizacion(modelo: str, cp_destino: str):
    if modelo not in EQUIPOS:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    equipo = EQUIPOS[modelo]
    
    resultado_via_cargo = await cotizar_via_cargo(cp_destino, equipo)
    resultado_andreani = await cotizar_andreani(cp_destino, equipo)
    
    return {
        "modelo": modelo,
        "cp_destino": cp_destino,
        "cotizaciones": [resultado_via_cargo, resultado_andreani]
    }
