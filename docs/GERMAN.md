# Germán · NexusCold 6.3

Operador integrado: revisión local, mapeo EN/ES, cascada web, buzones, publicación SPF/DMARC y trabajos reanudables. Todas esas operaciones funcionan sin modelo. El chat opcional usa Ollama local o el gateway que puedes alojar en tu servidor.

## Escritorio

1. `python -m pip install -r requirements.txt`.
2. Abre `python ALICELABS_EXTRACTOR_GUI.py` o `ALICELABS_NEXUS_6.3.bat` en Windows.
3. Pulsa **Germán · Operador local**, abre un CSV UTF-8 y revisa/corrige el mapeo propuesto.
4. Elige `offline`, `mx`, `smtp`, `enrich` o `enrich_smtp`. Los modos con red requieren activar su autorización explícita.
5. Elige fuentes web. La cascada para al encontrar una web útil; no garantiza matching de identidad. No usa registros que requieren claves en los trabajos nuevos.
6. Ejecuta y elige el CSV de salida. **Detener** guarda las filas terminadas. **Reanudar** requiere la misma entrada, mapeo, modo, fuentes y salida. No repite las filas guardadas.

Límite: CSV de hasta 50 MiB, procesamiento secuencial por fila. La interfaz original conserva soporte XLSX. No se admite escribir el mismo checkpoint desde varios procesos.

## Modelo gratuito y almacenamiento

