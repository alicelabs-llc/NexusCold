# NexusCold v6.0 — AliceLabs B2B Data Enrichment Engine 🌐

> **WORLD EDITION** — Multi-source parallel enrichment con 20+ workers.  
> Cobertura global: USA, UK, EU, LATAM, AU, IN, SG, HK + más.

## 🚀 Cómo usar

1. **Ejecutar** `ALICELABS_NEXUS_6.0.bat` (Windows)
2. Cargar un CSV o XLSX con empresas
3. Mapear columnas: Nombre → Location
4. Seleccionar fuentes de enriquecimiento
5. Click **INITIALIZE EXTRACTION ENGINE**

## 📦 Archivos principales

| Archivo | Descripción |
|---------|-------------|
| `ALICELABS_EXTRACTOR_GUI.py` | Interfaz gráfica (customtkinter) |
| `enricher_core.py` | Motor de enriquecimiento multi-fuente |
| `email_warmer.py` | Sistema de calentamiento de emails |
| `build_nexus.bat` | Builder para generar .exe |

## 🔧 Requisitos

```bash
pip install customtkinter openpyxl requests beautifulsoup4 aiohttp pandas
```

## 👤 Autor

**AliceLabs LLC** — Edison Flores
