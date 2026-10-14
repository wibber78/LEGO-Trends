import os, json, time, threading
from datetime import datetime, date, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import requests

app=FastAPI(title='Retired Sets Trends Radar')

@app.get('/logo.png', include_in_schema=False)
def logo():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'logo.png'), media_type='image/png')
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
      'days_to_exit':days,'score':score,'investment_label':('Good Investment' if score>=65 else 'Possible Investment' if score>=40 else 'Not worth investing'),'score_breakdown':{'retirement':retirement,'rating':popularity,'interest':interest,'data':confidence},
      'owned_count':owned,'wanted_count':wanted,'rating':rating,'image':image.get('thumbnailURL') or image.get('imageURL'),
      'brickset_url':f'https://brickset.com/sets/{number}-{variant}'}

def load_catalog(year, theme, max_pages):
    items=[]; matches=0
    for page in range(1,max_pages+1):
        p={'year':str(year),'pageSize':500,'pageNumber':page}
        if theme:p['theme']=theme
        data=fetch(p)
        matches+=0 if page>1 else int(data.get('matches') or 0)
        batch=data.get('sets') or []
        items.extend(batch)
        if len(batch)<500:break
    return items,matches

@app.get('/api/radar')
def radar(year:str='',theme:str='',window:int=365,max_pages:int=3):
    if window not in (90,180,365,730):raise HTTPException(400,'Invalid window')
    max_pages=max(1,min(max_pages,5))
    this_year=date.today().year
    if not year.strip():
        raise HTTPException(400, 'Release year is required')
    try:
        selected_year=int(year)
    except ValueError:
        raise HTTPException(400, 'Invalid release year')
    if not 2000<=selected_year<=this_year+2:
        raise HTTPException(400, 'Invalid release year')
    years=[selected_year]
    items=[];matches=0
    for y in years:
        batch,total=load_catalog(y,theme.strip()[:70],max_pages)
        items.extend(batch);matches+=total
    result=[normalize(x) for x in items]
    candidates=[x for x in result if x['days_to_exit'] is not None and 0<=x['days_to_exit']<=window]
    candidates.sort(key=lambda x:(-x['score'],x['days_to_exit']))
    return {'year':year or None,'years_scanned':years,'theme':theme,'window':window,'scanned':len(items),
            'matches':matches,'truncated':len(items)<matches,'candidates':candidates[:20],
            'total_candidates':len(candidates),'note':'Screening heuristic only; not a market value or investment forecast.'}

@app.get('/',response_class=HTMLResponse)
def home():
 return HTML