Instala [Ollama](https://ollama.com/download) en el equipo que ejecutará el modelo. Descárgalo una vez:

```bash
ollama pull qwen3.5:4b
ollama list
```

Configura `OLLAMA_NO_CLOUD=1` en el **servidor Ollama** y reinícialo. En Windows usa una variable de usuario y reinicia Ollama; en Linux configúrala en su servicio. El panel usa `http://127.0.0.1:11434`, sin cuenta ni token. Los pesos quedan en el almacenamiento que administra Ollama, fuera del repositorio. La descarga requiere internet; la inferencia posterior se ejecuta en ese equipo.

Investigación del 20 de octubre de 2026:

| Opción | Uso | Recursos de planificación |
| --- | --- | --- |
| Qwen3.5 4B + Ollama | Predeterminado, descargable, Apache 2.0 | Pesos de varios GB; empezar con 8–12 GB RAM y contexto 4096 |
| Qwen3.5 0.8B/2B | Equipos pequeños; evaluar calidad y licencia del artefacto elegido | Menor consumo, modelo configurable en el panel |
| Qwen3.5 9B + Ollama | Evaluar en servidor más potente; ficha Apache 2.0 | Empezar con 16 GB RAM disponibles; GPU opcional para velocidad |
| IBM Granite 4.2 3B | Alternativa descargable Apache 2.0; su ficha incluye español | Artefacto Q4 de unos 2.2 GB; probar calidad/latencia antes de sustituir el predeterminado |
| Microsoft Phi-4-mini-instruct | Alternativa descargable con licencia MIT | Requiere instalar el artefacto compatible y evaluar el runtime; no validado en este cliente |
| Cloudflare Workers AI | Alternativa gestionada futura, no integrada | Cuota gratis de 10,000 neuronas/día; cuenta y configuración de servidor |

La RAM es estimación, no mínimo certificado. No se midió precisión ni velocidad de estos modelos en NexusCold. Los tags pueden cambiar: registra el digest al validar. El modelo no cobra por petición local; electricidad, hardware y servidor alquilado sí tienen costo. La licencia de NexusCold sigue siendo AL-1.0. Conserva avisos/licencias de los modelos que redistribuyas.

Fuentes oficiales:
- https://ollama.com/library/qwen3.5:4b
- https://ollama.com/library/qwen3.5:9b
- https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE
- https://docs.ollama.com/faq
- https://docs.ollama.com/api/introduction
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/docker
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://ollama.com/library/granite4.2:3b
- https://huggingface.co/microsoft/Phi-4-mini-instruct/blob/main/LICENSE

## CLI

```bash
# Sin red
python german_cli.py review empresas.csv
python german_cli.py run empresas.csv --output revisadas.csv

# SMTP no envía mensajes
python german_cli.py run empresas.csv --output verificados.csv --mode smtp --allow-network

# Cascada y reanudación con la MISMA configuración
python german_cli.py run empresas.csv --output salida.csv --mode enrich_smtp --allow-network --sources ddg bing
python german_cli.py run empresas.csv --output salida.csv --mode enrich_smtp --allow-network --sources ddg bing --resume

# Mapeo personalizado
python german_cli.py run empresas.csv --output salida2.csv --mapping '{"company_name":"Cliente","email":"Contacto"}'

python german_cli.py domain empresa.com --allow-network
python german_cli.py ask revisadas.csv "¿Qué debo corregir antes de verificar?"
```

Germán ejecuta las herramientas enumeradas mediante controles explícitos; el modelo solo aconseja. No ejecuta shell, código ni instrucciones del CSV. Al chat solo se envían métricas numéricas/estados admitidos y tu pregunta. Si incluyes datos personales en la pregunta, sí se transmitirán al backend que elegiste. No se envían filas, contactos ni páginas web al modelo automáticamente. Sus respuestas pueden ser incorrectas y no modifican archivos.

## Privacidad y significado de resultados

- Checkpoint `salida.csv.german` cifrado con Fernet; clave separada `salida.csv.german.key`. Conserva ambos. Quien accede a ambos puede descifrarlo; no hay contraseña de usuario. En Unix se crean con permisos privados; en Windows protege la carpeta con ACL/cifrado del dispositivo. No subas ninguno a git.
- Entrada/salida CSV son archivos normales, protegidos contra fórmulas al exportar. No se anuncian como cifrados.
- Los trabajos nuevos de Germán desactivan la caché heredada de enriquecimiento. La interfaz original aún puede usar caché sin cifrar; los archivos anteriores no se migran ni borran automáticamente.
- Reanudar rechaza entrada/configuración distinta. Una consulta que terminó antes de guardar podría repetirse si cae el proceso: no es garantía de ejecución única de efectos externos.
- El checkpoint es un diario de registros cifrados: añade una fila confirmada sin reescribir las anteriores. Al reanudar descarta solamente una última escritura incompleta y valida la secuencia y autenticidad de las filas confirmadas.
- `ENRICHED_EVIDENCE` incluye `_fields` (fuente por campo) y `_conflicts` (observaciones distintas), además de las URLs que ya aportaba el scraper para correos. Conserva el valor suministrado. No es identidad certificada ni evidencia documental completa.
- SPF informa publicación, no autorización de una IP. DMARC consulta el nombre exacto: no calcula herencia del dominio organizacional, alineamiento, porcentaje efectivo o validez completa de todas sus etiquetas. DKIM requiere selector. Una política ausente en un subdominio podría heredarse.
- Las consultas web transmiten nombre/ubicación a fuentes externas. SMTP aceptado no garantiza entrega; `unknown` es inconcluso. No se añaden campañas, IMAP, OAuth, CRM ni bajas en esta versión.

## Hosting con dominio propio

Recomendación: tu servidor Linux o PC con Docker y memoria suficiente. El modelo queda en el volumen `models`, Caddy gestiona HTTPS y solo el gateway publica chat autenticado. Ollama no publica el puerto 11434. Usa un subdominio que ya controles; no es necesario comprar otro.

Desde la raíz del repo:

```bash
cp deploy/.env.example deploy/.env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Edita `deploy/.env`: `GERMAN_DOMAIN` con el nombre real cuyo DNS A/AAAA apuntaste al servidor; `NEXUS_GERMAN_TOKEN` con el secreto; modelo elegido en `NEXUS_GERMAN_MODEL`. Fija una versión/digest probado en `OLLAMA_IMAGE`: `latest` es solo arranque y no es reproducible. Permite puertos 80/443.

```bash
docker compose --env-file deploy/.env -f deploy/compose.yml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yml up -d --build
docker compose --env-file deploy/.env -f deploy/compose.yml exec ollama ollama pull qwen3.5:4b
docker compose --env-file deploy/.env -f deploy/compose.yml exec ollama ollama list
```

Para NVIDIA instala NVIDIA Container Toolkit y añade `-f deploy/compose.gpu.yml` a esos comandos. En el cliente configura el mismo secreto en `NEXUS_GERMAN_TOKEN`, usa tu origen HTTPS en el panel y activa autorización remota. CLI (sustituye el host):

```bash
python german_cli.py ask revisadas.csv "Resume pendientes" --endpoint https://TU_DOMINIO --allow-remote
```

El gateway fija modelo/contexto/salida, limita dos peticiones activas y 30/minuto para el token compartido. HTTP máximo 16 KiB. No habilita herramientas, imágenes, administración de modelos ni redirecciones de inferencia; no guarda conversaciones ni logs de acceso. Quien tiene el token usa esa cuota. Para clientes separados hace falta autenticación y cuotas por tenant. `/health` indica vida del gateway, no que el modelo esté instalado: verifica un chat real antes de publicar el servicio.

## Validación de esta entrega

Pruebas offline con HTTP/DNS controlados, CSV, interrupción, cifrado y reanudación. Este entorno no tiene Ollama, Docker ni pantalla: no se validaron inferencia real, Compose ejecutándose, GUI visual ni binario Windows. No se desplegó un servidor ni se modificó DNS. La guía y configuración quedan preparadas para validar en el entorno de destino.
