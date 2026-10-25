/** Public-source enrichment. No inferred contacts; every observation has provenance. */
const WD='https://www.wikidata.org/w/api.php';
export function domainOf(value){
 try{const u=new URL(String(value).includes('://')?value:'https://'+value);const h=u.hostname.toLowerCase().replace(/^www\./,'');
 if(u.protocol!=='https:'&&u.protocol!=='http:'||u.username||u.password||u.port||!h.includes('.')||/^[\d.]+$/.test(h)||h.includes(':')||h.endsWith('.local')||h.endsWith('.internal')||h.endsWith('.localhost'))return '';return h;}catch{return '';}
}
export async function jsonGet(url,{fetcher=fetch,signal}={}){
 const response=await fetcher(url,{credentials:'omit',referrerPolicy:'no-referrer',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(12000)]):AbortSignal.timeout(12000),headers:{Accept:'application/json'}});
 if(!response.ok){const error=Error('HTTP_'+response.status);error.retryAfter=response.headers?.get?.('Retry-After');throw error;}
 const text=await response.text();if(text.length>1500000)throw Error('RESPONSE_LIMIT');return JSON.parse(text);
}
const api=(params)=>WD+'?'+new URLSearchParams({format:'json',origin:'*',maxlag:'5',...params});
export async function searchCompanies(name,options={}){
 if(!String(name).trim())return [];
 const data=await jsonGet(api({action:'wbsearchentities',search:String(name).slice(0,150),language:'en',uselang:options.language||'es',type:'item',limit:'5'}),options);
 if(data.error)throw Error('WIKIDATA_'+data.error.code);
 return (data.search||[]).filter(x=>/^Q\d+$/.test(x.id)).map(x=>({id:x.id,label:x.label||x.id,description:x.description||'',url:'https://www.wikidata.org/wiki/'+x.id}));
}
export async function entityDetails(id,options={}){
 if(!/^Q\d+$/.test(id))throw Error('ENTITY_ID');
 const data=await jsonGet(api({action:'wbgetentities',ids:id,props:'claims|labels|descriptions',languages:'es|en'}),options);
 if(data.error)throw Error('WIKIDATA_'+data.error.code);
 const entity=data.entities?.[id];if(!entity||entity.missing!==undefined)throw Error('ENTITY_MISSING');
 const values=p=>(entity.claims?.[p]||[]).filter(c=>c.rank!=='deprecated'&&c.mainsnak?.snaktype==='value').map(c=>c.mainsnak.datavalue?.value).filter(v=>v!==undefined);
 const first=p=>values(p)[0];const fields={};
 const set=(k,v)=>{if(v!==undefined&&v!==null&&String(v).trim())fields[k]=String(v).slice(0,1000);};
 const site=values('P856').find(x=>typeof x==='string'&&domainOf(x));set('website',site);
 set('description',entity.descriptions?.[options.language||'es']?.value||entity.descriptions?.en?.value);
 set('phone',first('P1329'));const mail=first('P968');if(typeof mail==='string'&&/^mailto:[^?\s]+@[^?\s]+$/.test(mail))set('email',mail.slice(7));
 const inception=first('P571');if(inception?.time)set('founded',inception.time.replace(/^\+/,'').slice(0,10));
 const employees=first('P1128');if(employees?.amount)set('employees',employees.amount.replace(/^\+/,''));
 const li=first('P4264');if(typeof li==='string'&&/^[a-zA-Z0-9_-]+$/.test(li))set('linkedin','https://www.linkedin.com/company/'+li);
 const related=[['industry','P452'],['country','P17'],['headquarters','P159']].map(([k,p])=>[k,first(p)?.id]).filter(([,v])=>/^Q\d+$/.test(v||''));
 if(related.length){const labels=await jsonGet(api({action:'wbgetentities',ids:[...new Set(related.map(x=>x[1]))].join('|'),props:'labels',languages:'es|en'}),options);for(const[k,v]of related)set(k,labels.entities?.[v]?.labels?.[options.language||'es']?.value||labels.entities?.[v]?.labels?.en?.value);}
 const organization=values('P31').some(x=>['Q4830453','Q783794','Q6881511','Q43229','Q891723','Q79913','Q163740','Q161726'].includes(x?.id));
 return {organization,id,label:entity.labels?.[options.language||'es']?.value||entity.labels?.en?.value||id,fields,source:'https://www.wikidata.org/wiki/'+id,checked_at:new Date().toISOString(),note:'Public observations; may be historical or incomplete. Not mailbox verification.'};
}
export async function dnsProfile(domain,options={}){
 if(domainOf(domain)!==domain)throw Error('DOMAIN_INVALID');
 const evidence=[];const fields={domain};
 for(const [key,name,type]of [['mx',domain,'MX'],['spf',domain,'TXT'],['dmarc','_dmarc.'+domain,'TXT']]){
 const url='https://dns.google/resolve?'+new URLSearchParams({name,type});
 try{const d=await jsonGet(url,options);if(d.Status!==0&&d.Status!==3)throw Error('DNS_'+d.Status);
 const answers=(d.Answer||[]).filter(a=>a.type===(type==='MX'?15:16)).map(a=>a.data);
 if(key==='mx')fields[key]=d.Status===3?'nxdomain':answers.some(a=>/^0\s+\.$/.test(a))?'null_mx':answers.length?answers.join('; '):'no_mx';
 else fields[key]=answers.filter(a=>a.replaceAll('"','').toLowerCase().startsWith(key==='spf'?'v=spf1':'v=dmarc1')).join('; ')||'not_observed';
 evidence.push({field:key,source:url,status:'observed'});
 }catch(e){if(options.signal?.aborted)throw e;fields[key]='unknown';evidence.push({field:key,source:url,status:e.message});}
 }
 return {fields,evidence,checked_at:new Date().toISOString()};
}
export function mergeObservations(original,observations){
 const fields={...original},conflicts=[];
 for(const [key,value]of Object.entries(observations)){if(!value)continue;if(fields[key]&&String(fields[key]).trim()!==String(value).trim())conflicts.push({field:key,existing:fields[key],observed:value});else fields[key]=value;}
 return {fields,conflicts};
}
export function exportEnrichment(parsed,results){
 const keys=['status','legal_name','lei','registry_status','website','email','phone','description','industry','country','headquarters','founded','employees','linkedin','domain','mx','spf','dmarc','source','source_status','identifiers','checked_at','conflicts','errors'];
 const headers=[...parsed.headers];const added=keys.map(k=>{let h='ENRICH_'+k.toUpperCase();while(headers.includes(h))h+='_2';headers.push(h);return h;});
 const safe=v=>/^\s*[=+@-]/.test(String(v??''))?"'"+v:String(v??'');const encode=vs=>vs.map(v=>'"'+safe(v).replaceAll('"','""')+'"').join(',');
 return '\uFEFF'+[encode(headers),...parsed.rows.map((r,i)=>{const x=results[i]||{status:'not_processed'};return encode([...parsed.headers.map(h=>r[h]),...keys.map(k=>typeof x[k]==='object'?JSON.stringify(x[k]):x[k]??'')]);})].join('\r\n')+'\r\n';
}

