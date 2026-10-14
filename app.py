import os, json, time, threading
from datetime import datetime, date, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import requests

app=FastAPI(title='Retired Sets Trends Radar')
API='https://brickset.com/api/v3.asmx/getSets'
CACHE={}; LOCK=threading.Lock(); TTL=3600*6

def fetch(params):
    key=os.getenv('BRICKSET_API_KEY')
    if not key: raise HTTPException(503,'Set BRICKSET_API_KEY in Railway Variables.')
    k=json.dumps(params,sort_keys=True)
    with LOCK:
        hit=CACHE.get(k)
        if hit and time.time()-hit[0]<TTL:return hit[1]
    try:
        r=requests.post(API,data={'apiKey':key,'userHash':'','params':json.dumps(params)},timeout=25)
        r.raise_for_status(); data=r.json()
    except (requests.RequestException,ValueError) as e:raise HTTPException(502,f'Brickset request failed: {e}')
    if data.get('status')!='success':raise HTTPException(502,data.get('message','Brickset API error'))
    with LOCK:CACHE[k]=(time.time(),data)
    return data

def parse_date(v):
    if not v:return None
    try:return date.fromisoformat(str(v)[:10])
    except ValueError:return None

def money(v):
    try:return round(float(str(v).replace('£','').replace(',','')),2)
    except (TypeError,ValueError):return None

def normalize(s):
    uk=(s.get('LEGOCom') or {}).get('UK') or {}
    exit_d=parse_date(uk.get('dateLastAvailable') or s.get('exitDate'))
    launch=parse_date(uk.get('dateFirstAvailable') or s.get('launchDate'))
    today=date.today()
    if exit_d and exit_d<today: status='Retired'
    elif s.get('released') is False:status='Not released'
    elif exit_d:status='Planned retirement'
    else:status='Current / unconfirmed'
    days=(exit_d-today).days if exit_d else None
    retail=money(uk.get('retailPrice'))
    owned=s.get('ownedBy') or s.get('ownCount') or 0
    wanted=s.get('wantedBy') or s.get('wantCount') or 0
    # This is an intentionally simple transparent screening score, not a forecast.
    retirement=40 if days is not None and 0<=days<=90 else 30 if days is not None and 90<days<=180 else 20 if days is not None and 180<days<=365 else 0
    rating=s.get('rating') or 0
    if isinstance(rating,dict):rating=rating.get('overall') or 0
    try:rating=float(rating)
    except (ValueError,TypeError):rating=0
    popularity=min(20,round(rating*4))
    try:ratio=float(wanted)/(float(owned)+1)
    except (ValueError,TypeError,ZeroDivisionError):ratio=0
    interest=min(20,round(ratio*100))
    confidence=10 if retail is not None else 0
    score=retirement+popularity+interest+confidence
    image=s.get('image') or {}
    number=str(s.get('number') or '')
    variant=s.get('numberVariant') or 1
    return {'number':number,'name':s.get('name') or number,'theme':s.get('theme') or '', 'year':s.get('year'),
      'rrp':retail,'status':status,'exit_date':exit_d.isoformat() if exit_d else None,'launch_date':launch.isoformat() if launch else None,
      'days_to_exit':days,'score':score,'score_breakdown':{'retirement':retirement,'rating':popularity,'interest':interest,'data':confidence},
      'owned_count':owned,'wanted_count':wanted,'rating':rating,'image':image.get('thumbnailURL') or image.get('imageURL'),
      'brickset_url':f'https://brickset.com/sets/{number}-{variant}'}

def load_catalog(year,theme,max_pages):
    items=[];matches=0
    for page in range(1,max_pages+1):
        p={'year':str(year),'pageSize':500,'pageNumber':page}
        if theme:p['theme']=theme
        data=fetch(p);matches=data.get('matches',0)
        batch=data.get('sets') or []
        items.extend(batch)
        if len(batch)<500:break
    return items,matches

