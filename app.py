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
THEMES_API='https://brickset.com/api/v3.asmx/getThemes'
THEMES_CACHE={'time':0,'themes':None}
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

@app.get('/api/themes')
def get_themes():
    """Fetch the official Brickset theme names, cached for 24 hours."""
    with LOCK:
        if THEMES_CACHE['themes'] is not None and time.time()-THEMES_CACHE['time']<86400:
            return {'themes':THEMES_CACHE['themes']}
    key=os.getenv('BRICKSET_API_KEY')
    if not key: raise HTTPException(503,'Set BRICKSET_API_KEY in Railway Variables.')
    try:
        response=requests.post(THEMES_API,data={'apiKey':key},timeout=25)
        response.raise_for_status()
        payload=response.json()
    except (requests.RequestException,ValueError) as exc:
        raise HTTPException(502,f'Could not load Brickset themes: {exc}')
    if payload.get('status')!='success':
        raise HTTPException(502,payload.get('message','Brickset themes unavailable'))
    themes=sorted({str(item.get('theme') or item.get('name') or '').strip()
                   for item in payload.get('themes',[]) if isinstance(item,dict)}- {''},key=str.casefold)
    with LOCK:THEMES_CACHE.update(time=time.time(),themes=themes)
    return {'themes':themes}

def parse_date(v):
    if not v:return None
    try:return date.fromisoformat(str(v)[:10])
    except ValueError:return None

def money(v):
    try:return round(float(str(v).replace('£','').replace(',','')),2)
    except (TypeError,ValueError):return None

def numeric(value):
    if isinstance(value, bool): return None
    try:
        if value is None or str(value).strip() == '': return None
        return float(str(value).replace(',', ''))
    except (TypeError, ValueError): return None

def get_first(source, *names):
    if not isinstance(source, dict): return None
    for name in names:
        value = source.get(name)
        if value is not None: return value
    return None

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
    collections=s.get('collections') or {}
    owned=numeric(get_first(collections,'ownedBy','ownCount'))
    wanted=numeric(get_first(collections,'wantedBy','wantCount'))
    # Older/alternative payloads may expose the counts at the top level.
    if owned is None: owned=numeric(get_first(s,'ownedBy','ownCount'))
    if wanted is None: wanted=numeric(get_first(s,'wantedBy','wantCount'))
    rating_data=s.get('rating')
    if isinstance(rating_data,dict):
        rating=numeric(get_first(rating_data,'overall','rating','average'))
        votes=numeric(get_first(rating_data,'votes','voteCount','count','ratingCount'))
    else:
        rating=numeric(rating_data)
        votes=None
    if votes is None: votes=numeric(get_first(s,'ratingCount','votes','voteCount'))
    if rating is not None and not (0 <= rating <= 5): rating=None
    if votes is not None and votes < 0: votes=None
    image=s.get('image') or {}
    number=str(s.get('number') or '')
    variant=s.get('numberVariant') or 1
    return {'number':number,'name':s.get('name') or number,'theme':s.get('theme') or '', 'year':s.get('year'),
      'rrp':retail,'status':status,'exit_date':exit_d.isoformat() if exit_d else None,'launch_date':launch.isoformat() if launch else None,
      'days_to_exit':days,'owned_count':int(owned) if owned is not None else None,
      'wanted_count':int(wanted) if wanted is not None else None,
      'rating':rating,'rating_count':int(votes) if votes is not None else None,
      'image':image.get('thumbnailURL') or image.get('imageURL'),
      'brickset_url':f'https://brickset.com/sets/{number}-{variant}'}

def percentile(value, cohort):
    """Midrank percentile within the scanned retirement candidates; ties share a score."""
    if value is None or not cohort: return None
    if len(cohort)==1: return 0.5
    less=sum(v < value for v in cohort)
    equal=sum(v == value for v in cohort)
    return (less + (equal-1)/2) / (len(cohort)-1)