export async function searchLegalEntities(name,options={}){
 if(!String(name).trim())return [];
 const url='https://api.gleif.org/api/v1/lei-records?'+new URLSearchParams({'filter[entity.legalName]':String(name).slice(0,150),'page[size]':'5'});
 const data=await jsonGet(url,options);if(data.errors)throw Error('GLEIF_ERROR');
 return (data.data||[]).filter(x=>/^[A-Z0-9]{20}$/.test(x.id)).map(x=>{
 const entity=x.attributes?.entity||{},address=entity.legalAddress||{};
 return {id:x.id,label:entity.legalName?.name||x.id,description:[address.city,address.country,entity.status].filter(Boolean).join(' · '),provider:'GLEIF',fields:{legal_name:entity.legalName?.name||'',lei:x.id,country:address.country||'',headquarters:[...(address.addressLines||[]),address.city,address.postalCode].filter(Boolean).join(', '),registry_status:entity.status||''},source:'https://api.gleif.org/api/v1/lei-records/'+x.id,checked_at:new Date().toISOString()};
 });
}

/** Prepare an isolated candidate result; callers commit only after every await. */
export async function confirmedObservation(base,entity,enrichDomain,signal){
 const draft=JSON.parse(JSON.stringify(base));draft.errors??=[];draft.conflicts??=[];
 for(const [key,value]of Object.entries(entity.fields||{})){
 if(key==='identifiers'){const merged=mergeIdentifiers(draft[key],value);draft.identifiers=merged.value;draft.conflicts.push(...merged.conflicts);continue;}
 if(draft[key]&&draft[key]!==value)draft.conflicts.push({field:key,existing:draft[key],observed:value});else if(value)draft[key]=value;
 }
 draft.source=[draft.source,entity.source].filter(Boolean).join('\n');draft.checked_at=new Date().toISOString();draft.status='enriched';
 await enrichDomain(draft,signal);if(signal.aborted)throw Error('CANCELLED');return draft;
}

export function exactCompanyCandidate(name,candidates){
 const norm=v=>String(v).normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/\b(incorporated|inc|corporation|corp|llc|ltd|limited|sa|srl)\b/g,'').replace(/[^a-z0-9]/g,'');
 const matches=candidates.filter(c=>!c.provider&&norm(c.label)===norm(name));return matches.length===1?matches[0]:null;
}

export function pauseIncompleteRow(results,index){if(index>=0&&results[index])results[index].status='not_processed';}
export function recordInputConflicts(result,record,mapping){const old=record[mapping.email];if(old&&result.email&&old!==result.email&&!result.conflicts.some(c=>c.field==='email'&&c.input===old&&c.observed===result.email))result.conflicts.push({field:'email',input:old,observed:result.email});return result;}
export function retryDelayMs(value){const seconds=Number(value);return Number.isFinite(seconds)&&seconds>=0?Math.max(1000,Math.min(300000,seconds*1000)):60000;}

export function checkpointResults(results,inFlight){return results.map((r,i)=>i===inFlight?{...r,status:'not_processed'}:r);}
export function retryWebsite(record,mapping,result){return (record[mapping.website]||result.website||'').trim();}

export function mergeIdentifiers(existing,observed){const allowed=new Set(['siren','siret','org_number','business_id','ror','crossref_member','cnpj','fdic_cert','npi','sec_cik','ticker','nyc_camis','fsa_fhrsid','agency_slug']);const output={},conflicts=[];for(const text of [existing,observed]){if(!text)continue;let values;try{values=JSON.parse(text);}catch{throw Error('IDENTIFIERS_INVALID');}for(const[k,v]of Object.entries(values)){if(!allowed.has(k)||!['string','number'].includes(typeof v))continue;const value=String(v);if(output[k]&&output[k]!==value)conflicts.push({field:k,existing:output[k],observed:value});else output[k]=value;}}return{value:JSON.stringify(output),conflicts};}
