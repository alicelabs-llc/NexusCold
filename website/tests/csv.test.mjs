import test from 'node:test';
import assert from 'node:assert/strict';
import {parseCSV, analyze, toCSV} from '../assets/csv.mjs';

test('quoted newlines, escaped quotes and leading zeros survive CSV parsing', () => {
 const p=parseCSV('\uFEFFEmpresa,Correo,Codigo\r\n"ACME, \"\"Norte\"\"\nSA",a@example.com,0012\r\n');
 assert.equal(p.rows[0].Empresa,'ACME, "Norte"\nSA'); assert.equal(p.rows[0].Codigo,'0012');
});
test('semicolon and quoted comma do not confuse delimiter detection',()=>{
 const p=parseCSV('Empresa;Correo\n"Uno, dos";a@example.com'); assert.equal(p.rows[0].Correo,'a@example.com');
});
test('rejects duplicate headers, malformed quotes, mismatched rows and empty content',()=>{
 for(const s of ['', 'a,a\n1,2', 'a,b\n"oops,2', 'a,b\n1,2,3', 'a,b\n1"x,2']) assert.throws(()=>parseCSV(s));
});
test('Spanish mapping, explicit selection and inconclusive mailbox states',()=>{
 const p=parseCSV('Empresa,Correo,ENRICHED_EMAIL,MAILBOX_STATUS\nACME,,a@example.com,unknown\nACME,bad,b@example.com,catch_all');
 const auto=analyze(p);assert.equal(auto.mapping.email,'ENRICHED_EMAIL'); assert.equal(auto.metrics.duplicates,1);
 assert.equal(auto.metrics.inconclusive,2); assert.equal(auto.metrics.syntaxOnly,2);
 const selected=analyze(p,{company:'Empresa',email:'Correo',website:'',city:''});
 assert.equal(selected.metrics.missingEmail,1);assert.equal(selected.metrics.invalidEmail,1);
});
test('detects website domain mismatch without converting it to invalid syntax',()=>{
 const p=parseCSV('Empresa,Correo,Web\nACME,a@other.example,https://acme.example');
 const r=analyze(p);assert.equal(r.metrics.domainMismatch,1);assert.equal(r.rows[0].emailStatus,'domain_mismatch');
});
test('safe export preserves malicious text as text and roundtrips escaped cells',()=>{
 const p=parseCSV('Empresa,Correo\n=HYPERLINK("x"),a@example.com'.replace('=HYPERLINK("x")','"=HYPERLINK(""x"")"'));
 const report=analyze(p);const out=parseCSV(toCSV(p,report));
 assert.equal(out.rows[0].Empresa,'\'=HYPERLINK("x")');
 assert.equal(out.rows[0].PROSPECT_EMAIL_STATUS,'syntax_only');
});
test('untrusted markup is retained as inert text; no data executed by analysis',()=>{
 const p=parseCSV('Empresa,Correo\n<img src=x onerror=alert(1)>,bad');
 assert.equal(analyze(p).rows[0].values.Empresa,'<img src=x onerror=alert(1)>');
});
