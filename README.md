# NexusCold v6.0 — AliceLabs B2B Data Enrichment Engine

> **WORLD EDITION** — Multi-source parallel enrichment con 20+ workers.
> Cobertura global: USA, UK, EU, LATAM, AU, IN, SG, HK + más.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AL-1.0](https://img.shields.io/badge/License-AliceLabs%20AL--1.0-orange.svg)](./LICENSE-AL-1.0)
[![CI](https://github.com/alicelabs-llc/NexusCold/actions/workflows/ci.yml/badge.svg)](https://github.com/alicelabs-llc/NexusCold/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-18%20passed-brightgreen.svg)](#tests)

`NexusCold` es un motor de enriquecimiento de datos B2B multi-fuente con scraping
paralelo y cobertura global. Incluye:

- GUI de escritorio (customtkinter) para ingestión de CSV/XLSX
- Motor de enriquecimiento con 20+ workers asíncronos (aiohttp)
- Sistema de calentamiento de emails (`email_warmer.py`) con ramp control
- Fuentes: DuckDuckGo, Bing, Google, Clearbit, sam.gov, OpenCorporates,
  UK Companies House, Brasil CNPJ, EU VAT, y más
- Cache local en disco, rate-limiting por dominio, y proxy rotativo opcional

## 📦 Instalación

### Desde código fuente

```bash
git clone https://github.com/alicelabs-llc/NexusCold.git
cd NexusCold

# Recomendado: entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### Windows: binario precompilado

```cmd
build_nexus.bat
```

Genera `dist/ALICELABS_NEXUS_6.0.exe` (standalone, no requiere Python instalado).

## 🚀 Uso

### GUI

```bash
python ALICELABS_EXTRACTOR_GUI.py
```

1. Cargar un CSV o XLSX con empresas (columnas: `Nombre`, `Location`)
2. Mapear las columnas
3. Seleccionar fuentes de enriquecimiento
4. Click **INITIALIZE EXTRACTION ENGINE**

### Como librería (CLI o scripts)

```python
from enricher_core import EnrichedCompany, run_enrichment

companies = [
    EnrichedCompany(company_name="Microsoft", city="Redmond", country="USA"),
    EnrichedCompany(company_name="AliceLabs LLC", city="Quito", country="Ecuador"),
]

# 20 workers paralelos, con progress_callback opcional
def progress(done, total, name):
    print(f"[{done}/{total}] {name}")

results = run_enrichment(companies, workers=20, progress_callback=progress)

for c in results:
    print(f"{c.company_name}: website={c.website} email={c.email}")
```

## 📦 Archivos principales

| Archivo | Descripción |
|---------|-------------|
| `ALICELABS_EXTRACTOR_GUI.py` | Interfaz gráfica (customtkinter) |
| `enricher_core.py` | Motor de enriquecimiento multi-fuente (60 KB, 1.2K+ líneas) |
| `email_warmer.py` | Sistema de calentamiento de emails (ramp + scheduling) |
| `build_nexus.bat` | Builder para generar `.exe` en Windows |
| `tests/` | Suite de tests en pytest |
| `requirements.txt` | Dependencias Python |
| `.github/workflows/ci.yml` | CI en GitHub Actions |

## 🧪 Tests

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest tests/ -v
```

Los tests cubren:

- `tests/test_enricher_core.py` — dataclass `EnrichedCompany`, helpers
  (`clean_email`, `clean_phone`, `extract_domain`, `is_valid_website`,
  `get_cache_key`), y `run_enrichment` con lista vacía.
- `tests/test_email_warmer.py` — ramp logic, scheduling, dedup.
- `tests/test_imports.py` — todos los módulos importan sin error.

Tests offline (no network): corren en CI sin tocar DuckDuckGo/Bing/Google.

## 🔧 Requisitos

- Python 3.8+
- Dependencias listadas en `requirements.txt`:

```
customtkinter>=5.2.0
openpyxl>=3.1.0
requests>=2.31.0
beautifulsoup4>=4.12.0
aiohttp>=3.9.0
pandas>=2.0.0
brotli>=1.1.0
```

`brotli` es requerido porque `aiohttp` lo usa para descomprimir respuestas
de DuckDuckGo/Bing (que mandan Content-Encoding: br).

## 🏗️ Arquitectura

```
enricher_core.py
├── EnrichedCompany        (dataclass con 37 campos: identity, contact, geo, IDs fiscales)
├── Helpers                (clean_email, clean_phone, extract_domain, etc.)
├── Cache                  (load_cache, save_cache, get_cache_key — disco JSON)
├── Rate limiting          (check_rate_limit por dominio, persistente)
├── Sources (async)        (source_ddg, source_bing, source_google, source_clearbit,
│                           source_website, source_samgov, source_opencorp,
│                           source_uk_companies, source_brazil_cnpj, source_eu_vat, ...)
├── AI heuristic           (ai_agent_heuristic — confidence scoring)
└── Orquestación           (enrich_company, enrich_batch, run_enrichment)
```

## 🌐 Cobertura por país

| País | ID fiscal | Fuente principal |
|------|----------|-----------------|
| USA | EIN | sam.gov, OpenCorporates |
| UK | Company Number | UK Companies House API |
| Brasil | CNPJ | receita.fazenda API |
| EU | VAT | EU VIES |
| México | RFC | SAT |
| Australia | ABN | ABR |
| India | CIN | mca.gov.in |
| Latam (genérico) | RUC/RUT | OpenCorporates + scraping |

## ⚠️ Notas de uso

- **Sigue los robots.txt** y los Términos de Servicio de cada fuente.
- **No uses este motor para spam**. Respeta CAN-SPAM, GDPR, LGPD.
- El `email_warmer.py` está diseñado para **warming legítimo** de tus propias
  cuentas de envío, no para evadir filtros anti-spam.

## 👤 Autor

**AliceLabs LLC** — Edison Flores

## 📄 Licencia

AliceLabs Source-Available License AL-1.0. Ver
[`LICENSE-AL-1.0`](./LICENSE-AL-1.0). El código es visible y auditable, pero
la redistribución comercial requiere permiso explícito.
