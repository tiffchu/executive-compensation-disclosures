"""Download primary evidence only; no extraction or substitutions."""
from pathlib import Path
from urllib.request import Request, urlopen
import json, hashlib
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from execcomp.documents import fetch
URLS = {
 'fx_annual_2025.json':'https://www.bankofcanada.ca/valet/observations/group/FX_RATES_ANNUAL/json?start_date=2025-01-01&end_date=2025-12-31',
 'b2gold_financials.pdf':'https://s204.q4cdn.com/324791784/files/doc_financials/2026/ar/Compliled-BTG-12-31-25-40-F-March-11-2026.pdf',
 'b2gold_circular.pdf':'https://s204.q4cdn.com/324791784/files/doc_downloads/2026/04/B2Gold-MIC-FYE-December-31-2025.pdf',
 'b2gold_financials_index.html':'https://www.b2gold.com/investors/financials/',
 'interfor_circular.pdf':'https://interfor.com/wp-content/uploads/2026/03/Information-Circular.pdf',
 'interfor_financials.pdf':'https://interfor.com/wp-content/uploads/2026/02/Annual-Financial-Statements.pdf',
 'methanex_circular.pdf':'https://www.methanex.com/wp-content/uploads/2026-Information-Circular.pdf',
 'methanex_financials.pdf':'https://www.methanex.com/wp-content/uploads/2025-Annual-Report.pdf',
 'b2gold_agm.html':'https://www.b2gold.com/investors/agm/default.aspx',
}
if __name__ == '__main__':
 failures=0
 for name, url in URLS.items():
  path=ROOT/'data/documents'/name
  if path.exists(): continue
  try:
   data=fetch(url)
   if name.endswith('.pdf') and not data.startswith(b'%PDF'): raise ValueError('Not a PDF')
   path.write_bytes(data)
   path.with_suffix(path.suffix+'.meta.json').write_text(json.dumps({'url':url,'filename':name,'sha256':hashlib.sha256(data).hexdigest(),'retrieved_at':datetime.now().astimezone().isoformat()},indent=2))
   print(name,len(data))
  except Exception as exc:
   failures+=1; print(name, type(exc).__name__, str(exc))
 sys.exit(1 if failures else 0)
