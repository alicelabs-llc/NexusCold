# TechDigital Prospect 6.4 · validación de entrega

Fecha: 20 de octubre de 2026. Base funcional: versión Germán del PR #3, commit `56553c3743f2de1eb1cbfca02d9f19485a032aca`.

- 83 pruebas Python pasan, incluidas dos regresiones del empaquetado público.
- 7 pruebas Node pasan: parser CSV, comillas, saltos de línea, delimitadores, columnas, mapeo, duplicados, calidad, fórmulas y texto no confiable.
- 22 páginas HTML ES/EN generadas; rutas, anchors, assets, autor corporativo, viewport, canonical y manifiesto verificados.
- Revisión independiente: el revisor web no utiliza llamadas de red, almacenamiento persistente, tracking ni inserción de HTML derivado de celdas. Las políticas separan uso del revisor alojado y licencia AL-1.0 del escritorio.
- Un defecto importante de empaquetado fue reproducido con un archivo privado ficticio y corregido: la descarga ahora usa blobs del commit Git, excluye archivos privados no versionados y falla sin inventario verificable. La compilación de releases rechaza modificaciones versionadas pendientes.
- Correcciones adicionales: lecturas de archivos obsoletas no reemplazan una selección más reciente, checksum con wrap y cabecera móvil compacta.
- Compilación Python, sintaxis JavaScript y diff sin errores.

## Límites

No hubo una capability `control-browser` disponible para la previsualización de Sites; su skill prohíbe improvisar otra ruta de preview. No se instaló un navegador ni se afirma validación visual real de los breakpoints. El diseño contiene layouts para 1100/800/480 px, navegación móvil, foco visible, soporte de movimiento reducido y tablas con scroll interno; debe verificarse en dispositivos de destino.

Se observó la pantalla de login de Hostinger, sin sesión iniciada. El paquete de despliegue añade `/prospect/` y conserva la raíz del marketplace. No se afirma publicación, configuración DNS ni un plan de hosting verificado hasta completar ese acceso y comprobar el resultado real.

Las páginas legales describen el producto actual y preservan derechos imperativos. No equivalen a revisión profesional de todas las jurisdicciones, certificación de cumplimiento ni inmunidad frente a reclamaciones. La identidad societaria se toma de la licencia publicada; no se ha verificado registro de marca o documentación registral de la entidad.
