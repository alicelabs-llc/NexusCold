# Validación NexusCold 6.3 · 20 octubre 2026

## Evidencia
- Base: `9318c07`; rama `feat/german-local-agent`.
- `python -m pytest -q`: 81 passed.
- `python -m unittest discover -q`: 81 tests, OK.
- `python -m compileall -q .`: sin errores.
- `git diff --check`: sin errores.
- Commit local de implementación: `2058fbf`. La revisión automática bloqueó el push al repositorio público por falta de autorización explícita de publicación; no se abrió PR ni se reintentó por otra vía.
- Humo CLI: mapeo Empresa/Correo/Ciudad, revisión, ejecución offline y reanudación, contacto ausente del checkpoint cifrado; módulos GUI/gateway importan.
- HTTP real controlado: cliente -> gateway autenticado -> backend simulado; fallos de protocolo, tamaño, token y tasa. No es un test de un LLM real.
- DNS controlado: publicación SPF, TXT dividido, DMARC monitorización/rechazo, duplicados, ausencia y timeout.

## Revisión independiente
Revisión por otro agente: tres defectos P2 encontrados y corregidos con regresiones RED→GREEN:
1. El resumen perdía mapeos personalizados: ahora recibe el mapeo confirmado.
2. Calidad/verificación podían usar correos distintos al reimportar resultados: un mapeo seleccionado gobierna ambos; selección explícita tiene prioridad.
3. Checkpoint crecía con escrituras cuadráticas: diario cifrado por registro con confirmación por salto de línea. Reanudación valida autenticidad y secuencia y descarta una última escritura incompleta.

Humo de rendimiento offline del diario, entorno de desarrollo: 1,000 filas ~0.385s y 249,261 bytes; 2,000 ~0.680s y 498,261 bytes. No es benchmark comercial de red, precisión ni inferencia.

## Decisiones
- Herramientas deterministas y chat asesor desacoplados; el modelo no ejecuta código ni decide permisos. Costo de esta decisión: las acciones se eligen con controles/modos explícitos, no en lenguaje natural libre.
- Los trabajos nuevos desactivan la caché heredada sin cifrar; no migran archivos anteriores. Costo: no aprovechan esa caché para acelerar consultas repetidas.
- Sin infraestructura online identificada: se prepara despliegue, sin afirmar publicación. Equipo remoto disponible en el inventario: HP offline.
- Ollama/Docker/pantalla no disponibles aquí: inferencia real, contenedores, certificados, revisión visual y binario Windows quedan para el equipo de destino.

## Observaciones menores diferidas
- La carga/revisión inicial del CSV en el panel es síncrona y puede pausar la interfaz con archivos grandes; también conviene presentar `csv.Error` como diálogo. Los trabajos posteriores sí usan un hilo y una cola de UI.
- Una pregunta de 2,000 caracteres no BMP puede superar los 16 KiB del gateway por serialización Unicode. El servidor rechaza con 413; acorta la pregunta. No afecta trabajos locales ni filtra datos.

## Fuera del alcance validado
No se prueban entrega real de mensajes, matching certificado de entidades, cobertura global de fuentes, campañas, OAuth/IMAP, supresión/bajas, CRM ni multitenancy. No se afirma superioridad de precisión sobre competidores. Consulta `GERMAN.md` para instalación, modelos, costos y hosting.
