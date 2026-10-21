/** Browser-only CSV quality. No DNS, SMTP, network calls, storage or generated code. */
export function parseCSV(input) {
 if(typeof input!=='string'||!input.trim())throw Error('CSV_EMPTY');
 if(input.length>2*1024*1024||input.includes('\0'))throw Error('CSV_LIMIT');
 const text=input.replace(/^\uFEFF/,'');let quoted=false;const counts={',':0,';':0,'\t':0};
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){i++;continue;}quoted=!quoted;}if(!quoted){if(c==='\r'||c==='\n')break;if(c in counts)counts[c]++;}}
 const delimiter=Object.entries(counts).sort((a,b)=>b[1]-a[1])[0][0];
 let field='',row=[],matrix=[],state='plain';
 function cell(){row.push(field);field='';state='plain';if(row.length>100)throw Error('CSV_LIMIT');}
 function line(){cell();if(row.length>1||row[0]!=='')matrix.push(row);row=[];if(matrix.length>10001)throw Error('CSV_LIMIT');}
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(state==='quoted'){
   if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else state='closed';}else field+=c;
  }else if(c===delimiter)cell();
  else if(c==='\n'||c==='\r'){line();if(c==='\r'&&text[i+1]==='\n')i++;}
  else if(c==='"'){if(state==='closed'||field!=='')throw Error('CSV_QUOTES');state='quoted';}
  else {if(state==='closed'){if(c===' '||c==='\t')continue;throw Error('CSV_QUOTES');}field+=c;}
  if(field.length>100000)throw Error('CSV_LIMIT');
 }
 if(state==='quoted')throw Error('CSV_QUOTES');
 if(field!==''||row.length||state==='closed')line();
 const headers=(matrix.shift()||[]).map(v=>v.trim());
 if(!headers.length||headers.some(h=>!h)||new Set(headers).size!==headers.length)throw Error('CSV_HEADERS');
 if(matrix.some(r=>r.length!==headers.length))throw Error('CSV_COLUMNS');
 const rows=matrix.map(values=>Object.fromEntries(headers.map((h,i)=>[h,values[i]])));
 return {headers,rows,delimiter};
}
const norm=v=>String(v).toLowerCase().normalize('NFKD').replace(/\p{M}/gu,'').replace(/[^a-z0-9]/g,'');
const aliases={company:['companyname','company','empresa','razonsocial','nombreempresa','name','nombre','enrichedcompanyname'],email:['email','correo','correoelectronico','enrichedemail'],website:['website','web','sitioweb','paginaweb','url','enrichedwebsite'],city:['city','ciudad','localidad','enrichedcity']};
export function suggestMapping(headers){return Object.fromEntries(Object.entries(aliases).map(([key,names])=>[key,headers.find(h=>norm(h)==='enriched'+(key==='company'?'companyname':key))||headers.find(h=>names.includes(norm(h)))||'']));}
export function analyze(parsed, selection){
 const mapping=selection||suggestMapping(parsed.headers);
 if(Object.values(mapping).some(v=>v&&!parsed.headers.includes(v)))throw Error('CSV_MAPPING');
 const metrics={records:parsed.rows.length,duplicates:0,missingCompany:0,missingEmail:0,invalidEmail:0,syntaxOnly:0,domainMismatch:0,inconclusive:0};
 const seen=new Map();
 const rows=parsed.rows.map((values,index)=>{
  const company=(values[mapping.company]||'').trim(),email=(values[mapping.email]||'').trim().toLowerCase();
  const city=(values[mapping.city]||'').trim();let emailStatus='syntax_only',duplicateOf='';
  if(!company)metrics.missingCompany++;
  if(company){const key=JSON.stringify([company.toLowerCase(),city.toLowerCase()]);if(seen.has(key)){metrics.duplicates++;duplicateOf=seen.get(key);}else seen.set(key,index+1);}
  if(!email){emailStatus='not_found';metrics.missingEmail++;}
  else if(email.length>254||! /^[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+$/.test(email)||email.includes('..')||email.split('@')[0].endsWith('.')){emailStatus='invalid_syntax';metrics.invalidEmail++;}
  else {let domain='';const website=(values[mapping.website]||'').trim();try{domain=new URL(website.includes('://')?website:'https://'+website).hostname.replace(/^www\./,'').toLowerCase();}catch{}if(domain&&email.split('@')[1]!==domain&&!email.split('@')[1].endsWith('.'+domain)){emailStatus='domain_mismatch';metrics.domainMismatch++;}else metrics.syntaxOnly++;}
  if(['unknown','catch_all'].includes(values.MAILBOX_STATUS))metrics.inconclusive++;
  return {values,emailStatus,duplicateOf};
 });
 return {mapping,metrics,rows};
}
function safe(v){const text=String(v??'');return /^\s*[=+@-]/.test(text)?"'"+text:text;}
export function toCSV(parsed,report){
 const headers=[...parsed.headers];let status='PROSPECT_EMAIL_STATUS',duplicate='PROSPECT_DUPLICATE_OF';
 while(headers.includes(status))status+='_2';headers.push(status);
 while(headers.includes(duplicate))duplicate+='_2';headers.push(duplicate);
 const escaped=[],used=new Set();for(const h of headers){const base=safe(h);let value=base,n=2;while(used.has(value))value=base+'_'+n++;used.add(value);escaped.push(value);}
 const encode=values=>values.map(v=>'"'+safe(v).replaceAll('"','""')+'"').join(',');
 return '\uFEFF'+[encode(escaped),...report.rows.map(r=>encode([...parsed.headers.map(h=>r.values[h]),r.emailStatus,r.duplicateOf]))].join('\r\n')+'\r\n';
}
