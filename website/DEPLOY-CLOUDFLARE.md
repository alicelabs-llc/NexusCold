# Publicación estática en Cloudflare

La web pública se sirve en Cloudflare Workers mediante Sites. El dominio puede
seguir registrado en Hostinger; el registrador y el alojamiento no tienen que
ser el mismo proveedor. El proyecto de escritorio y Ollama siguen ejecutándose
en el equipo del usuario o en su propio servidor.

Sitio preparado: https://techdigital-prospect.toastyrice32.chatgpt.site/
Dominio personalizado previsto: `prospect.techdigital.site`.
El estado de publicación y del dominio debe verificarse en el proveedor; esta
guía por sí sola no demuestra que el DNS esté activo.

## Construir para cualquier alojamiento estático

```bash
python -m pip install -r website/requirements-build.txt
node --test website/tests/*.test.mjs
python -m unittest discover -s website/tests -p 'test_*.py'
python website/build.py --origin https://techdigital-prospect.toastyrice32.chatgpt.site/
python website/check.py
```

Publicar **el contenido de `website/dist/prospect/` en la raíz del sitio**.
Los enlaces internos son relativos. `--origin` (o `SITE_ORIGIN`) configura las
URL absolutas de canonical, Open Graph, sitemap y manifiesto de agentes.
Confirmar los cambios de código en Git antes de construir: la descarga de
evaluación solo incluye el contenido del commit y nunca archivos privados no
versionados. La CI genera un artefacto descargable `techdigital-prospect-static`.

Para Cloudflare Pages con integración Git, usar el mismo comando de build y
`website/dist/prospect` como directorio de salida. `_headers` conserva las
cabeceras de seguridad en Cloudflare; `.htaccess` se utiliza solo en Apache.

## Conectar Hostinger

1. Registrar primero `prospect.techdigital.site` como dominio del alojamiento.
2. Añadir los registros exactos devueltos por el proveedor (CNAME y validación
   de propiedad/TLS) en el DNS autoritativo de `techdigital.site`.
3. Esperar estado activo y certificado válido, comprobar páginas, módulos JS y
   descargas por HTTPS. Después reconstruir con
   `--origin https://prospect.techdigital.site/` y volver a publicar.

No cambiar el registro raíz, sus nameservers ni sus registros MX para añadir
este subdominio: el marketplace de `techdigital.site` sigue teniendo su propio
alojamiento. DNS no puede apuntar una carpeta como `/prospect/` a otro servidor;
para esa ruta se necesita una regla de proxy en el alojamiento de la raíz.

## Alternativa GitHub Pages

Este mismo directorio se puede publicar con GitHub Pages después de habilitarlo
en Settings → Pages. Construir con
`--origin https://alicelabs-llc.github.io/NexusCold/` y subir ese directorio usando
`actions/upload-pages-artifact` y `actions/deploy-pages`, con permisos
`pages: write` e `id-token: write`. Para un dominio propio, configurarlo primero
en Pages y después añadir CNAME `prospect` → `alicelabs-llc.github.io` en el DNS.
El CNAME no incluye el nombre del repositorio. No se considera publicada esta
alternativa hasta completar y verificar su despliegue.
