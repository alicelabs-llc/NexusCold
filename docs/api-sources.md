# APIs para TechDigital · selección del catálogo público

AliceLabs LLC · revisión del 24 de octubre de 2026.

Catálogo revisado: https://github.com/public-apis/public-apis . Snapshot Git
82e763edc4919e2cb13ce8c8c57a33bc73ff4caf: 2.225 entradas de tabla, 2.217 URLs
únicas. Es un directorio comunitario, no un proveedor de datos ni una garantía
de gratuidad, acceso comercial o funcionamiento actual. Los metadatos Auth/CORS
se contrastaron con documentación oficial y peticiones reales para los adaptadores.

## Del catálogo a funciones concretas

| Entrada del catálogo | Utilidad para listas | Decisión y estado |
|---|---|---|
| Crossref Metadata Search | Identificar editoriales y ubicación declarada | Conectada, pública sin clave; no pretende encontrar emails |
| Socrata | Directorios oficiales municipales | Conectado el dataset NYC DOHMH de establecimientos: nombre, teléfono y dirección; excluye inspecciones y datos ajenos al contacto |
| Pick an Agency | Agencias de marketing y sus sitios, servicios y tamaño reportado | Conectada, respuesta real sin clave; atribución CC BY 4.0 con enlace al perfil |
| Microlink.io | Descripción y metadata de una web conocida | Útil como complemento, no activado en este cambio. Su pricing actual ofrece cuota de 100/mes y registro de clave; una respuesta pública puntual no demuestra acceso ilimitado |
| Hunter | Correos profesionales de un dominio y verificación | Útil con cuenta, clave y créditos. No se obtuvo clave ni se activó consumo |
| OpenCorporates | Entidades legales de múltiples países | Útil mediante acceso/licencia acordados; no se anuncia acceso comercial gratuito universal |
| UK Companies House | Empresas, estado y registros UK | Útil con registro de aplicación/clave. El catálogo dice OAuth, pero el acceso público de datos documenta API key con Basic auth |
| Domainsdb.info / DomainDb Info | Dominios candidatos por palabras | Útil para descubrimiento con servidor; no acredita que un dominio sea de la empresa buscada. No activada como fuente de contactos |
| OpenStreetMap | Comercios y contactos publicados en mapas | Útil con extractos o instancia propia para volumen; no se usa un servidor comunitario como backend de miles de consultas globales |
| Host.io / SecurityTrails | Dominios relacionados y contexto técnico | Requieren cuenta/clave y límites; no activados |
| Crustdata / PeopleSearch / ORB | Datos corporativos o profesionales | Candidatos comerciales sujetos a acceso, licencia y precio; no incorporados como supuestas APIs gratuitas |
| Clearbit Logo | Logos de empresas | No enriquece contactos; no se cuenta como fuente de leads |
| APIs de email temporal/envío | Calidad de dominio o envío | No descubren empresas; no se agregan para inflar el número de fuentes |

No se hicieron registros, compras, envíos de correos ni altas de suscripciones.
No se envió el CSV completo a estas plataformas. La revisión del catálogo no
implica que todas sus entradas hayan sido probadas o integradas.

## Fuentes oficiales adicionales que sí amplían la cobertura

Se implementaron también consultas públicas a France Recherche d’Entreprises,
Brønnøysund (Noruega), PRH/YTJ (Finlandia), ROR, BrasilAPI CNPJ, FDIC y la Food
Standards Agency británica. Son fuentes de alcance distinto: registros nacionales,
organizaciones de investigación, bancos, agencias, restaurantes o empresas con un
identificador dado. No equivalen a una base mundial de correos personales.

Las siete primeras fuentes y los adaptadores Crossref/Socrata/Agency se comprobaron
con respuestas JSON reales y CORS público. Los resultados y fallos del navegador
se muestran por fuente. CNPJ exige una columna con el identificador, sin generarlo.
Los contactos solo se toman de campos corporativos publicados. No se extraen
nombres de directivos, socios, fechas de nacimiento, responsables sanitarios ni
correos de autoridades reguladoras como si fueran contactos de la empresa.

CMS NPI-2 y SEC también tienen adaptadores con servidor y autenticación del
operador; aparecen desactivados sin un servicio conectado. NPI permite consultas
solo de organizaciones; SEC devuelve identidad/CIK/ticker y cachea el catálogo,
sin inventar un sitio o presentar cotización como prueba de vigencia societaria.

## Documentación y límites

- Crossref: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Socrata NYC: https://dev.socrata.com/foundry/data.cityofnewyork.us/43nn-pn8j
- Pick an Agency: https://www.pickanagency.com/developers
- Microlink: https://microlink.io/pricing
- Hunter: https://hunter.io/api-documentation
- OpenCorporates: https://api.opencorporates.com/documentation/API-Reference
- Companies House: https://developer.company-information.service.gov.uk/
- France: https://recherche-entreprises.api.gouv.fr/docs/
- Brønnøysund: https://www.brreg.no/en/use-of-data-from-the-bronnoysund-register-centre/datasets-and-api/data-about-organisations/
- PRH: https://avoindata.prh.fi/en/ytj/swagger-ui
- ROR: https://ror.readme.io/docs/rest-api y https://ror.readme.io/docs/client-id
- BrasilAPI: https://brasilapi.com.br/docs
- FDIC: https://api.fdic.gov/banks/docs/
- FSA: https://api.ratings.food.gov.uk/help
- CMS NPI: https://npiregistry.cms.hhs.gov/api-page
- SEC: https://www.sec.gov/about/developer-resources

No se usan proxies públicos, credenciales compartidas ni evasión de cuotas.
El procesador mantiene caché en memoria, espacia peticiones por fuente y pausa
un proveedor que responda 429. El volumen útil depende de sus políticas, estado y
cobertura. Usar varias APIs no garantiza encontrar todos los campos de cada fila.
