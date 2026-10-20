import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';

const input=path.resolve(process.argv[2]||'outputs/pilot/records.json');
const dir=path.dirname(input), data=JSON.parse(await fs.readFile(input,'utf8'));
const workbookName=data.run.workbook_filename||'execs_comp_roster.xlsx';
const template=await SpreadsheetFile.importXlsx(await FileBlob.load(path.resolve('data/templates/execs_comp_template.xlsx')));
const templateHeaders=template.worksheets.getItemAt(0).getRange('A1:AJ1').values[0];
assert.equal(templateHeaders[0],'First Name'); assert.equal(templateHeaders[32],'Total comp CAD upload 2025');
const wb=Workbook.create();
const results=wb.worksheets.add('Results'), source=wb.worksheets.add('Source data');
const ink='#182D47', muted='#52657A', numberFormat='#,##0;(#,##0);0';
const missing='';
const fields=['total','salary','share_awards','option_awards','annual_incentive','long_term_incentive','pension','other'];
function base(sheet,last,cols){
 sheet.showGridLines=false;
 sheet.getRangeByIndexes(0,0,last,cols).format.font={name:'Arial',size:10,color:ink};
 sheet.getRangeByIndexes(0,0,last,cols).format.verticalAlignment='center';
 sheet.getRangeByIndexes(0,0,last,cols).format.rowHeight=25;
 sheet.tabColor=ink;
}
function header(sheet,address){
 sheet.getRange(address).format={fill:ink,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:42};
}
function literal(v){return typeof v==='string'&&/^[=+@]/.test(v)?"'"+v:v;}
function date(value){return value?new Date(value+'T12:00:00Z'):null;}
const sourceRows=[], index=new Map();
for(const r of data.records){
 for(const period of [r,...(r.prior_year?.fields&&Object.keys(r.prior_year.fields).length?[r.prior_year]:[])]){
 for(const field of fields){
  const v=period.fields[field], e=v.evidence||{}, row=sourceRows.length+6;
  index.set(r.record_id+'|'+period.fiscal_end+'|'+field,row);
  sourceRows.push([r.record_id,r.company,r.executive,date(period.fiscal_end),field,v.source_label||null,v.raw??null,
   v.amount===null?null:Number(v.amount),v.currency||null,v.units??null,v.applied_rate===null?null:Number(v.applied_rate),null,
   v.status,v.converted_from_usd?'Yes':'No',v.fx_period?Number(v.fx_period):null,v.fx_url||'',date(e.document_date),e.table_heading||'',e.page||e.locator||missing,e.filename||'',
   e.document_url||'',e.sha256||'',v.footnote_reference||'',v.mapping||'',v.reason||'']);
 }
 }
}
base(source,Math.max(sourceRows.length+8,30),30);
source.getRange('A2').values=[['Original figures and conversion evidence']];
source.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:ink};
source.getRange('A3').values=[['CAD = original amount × source multiplier × FX to CAD. Exact page text and footnotes begin at AA5.']];
source.getRange('A3').format.font={italic:true,color:muted};
source.getRange('A5:Y5').values=[['Record ID','Company','Executive','Fiscal end','Field','Exact source label','Original cell','Original amount','Currency','Source multiplier','FX to CAD','Full-dollar CAD','Source meaning','Converted from USD','FX annual-average year','Official rate URL','Document date','Table heading','PDF page / HTML locator','Filename','Document URL','SHA256','Footnote reference','Mapping explanation','Review reason']];
header(source,'A5:Y5');
if(sourceRows.length){
 source.getRange(`A6:Y${sourceRows.length+5}`).values=sourceRows.map(row=>row.map(literal));
 source.getRange(`L6:L${sourceRows.length+5}`).formulas=sourceRows.map((_,i)=>[`=IF(AND(ISNUMBER(H${i+6}),ISNUMBER(J${i+6}),ISNUMBER(K${i+6})),H${i+6}*J${i+6}*K${i+6},"${missing}")`]);
 source.getRange(`H6:H${sourceRows.length+5}`).format.numberFormat='#,##0.00;(#,##0.00);0.00';
 source.getRange(`L6:L${sourceRows.length+5}`).format.numberFormat=numberFormat;
 source.getRange(`K6:K${sourceRows.length+5}`).format.numberFormat='0.0000';
 source.getRange(`H6:K${sourceRows.length+5}`).format.font.color='#1749A0';
}
const sourceWidths=[24,27,26,14,22,42,22,20,12,18,16,22,20,19,18,85,16,40,18,40,100,72,100,100,70];
sourceWidths.forEach((width,c)=>source.getRangeByIndexes(0,c,Math.max(8,sourceRows.length+6),1).format.columnWidth=width);
if(sourceRows.length){
 source.getRange(`A6:Y${sourceRows.length+5}`).format.rowHeight=48;
 for(const col of ['F','P','R','T','U','V','W','X','Y'])source.getRange(`${col}6:${col}${sourceRows.length+5}`).format.wrapText=true;
}
for(const col of ['D','Q'])source.getRange(`${col}6:${col}${Math.max(6,sourceRows.length+5)}`).format.numberFormat='yyyy-mm-dd';
source.getRange(`O6:O${Math.max(6,sourceRows.length+5)}`).format.numberFormat='0';
// Full exact text is readable in a separate area of the same Source data sheet.
const evidenceRows=[];
for(const s of data.sources){
 for(const [page,text] of Object.entries(s.page_text||{})){
  text.split('\n').flatMap(line=>line.match(/.{1,160}/gu)||['']).forEach((line,i)=>evidenceRows.push([s.id,Number.isNaN(Number(page))?page:Number(page),i+1,line]));
 }
}
source.getRange('AA5:AD5').values=[['Source ID','PDF page','Line in extract','Exact source text, including footnotes']];
header(source,'AA5:AD5');
if(evidenceRows.length){
 source.getRange(`AA6:AD${evidenceRows.length+5}`).values=evidenceRows.map(row=>row.map(literal));
 source.getRange(`AA6:AD${evidenceRows.length+5}`).format.font={name:'Arial',size:10,color:ink};
 if(evidenceRows.length>sourceRows.length)source.getRange(`AA${sourceRows.length+6}:AD${evidenceRows.length+5}`).format.rowHeight=28;
 source.getRange(`AD6:AD${evidenceRows.length+5}`).format.wrapText=true;
 // Fit lines to the evidence column so long source sentences remain fully visible.
 evidenceRows.forEach((r,i)=>{if(r[3].length>160&&i>=sourceRows.length)source.getRange(`AA${i+6}:AD${i+6}`).format.rowHeight=42;});
}
source.getRange(`AA1:AA${Math.max(6,evidenceRows.length+5)}`).format.columnWidth=25;
source.getRange(`AB1:AC${Math.max(6,evidenceRows.length+5)}`).format.columnWidth=16;
source.getRange(`AD1:AD${Math.max(6,evidenceRows.length+5)}`).format.columnWidth=165;
source.freezePanes.freezeRows(5); source.freezePanes.freezeColumns(3);

