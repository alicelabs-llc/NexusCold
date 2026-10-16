# NexusCold 6.2 — Mailbox Checks

Enriquecimiento B2B local de AliceLabs LLC. Revisa archivos CSV sin subirlos a una plataforma y activa búsquedas web cuando las necesites. Sin cuenta ni clave API para el flujo básico. Python 3.10 o superior.

## Instalar y abrir

```bash
python -m pip install -r requirements.txt
python ALICELABS_EXTRACTOR_GUI.py
```

Windows: después de instalar, abre `ALICELABS_NEXUS_6.2.bat`. Para generar un ejecutable, ejecuta `build_nexus.bat` desde Windows. El builder ya no depende de una ruta privada de otro equipo ni de un archivo de caché inexistente. El ejecutable debe compilarse y probarse en Windows; esta versión no adjunta un binario validado.

En la interfaz, carga CSV/XLSX, mapea nombre y ciudad, confirma y ejecuta. Las columnas opcionales `website`, `email`, `country` y `state` se aprovechan cuando están presentes. Detener conserva resultados parciales y marca filas que no empezaron como `cancelled`; las consultas en curso finalizan con sus timeouts.

## Revisar CSV sin conexión

Solo necesita Python estándar para este modo. Columna obligatoria: `company_name`. Opcionales: `website`, `email`, `city`, `state`, `country`. Conserva las demás columnas y los ceros iniciales.

```bash
python nexus_cli.py empresas.csv --output empresas_revisadas.csv
```

Detecta duplicados sin borrar filas, errores de sintaxis y correos cuyo dominio no coincide con la web. `DUPLICATE_OF` apunta al número de línea de la primera aparición, contando la cabecera. Devuelve un resumen JSON por consola. Protege celdas y cabeceras que podrían ejecutarse como fórmulas al abrir Excel.

Para consultar fuentes públicas por internet:

```bash
python nexus_cli.py empresas.csv --output empresas_enriquecidas.csv --enrich --workers 10
```

La salida añade columnas `ENRICHED_*`. Este modo necesita `aiohttp` y transmite nombres/ubicaciones a buscadores y registros públicos. La calidad y disponibilidad de esas fuentes varía; algunos endpoints heredados requieren credenciales o pueden dejar de responder. No existe garantía de cobertura.

## Verificación de buzones sin API

En la interfaz, `Verify mailboxes: DNS + SMTP` está activado por defecto y se puede desmarcar. Después del enriquecimiento, el programa consulta MX/A/AAAA y realiza una comprobación SMTP de destinatario. No utiliza credenciales ni envía `DATA`, el asunto o el cuerpo de un mensaje. Si el servidor ofrece STARTTLS, verifica el certificado contra el nombre del MX. La aceptación de SMTP sigue siendo una señal puntual, no una garantía de entrega.

Verificar correos que ya tienes, sin buscar empresas en internet:

```bash
python nexus_cli.py empresas.csv --output verificados.csv --verify-mailboxes
```

Buscar datos y verificar los correos encontrados en una sola ejecución:

```bash
python nexus_cli.py empresas.csv --output enriquecidos_verificados.csv --enrich --verify-mailboxes
```

Comprobar solo las rutas de correo, sin abrir conexiones SMTP:

```bash
python nexus_cli.py empresas.csv --output rutas_correo.csv --mx-only
```

| `MAILBOX_STATUS` | Significado |
| --- | --- |
| `smtp_accepted` | El MX aceptó el destinatario y rechazó un destinatario aleatorio con `5.1.1`. No garantiza que haya un buzón físico ni entrega final. |
| `mailbox_rejected` | El MX rechazó el destinatario con código explícito `5.1.1`. |
| `catch_all` | También aceptó el destinatario aleatorio; no se puede confirmar el buzón individual. |
| `mx_found` | Se encontró una ruta pública MX o A/AAAA implícita; no se comprobó el buzón. |
| `domain_no_mail` | El dominio publica Null MX: declara que no recibe correo. |
| `domain_not_found` | Respuesta DNS NXDOMAIN. |
| `unknown` | Timeout, bloqueo, greylisting, rechazo por política, DNS no disponible o respuesta ambigua. No equivale a inválido. |
| `invalid_syntax`, `not_found`, `not_checked` | Formato no admitido, sin correo o comprobación desactivada/cancelada. |

