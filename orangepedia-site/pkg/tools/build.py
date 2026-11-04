#!/usr/bin/env python3
"""Orangepedia static site builder.
Usage:  python tools/build.py [source_dir] [out_dir]
Drop any saved Orangepedia page (.html) into source/ and re-run — it appears on Home + in search.
"""
import re,sys,os,json,glob,base64,hashlib,urllib.parse,html
from bs4 import BeautifulSoup
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC=sys.argv[1] if len(sys.argv)>1 else os.path.join(ROOT,'source')
OUT=sys.argv[2] if len(sys.argv)>2 else ROOT
os.makedirs(OUT+'/assets/img',exist_ok=True)
ORANGE=re.compile(r'background(?:-color)?:\s*(#f[0-9a-f]{5}|orange)',re.I)
E=html.escape
def slugify(t): return re.sub(r'[^a-z0-9]+','-',t.lower()).strip('-')
def tx(n): return html.unescape(re.sub(r'\s+',' ',n.get_text()).replace('\u200b','')).strip() if n else ''
def href_slug(h):
    last=urllib.parse.unquote((h or '').split('?')[0].rstrip('/').split('/')[-1]).replace('.aspx','')
    return slugify(last.replace('-',' '))
def pretty(h):
    last=urllib.parse.unquote(h.split('?')[0].rstrip('/').split('/')[-1]).replace('.aspx','')
    return re.sub(r'\s+',' ',last.replace('-',' ')).strip()
def full_title(text,h):
    return pretty(h) if text.endswith('...') or text.endswith('…') else text

# ---------- load sources
docs={}
for f in sorted(glob.glob(SRC+'/*.html')):
    soup=BeautifulSoup(open(f,encoding='utf-8',errors='ignore').read(),'lxml')
    raw=open(f,encoding='utf-8',errors='ignore').read()
    kind_m=re.search(r"alt=(Products|Services|Promotions|Devices)\b",raw)
    for t in soup(['script','style','noscript']): t.decompose()
    title=(soup.title.get_text().strip() if soup.title else os.path.basename(f))
    cb=soup.select_one('#contentBox')
    if not cb: continue
    if cb.select_one('.products-container'): typ='home'
    elif cb.select_one('.search-page'): typ='listing'
    elif cb.select_one('.details-header-caption'): typ='article'
    else: continue
    slug='home' if typ=='home' else slugify(title)
    docs[slug]={'type':typ,'title':title,'cb':cb,'kind':kind_m.group(1) if kind_m else 'Products','file':f}
KNOWN={s for s,d in docs.items()}
print('pages:',{s:d['type'] for s,d in docs.items()})

# ---------- rich-html cleaner
imgn=0
def save_img(src,slug):
    m=re.match(r'data:image/(png|jpe?g|gif|webp);base64,(.+)',src,re.S)
    if not m: return None
    data=base64.b64decode(m.group(2)); h=hashlib.md5(data).hexdigest()[:10]
    ext='jpg' if m.group(1).startswith('jp') else m.group(1)
    name=f'assets/img/{slug}-{h}.{ext}'; open(OUT+'/'+name,'wb').write(data); return name
def link_for(h):
    s=href_slug(h)
    return (s+'.html') if s in KNOWN else None