const mapping=data.run.template.mapping, displayRows=[...data.records,...(data.removed_executives||[]),...(data.unverified_executives||[])], last=displayRows.length+1;
base(results,last+1,44);
const headers=templateHeaders.map(v=>String(v).replace(/2025|2024/g,y=>String(data.run.target_year-(y==='2024'?1:0))));
results.getRange('A1:AR1').values=[[...headers,'Rank',`Long-term incentives ${data.run.target_year} USD`,`Long-term incentives ${data.run.target_year} CDN$:`, 'Fiscal year end','Review notes',`Long-term incentives ${data.run.target_year-1} USD`,`Long-term incentives ${data.run.target_year-1} CDN$:`, 'Roster status']];
results.getRange('A1:AR1').format={font:{name:'Arial',size:10,bold:true,color:'#000000'},fill:'#FFFFFF',wrapText:true,rowHeight:60,verticalAlignment:'center',borders:{bottom:{style:'thin',color:'#000000'}}};
results.getRange(`A2:AR${Math.max(2,last)}`).format.rowHeight=36;
results.getRange('A1:AR1').format.columnWidth=21;
results.getRange(`A2:AR${Math.max(2,last)}`).format.font.color='#000000';
for(const m of mapping.fields){
 results.getRange(`${m.cad}1:${m.cad}${Math.max(2,last)}`).format.columnWidth=29;
 results.getRange(`${m.usd}1:${m.usd}${Math.max(2,last)}`).format.columnWidth=22;
 results.getRange(`${m.prior_cad}1:${m.prior_cad}${Math.max(2,last)}`).format.columnWidth=29;
 results.getRange(`${m.prior_usd}1:${m.prior_usd}${Math.max(2,last)}`).format.columnWidth=22;
}
for(const [col,width] of [['A',20],['B',21],['E',30],['F',60],['AJ',12],['AK',9],['AO',55]])results.getRange(`${col}1:${col}${Math.max(2,last)}`).format.columnWidth=width;
for(const col of ['F','AO'])results.getRange(`${col}2:${col}${Math.max(2,last)}`).format.wrapText=true;
source.getRange('A4').values=[[`Bank of Canada annual CAD per USD: ${data.run.target_year} = ${data.run.fx?.rate||'unavailable'}; ${data.run.target_year-1} = ${data.run.prior_fx?.rate||'unavailable'}. Missing amounts display blank.`]];
for(let i=0;i<displayRows.length;i++){
 const r=displayRows[i],row=i+2;
 const note=r.status+(r.roster_status==='new'&&r.prior_year?.reason?' Prior year: '+r.prior_year.reason:'');
 for(const [col,value] of [['A',r.first_name],['B',r.last_name],['E',r.company],['F',r.title],['AJ',r.symbol],['AN',date(r.fiscal_end)],['AO',note],['AR',r.roster_status||'']])results.getRange(`${col}${row}`).values=[[literal(value)]];
 if(!r.fields)continue;
 for(const m of mapping.fields){
  for(const [period,usd,cad] of [[r,m.usd,m.cad],...(r.roster_status==='new'&&r.prior_year?.fields?.[m.field]?[[r.prior_year,m.prior_usd,m.prior_cad]]:[])]){
  const v=period.fields[m.field],s=index.get(r.record_id+'|'+period.fiscal_end+'|'+m.field);
  results.getRange(`${cad}${row}`).formulas=[[`='Source data'!L${s}`]];
  results.getRange(`${cad}${row}`).format.numberFormat=numberFormat;
  if(v.currency==='USD'&&v.amount!==null){
   results.getRange(`${usd}${row}`).formulas=[[`='Source data'!H${s}*'Source data'!J${s}`]];
   results.getRange(`${usd}${row}`).format.numberFormat=numberFormat;
  }
  }
 }
 results.getRange(`AK${row}`).formulas=[[`=IF(ISNUMBER(AG${row}),RANK(AG${row},$AG$2:$AG$${last},0),"")`]];
}
results.getRange(`A2:AR${Math.max(2,last)}`).conditionalFormats.addCustom('$AR2="removed"',{fill:'#FFC7CE',font:{color:'#9C0006'}});
results.getRange(`AN2:AN${Math.max(2,last)}`).format.numberFormat='yyyy-mm-dd';
results.getRange(`AG2:AG${Math.max(2,last)}`).format.font.bold=true;
results.freezePanes.freezeRows(1); results.freezePanes.freezeColumns(2);
wb.recalculate();
// Verify every exported financial amount and rank against the Decimal-based pipeline.
for(let i=0;i<data.records.length;i++){
 const r=data.records[i],row=i+2;
 for(const m of mapping.fields){
  for(const [period,cad] of [[r,m.cad],...(r.roster_status==='new'&&r.prior_year?.fields?.[m.field]?[[r.prior_year,m.prior_cad]]:[])]){
  const actual=results.getRange(`${cad}${row}`).values[0][0],expected=period.fields[m.field].cad;
  if(expected===null)assert.equal(actual,missing);
  else assert.ok(Math.abs(Number(actual)-Number(expected))<0.00001,`${r.executive} ${m.field}: ${actual} vs ${expected}`);
  }
 }
 assert.equal(results.getRange(`AK${row}`).values[0][0],r.rank??'');
}
// Input perturbation proves conversion formulas update; restore before delivery.
const perturbIndex=sourceRows.findIndex(r=>r[8]==='USD'&&typeof r[7]==='number');
if(perturbIndex>=0){
 const row=perturbIndex+6,rateCell=`K${row}`,valueCell=`H${row}`,cadCell=`L${row}`;
 const oldRate=source.getRange(rateCell).values[0][0],oldAmount=source.getRange(valueCell).values[0][0],before=source.getRange(cadCell).values[0][0];
 source.getRange(rateCell).values=[[oldRate*2]];wb.recalculate();
 assert.ok(Math.abs(source.getRange(cadCell).values[0][0]-before*2)<0.00001);
 source.getRange(rateCell).values=[[oldRate]];
 source.getRange(valueCell).values=[[0]];wb.recalculate();assert.equal(source.getRange(cadCell).values[0][0],0);
 source.getRange(valueCell).values=[[null]];wb.recalculate();assert.equal(source.getRange(cadCell).values[0][0],'');
 source.getRange(valueCell).values=[[oldAmount]];
}
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'Final formula error scan'});
await fs.mkdir(path.join(dir,'previews'),{recursive:true});
await fs.writeFile(path.join(dir,'workbook_validation.json'),JSON.stringify({checked_records:data.records.length,checked_monetary_cells:data.records.length*fields.length,input_perturbation:'USD rate, zero and blank checks passed; restored',formula_scan:errors.ndjson},null,2));
for(const [name,sheetName,range] of [['results','Results','A1:G10'],['results_components','Results','H1:S8'],['results_totals','Results','AB1:AR8'],['removed_names','Results',`A${Math.max(2,data.records.length)}:F${last}`],['removed_status','Results',`AN${Math.max(2,data.records.length)}:AR${last}`],['source_values','Source data','E5:M14'],['source_evidence','Source data','AA5:AD17'],['source_citations','Source data','Q5:U9']]){
 const image=await wb.render({sheetName,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(dir,'previews',name+'.png'),new Uint8Array(await image.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb); await xlsx.save(path.join(dir,workbookName));
console.log(JSON.stringify({records:data.records.length,workbook:path.join(dir,workbookName),verification:'All monetary formulas and ranks match pipeline; conversion perturbation restored.'}));
// All writes and validations above are awaited before shutting down the renderer.
process.exit(0);