@app.get('/api/radar')
def radar(year:int=date.today().year,theme:str='',window:int=365,max_pages:int=3):
    if not 2000<=year<=date.today().year+2:raise HTTPException(400,'Invalid year')
    if window not in (90,180,365,730):raise HTTPException(400,'Invalid window')
    max_pages=max(1,min(max_pages,5))
    items,matches=load_catalog(year,theme.strip()[:70],max_pages)
    result=[normalize(x) for x in items]
    # Rank retirement candidates from the scanned catalogue.
    candidates=[x for x in result if x['days_to_exit'] is not None and 0<=x['days_to_exit']<=window]
    candidates.sort(key=lambda x:(-x['score'],x['days_to_exit']))
    return {'year':year,'theme':theme,'window':window,'scanned':len(items),'matches':matches,'truncated':len(items)<matches,
            'candidates':candidates,'note':'Score is a screening heuristic, not a price forecast. Retirement dates are based on Brickset records.'}

@app.get('/api/usage')
def usage():
    key=os.getenv('BRICKSET_API_KEY')
    if not key:raise HTTPException(503,'Set BRICKSET_API_KEY in Railway Variables.')
    try:
        response=requests.post('https://brickset.com/api/v3.asmx/getKeyUsageStats',data={'apiKey':key},timeout=15)
        response.raise_for_status()
        data=response.json()
        if data.get('status') not in (None,'success'):
            raise HTTPException(502,data.get('message','Brickset usage lookup failed'))
        # Return the provider's values unchanged: field names/allowances can change.
        return {'status':'ok','usage':data,'note':'Brickset-reported usage for the shared API key; includes other apps using this key.'}
    except (requests.RequestException,ValueError) as e:
        raise HTTPException(502,f'Unable to retrieve Brickset usage: {e}')

@app.get('/',response_class=HTMLResponse)
def home():
 return HTML