def clean_html(node,slug):
    node=BeautifulSoup(str(node),'lxml').body
    for t in node(['script','style','noscript','input','button','svg']): t.decompose()
    for t in node.select('.sf-hidden,.d-edit-mode,[style*="display:none"]'): t.decompose()
    for im in node.find_all('img'):
        new=save_img(im.get('src') or '',slug)
        if new: im.attrs={'src':new,'alt':im.get('alt',''),'loading':'lazy'}
        else: im.decompose()
    for a in node.find_all('a'):
        h=a.get('href') or ''; a.attrs={k:v for k,v in a.attrs.items() if k=='href'}
        if 'orangepedia' in h or h.startswith('/'):
            l=link_for(h)
            if l: a['href']=l
            else: del a['href']; a['class']='dead'; a['title']='Internal Orangepedia link — page not included in this site'
        elif not h or h.startswith('javascript') or h.startswith('#'):
            a.attrs.pop('href',None)
        else: a['target']='_blank'; a['rel']='noopener'
    for t in node.find_all(True):
        st=t.get('style','') or ''; keep={}
        if t.name in('td','th') and ORANGE.search(st): keep['class']='hd'
        if t.name=='a' and 'class' in t.attrs: keep['class']=t['class']
        for k in('href','src','alt','loading','target','rel','title','colspan','rowspan'):
            if k in t.attrs: keep[k]=t[k]
        if t.name in('p','li','td','th','div','h1','h2','h3','h4') : keep['dir']='auto'
        t.attrs=keep
    for t in node.find_all(['span','font']): t.unwrap()
    for _ in range(3):
        for t in node.find_all(['p','div','strong','b','em','u','li']):
            if not t.get_text(strip=True) and not t.find(['img','table']): t.decompose()
    # header rows of tables: first row all .hd -> th
    for tb in node.find_all('table'):
        rows=tb.find_all('tr')
        if rows and all('hd' in (c.get('class') or []) for c in rows[0].find_all(['td','th'])):
            for c in rows[0].find_all('td'): c.name='th'
            rows[0]['class']='head'
    h=''.join(str(c) for c in node.children)
    h=re.sub(r'[\u200b\u200c\u200d\ufeff]','',h)
    h=re.sub(r'(<br\s*/?>\s*){3,}','<br/><br/>',h)
    h=re.sub(r'^(\s*<(div|p)[^>]*>\s*)*(<br\s*/?>\s*)+','',h)
    return h.strip()
def empty_html(h):
    t=re.sub(r'<[^>]+>',' ',h); t=re.sub(r'\s+',' ',t).strip()
    return (not t and '<img' not in h and '<table' not in h) or t.lower() in('no data found','')

# ---------- parse articles
ART={}
for slug,d in docs.items():
    if d['type']!='article': continue
    cb=d['cb']; cap=tx(cb.select_one('.details-header-caption'))
    upd=re.search(r'Last Update\s+(.+?)\s+Status',cap); st=re.search(r'Status\s*:\s*(\w+)',cap)
    content=cb.select_one('.content'); dates={}
    for row in content.select('.row.mt-4 > div'):
        tt=[tx(x) for x in row.select('.title')]
        if len(tt)==2: dates[tt[0]]=tt[1]
    secs=[]
    for sec in content.find_all('section',recursive=False):
        ttl=sec.select_one('.title-large')
        if not ttl: continue
        s={'title':tx(ttl),'html':'','chips':[],'valid':{},'id':slugify(tx(ttl))}
        en=sec.select_one('[data-lang=en]')
        f_=(en.select_one('.ms-rtestate-field') if en else None) or sec.select_one('.list-links-container .ms-rtestate-field')
        if f_: s['html']=clean_html(f_,slug)
        for lc in sec.select('.valid-list-container'):
            s['valid'][tx(lc.select_one('.title'))]=[tx(a) for a in lc.select('.valid-list a')]
        for a in sec.select('.plans-container a,.promos-container a,.services-container a,.technical-container a'):
            t=tx(a); h=a.get('href','')
            if t and 'orangepedia' in h and t.lower()!='view all': s['chips'].append({'t':full_title(t,h) if t.endswith('...') else t,'l':link_for(h)})
        if empty_html(s['html']): s['html']=''
        secs.append(s)
    ART[slug]={'slug':slug,'title':d['title'],'kind':d['kind'],'updated':upd.group(1) if upd else '','status':st.group(1) if st else '','dates':dates,'sections':secs}

