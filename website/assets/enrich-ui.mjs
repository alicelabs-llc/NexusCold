import {domainOf,searchCompanies,searchLegalEntities,entityDetails,dnsProfile,exportEnrichment} from './enrich.mjs';
export function mountEnrichment({container,getData,language='es'}){
 const en=language==='en';const t=(es,english)=>en?english:es;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const panel=el('section');panel.className='enrichment-panel';panel.append(el('h3',t('Enriquecer desde fuentes públicas','Enrich from public sources')),el('p',t('Busca empresas en Wikidata y GLEIF, confirma su identidad y consulta MX, SPF y DMARC. Los correos y teléfonos solo se incluyen cuando la fuente los publica.','Find companies in Wikidata and GLEIF, confirm identity and query MX, SPF and DMARC. Emails and phones are included only when published by the source.')));
 const notice=el('label');notice.className='network-consent';const consent=el('input');consent.type='checkbox';notice.append(consent,document.createTextNode(t(' Autorizo enviar nombres de empresas a Wikidata y GLEIF, y dominios a Google Public DNS. El CSV completo no se sube. Las coincidencias requieren revisión.',' I authorize sending company names to Wikidata and GLEIF, and domains to Google Public DNS. The full CSV is not uploaded. Matches require review.')));panel.append(notice);
 const tools=el('div');tools.className='enrichment-actions';const countLabel=el('label',t('Filas a procesar (máx. 100) ','Rows to process (max. 100) '));const count=el('input');count.type='number';count.min='1';count.max='100';count.value='25';countLabel.append(count);
 const run=el('button',t('Enriquecer lista ↗','Enrich list ↗'));run.type='button';run.className='button primary';const stop=el('button',t('Detener','Stop'));stop.type='button';stop.className='button';stop.disabled=true;const download=el('button',t('Exportar enriquecimiento ↓','Export enrichment ↓'));download.type='button';download.className='button';download.disabled=true;tools.append(countLabel,run,stop,download);panel.append(tools);
 const details=el('details');details.append(el('summary',t('Extracción de sitios web: conectar mi servidor','Website extraction: connect my server')));
 details.append(el('p',t('El rastreador Python incluido extrae contactos publicados del sitio confirmado, respeta robots.txt y limita las páginas. Necesita un servidor propio; GitHub Pages no ejecuta Python. La URL y la clave se conservan solo en esta pestaña.','The included Python crawler extracts published contacts from the confirmed site, respects robots.txt and limits pages. It requires your own server; GitHub Pages cannot run Python. URL and key stay in this tab only.')));
 const endpointLabel=el('label',t('URL HTTPS del servicio ','Service HTTPS URL ')),endpoint=el('input');endpoint.type='url';endpoint.placeholder='https://api.example.com';endpointLabel.append(endpoint);
 const tokenLabel=el('label',t('Clave de acceso ','Access token ')),token=el('input');token.type='password';token.autocomplete='off';tokenLabel.append(token);details.append(endpointLabel,tokenLabel);panel.append(details);
 const progress=el('p',t('Carga un CSV arriba o usa un ejemplo real de empresas.','Load a CSV above or use a real company sample.'));progress.setAttribute('role','status');progress.setAttribute('aria-live','polite');panel.append(progress);
 const sample=el('button',t('Cargar empresas reales de ejemplo','Load real company sample'));sample.className='text-button';sample.type='button';panel.append(sample);
 const rows=el('div');rows.className='enrichment-rows';panel.append(rows);container.append(panel);
 let results=[],controller=null,generation=0,snapshot=null,running=false;
 const abort=()=>{generation++;controller?.abort();controller=null;running=false;run.disabled=false;stop.disabled=true;};
 const reset=()=>{abort();results=[];snapshot=null;rows.replaceChildren();download.disabled=true;progress.textContent=t('Listo para enriquecer el archivo actual.','Ready to enrich the current file.');};
 stop.addEventListener('click',()=>{abort();progress.textContent=t('Detenido. Puedes exportar los resultados completados.','Stopped. You can export completed results.');});
 async function scrape(website,signal){
 if(!endpoint.value.trim())return null;const u=new URL(endpoint.value.trim());if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||u.pathname!=='/')throw Error(t('Usa un origen HTTPS sin ruta.','Use an HTTPS origin without a path.'));if(token.value.length<32)throw Error(t('La clave del servicio debe tener al menos 32 caracteres.','Service token must have at least 32 characters.'));
 const r=await fetch(u.origin+'/api/enrich',{method:'POST',credentials:'omit',referrerPolicy:'no-referrer',signal:AbortSignal.any([signal,AbortSignal.timeout(45000)]),headers:{'Content-Type':'application/json',Authorization:'Bearer '+token.value},body:JSON.stringify({website})});if(!r.ok)throw Error('Crawler HTTP_'+r.status);const text=await r.text();if(text.length>100000)throw Error('RESPONSE_LIMIT');return JSON.parse(text);
 }
 function rowView(index){const article=el('article');article.className='enrichment-row';const title=el('strong',(index+1)+'. '+(snapshot.rows[index][snapshot.mapping.company]||snapshot.rows[index][snapshot.mapping.website]||'—'));const state=el('span',t('Pendiente','Pending'));const info=el('p');const options=el('div');options.className='enrichment-candidates';article.append(title,state,info,options);rows.append(article);return{article,state,info,options};}
 function display(view,result){view.state.textContent=result.status;view.info.replaceChildren();for(const key of ['legal_name','lei','registry_status','website','email','phone','description','industry','country','founded','employees','mx','spf','dmarc'])if(result[key])view.info.append(el('span',key+': '+result[key]),el('br'));for(const url of (result.source||'').split('\n').filter(Boolean)){try{const u=new URL(url);if(u.protocol!=='https:'&&u.protocol!=='http:')continue;const a=el('a',t('Ver fuente ↗','View source ↗'));a.href=url;a.target='_blank';a.rel='noopener noreferrer';view.info.append(a,document.createTextNode(' '));}catch{}}if(result.errors?.length)view.info.append(el('span',result.errors.join('; ')));}
 async function applyEntity(index,entity,view,epoch,signal){
 const result=results[index];Object.assign(result,entity.fields);result.source=[result.source,entity.source].filter(Boolean).join('\n');result.checked_at=new Date().toISOString();result.status='enriched';
 const input=snapshot.rows[index],originalWebsite=input[snapshot.mapping.website];if(originalWebsite&&domainOf(originalWebsite)!==domainOf(result.website||'')){result.conflicts.push({field:'website',input:originalWebsite,observed:result.website});result.website=originalWebsite;}
 for(const key of ['email']){const old=input[snapshot.mapping[key]];if(old&&result[key]&&old!==result[key])result.conflicts.push({field:key,input:old,observed:result[key]});}
 await finishDomain(result,signal);if(epoch!==generation)return;view.options.replaceChildren();display(view,result);
 }
 async function finishDomain(result,signal){
 const domain=domainOf(result.website||'');if(!domain)return;
 const dns=await dnsProfile(domain,{signal});Object.assign(result,dns.fields);result.source=[result.source,...dns.evidence.map(e=>e.source)].filter(Boolean).join('\n');result.errors.push(...dns.evidence.filter(e=>e.status!=='observed').map(e=>e.field+': '+e.status));
 if(endpoint.value.trim()){try{const scraped=await scrape(result.website,signal);if(scraped){for(const k of ['email','phone','description'])if(scraped.fields?.[k]){if(result[k]&&result[k]!==scraped.fields[k])result.conflicts.push({field:k,existing:result[k],observed:scraped.fields[k]});else result[k]=scraped.fields[k];}result.source+='\n'+(scraped.sources||[]).join('\n');result.errors.push(...(scraped.errors||[]));}}catch(e){if(signal.aborted)throw e;result.errors.push('crawler: '+e.message);}}
 result.checked_at=new Date().toISOString();
 }
 run.addEventListener('click',async()=>{
 if(!consent.checked){progress.textContent=t('Confirma el permiso de consultas antes de empezar.','Confirm network permission before starting.');return;}
 const data=getData();if(!data?.parsed?.rows.length){progress.textContent=t('Carga primero una lista CSV.','Load a CSV first.');return;}
 if(!data.mapping.company&&!data.mapping.website){progress.textContent=t('Mapea la columna empresa o sitio web.','Map company or website column.');return;}
 reset();snapshot={...data.parsed,mapping:{...data.mapping}};controller=new AbortController();const signal=controller.signal,epoch=generation;running=true;run.disabled=true;stop.disabled=false;results=snapshot.rows.map(()=>({status:'not_processed',errors:[],conflicts:[]}));
 const limit=Math.min(snapshot.rows.length,Math.max(1,Math.min(100,Number(count.value)||25)));
 try{for(let i=0;i<limit;i++){
 if(signal.aborted)break;const view=rowView(i),r=results[i],record=snapshot.rows[i],company=(record[snapshot.mapping.company]||'').trim(),website=(record[snapshot.mapping.website]||'').trim();r.website=website;r.status='searching';r.checked_at=new Date().toISOString();display(view,r);progress.textContent=t('Consultando ','Querying ')+(i+1)+' / '+limit;
 try{const candidates=[];if(company){for(const [provider,search]of [['Wikidata',searchCompanies],['GLEIF',searchLegalEntities]]){try{candidates.push(...await search(company,{signal,language}));}catch(e){if(signal.aborted)throw e;r.errors.push(provider+': '+e.message);}}}if(epoch!==generation)return;
 r.status=candidates.length?'needs_confirmation':website?'domain_checked':'no_match';
 // Never auto-attach a namesake to the input list. User explicitly selects an entity.
 for(const candidate of candidates){const b=el('button',candidate.label+' — '+candidate.description);b.type='button';b.className='button small';b.addEventListener('click',async()=>{if(running){progress.textContent=t('Espera a que termine la búsqueda de la lista.','Wait for list search to finish.');return;}const localEpoch=generation;const c=new AbortController();controller=c;running=true;run.disabled=true;stop.disabled=false;b.disabled=true;try{const entity=candidate.provider==='GLEIF'?candidate:await entityDetails(candidate.id,{signal:c.signal,language});if(localEpoch!==generation)return;await applyEntity(i,entity,view,localEpoch,c.signal);}catch(e){if(localEpoch===generation){r.errors.push(e.message);display(view,r);}}finally{if(localEpoch===generation){running=false;run.disabled=false;stop.disabled=true;b.disabled=false;}}});view.options.append(b);}
 if(website)await finishDomain(r,signal);if(epoch!==generation)return;display(view,r);
 }catch(e){if(signal.aborted)break;r.status='source_error';r.errors.push(e.message);display(view,r);}
 download.disabled=false;
 // Pace calls instead of bulk parallel searches against a public service.
 await new Promise(resolve=>setTimeout(resolve,250));
 }
 if(epoch===generation)progress.textContent=t('Consultas terminadas. Confirma las coincidencias de empresa y exporta los datos encontrados. Los campos vacíos no se inventan.','Queries finished. Confirm company matches and export observations. Missing fields are not fabricated.');
 }finally{if(epoch===generation){running=false;run.disabled=false;stop.disabled=true;}}
 });
 download.addEventListener('click',()=>{if(!snapshot)return;const a=el('a');const url=URL.createObjectURL(new Blob([exportEnrichment(snapshot,results)],{type:'text/csv;charset=utf-8'}));a.href=url;a.download='TechDigital-enriched.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 return {reset,onSample:fn=>sample.addEventListener('click',fn)};
}
