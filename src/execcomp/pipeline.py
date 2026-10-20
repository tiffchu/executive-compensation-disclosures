import json, hashlib
from pathlib import Path
from decimal import Decimal
from .config import RunConfig
from .inputs import load_companies, match_executive
from .documents import acquire, discover, fetch
from .extraction import pdf_evidence, extract_compensation, extract_net_income, html_evidence, extract_html_compensation
from .currency import cad, select_rate, load_snapshot, annual_rate_url
from .validation import reconcile, rank_records

def json_write(path, obj):
    Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')

def run(root, input_path, output_dir, config=None, profile_dir=None, fx_path=None):
    root=Path(root); output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    config=config or RunConfig.start(); profiles=Path(profile_dir or root/'config')
    fx_path=Path(fx_path or root/'data/documents'/f'fx_annual_{config.target_year}.json')
    issues=[]; records=[]; contexts=[]; candidates=[]
    try:
        if not fx_path.exists():
            url=annual_rate_url(config.target_year)
            payload=fetch(url); select_rate(json.loads(payload),config.target_year)
            fx_path.parent.mkdir(parents=True,exist_ok=True); fx_path.write_bytes(payload)
            json_write(fx_path.with_suffix(fx_path.suffix+'.meta.json'),{'url':url,'filename':fx_path.name,'sha256':hashlib.sha256(payload).hexdigest()})
        fx=load_snapshot(fx_path,config.target_year)
    except (OSError, ValueError,KeyError) as exc:
        fx=None; issues.append({'scope':'FX','reason':str(exc)})
    for company in load_companies(input_path):
        scope=company['company']; profile_name=company.get('profile','')
        try:
            if not company.get('document'):
                if company.get('ir_url'):
                    candidates.extend(dict(c,company=scope) for c in discover(company['ir_url'],config.target_year))
                raise ValueError('Document selection requires review; inspect discovery candidates and supply original document')
            if not profile_name or not (profiles/f'{profile_name}.json').is_file():
                raise ValueError('No reviewed deterministic layout adapter. Supply a reviewed profile; no figures collected.')
            profile=json.loads((profiles/f'{profile_name}.json').read_text())
            source_location=company['document']
            path=acquire(source_location if source_location.startswith('https://') else root/source_location,root/'data/documents')
            if profile.get('document_format')=='html':
                evidence=html_evidence(path)
                parsed=extract_html_compensation(evidence,profile,config.target_year)
                evidence['pages']={'HTML document':{'text':evidence['text']}}
            else:
                evidence=pdf_evidence(path,profile['evidence_pages'],root/'data/extracted/cache')
                parsed=extract_compensation(evidence,profile,config.target_year)
            meta_path=(root/source_location).with_suffix(Path(source_location).suffix+'.meta.json') if not source_location.startswith('https://') else None
            url=source_location if source_location.startswith('https://') else (json.loads(meta_path.read_text())['url'] if meta_path and meta_path.exists() else None)
            context={'id':profile_name,'url':url,'filename':Path(source_location).name,'saved_file':str(path.relative_to(root)),
                'sha256':evidence['sha256'],'document_date':profile['document_date'],'fiscal_end':profile['fiscal_end'],
                'selection_note':profile['selection_note'],'table_heading':'Summary Compensation Table',
                'page_text':{p:v['text'] for p,v in evidence['pages'].items()},'footnote_reference':profile['footnote_reference']}
            contexts.append(context)
            net=None
            try:
                fp=json.loads((profiles/f'{profile_name}_financials.json').read_text())
                if fp['fiscal_end'] != profile['fiscal_end']: raise ValueError('Net-income fiscal period differs from compensation')
                fs=company.get('financial_document','')
                if not fs: raise ValueError('Audited financial statement document not supplied')
                fpath=acquire(fs if fs.startswith('https://') else root/fs,root/'data/documents')
                fe=pdf_evidence(fpath,[fp['page']],root/'data/extracted/cache')
                net=extract_net_income(fe,fp)
                fm=(root/fs).with_suffix(Path(fs).suffix+'.meta.json') if not fs.startswith('https://') else None
                net['evidence']={'document_url':fs if fs.startswith('https://') else json.loads(fm.read_text())['url'] if fm and fm.exists() else None,
                     'filename':Path(fs).name,'document_date':fp['document_date'],'fiscal_end':fp['fiscal_end'],
                     'sha256':fe['sha256'],'table_heading':fp['guards'][0],'page':fp['page']}
                contexts.append({'id':profile_name+'_financials','page_text':{str(fp['page']):fe['pages'][str(fp['page'])]['text']},**net['evidence']})
            except (OSError,ValueError,KeyError,IndexError) as exc:
                issues.append({'scope':scope+' / net income','reason':str(exc)})
                net={'amount':None,'raw':None,'status':'uncertain','reason':str(exc),'currency':None,'units':None,'source_label':None,'mapping':'Audited consolidated net income including NCI required.'}
            if company['all_executives']:
                selected=parsed
            else:
                selected=[]
                for request in company['executives']:
                    try:
                        name=match_executive(request,[r['executive'] for r in parsed]); selected.append(next(r for r in parsed if r['executive']==name))
                    except ValueError as exc: issues.append({'scope':scope+' / '+request,'reason':str(exc)})
            for record in selected:
                record.update(company=scope,symbol=company['symbol'],fiscal_end=profile['fiscal_end'],source_id=profile_name)
                record['record_id']=hashlib.sha256(f'{scope}|{record["executive"]}|{profile["fiscal_end"]}'.encode()).hexdigest()[:20]
                record['fields']['net_income']=dict(net)
                for field,value in record['fields'].items():
                    if field != 'net_income': value['evidence']={'document_url':url,'filename':Path(source_location).name,'document_date':profile['document_date'],'fiscal_end':profile['fiscal_end'],'table_heading':'Summary Compensation Table','page':value['page'],'locator':value.get('locator'),'sha256':evidence['sha256']}
                    converted,rate,was_usd,reason=cad(value['amount'],value['currency'],value['units'],fx)
                    value.update(cad=converted,applied_rate=rate,converted_from_usd=was_usd,
                        fx_date=fx['date'] if was_usd else None,fx_url=fx['url'] if was_usd else None,
                        fx_period=fx['period'] if was_usd else None,fx_basis=fx['basis'] if was_usd else None,
                        fx_observation_label=fx['observation_label'] if was_usd else None)
                    if reason and not value.get('reason'): value['reason']=reason
                    if value['amount'] is not None and converted is None: value['status']='uncertain'
                    if converted is None: issues.append({'scope':scope+' / '+record['executive']+' / '+field,'reason':value['reason']})
                record['reconciliation']=reconcile(record['fields'])
                if record['reconciliation']['reported_minus_known'] not in ('0',None):
                    issues.append({'scope':scope+' / '+record['executive']+' / reconciliation',
                        'reason':'Reported total minus known components is '+record['reconciliation']['reported_minus_known']+' '+profile['currency']+'. No source rounding tolerance assumed. Missing components remain unresolved.'})
                record['status']='Verified total; component review required' if any(v['cad'] is None for v in record['fields'].values()) else 'Collected'
                records.append(record)
        except (OSError,ValueError,KeyError,IndexError) as exc:
            issues.append({'scope':scope,'reason':str(exc)})
    keys=[r['record_id'] for r in records]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate company/executive/fiscal-year record')
    records=rank_records(records)
    result={'schema_version':'1.0','run':{'target_year':config.target_year,'started_local':config.started_local,
        'method':'Deterministic PDF word coordinates and explicit reviewed layout profiles; no generative extraction.',
        'fx':fx,'ranking':'Descending confirmed CAD reported totals; competition ranks for ties; unavailable totals unranked.'},
        'records':records,'sources':contexts,'unresolved':issues,'discovery_candidates':candidates}
    json_write(output/'records.json',result)
    lines=[f'# Run report: fiscal years ending in {config.target_year}',f'\nStarted locally: {config.started_local}',
        f'\nCollected {len(records)} executive records across {len(set(r["company"] for r in records))} companies.',
        f'Ranked {sum(r["rank"] is not None for r in records)} confirmed totals. {len(issues)} unresolved field or collection items.',
        f'\nUSD conversion: Bank of Canada annual average for {config.target_year}, '+(fx['rate']+' CAD per USD. Source: '+fx['url'] if fx else 'Needs manual input.'),
        '\nDashes remain null. Not applicable and not disclosed remain distinct. Missing components do not invalidate an independently verified total.',
        '\nReconciliation is incomplete when any source component is nonnumeric. The diagnostic sum of known components is not a reconstructed total.',
        '\n## Unresolved items']
    lines.extend(f'- {i["scope"]}: {i["reason"]}' for i in issues)
    if not issues: lines.append('None.')
    lines.extend(['\n## Implementation limits','- Reviewed PDF adapters are provided for the three pilot circulars only, pinned to source hashes and 2025 fiscal ends.',
        '- Discovery returns candidate links from supplied IR pages. It does not automatically certify an original circular or fiscal period.',
        '- HTML/SEC DEF 14A extraction supports reviewed table/column profiles with explicit year/identity rules, spans and exact cell locators. Arbitrary layouts, nested HTML tables and OCR scans are not implemented.',
        '- New issuers, later years, ambiguous identity matches, restricted sites and unsupported currencies require reviewed inputs. No placeholder rows count as successful collection.',
        '- Re-run the pipeline to refresh ranking/order after changing source inputs. Workbook formulas show conversions; it is a run snapshot.'])
    (output/'run_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result
