import argparse, json, subprocess, os, shutil
from pathlib import Path
from .config import ROOT
from .pipeline import run
from .documents import discover, html_tables
from .export import verify_saved_workbook

def main():
    parser=argparse.ArgumentParser(description='Evidence-preserving executive compensation collector')
    sub=parser.add_subparsers(dest='command',required=True)
    collect=sub.add_parser('run'); collect.add_argument('--input',default='inputs/pilot.csv'); collect.add_argument('--output',default='outputs/pilot'); collect.add_argument('--no-excel',action='store_true')
    collect.add_argument('--profile-dir'); collect.add_argument('--fx-file')
    discovery=sub.add_parser('discover'); discovery.add_argument('ir_url'); discovery.add_argument('--year',type=int,required=True)
    html=sub.add_parser('inspect-html'); html.add_argument('path')
    args=parser.parse_args()
    if args.command=='discover': print(json.dumps(discover(args.ir_url,args.year),indent=2)); return
    if args.command=='inspect-html': print(json.dumps(html_tables(args.path),indent=2)); return
    result=run(ROOT,ROOT/args.input,ROOT/args.output,profile_dir=args.profile_dir,fx_path=args.fx_file)
    if not args.no_excel:
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        node=os.environ.get('EXECOMP_NODE') or shutil.which('node') or (str(bundled) if bundled.is_file() else 'node')
        completed=subprocess.run([node,str(ROOT/'scripts/export_workbook.mjs'),str(ROOT/args.output/'records.json')],cwd=ROOT,capture_output=True,text=True)
        book=ROOT/args.output/'compensation.xlsx'
        # A bundled renderer can return a nonzero shutdown status after export.
        # Accept it only when its success marker and independent saved-file audit pass.
        if completed.returncode and '"verification":"All monetary formulas and ranks match pipeline' not in completed.stdout:
            raise RuntimeError(completed.stderr or completed.stdout or 'Workbook export failed')
        audit=verify_saved_workbook(book,result)
        audit['authoring_process_exit_code']=completed.returncode
        (ROOT/args.output/'saved_workbook_validation.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        print(completed.stdout.strip())
        if completed.returncode:
            message=f'Workbook renderer returned Windows shutdown status {completed.returncode} after export; independent saved-file checks passed.'
            print(message)
            with (ROOT/args.output/'run_report.md').open('a',encoding='utf-8') as report: report.write('\n## Workbook verification\n'+message+'\n')
    print(f'{len(result["records"])} records; {len(result["unresolved"])} unresolved items; {ROOT/args.output}')

if __name__=='__main__': main()
