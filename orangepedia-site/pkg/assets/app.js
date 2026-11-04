(function(){
const IDX=window.OP_INDEX||[];
/* ---------- normalization ---------- */
const AR=/[\u064B-\u065F\u0670\u0640]/g;
function norm(s){return (s||'').toLowerCase().replace(AR,'').replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/[^\u0600-\u06FFa-z0-9]+/g,' ').trim()}
function squash(s){return norm(s).replace(/ /g,'')}
const MAP={
 'خدمات':'services service','خدمه':'service','الخدمات':'services','عروض':'offer offers promotions','عرض':'offer','العروض':'offers promotions','منتجات':'products','المنتجات':'products','اجهزه':'devices','الاجهزه':'devices',
 'باقات':'plan plans profile profiles tariff','باقه':'plan profile','بروفايل':'profile','بروفايلات':'profiles','دفع':'pay payment','شكوي':'complain','شكاوي':'complain complaint','اسئله':'questions asked','سيبل':'siebel',
 'حظر':'block','بلوك':'block','تسعير':'repricing','مؤتمر':'conference','كونفرانس':'conference','كونفرنس':'conference','جديد':'new','الجديد':'new','قديم':'old','القديم':'old','شركات':'business','بزنس':'business','اعمال':'business',
 'صوت':'voice','خط':'line','مكالمات':'calls call','مكالمه':'call','حساب':'account','ادارة':'manage','ادارت':'manage','فري':'free','ماكس':'max','فريماكس':'freemax','الو':'alo','كينج':'king','الكينج':'king','سبيشل':'special','احتياجات':'needs','خاصه':'special','الخاصه':'special','افتراضيه':'default','الافتراضيه':'default','عملاء':'customers consumer','العملاء':'customers consumer','رئيسيه':'home','الرئيسيه':'home','هوم':'home','بحث':'search','تعليمات':'instructions','روابط':'links','اتصال':'call','جماعيه':'conference group'
};
const MAPN={};Object.keys(MAP).forEach(k=>MAPN[norm(k)]=MAP[k]);
function tokens(q){
  const base=norm(q).split(' ').filter(Boolean);
  return base.map(t=>{const ex=MAPN[t]?MAPN[t].split(' '):[];return {t,alt:ex}});
}
function lev1(a,b){ // edit distance <=1
  if(Math.abs(a.length-b.length)>1)return false;let i=0,j=0,e=0;
  while(i<a.length&&j<b.length){if(a[i]===b[j]){i++;j++;continue}if(++e>1)return false;
    if(a.length>b.length)i++;else if(a.length<b.length)j++;else{i++;j++}}
  return e+(a.length-i)+(b.length-j)<=1;
}
const DOCS=IDX.map(d=>({d,t:norm(d.t),ts:squash(d.t),a:norm(d.a),h:norm(d.h),x:norm(d.x)}));
function words(s){return s.split(' ')}
function scoreTok(doc,tk){
  let best=0,why='';
  for(const w of [tk.t,...tk.alt]){
    if(!w)continue;const pen=w===tk.t?1:.8;let s=0,y='';
    if(doc.t===w){s=120;y='title'}
    else if(doc.t.startsWith(w)){s=95;y='title'}
    else if(doc.t.includes(w)||doc.ts.includes(w.replace(/ /g,''))){s=80;y='title'}
    else if(doc.a.includes(w)){s=70;y='keywords'}
    else if(doc.h.includes(w)){s=40;y='section'}
    else if(w.length>=3&&doc.x.includes(w)){s=15+Math.min(20,(doc.x.split(w).length-1)*1.2);y='content'}
    else if(w.length>=4){ // typo tolerance on title/alias words
      const ws=words(doc.t).concat(words(doc.a));
      if(ws.some(x=>x.length>=4&&lev1(x,w))){s=45;y='title (similar)'}
    }
    s*=pen;if(s>best){best=s;why=y}
  }
  return [best,why];
}
function search(q){
  const tk=tokens(q);if(!tk.length)return[];
  const out=[];
  for(const doc of DOCS){
    let tot=0,miss=0,whys=new Set();
    for(const k of tk){const[s,w]=scoreTok(doc,k);if(s>0){tot+=s;whys.add(w)}else miss++}
    if(miss===tk.length)continue;
    if(miss>0)tot*=.35; // partial matches rank lower than all-token matches
    // whole-query squashed match on title (e.g. "free max" -> freemax)
    const sq=squash(q);if(sq.length>=3&&doc.ts.includes(sq))tot+=60;
    out.push({d:doc.d,score:tot,why:[...whys].join(' · '),partial:miss>0});
  }
  out.sort((a,b)=>b.score-a.score);const top=out.length?out[0].score:0;return top>=80?out.filter(r=>r.score>=top*.3):out;
}
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function snippet(d,q){
  const text=(d.x||'');const tk=tokens(q);const lt=text.toLowerCase();
  let pos=-1,hit='';
  for(const k of tk){for(const w of [k.t,...k.alt]){ if(w.length<2)continue;const i=lt.indexOf(w);if(i>=0&&(pos<0||i<pos)){pos=i;hit=w}}}
  if(pos<0)return esc(text.slice(0,150))+(text.length>150?'…':'');
  const a=Math.max(0,pos-70),b=Math.min(text.length,pos+110);
  let s=esc(text.slice(a,b));
  tk.forEach(k=>[k.t,...k.alt].forEach(w=>{if(w.length>=2)s=s.replace(new RegExp('('+w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig'),'<mark>$1</mark>')}));
  return (a>0?'…':'')+s+(b<text.length?'…':'');
}
/* ---------- live suggestions ---------- */
function mountSugg(form){
  const input=form.querySelector('input[type=search]'),box=form.querySelector('.sugg');if(!input||!box)return;let sel=-1,items=[];
  function render(){
    const q=input.value.trim();if(!q){box.hidden=true;return}
    items=search(q).slice(0,6);sel=-1;
    box.innerHTML=items.length?items.map((r,i)=>`<a href="${r.d.u}" data-i="${i}"><span><span class="st">${esc(r.d.t)}</span><small>${esc(r.why||'')}</small></span><span class="kk">${esc(r.d.k)}</span></a>`).join('')+`<a href="search.html?q=${encodeURIComponent(q)}"><span class="st">See all results for “${esc(q)}”</span></a>`
      :`<div class="none">No matches for “${esc(q)}” — جرّب كلمة تانية</div>`;
    box.hidden=false;
  }
  input.addEventListener('input',render);input.addEventListener('focus',render);
  input.addEventListener('keydown',e=>{
    const as=[...box.querySelectorAll('a')];if(box.hidden||!as.length)return;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();sel=(sel+(e.key==='ArrowDown'?1:-1)+as.length)%as.length;as.forEach((a,i)=>a.classList.toggle('sel',i===sel))}
    else if(e.key==='Enter'&&sel>=0){e.preventDefault();location.href=as[sel].getAttribute('href')}
    else if(e.key==='Escape'){box.hidden=true}
  });
  document.addEventListener('click',e=>{if(!form.contains(e.target))box.hidden=true});
}
document.querySelectorAll('form.hsearch').forEach(f=>{if(!document.body.classList.contains('searchp')||f.closest('.top'))mountSugg(f)});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!/input|textarea/i.test(document.activeElement.tagName)){const i=document.querySelector('#q,#q2');if(i){e.preventDefault();i.focus()}}});
/* ---------- results page ---------- */
if(document.body.classList.contains('searchp')){
  const p=new URLSearchParams(location.search),q=(p.get('q')||'').trim(),inp=document.getElementById('q2'),res=document.getElementById('results'),info=document.getElementById('sinfo');
  inp.value=q;if(!q)inp.focus();
  function run(){
    const v=inp.value.trim();
    if(!v){res.innerHTML='<div class="empty"><b>Type something to search</b>اكتب اسم صفحة أو أي كلمة (عربي أو English)</div>';info.textContent='';return}
    const r=search(v);info.textContent=r.length?`${r.length} result${r.length>1?'s':''} for “${v}”`:'';
    res.innerHTML=r.length?r.map(x=>`<a class="sr" href="${x.d.u}"><h3>${esc(x.d.t)}<em>${esc(x.d.k)}</em></h3><p>${snippet(x.d,v)}</p><div class="why">matched in: ${esc(x.why)}${x.partial?' (partial)':''}${x.d.d?' · updated '+esc(x.d.d):''}</div></a>`).join(''):`<div class="empty"><b>No results for “${esc(v)}”</b>جرّب اسم تاني أو كلمة أقصر — البحث بيشتغل بالعربي والإنجليزي.</div>`;
    history.replaceState(null,'','?q='+encodeURIComponent(v));
  }
  inp.addEventListener('input',run);run();
}
/* ---------- listing filter ---------- */
const lf=document.getElementById('lf');
if(lf)lf.addEventListener('input',()=>{const q=norm(lf.value);document.querySelectorAll('#rl .res').forEach(r=>r.style.display=norm(r.textContent).includes(q)?'':'none')});
/* ---------- home: show more ---------- */
document.querySelectorAll('[data-more]').forEach(b=>b.addEventListener('click',()=>{const g=b.previousElementSibling;const c=g.classList.toggle('collapsed');b.textContent=c?'Show all '+g.children.length:'Show less'}));
document.querySelectorAll('[data-fold]').forEach(b=>b.addEventListener('click',()=>{const s=b.previousElementSibling;const o=s.classList.toggle('open');b.textContent=o?'Show less':'Show all '+s.children.length}));
/* ---------- article: toc, expand, lightbox ---------- */
document.querySelectorAll('[data-expand]').forEach(b=>b.onclick=()=>document.querySelectorAll('details.sec').forEach(d=>d.open=true));
document.querySelectorAll('[data-collapse]').forEach(b=>b.onclick=()=>document.querySelectorAll('details.sec').forEach(d=>d.open=false));
const tl=[...document.querySelectorAll('.toc a')];
if(tl.length&&'IntersectionObserver'in window){
  const m=new Map(tl.map(a=>[a.getAttribute('href').slice(1),a]));
  const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){tl.forEach(a=>a.classList.remove('on'));const a=m.get(e.target.id);a&&a.classList.add('on')}}),{rootMargin:'-90px 0px -65% 0px'});
  document.querySelectorAll('details.sec').forEach(s=>io.observe(s));
}
tl.forEach(a=>a.addEventListener('click',()=>{const d=document.getElementById(a.getAttribute('href').slice(1));if(d)d.open=true}));
const lb=document.querySelector('.lb');
if(lb){document.addEventListener('click',e=>{if(e.target.matches('.rich img')){lb.querySelector('img').src=e.target.src;lb.hidden=false}else if(!lb.hidden)lb.hidden=true});document.addEventListener('keydown',e=>{if(e.key==='Escape')lb.hidden=true})}
/* ---------- theme + dropdown ---------- */
document.querySelector('.theme').addEventListener('click',()=>{const r=document.documentElement;const cur=r.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');const n=cur==='dark'?'light':'dark';r.dataset.theme=n;try{localStorage.setItem('op-theme',n)}catch(e){}});
const dd=document.querySelector('.dd');if(dd)dd.querySelector('.ddb').addEventListener('click',e=>{e.stopPropagation();dd.classList.toggle('open')});
document.addEventListener('click',()=>dd&&dd.classList.remove('open'));
window.__op={search,norm};
})();
