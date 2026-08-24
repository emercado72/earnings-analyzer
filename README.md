# Análisis de earnings por ticker

Herramienta que, dado un ticker, analiza sus **últimos 20 eventos de earnings**:

- **Beat / miss / meet** por evento (EPS reportado vs consenso) y **sorpresa %**.
- **Reacción del precio** en la primera sesión tras el anuncio (1 día) y a 5 días,
  teniendo en cuenta si el reporte fue antes de apertura (BMO) o tras el cierre (AMC).
- Estadísticas: tasa de beat, sorpresa media/mediana, movimiento típico, reacción media
  si beat / si miss, racha actual, correlación sorpresa↔reacción, últimos 4 y 8.
- **Valoración de analistas**: consenso (buy/hold/sell), distribución de recomendaciones
  de los últimos 3 meses, precio objetivo (bajo/medio/mediana/alto) y potencial.
- **Expectativa del próximo earning**: fecha, EPS e ingresos consenso (rango, nº de
  analistas, crecimiento interanual), EPS ajustado por la sorpresa histórica y rango de
  precio implícito por el movimiento típico.

Fuente de datos: Yahoo Finance (vía `yfinance`), sin API key.

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso

```bash
./earnings AAPL                    # reporte en terminal
./earnings NVDA --open             # además genera NVDA_earnings.html y lo abre
./earnings MSFT --html msft.html --json msft.json
./earnings TSLA -n 12              # solo los últimos 12 eventos
./earnings --serve                 # interfaz web en http://127.0.0.1:8765
```

En modo `--serve` hay también un endpoint JSON: `/api/report?ticker=AAPL`.

## Estructura

```
earnings_tool/
  data.py             # descarga (yfinance): earnings, precios, analistas, estimaciones
  analysis.py         # estadísticas, expectativa y conclusiones
  report_terminal.py  # salida rich en terminal
  report_html.py      # reporte HTML autocontenido con gráficos SVG
  server.py           # UI web local (stdlib http.server)
  cli.py              # línea de comandos
```

## Notas

- "Beat" si la sorpresa de EPS es > +0,05 %, "miss" si < −0,05 %, "meet" en caso contrario.
- La reacción 1d compara el cierre de la primera sesión posterior al anuncio con el
  cierre anterior; el rango implícito para el próximo earning usa la media del
  movimiento absoluto histórico (no es una volatilidad implícita de opciones).
- Yahoo a veces no publica hora del anuncio (columna "Hora" = n/d); en ese caso se
  asume AMC.

## Despliegue en Vercel

El proyecto incluye `api/index.py` (función serverless Python) y `vercel.json`, que
reescribe todas las rutas a esa función. Rutas disponibles en producción:

- `/` — formulario para elegir ticker
- `/report?ticker=AAPL` — reporte HTML (parámetro opcional `n=12`)
- `/api/report?ticker=AAPL` — JSON con eventos, analistas, próximo earning y estadísticas

```bash
vercel --prod
```
