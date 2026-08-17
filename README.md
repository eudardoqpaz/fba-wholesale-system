# Amazon FBA Wholesale Automation System

Sistema completo para automatizar tu negocio de Amazon FBA Wholesale.

## Que hace este sistema

- **Scanner de Productos**: Sube CSVs de proveedores y encuentra productos rentables automaticamente
- **Calculadora de Rentabilidad**: Calcula ROI, margen neto, y todas las tarifas de Amazon
- **Gestion de Inventario**: Trackea stock en FBA, inbound, y local
- **Dashboard**: Ve metricas clave de tu negocio en un solo lugar
- **Alertas**: Notificaciones de cambios de precio, stock bajo, nuevos competidores
- **Reportes**: Reportes automaticos diarios y semanales

## Instalacion Rapida

### Opcion 1: Usar start.bat (Windows)
```
Doble click en start.bat
```

### Opcion 2: Manual
```bash
cd fba_system
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus API keys

python main.py
```

Abre http://localhost:8000 en tu navegador.

## Configuracion de APIs

### Keepa API (Recomendado - $19/mes)
1. Ve a https://keepa.com/#!api
2. Crea cuenta y suscribete
3. Copia tu API key al .env

### Amazon SP-API (Opcional - Gratis)
1. Ve a https://developer-docs.amazon.com/sp-api/
2. Registra como developer
3. Obtén las credenciales y copialas al .env

## Como usar el Scanner

1. Prepara tu CSV del proveedor con columnas: ASIN, Cost (precio de compra)
2. Ve a la pagina Scanner
3. Sube el CSV
4. Ajusta los filtros (ROI minimo, max sellers, etc.)
5. Click en "Escanear"
6. Revisa los productos rentables
7. Agregalos a tu lista de productos con un click

## Estructura

```
fba_system/
├── main.py              # App principal (FastAPI)
├── config.py            # Configuracion y tarifas
├── database.py          # Base de datos SQLite
├── models.py            # Modelos de datos
├── routers/             # Rutas API
│   ├── dashboard.py     # Dashboard y reportes
│   ├── products.py      # CRUD de productos
│   ├── scanner.py       # Scanner de price lists
│   ├── inventory.py     # Gestion de inventario
│   └── suppliers.py     # Gestion de proveedores
├── services/            # Logica de negocio
│   ├── calculator.py    # Calculadora de rentabilidad
│   ├── keepa_api.py     # Integracion con Keepa
│   ├── scanner.py       # Motor de escaneo
│   ├── alerts.py        # Sistema de alertas
│   └── reports.py       # Generacion de reportes
├── templates/           # HTML templates
├── static/              # CSS y JS
└── uploads/             # CSVs subidos
```

## Tech Stack

- **Backend**: Python 3.10+ / FastAPI
- **Database**: SQLite (via SQLAlchemy async)
- **Frontend**: Bootstrap 5 / Jinja2 templates
- **APIs**: Keepa API, Amazon SP-API
