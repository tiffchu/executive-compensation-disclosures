import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const input=path.resolve(process.argv[2]||'outputs/pilot/records.json');
const dir=path.dirname(input), data=JSON.parse(await fs.readFile(input,'utf8'));
const wb=Workbook.create();
const results=wb.worksheets.add('Results'), source=wb.worksheets.add('Source data');
const ink='#182D47', muted='#52657A', pale='#EFF3F8', numberFormat='#,##0;(#,##0);0';
const missing='Needs manual input';
const fields=['total','salary','net_income','share_awards','option_awards','annual_incentive','long_term_incentive','pension','other'];
const names=['Reported total (CAD)','Salary (CAD)','Company net income (CAD)','Share awards (CAD)','Option awards (CAD)','Annual incentives (CAD)','Long-term incentives (CAD)','Pension value (CAD)','Other compensation (CAD)'];
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
function warning(range){range.conditionalFormats.add('containsText',{text:missing,format:{fill:'#FFF0CF',font:{color:'#8A4B00'}}});}
function literal(v){return typeof v==='string'&&/^[=+@]/.test(v)?"'"+v:v;}
function date(value){return value?new Date(value+'T12:00:00Z'):null;}
const sourceRows=[], index=new Map();
for(const r of data.records){
 for(const field of fields){
  const v=r.fields[field], e=v.evidence||{}, row=sourceRows.length+6;
  index.set(r.record_id+'|'+field,row);
  sourceRows.push([r.record_id,r.company,r.executive,date(r.fiscal_end),field,v.source_label||'(not separately disclosed)',v.raw??'(blank)',
   v.amount===null?missing:Number(v.amount),v.currency||missing,v.units??missing,v.applied_rate===null?missing:Number(v.applied_rate),null,
   v.status,v.converted_from_usd?'Yes':'No',date(v.fx_date),v.fx_url||'',date(e.document_date),e.table_heading||'',e.page||e.locator||missing,e.filename||'',
   e.document_url||'',e.sha256||'',v.footnote_reference||'',v.mapping||'',v.reason||'']);
 }
}
base(source,Math.max(sourceRows.length+8,30),30);
source.getRange('A2').values=[['Original figures and conversion evidence']];
source.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:ink};
source.getRange('A3').values=[['CAD = original amount × source multiplier × FX to CAD. Exact page text and footnotes begin at AA5.']];
source.getRange('A3').format.font={italic:true,color:muted};
source.getRange('A5:Y5').values=[['Record ID','Company','Executive','Fiscal end','Field','Exact source label','Original cell','Original amount','Currency','Source multiplier','FX to CAD','Full-dollar CAD','Source meaning','Converted from USD','FX observation date','Official rate URL','Document date','Table heading','PDF page / HTML locator','Filename','Document URL','SHA256','Footnote reference','Mapping explanation','Review reason']];
header(source,'A5:Y5');
if(sourceRows.length){
 source.getRange(`A6:Y${sourceRows.length+5}`).values=sourceRows.map(row=>row.map(literal));
 source.getRange(`L6:L${sourceRows.length+5}`).formulas=sourceRows.map((_,i)=>[`=IF(AND(ISNUMBER(H${i+6}),ISNUMBER(J${i+6}),ISNUMBER(K${i+6})),H${i+6}*J${i+6}*K${i+6},"${missing}")`]);
 source.getRange(`H6:H${sourceRows.length+5}`).format.numberFormat='#,##0.00;(#,##0.00);0.00';
 source.getRange(`L6:L${sourceRows.length+5}`).format.numberFormat=numberFormat;
 source.getRange(`K6:K${sourceRows.length+5}`).format.numberFormat='0.0000';
 source.getRange(`H6:K${sourceRows.length+5}`).format.font.color='#1749A0';
 warning(source.getRange(`H6:L${sourceRows.length+5}`));
}
const sourceWidths=[24,27,26,14,22,42,22,20,12,18,16,22,20,19,18,85,16,40,18,40,100,72,100,100,70];
sourceWidths.forEach((width,c)=>source.getRangeByIndexes(0,c,Math.max(8,sourceRows.length+6),1).format.columnWidth=width);
if(sourceRows.length){
 source.getRange(`A6:Y${sourceRows.length+5}`).format.rowHeight=48;
 for(const col of ['F','P','R','T','U','V','W','X','Y'])source.getRange(`${col}6:${col}${sourceRows.length+5}`).format.wrapText=true;
}
for(const col of ['D','O','Q'])source.getRange(`${col}6:${col}${Math.max(6,sourceRows.length+5)}`).format.numberFormat='yyyy-mm-dd';
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

