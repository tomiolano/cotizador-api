from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from playwright.async_api import async_playwright
import re

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

CHROMIUM_ARGS = [
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-gpu",
    "--no-zygote",
    "--single-process",
    "--disable-extensions",
    "--js-flags=--max-old-space-size=256",
]


@app.get("/")
def bienvenida():
    return {"mensaje": "API Online v6 - Con diagnostico"}


async def crear_pagina(playwright):
    browser = await playwright.chromium.launch(headless=True, args=CHROMIUM_ARGS)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
    )
    page = await context.new_page()
    await page.route(
        "**/*",
        lambda route: (
            route.abort()
            if route.request.resource_type in ["image", "media", "font"]
            else route.continue_()
        ),
    )
    return browser, page


@app.get("/debug/viacargo", response_class=HTMLResponse)
async def debug_viacargo():
    try:
        async with async_playwright() as p:
            browser, page = await crear_pagina(p)
            try:
                await page.goto("https://viacargo.com.ar/cotizar-envio/", timeout=60000)
                await page.wait_for_timeout(8000)
                html = await page.content()
                return html
            finally:
                await browser.close()
    except Exception as e:
        return HTMLResponse(content="Error: " + str(e))


@app.get("/debug/andreani", response_class=HTMLResponse)
async def debug_andreani():
    try:
        async with async_playwright() as p:
            browser, page = await crear_pagina(p)
            try:
                await page.goto("https://www.andreani.com/?tab=cotizar-envio", timeout=60000)
                await page.wait_for_timeout(8000)
                html = await page.content()
                return html
            finally:
                await browser.close()
    except Exception as e:
        return HTMLResponse(content="Error: " + str(e))


@app.get("/debug/inputs")
async def debug_inputs():
    resultados = {}
    try:
        async with async_playwright() as p:
            browser, page = await crear_pagina(p)
            try:
                await page.goto("https://viacargo.com.ar/cotizar-envio/", timeout=60000)
                await page.wait_for_timeout(8000)
                inputs_vc = await page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input');
                    return Array.from(inputs).map((el, i) => ({
                        indice: i,
                        id: el.id,
                        name: el.name,
                        type: el.type,
                        placeholder: el.placeholder,
                        ariaLabel: el.getAttribute('aria-label'),
                        clase: el.className.substring(0, 80)
                    }));
                }""")
                resultados["viacargo_inputs"] = inputs_vc
                resultados["viacargo_url"] = page.url
            except Exception as e:
                resultados["viacargo_error"] = str(e)
            finally:
                await browser.close()
    except Exception as e:
        resultados["viacargo_fallo"] = str(e)

    try:
        async with async_playwright() as p:
            browser, page = await crear_pagina(p)
            try:
                await page.goto("https://www.andreani.com/?tab=cotizar-envio", timeout=60000)
                await page.wait_for_timeout(8000)
                inputs_an = await page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input');
                    return Array.from(inputs).map((el, i) => ({
                        indice: i,
                        id: el.id,
                        name: el.name,
                        type: el.type,
                        placeholder: el.placeholder,
                        ariaLabel: el.getAttribute('aria-label'),
                        clase: el.className.substring(0, 80)
                    }));
                }""")
                resultados["andreani_inputs"] = inputs_an
                resultados["andreani_url"] = page.url
            except Exception as e:
                resultados["andreani_error"] = str(e)
            finally:
                await browser.close()
    except Exception as e:
        resultados["andreani_fallo"] = str(e)

    return resultados


async def cotizar_via_cargo(cp_destino: str, equipo: dict):
    try:
        async with async_playwright() as p:
            browser, page = await crear_pagina(p)
            try:
                await page.goto("https://viacargo.com.ar/cotizar-envio/", timeout=60000)
                await page.wait_for_timeout(8000)

                await page.locator("#mat-input-0").fill("1264", timeout=15000)
                await page.wait_for_timeout(1500)
                await page.locator("mat-option").filter(has_text="BARRACAS").first.click(timeout=5000)
                await page.wait_for_timeout(500)

                await page.locator("#mat-input-1").fill(cp_destino, timeout=10000)
                await page.wait_for_timeout(1500)
                await page.locator("mat-option").first.click(timeout=5000)
                await page.wait_for_timeout(500)

                await page.locator("#mat-input-2").fill("1", timeout=5000)
                await page.locator("#mat-input-3").fill(str(equipo["peso_kg"]))
                await page.locator("#mat-input-4").fill(str(equipo["largo_cm"]))
                await page.locator("#mat-input-5").fill(str(equipo["ancho_cm"]))
                await page.locator("#mat-input-6").fill(str(equipo["alto_cm"]))
                await page.locator("#mat-input-7").fill(str(equipo["valor"]))

                pago_origen = page.locator("mat-radio-button, mat-checkbox").filter(
                    has_text=re.compile("origen", re.IGNORECASE)
                ).first
                await pago_origen.click(timeout=5000)

                await page.locator("button").filter(
                    has_text=re.compile("cotizar", re.IGNORECASE)
                ).first.click(timeout=5000)
                await page.wait_for_timeout(6000)

                precios = await page.evaluate(
                    """() => {
                    const matches = document.body.innerText.match(/\\$\\s?[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?/g);
                    return matches ? matches : [];
                }"""
                )
                if precios:
                    return {"transporte": "Via Cargo", "precios": precios}
                else:
                    return {"transporte": "Via Cargo", "precios": "No se encontraron precios"}
            except Exception as e:
                return {"transporte": "Via Cargo", "error": "Error: " + str(e)}
            finally:
                await browser.close()
    except Exception as e:
        return {"transporte": "Via Cargo", "error": "Fallo motor: " + str(e)}


async def cotizar_andreani(cp_destino: str, equipo: dict):
    try:
        async with async_playwright() as p:
            browser, page = await crear_pagina(p)
            try:
                await page.goto("https://www.andreani.com/?tab=cotizar-envio", timeout=60000)
                await page.wait_for_timeout(8000)

                await page.get_by_label("Desde").fill("1264", timeout=15000)
                await page.wait_for_timeout(1500)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(500)

                await page.get_by_label("Hasta").fill(cp_destino, timeout=10000)
                await page.wait_for_timeout(1500)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(500)

                peso_gramos = equipo["peso_kg"] * 1000
                await page.get_by_label("Peso").fill(str(peso_gramos), timeout=5000)
                await page.get_by_label("Largo").fill(str(equipo["largo_cm"]))
                await page.get_by_label("Ancho").fill(str(equipo["ancho_cm"]))
                await page.get_by_label("Alto").fill(str(equipo["alto_cm"]))

                await page.get_by_role(
                    "button", name=re.compile("cotizar", re.IGNORECASE)
                ).first.click(timeout=5000)
                await page.wait_for_timeout(6000)

                precios = await page.evaluate(
                    """() => {
                    const matches = document.body.innerText.match(/\\$\\s?[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?/g);
                    return matches ? matches : [];
                }"""
                )
                if precios:
                    return {"transporte": "Andreani", "precios": precios}
                else:
                    return {"transporte": "Andreani", "precios": "No se encontraron precios"}
            except Exception as e:
                return {"transporte": "Andreani", "error": "Error: " + str(e)}
            finally:
                await browser.close()
    except Exception as e:
        return {"transporte": "Andreani", "error": "Fallo motor: " + str(e)}


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
        "cotizaciones": [resultado_via_cargo, resultado_andreani],
    }