# ---------- listing page (saved search results)
LIST={}
for slug,d in docs.items():
    if d['type']!='listing': continue
    q=d['cb'].select_one('input[type=text]'); items=[]
    for it in d['cb'].select('div.ms-srch-item'):
        a=it.select_one('.ms-srch-item-link')
        if not a: continue
        sm=tx(it.select_one('.ms-srch-item-summary')); sm=re.sub(r'Visits - Last Update [\d/: APM]+','',sm).strip()
        items.append({'t':tx(a),'s':sm,'p':tx(it.select_one('.ms-srch-item-path')),'v':(tx(it.select_one('.ms-srch-hover-popularity')) or ''),'l':link_for(a.get('href',''))})
    nav=[tx(a) for a in d['cb'].select('.search-navigation .ms-srchnav-item a')]
    LIST[slug]={'slug':slug,'title':d['title'],'query':q.get('value','') if q else '','items':items,'nav':nav}

# ---------- home
HOME={'products':[],'services':[],'promotions':[],'devices':[],'most':[]}
if 'home' in docs:
    cb=docs['home']['cb']; seen=set()
    def add(key,t,h,sub='',extra=''):
        if not h or (key,h) in seen: return
        seen.add((key,h)); HOME[key].append({'t':full_title(t,h),'h':h,'s':sub,'l':link_for(h),'x':extra})
    for sl in cb.select('.products-container .slick-slide:not(.slick-cloned)'):
        a=sl.select_one('a.card-title'); 
        if a: add('products',tx(a),a['href'],tx(sl.select_one('.card-summary')))
    for sl in cb.select('#servicesTab .card-service'):
        a=sl.select_one('a.card-title'); 
        if a: add('services',tx(a),a['href'],re.sub(r'^\.$','',tx(sl.select_one('.card-summary'))))
    for sl in cb.select('#promotionsTab .card'):
        a=sl.select_one('a.card-title,a'); 
        if a and a.get('href'): add('promotions',tx(a),a['href'],tx(sl.select_one('.card-summary')))
    for sl in cb.select('#DeListVue .slick-slide:not(.slick-cloned)'):
        a=sl.select_one('a.title'); 
        if a: add('devices',tx(a),a['href'],'',tx(sl.select_one('.slider-tag')))
    for a in cb.select('.card-most-viewed'): add('most',tx(a),a['href'])
    print({k:len(v) for k,v in HOME.items()})

# ---------- aliases (Arabic keywords)
ALIASES={
 'home':'الرئيسية الصفحة الرئيسية هوم',
 'alo-profiles':'الو ألو بروفايلات الو باقات الو بروفايل',
 'business':'بزنس الاعمال الشركات باقات الشركات',
 'conference-calling':'كونفرانس مؤتمر مكالمات جماعية مكالمه جماعيه اجتماع',
 'el-king-portfolio':'الكينج ال كينج الملك كينج محفظه',
 'freemax-old-profiles':'فري ماكس القديم فريماكس قديم بروفايلات فريماكس',
 'freemax-new':'فري ماكس الجديد فريماكس جديد فريماكس',
 'mca-repricing-for-consumer-customers':'اعادة تسعير تسعير ام سي ايه العملاء الافراد المستهلكين',
 'special-needs-offer':'ذوي الاحتياجات الخاصة ذوي الهمم عرض الاحتياجات الخاصة',
 'voice-line-default-services':'خط صوت الخدمات الافتراضية الخدمات الافتراضية خط الصوت فويس',
 'services':'خدمات الخدمات حظر بلوك نتايج بحث',
}
ap=os.path.join(ROOT,'aliases.json')
if os.path.exists(ap): ALIASES.update(json.load(open(ap,encoding='utf-8')))

# ---------- layout helpers
NAVPAGES=[]
def page_nav_items():
    items=[]
    for s,a in ART.items(): items.append((a['title'],s+'.html',a['kind']))
    for s,l in LIST.items(): items.append((l['title'],s+'.html','Search'))
    return items
