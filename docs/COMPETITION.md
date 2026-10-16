# Competencia y dirección de producto

Investigación: 15 de octubre de 2026. Fuentes oficiales; las capacidades descritas por proveedores no son un benchmark independiente. No afirmamos superioridad global ni mayor exactitud sin una muestra etiquetada y una prueba comparativa reproducible.

| Producto | Referencia verificada | Respuesta de NexusCold 6.2 | Brecha pendiente |
| --- | --- | --- | --- |
| Hunter | Fuentes/fechas, estados de verificación y diferenciación entre correos encontrados e inferidos | Evidencia URL, DNS/MX y RCPT SMTP con control catch-all; respuestas bloqueadas como unknown | Verificación a escala desde IPs con reputación, actualizaciones de fuentes, benchmark de precisión |
| Apollo | Enriquecimiento CSV, informes de duplicados y completitud, sincronización CRM | Revisión CSV local sin cuenta, duplicados marcados sin borrar filas, resumen JSON | Base de contactos, matching de entidades, CRM |
| Clay | Waterfall secuencial que consulta proveedores posteriores solo cuando falla el anterior | Se conserva el motor multifuente existente; revisión local previa sin claves | Waterfall configurable, presupuesto por campo, proveedores autorizados, métricas de cobertura |
| Smartlead | Bandeja unificada, clasificación de respuestas y operaciones de correo | Módulo SMTP de prueba sin métricas inventadas ni destinatarios generados | OAuth, IMAP, secuencias, supresión, respuesta/opt-out y alertas reales |
| lemlist | Secuencias multicanal y herramientas de entregabilidad | Foco actual en calidad del archivo y control local | Canales adicionales, monitorización DNS y gestión de conversaciones |

## Diferenciación propuesta

Herramienta de escritorio para agencias pequeñas que quieren preparar y revisar sus propios archivos con instalación sencilla y sin crear una cuenta SaaS. El modo offline no envía datos; el enriquecimiento web sí consulta buscadores y registros. Esta es una propuesta de posicionamiento, no una ventaja exclusiva demostrada frente a todos los proveedores.

Prioridades siguientes, fuera de esta entrega:

1. Diagnóstico SPF/DMARC del remitente y medición real de entregabilidad. MX y comprobación de destinatarios ya implementados; no confundir SMTP aceptado con entrega garantizada.
2. Matching de entidad con nombre, país y web; evidencia por campo y detección de conflictos entre fuentes.
3. Adaptadores de fuentes mantenidos, con pruebas de contrato y disponibilidad; eliminar conectores que dependan de endpoints obsoletos.
4. Waterfall configurable, elección real de fuentes en interfaz y reanudación de trabajos persistentes.
5. OAuth y bandeja de respuestas con bajas/supresión antes de ofrecer campañas comerciales.
6. Benchmark público con empresas EN/ES/LATAM etiquetadas: precisión, cobertura, falsos positivos, latencia y coste por registro útil.

## Fuentes

- Hunter, datos y procedencia: https://hunter.io/transparency/our-data
- Hunter, estados y score: https://help.hunter.io/en/articles/1830792-domain-search-find-emails-from-companies
- Hunter, verificaciones técnicas: https://help.hunter.io/en/articles/1935168-what-checks-are-performed-on-an-email-with-the-email-verifier
- Apollo, enriquecimiento: https://www.apollo.io/product/data-enrichment
- Apollo, informes CSV: https://knowledge.apollo.io/hc/en-us/articles/4410613330701-CSV-Enrichment-Reports-Overview
- Clay, waterfall: https://www.clay.com/guides/waterfall-enrichment
- Smartlead, bandeja unificada: https://www.smartlead.ai/unified-inbox
- lemlist, producto: https://www.lemlist.com/

## Referencias técnicas de la verificación

- SMTP y MX implícito: https://www.rfc-editor.org/rfc/rfc5321.html
- Null MX: https://www.rfc-editor.org/rfc/rfc7505.html
- Resolver asíncrono: https://dnspython.readthedocs.io/en/stable/async-resolver-functions.html
