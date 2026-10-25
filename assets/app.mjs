import {parseCSV,analyze,toCSV} from './csv.mjs?v=90b81772f050';
import {mountEnrichment} from './enrich-ui.mjs?v=90b81772f050';
const en=document.documentElement.lang==='en';
const words=en?{
 none:'Not mapped',sample:'Fictional sample.csv',start:'Your file is processed in this tab. Explore with fictional sample data if you prefer.',ready:'Review complete. Confirm or change the column mapping below.',loading:'Reading the file locally…',noRows:'This file contains headers but no data records.',fileType:'Choose a .csv file encoded as UTF-8.',error:'Could not review this file. ',records:'Records',duplicates:'Duplicate candidates',invalid:'Format to review',missing:'No email',mismatch:'Domain difference',company:'No company',all:'Showing up to 20 rows. Export includes every record.',inconclusive:'Existing unknown/catch_all states remain inconclusive.',cleared:'File data cleared from this workspace.',statuses:{syntax_only:'Syntax only',invalid_syntax:'Review format',not_found:'No email',domain_mismatch:'Domain difference'},errors:{CSV_EMPTY:'The CSV is empty.',CSV_LIMIT:'Limit: 2 MiB, 10,000 records and 100 columns.',CSV_QUOTES:'Check quoted fields and escaped quotes.',CSV_HEADERS:'Use unique, non-empty column headers.',CSV_COLUMNS:'Every record must have the same number of columns.',CSV_MAPPING:'Choose existing columns.'}
}:{
 none:'Sin mapear',sample:'Ejemplo ficticio.csv',start:'Tu archivo se procesa en esta pestaña. Puedes usar un ejemplo ficticio para explorar.',ready:'Revisión lista. Confirma o cambia el mapeo de columnas.',loading:'Leyendo el archivo localmente…',noRows:'El archivo tiene cabeceras pero no filas de datos.',fileType:'Elige un archivo .csv codificado en UTF-8.',error:'No se pudo revisar el archivo. ',records:'Registros',duplicates:'Posibles duplicados',invalid:'Formato a revisar',missing:'Sin correo',mismatch:'Dominio distinto',company:'Sin empresa',all:'Se muestran hasta 20 filas. La exportación incluye todos los registros.',inconclusive:'Los estados unknown/catch_all existentes siguen siendo inconclusos.',cleared:'Datos eliminados de este espacio de revisión.',statuses:{syntax_only:'Solo sintaxis',invalid_syntax:'Revisar formato',not_found:'Sin correo',domain_mismatch:'Dominio distinto'},errors:{CSV_EMPTY:'El CSV está vacío.',CSV_LIMIT:'Límite: 2 MiB, 10,000 registros y 100 columnas.',CSV_QUOTES:'Revisa las comillas y el escape de campos.',CSV_HEADERS:'Usa cabeceras únicas y no vacías.',CSV_COLUMNS:'Cada fila debe tener la misma cantidad de columnas.',CSV_MAPPING:'Selecciona columnas existentes.'}
};
for(const details of document.querySelectorAll('.mobile-menu')){
 details.addEventListener('keydown',event=>{if(event.key==='Escape'){details.open=false;details.querySelector('summary').focus();}});
 details.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>{details.open=false;}));
}
const consent=document.getElementById('license-consent');const sourceLink=document.getElementById('download-source');
if(consent&&sourceLink){consent.addEventListener('change',()=>sourceLink.setAttribute('aria-disabled',String(!consent.checked)));sourceLink.addEventListener('click',event=>{if(!consent.checked)event.preventDefault();});}
const fileInput=document.getElementById('csv-file');
if(fileInput){
 let parsed=null,report=null,loadVersion=0,enrichment=null;
 const drop=document.getElementById('drop-zone'),message=document.getElementById('workspace-message');
 const mappingPanel=document.getElementById('mapping-panel'),resultsPanel=document.getElementById('results-panel');
 const names=['company','email','website','city'];const controls=Object.fromEntries(names.map(key=>[key,document.getElementById('map-'+key)]));
 enrichment=mountEnrichment({container:document.querySelector('.workspace-inner'),getData:()=>({parsed,mapping:Object.fromEntries(names.map(key=>[key,controls[key].value]))}),language:en?'en':'es'});
 enrichment.onNames(names=>load('company_name\n'+names.map(name=>'"'+name.replaceAll('"','""')+'"').join('\n'),en?'Company names.csv':'Nombres de empresas.csv'));
 enrichment.onSample(()=>load('company_name,email,website,city\nMicrosoft,,https://www.microsoft.com,Redmond\nMozilla,,https://www.mozilla.org,San Francisco\n',en?'Real companies.csv':'Empresas reales.csv'));
 function status(text,error=false){message.textContent=text;message.classList.toggle('error',error);}
 function reset(){enrichment?.reset();loadVersion++;parsed=null;report=null;fileInput.value='';Object.values(controls).forEach(control=>control.replaceChildren());mappingPanel.hidden=true;resultsPanel.hidden=true;document.getElementById('result-rows').replaceChildren();document.getElementById('result-stats').replaceChildren();document.getElementById('file-name').textContent=en?'No file selected':'Sin archivo';}
 function element(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
 function render(){
  if(!parsed)return;const mapping=Object.fromEntries(names.map(key=>[key,controls[key].value]));report=analyze(parsed,mapping);
  const metrics=report.metrics,stats=document.getElementById('result-stats');stats.replaceChildren();
  for(const [label,value]of [[words.records,metrics.records],[words.duplicates,metrics.duplicates],[words.invalid,metrics.invalidEmail],[words.missing,metrics.missingEmail],[words.mismatch,metrics.domainMismatch]]){
   const div=element('div',undefined,'result-stat');div.append(element('span',label),element('strong',value));stats.append(div);
  }
  const tbody=document.getElementById('result-rows');tbody.replaceChildren();
  for(const record of report.rows.slice(0,20)){
   const tr=element('tr');const company=record.values[report.mapping.company]||words.company,email=record.values[report.mapping.email]||'—';
   const c=element('td',company),e=element('td',email);c.title=company;e.title=email;
   const badge=element('span',words.statuses[record.emailStatus], 'table-status '+(record.emailStatus==='invalid_syntax'||record.emailStatus==='domain_mismatch'?'amber':record.emailStatus==='not_found'?'neutral':''));
   const signal=element('td');signal.append(badge);tr.append(c,e,signal,element('td',record.duplicateOf?'#'+record.duplicateOf:'—'));tbody.append(tr);
  }
  document.getElementById('report-description').textContent=words.all+(metrics.inconclusive?' '+words.inconclusive:'');
  resultsPanel.hidden=false;status(parsed.rows.length?words.ready:words.noRows);
 }
 function load(text,name){
  reset();parsed=parseCSV(text);enrichment.setRowCount(parsed.rows.length);document.getElementById('file-name').textContent=name;
  const initial=analyze(parsed).mapping;
  for(const key of names){const control=controls[key];control.replaceChildren();const empty=element('option',words.none);empty.value='';control.append(empty);for(const header of parsed.headers){const option=element('option',header);option.value=header;control.append(option);}control.value=initial[key];}
  mappingPanel.hidden=false;render();
 }
 async function readFile(file){
  if(!file)return;reset();const version=loadVersion;status(words.loading);
  try{if(!file.name.toLowerCase().endsWith('.csv'))throw Error(words.fileType);if(file.size>2097152)throw Error('CSV_LIMIT');const text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());if(version!==loadVersion)return;load(text,file.name);}
  catch(error){if(version!==loadVersion)return;reset();status(words.error+(words.errors[error.message]||error.message),true);}
 }
 fileInput.addEventListener('change',()=>readFile(fileInput.files[0]));
 const label=document.querySelector('.file-label');label.tabIndex=0;label.setAttribute('role','button');label.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();fileInput.click();}});
 for(const type of ['dragenter','dragover'])drop.addEventListener(type,event=>{event.preventDefault();drop.classList.add('dragging');});
 for(const type of ['dragleave','drop'])drop.addEventListener(type,event=>{event.preventDefault();drop.classList.remove('dragging');});
 drop.addEventListener('drop',event=>readFile(event.dataTransfer.files[0]));
 Object.values(controls).forEach(control=>control.addEventListener('change',()=>{enrichment.reset();render();}));
 document.getElementById('load-sample').addEventListener('click',()=>load('company_name,email,website,city\nNorthline Studio,hello@northline.example,northline.example,Quito\nOrbit Works,sales@orbit,orbit.example,Medellín\nMono Supply,,mono.example,Lima\nNorthline Studio,hello@northline.example,northline.example,Quito\n',words.sample));
 document.getElementById('clear-data').addEventListener('click',()=>{reset();status(words.cleared);});
 document.getElementById('export-csv').addEventListener('click',()=>{if(!parsed||!report)return;const blob=new Blob([toCSV(parsed,report)],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=element('a');a.href=url;a.download='TechDigital-Prospect-review.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
}