HTML=r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Retired Sets | Trends Radar</title><style>
:root{--yellow:#ffe500;--dark:#131717;--line:#e4e5e5}*{box-sizing:border-box}body{font:15px system-ui,-apple-system,Arial,sans-serif;margin:0;background:#f4f5f4;color:#202424}header{background:var(--dark);color:white;padding:26px 20px}header .wrap{max-width:1150px;margin:auto}header h1{font-size:clamp(27px,5vw,42px);margin:0;color:var(--yellow);font-weight:900;letter-spacing:-1px}header p{margin:5px 0 0;color:#ddd}main{max-width:1150px;margin:auto;padding:24px 16px}section{background:white;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px}h2{font-size:20px;margin:0 0 14px}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end}.controls label{display:grid;gap:5px;font-weight:600}.controls input,.controls select{padding:11px;border:1px solid #bbb;border-radius:8px;min-width:120px}button{background:var(--yellow);color:#111;border:0;border-radius:8px;padding:12px 16px;font-weight:800;cursor:pointer}button:hover{filter:brightness(.96)}.muted{color:#646969}.small{font-size:12px}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.stat{background:#f4f5f4;border-radius:10px;padding:12px 18px;min-width:150px}.stat strong{display:block;font-size:24px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}.card{border:1px solid var(--line);border-radius:12px;padding:14px}.card img{width:100%;height:140px;object-fit:contain}.card h3{font-size:16px;margin:8px 0}.pill{background:#fff3a3;border-radius:12px;padding:4px 9px;font-weight:700;font-size:12px;display:inline-block}.line{display:flex;justify-content:space-between;gap:12px;margin:7px 0}.empty{padding:20px;background:#f5f5f5;border-radius:10px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:680px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left}th{background:#f5f5f5}a{color:#333}input[type=file]{max-width:100%}.note{font-size:13px;color:#666;margin-top:12px}#error{color:#9d1414;font-weight:700}footer{text-align:center;color:#777;font-size:12px;padding:0 12px 25px}@media(max-width:600px){header{padding:20px 16px}main{padding:14px 10px}section{padding:14px}}</style></head><body>
<header><div class="wrap"><h1>RETIRED SETS <span style="color:white">/ TRENDS RADAR</span></h1><p>Retirement intelligence • Buying opportunities</p></div></header><main>
<section><h2>Find buying opportunities</h2><div class="controls"><label>Release year<input id="year" type="number" min="2000" max="2100"></label><label>Theme (optional)<input id="theme" placeholder="e.g. Star Wars"></label><label>Retirement window<select id="window"><option value="90">Next 90 days</option><option value="180">Next 6 months</option><option value="365" selected>Next 12 months</option><option value="730">Next 24 months</option></select></label><button onclick="loadRadar()">Scan Brickset</button></div><p class="note">Select a release year. The scan checks sets from that year, not the entire LEGO catalogue. Run multiple years to broaden coverage.</p><div id="error"></div><div id="stats" class="stats"></div><div id="results" class="cards"></div></section>
<section><h2>Brickset API usage</h2><p class="muted">Usage is shared with your Price Checker because both applications use the same API key.</p><div class="controls"><button onclick="loadUsage()">Refresh API usage</button></div><p id="usageStatus" class="note">Loading usage information…</p><div id="usageData" class="stats"></div></section>
<section><h2>How to interpret the scores</h2><p>Opportunity scores combine retirement proximity (up to 40), Brickset rating (up to 20), wanted-versus-owned interest (up to 20), and UK RRP availability (10). Scores are <b>screening signals, not resale price forecasts</b>. No automatic claim is made that inventory is appreciating. Review actual sold prices before purchasing.</p><p class="note">Results are cached for six hours in each running instance to conserve Brickset API calls. Future versions can add scheduled historical snapshots and approved community data sources.</p></section>
</main><footer>Retired Sets Trends Radar • Powered by Brickset catalogue data</footer><script>
const el=id=>document.getElementById(id);el('year').value=new Date().getFullYear();const gbp=n=>n==null?'—':new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(n);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function loadRadar(){el('error').textContent='';el('results').innerHTML='';el('stats').textContent='Loading Brickset data…';try{let q=new URLSearchParams({year:el('year').value,theme:el('theme').value,window:el('window').value});let r=await fetch('/api/radar?'+q),d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');el('stats').innerHTML=`<div class="stat"><strong>${d.scanned}</strong>sets scanned</div><div class="stat"><strong>${d.candidates.length}</strong>retirement candidates</div><div class="stat"><strong>${d.matches}</strong>catalogue matches</div>`;if(d.truncated)el('error').textContent='Partial catalogue: narrow the theme or scan smaller ranges.';el('results').innerHTML=d.candidates.length?d.candidates.map(x=>`<div class="card">${x.image?`<img src="${esc(x.image)}" alt="${esc(x.name)}" loading="lazy">`:''}<span class="pill">Opportunity ${x.score}/90</span><h3>${esc(x.name)} · ${esc(x.number)}</h3><div class="line"><span>Theme</span><b>${esc(x.theme)}</b></div><div class="line"><span>UK RRP</span><b>${gbp(x.rrp)}</b></div><div class="line"><span>Retirement</span><b>${esc(x.exit_date||'Unknown')}</b></div><div class="line"><span>Days remaining</span><b>${x.days_to_exit}</b></div><a href="${esc(x.brickset_url)}" target="_blank" rel="noopener noreferrer">View on Brickset →</a></div>`).join(''):'<div class="empty">No retirement candidates found in this release-year/theme scan. Try another year or a wider window.</div>';}catch(e){el('stats').textContent='';el('error').textContent=e.message}}
async function loadUsage(){el('usageStatus').textContent='Checking Brickset usage…';el('usageData').innerHTML='';try{const r=await fetch('/api/usage');const d=await r.json();if(!r.ok)throw Error(d.detail||'Usage request failed');const u=d.usage||{};const flat=[];function walk(obj,prefix,depth){if(depth>3||!obj||typeof obj!=='object')return;for(const [k,v] of Object.entries(obj)){if(['status','message'].includes(k))continue;if(v&&typeof v==='object')walk(v,prefix?prefix+' / '+k:k,depth+1);else if(v!==null&&v!==''&&['string','number','boolean'].includes(typeof v))flat.push([prefix?prefix+' / '+k:k,v]);}}walk(u,'',0);el('usageData').innerHTML=flat.length?flat.map(([k,v])=>`<div class="stat"><span class="small muted">${esc(k)}</span><strong>${esc(v)}</strong></div>`).join(''):'<p class="muted">Brickset returned no usage figures.</p>';el('usageStatus').textContent='Latest usage reported by Brickset (shared key).';}catch(e){el('usageStatus').textContent='Could not retrieve usage: '+e.message;}}
loadUsage();
</script></body></html>'''