def head(title,rel='',desc='Orangepedia — offline knowledge base'):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} · Orangepedia</title><meta name="description" content="{E(desc)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23ff7900'/%3E%3Ctext x='32' y='44' font-size='34' font-weight='700' text-anchor='middle' fill='white' font-family='Arial'%3EOP%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css"><script>try{{var t=localStorage.getItem('op-theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script></head>'''
def header(active='',home=False):
    pages=''.join(f'<a href="{u}"><span class="dot k-{k.lower()}"></span>{E(t)}</a>' for t,u,k in page_nav_items())
    search='' if home else '''<form class="hsearch" action="search.html" role="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="q" name="q" type="search" autocomplete="off" placeholder="Search · ابحث…" aria-label="Search"><kbd>/</kbd><div class="sugg" hidden></div></form>'''
    return f'''<header class="top"><div class="wrap bar">
<a class="logo" href="index.html"><span class="sq">OP</span><span class="wm">orange<b>pedia</b></span></a>
<nav class="main"><a href="index.html" class="{'on' if active=='home' else ''}">Home</a>
<div class="dd"><button type="button" class="ddb">Pages <svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button><div class="ddm">{pages}</div></div></nav>
{search}<button class="theme" type="button" aria-label="Toggle theme" title="Dark / Light"><svg viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg></button></div></header>'''
def footer():
    return '<footer class="foot"><div class="wrap">Orangepedia · static copy of saved pages · <a href="search.html">Search</a></div></footer><script src="assets/search-index.js"></script><script src="assets/app.js"></script></body></html>'
def card(i,showkind=False):
    t=E(i['t']); ini=E(re.sub(r'[^A-Za-z0-9؀-ۿ]','',i['t'])[:2].upper() or 'OP')
    sub=f'<span class="cs">{E(i["s"][:110])}</span>' if i.get('s') else ''
    x=f'<span class="tag">{E(i["x"])}</span>' if i.get('x') else ''
    inner=f'<span class="ci">{ini}</span><span class="ct"><b>{t}</b>{sub}</span>{x}'
    if i['l']: return f'<a class="card live" href="{i["l"]}">{inner}<svg class="go" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg></a>'
    return f'<div class="card soon" title="Page not included yet">{inner}</div>'

# ---------- build home
def build_home():
    avail=[(a['title'],s,a['kind'],a['updated']) for s,a in ART.items()]+[(l['title'],s,'Search','') for s,l in LIST.items()]
    chips=''.join(f'<a class="chip" href="{s}.html"><span class="dot k-{k.lower()}"></span>{E(t)}</a>' for t,s,k,u in avail)
    def sec(key,title,cls='',limit=12):
        its=HOME[key]
        if not its: return ''
        live=sorted(its,key=lambda i:0 if i['l'] else 1)
        cards=''.join(card(i) for i in live)
        n=len(its); nl=sum(1 for i in its if i['l'])
        more=f'<button class="more" type="button" data-more>Show all {n}</button>' if n>limit else ''
        return f'<section class="blk {cls}" id="{key}"><div class="wrap"><div class="bh"><h2>{title}</h2><span class="cnt">{n} items{f" · {nl} available" if nl else ""}</span></div><div class="grid collapsed" data-limit="{limit}">{cards}</div>{more}</div></section>'
    most=''
    if HOME['most']:
        most='<section class="blk"><div class="wrap"><div class="bh"><h2>Most viewed</h2></div><div class="grid g3">'+''.join(card(i) for i in HOME['most'])+'</div></div></section>'
    stats=f'<div class="stats"><div><b>{len(ART)+len(LIST)}</b><span>pages loaded</span></div><div><b>{len(HOME["products"])}</b><span>products</span></div><div><b>{len(HOME["devices"])}</b><span>devices</span></div><div><b>{len(HOME["services"])+len(HOME["promotions"])}</b><span>services &amp; promos</span></div></div>'
    h=head('Home')+'<body class="home">'+header('home',True)+f'''
<main><section class="hero"><div class="wrap">
<p class="eyebrow">FBB-DSL Training Team · Knowledge Base</p>
<h1>Find anything in <span>Orangepedia</span></h1>
<p class="lead">ابحث بالعربي أو بالإنجليزي — اسم الصفحة، كود، أو أي كلمة جوّه المحتوى.</p>
<form class="hero-search hsearch" action="search.html" role="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="q" name="q" type="search" autocomplete="off" placeholder="e.g. FREEmax · Siebel · Conference · فري ماكس · الو" aria-label="Search" autofocus><button type="submit">Search</button><div class="sugg" hidden></div></form>
<div class="chips"><span>Jump to:</span>{chips}</div>{stats}</div></section>
{sec('products','Products','p',12)}{sec('services','Services','s',12)}{sec('promotions','Promotions','pr',12)}{most}{sec('devices','Devices','d',12)}
<section class="note"><div class="wrap"><div class="notebox"><b>ملحوظة:</b> الكروت اللي لونها رمادي صفحاتها لسه مش مضافة. أضف ملف الـ HTML بتاعها في فولدر <code>source/</code> وشغّل <code>python tools/build.py</code> وهتفتح لوحدها وتظهر في البحث.</div></div></section></main>'''+footer()
    open(OUT+'/index.html','w',encoding='utf-8').write(h)

# ---------- build article pages
def build_article(a):
    secs=[s for s in a['sections'] if s['html'] or s['chips'] or any(s['valid'].values())]
    empty=[s['title'] for s in a['sections'] if s not in secs]
    toc=''.join(f'<a href="#{s["id"]}">{E(s["title"])}</a>' for s in secs)
    body=''
    for s in secs:
        c=''
        if any(s['valid'].values()):
            cols=''
            for lab,vals in s['valid'].items():
                if not vals: continue
                vs=''.join(f'<a class="chip" href="{(slugify(v)+".html") if slugify(v) in KNOWN else "#"}">{E(v)}</a>' if slugify(v) in KNOWN else f'<span class="chip dead">{E(v)}</span>' for v in vals)
                cols+=f'<div class="vcol"><h4>{E(lab)}</h4><div class="chipset">{vs}</div></div>'
            c+=f'<div class="valid">{cols}</div>'
        if s['html']: c+=f'<div class="rich">{s["html"]}</div>'
        if s['chips']:
            ch=''.join((f'<a class="chip" href="{x["l"]}">{E(x["t"])}</a>' if x['l'] else f'<span class="chip dead">{E(x["t"])}</span>') for x in s['chips'])
            big=len(s['chips'])>14
            c+=f'<div class="chipset {"fold" if big else ""}">{ch}</div>'+(f'<button type="button" class="more" data-fold>Show all {len(s["chips"])}</button>' if big else '')
        body+=f'<details class="sec" id="{s["id"]}" open><summary><h2>{E(s["title"])}</h2><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></summary><div class="secb">{c}</div></details>'
    dates=''.join(f'<div><span>{E(k)}</span><b>{E(v)}</b></div>' for k,v in a['dates'].items())
    st=a['status']; meta=f'<div class="meta"><div><span>Status</span><b class="st {st.lower()}">{E(st) or "—"}</b></div><div><span>Last update</span><b>{E(a["updated"]) or "—"}</b></div>{dates}</div>'
    noempty=f'<p class="muted small">Sections with no data: {E(", ".join(empty))}</p>' if empty else ''
    h=head(a['title'])+'<body class="article">'+header()+f'''
<main><section class="phead"><div class="wrap"><nav class="crumb"><a href="index.html">Home</a><span>/</span><span>{E(a["kind"])}</span></nav>
<div class="ptitle"><span class="kind k-{a["kind"].lower()}">{E(a["kind"])}</span><h1>{E(a["title"])}</h1></div>{meta}</div></section>
<div class="wrap lay"><aside class="toc"><div class="tocin"><h3>On this page</h3>{toc}<div class="tools"><button type="button" data-expand>Expand all</button><button type="button" data-collapse>Collapse all</button></div></div></aside>
<div class="col">{body}{noempty}</div></div></main><div class="lb" hidden><img alt=""></div>'''+footer()
    open(OUT+f'/{a["slug"]}.html','w',encoding='utf-8').write(h)

def build_listing(l):
    its=''
    for i in l['items']:
        v=f'<span class="views">{E(i["v"].replace("This result has been viewed","").replace("times.","views").strip())}</span>' if i['v'] else ''
        its+=f'<article class="res"><h3>{E(i["t"])}</h3>{v}<p>{E(i["s"])}</p><code>{E(i["p"])}</code></article>'
    nav=''.join(f'<span class="tab {"on" if t=="Services" else ""}">{E(t)}</span>' for t in l['nav'])
    h=head(l['title'])+'<body class="listing">'+header()+f'''
<main><section class="phead"><div class="wrap"><nav class="crumb"><a href="index.html">Home</a><span>/</span><span>{E(l["title"])}</span></nav>
<div class="ptitle"><span class="kind k-search">Search results</span><h1>{E(l["title"])}</h1></div>
<p class="muted">Saved results for <b>“{E(l["query"])}”</b> · {len(l["items"])} results</p></div></section>
<div class="wrap"><div class="tabs">{nav}</div><div class="filter"><input type="search" id="lf" placeholder="Filter these results · فلتر النتايج…"></div><div class="reslist" id="rl">{its}</div></div></main>'''+footer()
    open(OUT+f'/{l["slug"]}.html','w',encoding='utf-8').write(h)

def build_search():
    h=head('Search')+'<body class="searchp">'+header()+'''<main><section class="phead"><div class="wrap"><div class="ptitle"><h1>Search</h1></div>
<form class="hero-search hsearch big" action="search.html" role="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="q2" name="q" type="search" autocomplete="off" placeholder="Search · ابحث…" aria-label="Search"><button type="submit">Search</button></form>
<p class="muted" id="sinfo"></p></div></section><div class="wrap"><div id="results"></div></div></main>'''+footer()
    open(OUT+'/search.html','w',encoding='utf-8').write(h)

# ---------- search index
def plain(h): 
    return re.sub(r'\s+',' ',BeautifulSoup(h,'lxml').get_text(' ')).strip()
def build_index():
    idx=[]
    if 'home' in docs:
        idx.append({'id':'home','t':'Home','u':'index.html','k':'Home','a':ALIASES.get('home',''),'h':'','x':' '.join(i['t'] for k in HOME for i in HOME[k])})
    for s,a in ART.items():
        txt=' '.join(plain(x['html'])+' '+' '.join(c['t'] for c in x['chips']) for x in a['sections'])
        idx.append({'id':s,'t':a['title'],'u':s+'.html','k':a['kind'],'a':ALIASES.get(s,''),'h':' | '.join(x['title'] for x in a['sections'] if x['html'] or x['chips']),'x':txt,'d':a['updated']})
    for s,l in LIST.items():
        idx.append({'id':s,'t':l['title'],'u':s+'.html','k':'Search results','a':ALIASES.get(s,''),'h':l['query'],'x':' '.join(i['t']+' '+i['s'] for i in l['items'])})
    open(OUT+'/assets/search-index.js','w',encoding='utf-8').write('window.OP_INDEX='+json.dumps(idx,ensure_ascii=False)+';')
    print('index docs',len(idx))

if 'home' in docs: build_home()
for a in ART.values(): build_article(a)
for l in LIST.values(): build_listing(l)
build_search(); build_index()
print('done; images saved to assets/img')