def rank_candidates(candidates):
    # Compare only within the current search result, not against the entire LEGO catalogue.
    wanted_values=[x['wanted_count'] for x in candidates if x['wanted_count'] is not None]
    ratios=[x['wanted_count']/(x['owned_count']+1) for x in candidates
            if x['wanted_count'] is not None and x['owned_count'] is not None]
    for x in candidates:
        rating=x['rating']
        rating_pts=round(40*rating/5) if rating is not None else None
        demand_pct=percentile(x['wanted_count'],wanted_values)
        demand_pts=round(30*demand_pct) if demand_pct is not None else None
        ratio=(x['wanted_count']/(x['owned_count']+1)
               if x['wanted_count'] is not None and x['owned_count'] is not None else None)
        ratio_pct=percentile(ratio,ratios)
        ratio_pts=round(20*ratio_pct) if ratio_pct is not None else None
        # A saturation curve avoids giving tiny samples full confidence.
        # 25 ratings ~= 5/10; 100 ratings ~= 8/10.
        votes=x['rating_count']
        confidence_pts=round(10*votes/(votes+25)) if votes is not None else None
        breakdown={'rating':rating_pts,'demand':demand_pts,'ratio':ratio_pts,'confidence':confidence_pts}
        available=sum(weight for key,weight in [('rating',40),('demand',30),('ratio',20),('confidence',10)] if breakdown[key] is not None)
        earned=sum(p for p in breakdown.values() if p is not None)
        # Normalize only when adequate underlying information exists.
        score=round(earned*100/available) if available>=70 else None
        if score is None: label='Insufficient data'
        elif score>=70: label='Strong Collector Demand'
        elif score>=40: label='Moderate Collector Demand'
        else: label='Limited Collector Demand'
        x.update(score=score, collector_label=label, score_breakdown=breakdown,
                 available_points=available, wanted_owned_ratio=round(ratio,3) if ratio is not None else None)
    candidates.sort(key=lambda x:(x['score'] is None,-(x['score'] or 0),-(x['available_points']),x['days_to_exit']))
    return candidates

def load_catalog(year, theme, query, max_pages):
    items=[]; matches=0
    for page in range(1,max_pages+1):
        p={'year':str(year),'pageSize':500,'pageNumber':page}
        if theme:p['theme']=theme
        if query:p['query']=query
        data=fetch(p)
        matches+=0 if page>1 else int(data.get('matches') or 0)
        batch=data.get('sets') or []
        items.extend(batch)
        if len(batch)<500:break
    return items,matches

@app.get('/api/radar')
def radar(year:str='',theme:str='',query:str='',window:int=365,max_pages:int=3):
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
        batch,total=load_catalog(y,theme.strip()[:70],query.strip()[:100],max_pages)
        items.extend(batch);matches+=total
    result=[normalize(x) for x in items]
    candidates=[x for x in result if x['days_to_exit'] is not None and 0<=x['days_to_exit']<=window]
    rank_candidates(candidates)
    return {'year':year or None,'years_scanned':years,'theme':theme,'query':query,'window':window,'scanned':len(items),
            'matches':matches,'truncated':len(items)<matches,'candidates':candidates[:20],
            'total_candidates':len(candidates),'note':'Relative collector-demand screen, not a market value or investment forecast. Missing information is labelled, and scores compare sets in this search.'}

@app.get('/',response_class=HTMLResponse)
def home():
 return HTML

