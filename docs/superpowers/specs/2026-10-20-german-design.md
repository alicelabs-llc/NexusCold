# Germán: operador local para NexusCold 6.3

## Objetivo y autorización
El usuario autorizó implementar las mejoras propuestas y buscar un modelo gratuito que pueda alojarse en su infraestructura. Se conserva la aplicación Python de escritorio. No se presupone acceso SSH, GPU, DNS ni un servidor conectado.

## Diseño
Germán inspecciona archivos, propone mapeo de columnas, resume resultados y ejecuta un conjunto cerrado de operaciones (revisión local, MX, SMTP y enriquecimiento). Las consultas de red se activan mediante controles explícitos; el texto del modelo nunca ejecuta herramientas, shell ni código. Los comandos reales funcionan sin modelo. El chat usa Ollama local de forma opcional; el acceso remoto requiere HTTPS, token y consentimiento explícito, y solo recibe métricas agregadas más la pregunta escrita por el usuario.

Modelo recomendado: Qwen3.5 4B, configurable; alternativas 0.8B/2B para recursos pequeños y 9B con más memoria. No se descargan pesos automáticamente ni se afirma haber probado inferencia sin runtime instalado. El software y los pesos tienen licencias distintas. La licencia gratuita no hace gratuito el cómputo alquilado.

## Componentes
- `german_agent.py`: análisis determinista, mapeo EN/ES, recomendaciones, plan cerrado y cliente Ollama opcional con límites de tiempo y respuesta.
- `german_jobs.py`: CSV, validación de mapeo, ejecución secuencial por registro, checkpoint cifrado y reanudación ligada al hash de entrada y configuración. Exportación atómica y protegida para Excel.
- `domain_auth.py`: presencia SPF y política DMARC publicada en el nombre exacto consultado; no evalúa autorización de IP ni descubre DKIM sin selector. Ausencia, duplicados, errores DNS y políticas débiles se distinguen. No afirma salud completa del dominio.
- `german_cli.py`: revisar, ejecutar, reanudar, preguntar y diagnosticar dominio.
- `german_panel.py`: panel de escritorio conectado al mismo motor, sin bloquear Tk.
- `german_gateway.py` y `deploy/`: proxy autenticado mínimo, límites de tamaño/concurrencia, modelo fijado por servidor y Ollama interno sin puerto público. Caddy ofrece HTTPS con dominio configurable.

## Datos
Los checkpoints se cifran con Fernet; la clave local se crea con permisos privados y nunca entra a git. La pérdida de esa clave impide reanudar. La caché heredada de enriquecimiento sigue documentada como texto claro; se puede desactivar para trabajos privados. CSV/XLSX exportados no se anuncian como cifrados. El LLM no recibe filas, nombres de columnas personalizados, contactos ni páginas web; la pregunta del usuario sí se transmite al backend que eligió.

## Enriquecimiento
Añadir modo cascada de descubrimiento de web y lista explícita de fuentes. Parar al encontrar la primera web. Registrar qué fuente aporta cada campo y conflictos observados sin sobreescribir valores suministrados. Mantener el modo anterior para compatibilidad; los nuevos trabajos usan cascada y omiten conectores heredados que requieren claves.

## Verificación y entrega
Pruebas offline reproducibles para mapeo, salidas, inyección, consentimiento remoto, estados DNS, cifrado, reanudación, aislamiento de configuración, protocolo HTTP y gateway. Ejecutar suite completa y compilación. Preparar Docker Compose y guía por dominio; desplegar solo si hay infraestructura accesible y configuración real. Entregar rama/PR, sin afirmar publicación o benchmark no realizado.