Se exportan motivo, MX, código SMTP, señal catch-all y fecha UTC en columnas `MAILBOX_*`, separadas del análisis offline `EMAIL_STATUS`. Las comprobaciones se repiten en cada ejecución para no reutilizar estados SMTP antiguos de la caché de enriquecimiento.

Límites: cuatro verificaciones simultáneas, una por dominio, hasta dos MX y un destinatario aleatorio de control por intento. Duplicados exactos se verifican una sola vez por ejecución. Cada intento SMTP tiene un límite global de 12 segundos con cierre del socket, además de límites de tamaño/líneas. Detener evita nuevas comprobaciones; las activas terminan dentro de sus límites. Las consultas DNS tienen un límite de cuatro segundos cada una. DNS públicos y puerto TCP 25 deben estar disponibles en tu equipo: muchos alojamientos bloquean ese puerto, y algunos proveedores ocultan la existencia de buzones. Esos casos se conservan como `unknown`. La sintaxis admitida es ASCII habitual; SMTPUTF8 y direcciones con comillas no están soportadas.

## Cómo interpretar los resultados

- `EMAIL_STATUS`: `syntax_only`, `domain_mismatch`, `invalid_syntax`, `not_found` o `not_checked`. **Es solo calidad offline: la comprobación DNS/SMTP se exporta por separado en `MAILBOX_STATUS`.** Un dominio diferente requiere revisión y puede ser legítimo.
- `CONFIDENCE`: puntuación heurística de completitud de 0 a 100; no es probabilidad de exactitud ni de entrega.
- `EVIDENCE`: JSON que vincula correos extraídos del sitio con las páginas donde se observaron. No certifica identidad de empresa ni todos los campos de registros externos.
- `CHECKED_AT`: fecha UTC del procesamiento; la caché conserva la fecha original.
- Clasificación sectorial y datos fiscales extraídos por regex requieren revisión. Las descripciones observadas tienen prioridad sobre inferencias por nombre.

## Comprobaciones SMTP controladas

El módulo `email_warmer.py` funciona en `dry_run=True` por defecto. Ya no genera destinatarios ni inventa aperturas, respuestas o rebotes. No hay bandeja IMAP ni medición real de reputación del proveedor; el antiguo score interno no demuestra entregabilidad.

Para una prueba controlada, configura explícitamente `WarmerConfig(dry_run=False, test_recipients=[...])` con buzones que controlas o que aceptaron la prueba. Las credenciales se reciben en memoria o mediante `EmailAccount(password_env="NEXUS_SMTP_PASSWORD")`; configura esa variable fuera del repositorio. Las contraseñas no se serializan ni aparecen en el `repr` de la cuenta. Al cargar estados antiguos se ignora `password`; vuelve a introducirlo en memoria o usa una variable de entorno. Los archivos antiguos existentes no se borran automáticamente: elimina sus contraseñas o vuelve a guardar el estado.

## Seguridad y alcance

TLS verificado; bloqueo de URLs locales, DNS privados y redirecciones a redes internas en el procesador por lotes. Caché y estado con reemplazo atómico. La caché local contiene datos de contacto sin cifrar y dura 24 horas; protégela con los permisos/cifrado del dispositivo. No se implementa sincronización entre varios procesos que escriban simultáneamente. La interfaz de enriquecimiento no envía campañas.

## Pruebas

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m unittest discover -v
```

Suite automática offline y CI configurado para Python 3.10, 3.12 y 3.13. Los scripts `test_debug.py` y `test_sources.py` son sondas manuales de red, no pruebas de cobertura de proveedores. La suite valida DNS/SMTP con respuestas controladas y exportación; no sustituye pruebas visuales de interfaz ni una prueba de conectividad en tu red. En el entorno de implementación, la prueba DNS real devolvió `unknown / dns_unavailable`; no se ha demostrado acceso real a SMTP desde este entorno.

Comparación actual, límites y prioridades: [docs/COMPETITION.md](docs/COMPETITION.md).

AliceLabs LLC — Edison Flores. Licencia: [AL-1.0](LICENSE-AL-1.0).