HTML=r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Retired Sets | Trends Radar</title><style>
:root{--yellow:#ffe500;--dark:#131717;--line:#e4e5e5}*{box-sizing:border-box}body{font:15px system-ui,-apple-system,Arial,sans-serif;margin:0;background:#f4f5f4;color:#202424}header{background:var(--dark);color:white;padding:26px 20px}header .wrap{max-width:1150px;margin:auto;text-align:center}header h1{font-size:clamp(27px,5vw,42px);margin:0;color:var(--yellow);font-weight:900;letter-spacing:-1px}header p{margin:5px 0 0;color:#ddd}.brandlogo{display:block;width:min(410px,100%);height:auto;margin:0 auto 13px}.header-title{font-size:clamp(22px,4vw,31px);font-weight:850;color:var(--yellow);margin:0}main{max-width:1150px;margin:auto;padding:24px 16px}section{background:white;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px}h2{font-size:20px;margin:0 0 14px}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end}.controls label{display:grid;gap:5px;font-weight:600}.controls input,.controls select{padding:11px;border:1px solid #bbb;border-radius:8px;min-width:120px}button{background:var(--yellow);color:#111;border:0;border-radius:8px;padding:12px 16px;font-weight:800;cursor:pointer}button:hover{filter:brightness(.96)}.muted{color:#646969}.small{font-size:12px}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.stat{background:#f4f5f4;border-radius:10px;padding:12px 18px;min-width:150px}.stat strong{display:block;font-size:24px}.cards{display:flex;flex-direction:column;gap:12px}.card{border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;align-items:center;gap:20px}.cardbody{flex:1;min-width:0}.card .line{max-width:520px}.card img{width:150px;height:125px;object-fit:contain;flex-shrink:0}.card h3{font-size:16px;margin:8px 0}.pill{border-radius:12px;padding:5px 10px;font-weight:800;font-size:12px;display:inline-block}.pill.good{background:#d7f5e1;color:#116b36}.pill.possible{background:#fff0a0;color:#6b5300}.pill.neutral{background:#e9ebeb;color:#505656}.pill.unknown{background:#ececec;color:#555}.scoregrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.scoreitem{background:#f5f6f5;border-radius:8px;padding:9px 10px}.scoreitem small{display:block;color:#5c6363;margin-bottom:3px}.scoreitem b{font-size:15px}.scoretotal{font-size:12px;color:#626969;margin-top:5px}.line{display:flex;justify-content:space-between;gap:12px;margin:7px 0}.empty{padding:20px;background:#f5f5f5;border-radius:10px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:680px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left}th{background:#f5f5f5}a{color:#333}input[type=file]{max-width:100%}.note{font-size:13px;color:#666;margin-top:12px}#error{color:#9d1414;font-weight:700}footer{text-align:center;color:#777;font-size:12px;padding:0 12px 25px}@media(max-width:750px){.scoregrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){header{padding:20px 16px}main{padding:14px 10px}section{padding:14px}.card{align-items:flex-start;gap:12px}.card img{width:90px;height:95px}.card .line{font-size:13px}}</style></head><body>
<header><div class="wrap"><img class="brandlogo" src="/logo.png" alt="Retired Sets — The home of retired LEGO"><div class="header-title">TRENDS RADAR</div><p>Collector demand • Retirement intelligence</p></div></header><main>
<section><h2>Find collector demand among retiring sets</h2><div class="controls"><label>Release year (required)<input id="year" type="number" min="2000" max="2100" required placeholder="e.g. 2025"></label><label>Theme (optional)<input id="theme" list="themeOptions" autocomplete="off" placeholder="Type or choose a theme"><datalist id="themeOptions"></datalist></label><label>Keyword (optional)<input id="query" placeholder="e.g. Formula 1"></label><label>Retirement window<select id="window"><option value="90">Next 90 days</option><option value="180">Next 6 months</option><option value="365" selected>Next 12 months</option><option value="730">Next 24 months</option></select></label><button onclick="loadRadar()">Scan Brickset</button></div><p class="note">Select a Brickset theme from the suggestions, or leave it blank. For Formula 1 cars, try keyword <b>Formula 1</b> with no theme, or combine it with Speed Champions or Technic. Release year is required. Up to three catalogue pages per search.</p><p id="themeHelp" class="note"></p><div id="error"></div><div id="stats" class="stats"></div><div id="results" class="cards"></div></section>
<section><h2>How to interpret the scores</h2><p>The <b>Collector Demand Score</b> uses Brickset rating (40 points), wanted-by count relative to the sets in this search (30), wanted-to-owned ratio relative to this search (20), and number of ratings (10). The rating count is used to assess confidence in the rating, not demand itself.</p><p>Strong Collector Demand (70–100), Moderate Collector Demand (40–69), Limited Collector Demand (0–39). If less than 70 points' worth of source data is available, the result is labelled <b>Insufficient data</b> rather than given a misleading ranking. The displayed score is adjusted for available data, and its coverage is shown.</p><p class="note">The comparisons are relative to the retirement candidates in this specific scan. A set may score differently when you change the theme or retirement window. Retirement date and UK RRP are informational only and do not influence the score. Brickset members are not representative of all LEGO buyers; this is not a resale-price forecast or investment recommendation.</p><p class="note">Results are cached for six hours per running instance to conserve Brickset API calls. No extra per-set requests are made for the collector statistics.</p></section>
</main><footer>Retired Sets Trends Radar • Powered by Brickset catalogue data</footer><script>
const el=id=>document.getElementById(id);const gbp=n=>n==null?'—':new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(n);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function loadThemes(){
 try {const r=await fetch('/api/themes');const d=await r.json();if(!r.ok)throw Error(d.detail||'Could not load themes');
 el('themeOptions').innerHTML=d.themes.map(t=>`<option value="${esc(t)}"></option>`).join('');
 }catch(e){el('themeHelp').textContent='Theme suggestions unavailable; you can still type a theme or use a keyword.';}}
loadThemes();
async function loadRadar(){if(!el('year').value.trim()){el('error').textContent='Please enter a release year.';el('year').focus();return;}el('error').textContent='';el('results').innerHTML='';el('stats').textContent='Loading Brickset data…';try{let q=new URLSearchParams({year:el('year').value,theme:el('theme').value,query:el('query').value,window:el('window').value});let r=await fetch('/api/radar?'+q),d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');el('stats').innerHTML=`<div class="stat"><strong>${d.scanned}</strong>sets scanned</div><div class="stat"><strong>${d.total_candidates}</strong>retirement candidates</div><div class="stat"><strong>${d.candidates.length}</strong>shown (top 20)</div><div class="stat"><strong>${d.matches}</strong>catalogue matches</div><div class="stat"><strong>${d.years_scanned.join(", ")}</strong>release years scanned</div>`;if(d.truncated)el('error').textContent='Partial catalogue: narrow the theme or scan smaller ranges.';el('results').innerHTML=d.candidates.length?d.candidates.map((x,i)=>{const tier=x.score===null?'unknown':x.score>=70?'good':x.score>=40?'possible':'neutral';const fmt=(v,max)=>v==null?'Data unavailable':`${v} / ${max}`;return `<div class="card">${x.image?`<img src="${esc(x.image)}" alt="${esc(x.name)}" loading="lazy">`:''}<div class="cardbody"><span class="pill ${tier}">#${i+1} · ${esc(x.collector_label)}</span><h3>${esc(x.name)} · ${esc(x.number)}</h3><div class="line"><span>Theme</span><b>${esc(x.theme)}</b></div><div class="line"><span>UK RRP</span><b>${gbp(x.rrp)}</b></div><div class="line"><span>Retirement</span><b>${esc(x.exit_date||'Unknown')}</b></div><div class="line"><span>Days remaining</span><b>${x.days_to_exit}</b></div><div class="line"><span>Brickset rating</span><b>${x.rating==null?'Data unavailable':x.rating.toFixed(2)+' / 5'}</b></div><div class="line"><span>Want / Own</span><b>${x.wanted_count==null?'—':x.wanted_count.toLocaleString('en-GB')} / ${x.owned_count==null?'—':x.owned_count.toLocaleString('en-GB')}</b></div><div class="line"><span>Number of ratings</span><b>${x.rating_count==null?'Data unavailable':x.rating_count.toLocaleString('en-GB')}</b></div><div class="scoregrid" style="grid-template-columns:repeat(auto-fit,minmax(130px,1fr))"><div class="scoreitem"><small>Brickset rating</small><b>${fmt(x.score_breakdown.rating,40)}</b></div><div class="scoreitem"><small>Collector demand</small><b>${fmt(x.score_breakdown.demand,30)}</b></div><div class="scoreitem"><small>Demand vs ownership</small><b>${fmt(x.score_breakdown.ratio,20)}</b></div><div class="scoreitem"><small>Rating confidence</small><b>${fmt(x.score_breakdown.confidence,10)}</b></div></div><div class="scoretotal">${x.score===null?'Not ranked: insufficient data':`Collector Demand Score: ${x.score} / 100`} · Data coverage: ${x.available_points} / 100 points · Relative to this scan</div><a href="${esc(x.brickset_url)}" target="_blank" rel="noopener noreferrer">View on Brickset →</a></div></div>`}).join(''):'<div class="empty">No retirement candidates found in this scan. Try a wider window, another theme, or a different release year.</div>';}catch(e){el('stats').textContent='';el('error').textContent=e.message}}
</script></body></html>'''