HTML=r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Retired Sets | Trends Radar</title><style>
:root{--yellow:#ffe500;--dark:#131717;--line:#e4e5e5}*{box-sizing:border-box}body{font:15px system-ui,-apple-system,Arial,sans-serif;margin:0;background:#f4f5f4;color:#202424}header{background:var(--dark);color:white;padding:26px 20px}header .wrap{max-width:1150px;margin:auto}header h1{font-size:clamp(27px,5vw,42px);margin:0;color:var(--yellow);font-weight:900;letter-spacing:-1px}header p{margin:5px 0 0;color:#ddd}.brandlogo{display:block;width:min(410px,100%);height:auto;margin:0 0 13px}.header-title{font-size:clamp(22px,4vw,31px);font-weight:850;color:var(--yellow);margin:0}main{max-width:1150px;margin:auto;padding:24px 16px}section{background:white;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px}h2{font-size:20px;margin:0 0 14px}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end}.controls label{display:grid;gap:5px;font-weight:600}.controls input,.controls select{padding:11px;border:1px solid #bbb;border-radius:8px;min-width:120px}button{background:var(--yellow);color:#111;border:0;border-radius:8px;padding:12px 16px;font-weight:800;cursor:pointer}button:hover{filter:brightness(.96)}.muted{color:#646969}.small{font-size:12px}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.stat{background:#f4f5f4;border-radius:10px;padding:12px 18px;min-width:150px}.stat strong{display:block;font-size:24px}.cards{display:flex;flex-direction:column;gap:12px}.card{border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;align-items:center;gap:20px}.cardbody{flex:1;min-width:0}.card .line{max-width:520px}.card img{width:150px;height:125px;object-fit:contain;flex-shrink:0}.card h3{font-size:16px;margin:8px 0}.pill{border-radius:12px;padding:5px 10px;font-weight:800;font-size:12px;display:inline-block}.pill.good{background:#d7f5e1;color:#116b36}.pill.possible{background:#fff0a0;color:#6b5300}.pill.neutral{background:#e9ebeb;color:#505656}.scoregrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}.scoreitem{background:#f5f6f5;border-radius:8px;padding:9px 10px}.scoreitem small{display:block;color:#5c6363;margin-bottom:3px}.scoreitem b{font-size:15px}.scoretotal{font-size:12px;color:#626969;margin-top:5px}.line{display:flex;justify-content:space-between;gap:12px;margin:7px 0}.empty{padding:20px;background:#f5f5f5;border-radius:10px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:680px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left}th{background:#f5f5f5}a{color:#333}input[type=file]{max-width:100%}.note{font-size:13px;color:#666;margin-top:12px}#error{color:#9d1414;font-weight:700}footer{text-align:center;color:#777;font-size:12px;padding:0 12px 25px}@media(max-width:750px){.scoregrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){header{padding:20px 16px}main{padding:14px 10px}section{padding:14px}.card{align-items:flex-start;gap:12px}.card img{width:90px;height:95px}.card .line{font-size:13px}}</style></head><body>
<header><div class="wrap"><img class="brandlogo" src="/logo.png" alt="Retired Sets — The home of retired LEGO"><div class="header-title">TRENDS RADAR</div><p>Retirement intelligence • Buying opportunities</p></div></header><main>
<section><h2>Find buying opportunities</h2><div class="controls"><label>Release year (required)<input id="year" type="number" min="2000" max="2100" required placeholder="e.g. 2025"></label><label>Theme (optional)<input id="theme" placeholder="e.g. Star Wars"></label><label>Retirement window<select id="window"><option value="90">Next 90 days</option><option value="180">Next 6 months</option><option value="365" selected>Next 12 months</option><option value="730">Next 24 months</option></select></label><button onclick="loadRadar()">Scan Brickset</button></div><p class="note">Enter a release year to search sets from that year only (up to three Brickset pages per search), helping conserve API calls.</p><div id="error"></div><div id="stats" class="stats"></div><div id="results" class="cards"></div></section>
<section><h2>How to interpret the scores</h2><p>Labels are screening categories: Good Investment (65–90), Possible Investment (40–64), and Not worth investing (0–39). They are not recommendations to buy or guarantees of profit. Scores combine retirement proximity (up to 40), Brickset rating (up to 20), wanted-versus-owned interest (up to 20), and UK RRP availability (10). Scores are <b>screening signals, not resale price forecasts</b>. No automatic claim is made that inventory is appreciating. Review actual sold prices before purchasing.</p><p class="note">Results are cached for six hours in each running instance to conserve Brickset API calls. Future versions can add scheduled historical snapshots and approved community data sources.</p></section>
</main><footer>Retired Sets Trends Radar • Powered by Brickset catalogue data</footer><script>
const el=id=>document.getElementById(id);const gbp=n=>n==null?'—':new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(n);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function loadRadar(){if(!el('year').value.trim()){el('error').textContent='Please enter a release year.';el('year').focus();return;}el('error').textContent='';el('results').innerHTML='';el('stats').textContent='Loading Brickset data…';try{let q=new URLSearchParams({year:el('year').value,theme:el('theme').value,window:el('window').value});let r=await fetch('/api/radar?'+q),d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');el('stats').innerHTML=`<div class="stat"><strong>${d.scanned}</strong>sets scanned</div><div class="stat"><strong>${d.total_candidates}</strong>retirement candidates</div><div class="stat"><strong>${d.candidates.length}</strong>shown (top 20)</div><div class="stat"><strong>${d.matches}</strong>catalogue matches</div><div class="stat"><strong>${d.years_scanned.join(", ")}</strong>release years scanned</div>`;if(d.truncated)el('error').textContent='Partial catalogue: narrow the theme or scan smaller ranges.';el('results').innerHTML=d.candidates.length?d.candidates.map((x,i)=>`<div class="card">${x.image?`<img src="${esc(x.image)}" alt="${esc(x.name)}" loading="lazy">`:''}<div class="cardbody"><span class="pill ${x.score>=65?'good':x.score>=40?'possible':'neutral'}">#${i+1} · ${esc(x.investment_label)}</span><h3>${esc(x.name)} · ${esc(x.number)}</h3><div class="line"><span>Theme</span><b>${esc(x.theme)}</b></div><div class="line"><span>UK RRP</span><b>${gbp(x.rrp)}</b></div><div class="line"><span>Retirement</span><b>${esc(x.exit_date||'Unknown')}</b></div><div class="line"><span>Days remaining</span><b>${x.days_to_exit}</b></div><div class="scoregrid"><div class="scoreitem"><small>Retirement proximity</small><b>${x.score_breakdown.retirement} / 40</b></div><div class="scoreitem"><small>Brickset rating</small><b>${x.score_breakdown.rating} / 20</b></div><div class="scoreitem"><small>Collector interest</small><b>${x.score_breakdown.interest} / 20</b></div><div class="scoreitem"><small>UK RRP available</small><b>${x.score_breakdown.data} / 10</b></div></div><div class="scoretotal">Screening score: ${x.score} / 90 · Based on available Brickset data</div><a href="${esc(x.brickset_url)}" target="_blank" rel="noopener noreferrer">View on Brickset →</a></div></div>`).join(''):'<div class="empty">No retirement candidates found in this scan. Try a wider window, another theme, or a different release year.</div>';}catch(e){el('stats').textContent='';el('error').textContent=e.message}}
</script></body></html>'''