base(results,data.records.length+8,19);
results.getRange('A2').values=[[`Executive compensation for fiscal years ending in ${data.run.target_year}`]];
results.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:ink};
results.getRange('A3').values=[['Full dollars CAD. Rank covers the supplied company/executive universe. Amber cells require manual input; verified totals remain ranked.']];
results.getRange('A3').format.font={italic:true,color:muted};
results.getRange('A4').values=[[`USD rate: ${data.run.fx?.rate||missing} CAD per USD, observed ${data.run.fx?.date||missing}. Already reported CAD amounts are retained.`]];
results.getRange('A4').format.font={italic:true,color:muted};
results.getRange('A6:S6').values=[['Rank','Company','Executive','Fiscal year end',...names,'Reported position','Review status','Reconciliation','Reported minus known components (original currency)','Source ID','Record ID']];
header(results,'A6:S6');
const resultRows=data.records.map(r=>[r.rank??'',r.company,r.executive,date(r.fiscal_end),...fields.map(()=>null),r.position,r.status,r.reconciliation.status,r.reconciliation.reported_minus_known===null?missing:Number(r.reconciliation.reported_minus_known),r.source_id,r.record_id]);
if(resultRows.length){
 results.getRange(`A7:S${resultRows.length+6}`).values=resultRows.map(row=>row.map(literal));
 for(let i=0;i<data.records.length;i++){
  const r=data.records[i], row=i+7;
  for(let j=0;j<fields.length;j++)results.getCell(row-1,j+4).formulas=[[`='Source data'!L${index.get(r.record_id+'|'+fields[j])}`]];
  results.getRange(`A${row}`).formulas=[[`=IF(ISNUMBER(E${row}),RANK(E${row},$E$7:$E$${resultRows.length+6},0),"")`]];
  if(i%2===1)results.getRange(`A${row}:S${row}`).format.fill=pale;
 }
 results.getRange(`D7:D${resultRows.length+6}`).format.numberFormat='yyyy-mm-dd';
 results.getRange(`E7:M${resultRows.length+6}`).format.numberFormat=numberFormat;
 results.getRange(`Q7:Q${resultRows.length+6}`).format.numberFormat='#,##0.00;(#,##0.00);0.00';
 results.getRange(`E7:E${resultRows.length+6}`).format.font.bold=true;
 warning(results.getRange(`E7:M${resultRows.length+6}`));
}
const widths=[8,28,27,18,22,20,25,22,22,23,25,22,23,63,48,20,36,24,25];
widths.forEach((w,c)=>results.getRangeByIndexes(0,c,resultRows.length+8,1).format.columnWidth=w);
results.freezePanes.freezeRows(6); results.freezePanes.freezeColumns(3);
wb.recalculate();
// Verify every exported financial amount and rank against the Decimal-based pipeline.
for(let i=0;i<data.records.length;i++){
 const r=data.records[i],row=i+7;
 for(let j=0;j<fields.length;j++){
  const actual=results.getCell(row-1,j+4).values[0][0],expected=r.fields[fields[j]].cad;
  if(expected===null)assert.equal(actual,missing);
  else assert.ok(Math.abs(Number(actual)-Number(expected))<0.00001,`${r.executive} ${fields[j]}: ${actual} vs ${expected}`);
 }
 assert.equal(results.getRange(`A${row}`).values[0][0],r.rank??'');
}
// Input perturbation proves conversion formulas update; restore before delivery.
if(sourceRows.length){
 const old=source.getRange('K6').values[0][0], before=source.getRange('L6').values[0][0];
 if(typeof old==='number'&&typeof before==='number'){
  source.getRange('K6').values=[[old*2]]; wb.recalculate();
  assert.ok(Math.abs(source.getRange('L6').values[0][0]-before*2)<0.00001);
  source.getRange('K6').values=[[old]];
 }
}
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'Final formula error scan'});
await fs.mkdir(path.join(dir,'previews'),{recursive:true});
await fs.writeFile(path.join(dir,'workbook_validation.json'),JSON.stringify({checked_records:data.records.length,checked_monetary_cells:data.records.length*fields.length,input_perturbation:'passed',formula_scan:errors.ndjson},null,2));
for(const [name,sheetName,range] of [['results','Results',`A1:G${Math.max(8,resultRows.length+6)}`],['results_components','Results','H6:P13'],['source_values','Source data','E5:M14'],['source_evidence','Source data','AA5:AD17'],['source_citations','Source data','Q5:U9']]){
 const image=await wb.render({sheetName,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(dir,'previews',name+'.png'),new Uint8Array(await image.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb); await xlsx.save(path.join(dir,'compensation.xlsx'));
console.log(JSON.stringify({records:data.records.length,workbook:path.join(dir,'compensation.xlsx'),verification:'All monetary formulas and ranks match pipeline; conversion perturbation restored.'}));
// All writes and validations above are awaited before shutting down the renderer.
process.exit(0);
