from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import uvicorn
import asyncio

app = FastAPI(title="Cotizador Logístico Unificado")

# Habilitamos CORS para que Lovable.app pueda conectarse sin problemas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de datos de equipos
EQUIPOS = {
    "LH4300i": {"peso_kg": 23, "largo_cm": 50, "ancho_cm": 30, "alto_cm": 45, "valor": 650000},
    "GK7000ISE": {"peso_kg": 50, "largo_cm": 60, "ancho_cm": 47, "alto_cm": 50, "valor": 850000},
    "KPSC2500Pro": {"peso_kg": 32, "largo_cm": 30, "ancho_cm": 35, "alto_cm": 40, "valor": 850000},
}

async def cotizar_via_cargo(cp_destino: str, equipo: dict):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://viacargo.com.ar/cotizar-envio/")
            await page.wait_for_load_state("networkidle")
            
            # Origen
            await page.fill("input[placeholder*='Origen']", "1264")
            await page.click("text=BARRACAS (1264) - CAPITAL FEDERAL")
            
            # Destino
            await page.fill("input[placeholder*='Destino']", cp_destino)
            await page.keyboard.press("Enter")
            
            # Bultos y medidas
            await page.fill("input[name='bultos']", "1")
            await page.fill("input[name='peso']", str(equipo["peso_kg"]))
            await page.fill("input[name='largo']", str(equipo["largo_cm"]))
            await page.fill("input[name='ancho']", str(equipo["ancho_cm"]))
            await page.fill("input[name='alto']", str(equipo["alto_cm"]))
            await page.fill("input[name='valor']", str(equipo["valor"]))
            
            # Pago en origen y cotizar (Los selectores exactos pueden variar si la web de Via Cargo se actualiza)
            await page.check("input[name='pago_origen']") 
            await page.click("button:has-text('Cotizar')")
            
            await page.wait_for_timeout(4000) # Esperar a que cargue el precio
            
            # Extraer resultado
            precio = await page.evaluate("() => document.body.innerText.match(/\\$[0-9,.]+/)[0]")
            return {"transporte": "Vía Cargo", "precio": precio}
        except Exception as e:
            return {"transporte": "Vía Cargo", "error": "No se pudo obtener cotización"}
        finally:
            await browser.close()

async def cotizar_andreani(cp_destino: str, equipo: dict):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://www.andreani.com/?tab=cotizar-envio")
            await page.wait_for_load_state("networkidle")
            
            # Origen
            await page.fill("input[placeholder*='Código Postal de origen']", "1264")
            await page.click("text=1264 - CIUDAD AUTONOMA DE BUENOS AIRES")
            
            # Destino
            await page.fill("input[placeholder*='Código Postal de destino']", cp_destino)
            await page.keyboard.press("Enter")
            
            # Peso en gramos (kg * 1000)
            peso_gramos = equipo["peso_kg"] * 1000
            await page.fill("input[name='peso']", str(peso_gramos))
            
            # Medidas
            await page.fill("input[name='largo']", str(equipo["largo_cm"]))
            await page.fill("input[name='ancho']", str(equipo["ancho_cm"]))
            await page.fill("input[name='alto']", str(equipo["alto_cm"]))
            
            await page.click("button:has-text('Cotizar')")
            await page.wait_for_timeout(4000)
            
            precio = await page.evaluate("() => document.body.innerText.match(/\\$[0-9,.]+/)[0]")
            return {"transporte": "Andreani", "precio": precio}
        except Exception as e:
            return {"transporte": "Andreani", "error": "No se pudo obtener cotización"}
        finally:
            await browser.close()

@app.get("/cotizar")
async def obtener_cotizacion(modelo: str, cp_destino: str):
    if modelo not in EQUIPOS:
        raise HTTPException(status_code=404, detail="Modelo no encontrado en la base de datos")
    
    equipo = EQUIPOS[modelo]
    
    # Ejecuta ambos scrapings al mismo tiempo para que sea más rápido
    resultados = await asyncio.gather(
        cotizar_via_cargo(cp_destino, equipo),
        cotizar_andreani(cp_destino, equipo)
    )
    
    return {
        "modelo": modelo,
        "cp_destino": cp_destino,
        "cotizaciones": resultados
    }
