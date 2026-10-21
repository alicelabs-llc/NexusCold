# TechDigital Prospect · publicación en techdigital.site

Destino solicitado: Hostinger. Ruta preparada: **https://techdigital.site/prospect/**. El dominio raíz ya sirve un marketplace con pagos; este paquete solo añade la carpeta `prospect/`. No cambies su index, checkout, archivos de configuración raíz ni DNS para añadir la landing.

## Paquete

Desde la raíz del repo:

El empaquetado público requiere un checkout Git con los cambios destinados a publicación ya confirmados en un commit y sin modificaciones versionadas pendientes. Solo se incluyen archivos del commit, nunca archivos privados no versionados de la carpeta de trabajo. No existe un fallback de barrido del disco si falta Git.

```bash
python -m pip install -r website/requirements-build.txt
node --test website/tests/*.test.mjs
python website/build.py --zip TechDigital-Prospect-Hostinger.zip
python website/check.py
```

El ZIP contiene únicamente `prospect/`, con 22 páginas ES/EN, assets propios, `agent.json`, `llms.txt`, sitemap, políticas, fuente de evaluación y checksum. Incluye `.htaccess` limitado a esa carpeta para Apache/LiteSpeed. No incluye claves ni necesita PHP, base de datos, Node o Python en el hosting para servir la web.

## Antes de subir

1. Verifica en hPanel que **techdigital.site tiene un servicio web asociado**, no solo registro de dominio. El sitio público actual puede estar servido por infraestructura distinta del registrador: comprueba el hosting que responde antes de subir archivos.
2. Conserva una copia recuperable del sitio actual. Comprueba si ya existe una carpeta `prospect/` y revisa su contenido antes de reemplazarla.
3. Revisa las políticas, los contactos corporativos y la licencia. La identidad AliceLabs LLC está respaldada por la licencia del repositorio; esta entrega no verificó actas societarias, domicilio registral o disponibilidad de marca.
4. Si solo hay dominio o el DNS apunta a otro proveedor, se necesita acceso al alojamiento real. No migres ni compres un plan sin confirmar alcance y costo.

## Publicar

En el administrador de archivos del sitio correcto, extrae el ZIP dentro del directorio de documentos de techdigital.site (habitualmente `public_html`). Debe quedar `public_html/prospect/index.html`, no `public_html/prospect/prospect/index.html`. Conserva todos los archivos de la raíz. Revisa que `.htaccess` se haya incluido y que el servidor lo acepte; si muestra 500, consulta los logs y adapta las directivas admitidas sin desactivar protecciones globales.

Abre `/prospect/`, `/prospect/en/`, las páginas legales, el ejemplo CSV y la descarga de evaluación. Prueba en móvil y escritorio: menú, selección de archivo, cambio de mapeo, exportación y consentimiento de licencia. Confirma HTTPS, MIME JavaScript para `.mjs`, sin overflow de página y cabeceras de seguridad. Sirve la web con HTTP(S); el módulo ES no debe evaluarse abriendo el archivo directamente con file://.

`prospect/sitemap.xml` corresponde solo al producto. Si el dominio ya tiene sitemap o robots.txt, integra la referencia de forma aditiva tras revisar la configuración existente; este paquete no reemplaza esos archivos raíz.

## Qué no se despliega con la landing

El revisor web solo hace calidad offline. La aplicación Python, SMTP y el modelo Ollama no se ejecutan dentro del hosting compartido estático. El gateway de chat requiere un VPS o equipo con Docker y memoria suficiente, y un endpoint separado con autenticación. No pongas su token en el JavaScript público. Las instrucciones están en `docs/GERMAN.md` y `deploy/`.

## Acceso seguro

Se observó la pantalla de login de Hostinger, sin una sesión iniciada disponible. Para publicar, usa el acceso seguro de navegador solicitado por ChatGPT. Nunca pegues contraseñas, códigos o tokens en el chat. No se ha afirmado que la landing esté publicada antes de verificar el resultado en el dominio.
