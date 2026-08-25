# Análisis de earnings por ticker

**Demo en producción:** https://earnings-analyzer-nine.vercel.app

Herramienta que, dado un ticker, analiza sus **últimos 20 eventos de earnings**:

- **Beat / miss / meet** por evento (EPS reportado vs consenso) y **sorpresa %**.
- **Reacción del precio** en la primera sesión tras el anuncio (1 día) y a 5 días,
  teniendo en cuenta si el reporte fue antes de apertura (BMO) o tras el cierre (AMC).
- **Recorrido dentro de esa sesión**: apertura y gap, **máximo alcanzado en toda la
  sesión** y **máximo de la primera vela (09:30)**, para saber qué pico hubo realmente
  disponible antes de que el precio se desinflara hacia el cierre.
- Estadísticas: tasa de beat, sorpresa media/mediana, movimiento típico, reacción media
  si beat / si miss, racha actual, correlación sorpresa↔reacción, últimos 4 y 8.
- **Valoración de analistas**: consenso (buy/hold/sell), distribución de recomendaciones
  de los últimos 3 meses, precio objetivo (bajo/medio/mediana/alto) y potencial.
- **Movimiento esperado para el día del earning** (para elegir strike): movimiento
  implícito que descuenta el mercado de opciones — straddle ATM del primer vencimiento
  que cubre el reporte —, comparado con el movimiento histórico real, y una **escalera de
  strikes** con prima, breakeven, movimiento necesario, interés abierto, IV y con qué
  frecuencia los earnings pasados superaron ese breakeven.
- **Expectativa del próximo earning**: fecha, EPS e ingresos consenso (rango, nº de
  analistas, crecimiento interanual) y EPS ajustado por la sorpresa histórica.

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
./earnings AAPL --no-options       # omite la cadena de opciones (más rápido)
./earnings AAPL --no-intraday      # omite las velas intradía
./earnings --serve                 # interfaz web en http://127.0.0.1:8765
```

En modo `--serve` hay también un endpoint JSON: `/api/report?ticker=AAPL`.

## Estructura

```
earnings_tool/
  data.py             # descarga (yfinance): earnings, precios, analistas, estimaciones
  options.py          # movimiento implícito (straddle ATM) y escalera de strikes
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
- El movimiento implícito sale del straddle ATM (call + put del strike más cercano al
  spot) del primer vencimiento igual o posterior a la fecha del earning. Es la
  convención estándar de mesa, pero es una aproximación: incluye algo de valor temporal
  ajeno al evento.
- La columna "histórico supera BE" es **frecuencia pasada** sobre los últimos N earnings,
  no una probabilidad futura ni una recomendación. Los datos de la cadena de opciones
  llegan con retraso; contrasta precios con tu bróker antes de operar.
- **Máximo de la primera vela**: Yahoo solo conserva histórico intradía reciente
  (unos 60 días con velas de 30 minutos y unos 730 días con velas de 60 minutos), así
  que esa columna solo se rellena en los earnings dentro de esa ventana; el resto queda
  vacío. El **máximo de la sesión completa**, en cambio, está disponible para todos los
  eventos. Si el dato intradía no encaja en el rango diario (posible desajuste por
  splits) se descarta en lugar de mostrarse.
- Los precios usan `auto_adjust=False`: llevan splits aplicados pero no ajuste por
  dividendos, para que coincidan con lo que se vio en pantalla y con las barras intradía.
- No todos los valores tienen opciones listadas (las cotizadas europeas normalmente no);
  en ese caso la sección lo indica y el resto del informe funciona igual.

## Despliegue en Vercel

El proyecto incluye `api/index.py` (función serverless Python) y `vercel.json`, que
reescribe todas las rutas a esa función. Rutas disponibles en producción:

- `/` — formulario para elegir ticker
- `/report?ticker=AAPL` — reporte HTML (parámetro opcional `n=12`)
- `/api/report?ticker=AAPL` — JSON con eventos, analistas, próximo earning y estadísticas

```bash
vercel --prod        # o simplemente git push: el repo está conectado a Vercel
```
