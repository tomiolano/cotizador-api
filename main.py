from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import uvicorn
import re

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

async def optimizar_pagina(page):
    await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())

CHROMIUM_ARGS = [
    "--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox", 
    "--disable-gpu", "--no-zygote", "--single-process", "--disable-extensions",
    "--js-flags=--max-old-space-size=256"
]

# FUNCIÓN INTELIGENTE: Busca la cajita de 3 formas distintas a la vez
def encontrar_input(page, palabra_clave):
    # 1. Técnica Angular Material (Para Vía Cargo)
    loc_angular = page.locator("mat-form-field").filter(has_text=re.compile(palabra_clave, re.IGNORECASE)).locator("input").first
    # 2. Técnica Clásica
    loc_clasico = page.locator(f"input[placeholder*='{palabra_clave}' i], input[id*='{palabra_clave}' i], input[name*='{palabra_clave}' i]").first
    # 3. Técnica por etiqueta visible
    loc_label = page.get_by_label(re.compile(palabra_clave, re.IGNORECASE)).first
    
    # Devuelve el primero que encuentre en la pantalla
    return loc_angular.or_(loc_clasico).or_(loc_label)

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
                
                # Buscamos Origen y Destino con la nueva técnica
                await encontrar_input(page, "origen").fill("1264", timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                
                await encontrar_input(page, "destino").fill(cp_destino, timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                
                # Completar el resto de los datos
                await encontrar_input(page, "bulto").fill("1", timeout=5000)
                await encontrar_input(page, "peso").fill(str(equipo["peso_kg"]))
                await encontrar_input(page, "largo").fill(str(equipo["largo_cm"]))
                await encontrar_input(page, "ancho").fill(str(equipo["ancho_cm"]))
                await encontrar_input(page, "alto").fill(str(equipo["alto_cm"]))
                await encontrar_input(page, "valor").fill(str(equipo["valor"]))
                
                # Botón cotizar
                await page.locator("button:has-text('Cotizar'), button:has-text('COTIZAR')").first.click()
                await page.wait_for_timeout(6000)
                
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
                
                await encontrar_input(page, "origen").fill("1264", timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                
                await encontrar_input(page, "destino").fill(cp_destino, timeout=15000)
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                
                peso_gramos = equipo["peso_kg"] * 1000
                await encontrar_input(page, "peso").fill(str(peso_gramos), timeout=5000)
                await encontrar_input(page, "largo").fill(str(equipo["largo_cm"]))
                await encontrar_input(page, "ancho").fill(str(equipo["ancho_cm"]))
                await encontrar_input(page, "alto").fill(str(equipo["alto_cm"]))
                
                await page.locator("button:has-text('Cotizar'), button:has-text('COTIZAR')").first.click()
                await page.wait_for_timeout(6000)
                
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
