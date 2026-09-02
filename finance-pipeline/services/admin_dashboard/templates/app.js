const API='';
function tickClock(){document.getElementById('clock').textContent=new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}
setInterval(tickClock,1000);tickClock();

// Tunnel status check
async function checkTunnel(){
  try{
    const r=await fetch(API+'/api/tunnel-status');
    const d=await r.json();
    const b=document.getElementById('tunnel-badge');
    if(d.active&&d.url){
      b.className='badge badge-running';
      b.innerHTML=`<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> <a href="${d.url}" target="_blank" class="hover:underline">${d.url.replace('https://','').substring(0,30)}...</a>`;
    }else{
      b.className='badge badge-stopped';
      b.innerHTML=`<span class="w-1.5 h-1.5 rounded-full bg-red-400"></span> Tunnel: Kapali`;
    }
  }catch(e){
    const b=document.getElementById('tunnel-badge');
    b.className='badge badge-idle';
    b.innerHTML=`<span class="w-1.5 h-1.5 rounded-full bg-dark-500"></span> Tunnel: ?`;
  }
}
checkTunnel();
setInterval(checkTunnel,30000);
async function api(m,p){try{const r=await fetch(API+p,{method:m,headers:{'Content-Type':'application/json'}});return await r.json()}catch(e){return null}}
function formatDateTime(i){if(!i)return'—';const d=new Date(i);return`${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`}
function timeAgoShort(i){if(!i)return'';const d=(Date.now()-new Date(i).getTime())/1000;if(d<60)return`${Math.floor(d)}s once`;if(d<3600)return`${Math.floor(d/60)}dk once`;if(d<86400)return`${Math.floor(d/3600)}sa once`;return`${Math.floor(d/86400)}g once`}
function fmtNum(n){if(n==null)return'—';return Number(n).toLocaleString('tr-TR')}
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}
const SERVICES=[
    {key:'kap_worker',name:'KAP Worker',icon:'📈',port:8001,color:'#0ea5e9',desc:'BIST sirket, finansal tablo, bildirim verisi',schedule:'Yukleniyor...'},
    {key:'tefas_worker',name:'TEFAS Worker',icon:'💹',port:8002,color:'#8b5cf6',desc:'5 yillik fon fiyat ve portfoy verisi',schedule:'Yukleniyor...'},
    {key:'market_data_worker',name:'Market Data',icon:'🌍',port:8003,color:'#06b6d4',desc:'Doviz, altin, kripto, faiz verisi',schedule:'Yukleniyor...'},
];
let scheduleData={};
function buildScheduleLabel(k,c){if(!c)return'Bilinmiyor';if(!c.enabled)return'Kapali';const m=c.mode||'manual';if(m==='manual')return'Sadece Manuel';if(m==='daily')return`Her gun ${String(c.hour||0).padStart(2,'0')}:${String(c.minute||0).padStart(2,'0')}`;if(m==='interval'||m==='hourly'){const mn=c.interval_minutes||60;if(mn>=60){const h=Math.floor(mn/60),r=mn%60;return r>0?`Her ${h}sa ${r}dk`:`Her ${h} saatte`}return`Her ${mn} dk`}return m}
async function loadSchedules(){try{const r=await api('GET','/api/schedule/next-runs');if(r&&r.next_runs){scheduleData=r.next_runs;SERVICES.forEach(s=>{const n=scheduleData[s.key];if(n)s.schedule=buildScheduleLabel(s.key,n)})}}catch(e){}}
const KAP_MODULES=[{id:'seed',name:'Sirket Listesi',icon:'🏢',desc:'BIST sirket listesini ceker'},{id:'financials',name:'Mali Tablolar',icon:'📊',desc:'Finansal tablo verilerini ceker'},{id:'disclosures',name:'Bildirim Akisi',icon:'📢',desc:'KAP bildirimlerini ceker'},{id:'corporate',name:'Kurumsal Islemler',icon:'🎯',desc:'Temettu/sermaye islemleri'},{id:'buybacks',name:'Geri Alim',icon:'💰',desc:'Pay geri alim programlari'},{id:'ipo',name:'IPO',icon:'🏆',desc:'Halka arz verileri'},{id:'ownership',name:'Ortaklik',icon:'👥',desc:'Ortaklik yapisi / pay sahipleri'},{id:'cashflow',name:'Nakit Akis',icon:'💵',desc:'Nakit akis tablosu'},{id:'management',name:'Yonetim Kurulu',icon:'👔',desc:'YK uyeleri, CEO'},{id:'subsidiaries',name:'Bagli Ortaklik',icon:'🏭',desc:'Istirak ve bagli ortakliklar'},{id:'portfolio',name:'Portfoy Raporu',icon:'📋',desc:'Portfoy dagilim raporlari'},{id:'notes',name:'Dipnotlar',icon:'📝',desc:'Finansal dipnotlar'},{id:'prices',name:'BIST Fiyat',icon:'💹',desc:'Guncel hisse fiyatlari'},{id:'disclosure_details',name:'Bildirim Detay',icon:'🔍',desc:'Ihale, blok satis parse'},{id:'index_settlement',name:'Endeks & Takas',icon:'📊',desc:'XU100 uyeleri, takas oranlari'},{id:'selenium',name:'Selenium KAP',icon:'🤖',desc:'Sirket sayfasi scrape (anti-ban)'}];
function renderKapModules(){const g=document.getElementById('kap-modules-grid');if(!g)return;g.innerHTML=KAP_MODULES.map(m=>`<button onclick="triggerKapModule('${m.id}')" class="stat-chip hover:border-cyan-500/30 cursor-pointer group text-center" id="kap-mod-${m.id}"><div class="text-2xl mb-1 transition-transform group-hover:scale-110">${m.icon}</div><div class="text-xs font-bold text-white">${m.name}</div><div class="text-[10px] text-dark-600 mt-0.5">${m.desc}</div></button>`).join('')}
renderKapModules();

function renderServiceCard(svc,st){
const s=st||{},running=s.running||false,scraping=s.scraping||false,lastRun=s.last_run,lastStatus=s.last_status;
let badge=scraping?'<span class="badge badge-scraping"><span class="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span> CEKILIYOR</span>':running?'<span class="badge badge-running"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> CALISIYOR</span>':'<span class="badge badge-stopped"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> DURDURULDU</span>';
let lrHtml='<span class="text-dark-600">Henuz calistirilmadi</span>',lrDetail='';
if(lastRun){const ic=lastStatus==='SUCCESS'?'✅':lastStatus==='FAILED'?'❌':'⏳';lrHtml=`<span>${ic} ${formatDateTime(lastRun)}</span><span class="text-dark-600 ml-1">(${timeAgoShort(lastRun)})</span>`;const lrmr=s.last_run_module_results||s.module_results||{},lrr=s.last_run_records||0,lrp=s.last_run_prices||0,lrd=s.last_run_details||0;let ri='';if(Object.keys(lrmr).length>0){const t=Object.values(lrmr).reduce((a,b)=>a+(typeof b==='number'?b:0),0);if(t>0){ri=`<span class="text-emerald-400 font-semibold">${fmtNum(t)} kayit guncellendi</span>`;const p=Object.entries(lrmr).filter(([k,v])=>typeof v==='number'&&v>0).map(([k,v])=>`${k}:${fmtNum(v)}`).join(' / ');if(p)ri+=`<span class="text-dark-500 text-[10px] ml-1">(${p})</span>`}}else if(lrp>0||lrd>0){const p=[];if(lrd>0)p.push(`${fmtNum(lrd)} detay`);if(lrp>0)p.push(`${fmtNum(lrp)} fiyat`);ri=`<span class="text-emerald-400 font-semibold">${p.join(' + ')} guncellendi</span>`}else if(lrr>0)ri=`<span class="text-emerald-400 font-semibold">${fmtNum(lrr)} kayit islendi</span>`;if(ri)lrDetail=`<div class="flex items-center gap-1.5 text-[11px] mt-1.5 ml-9">${ri}</div>`}

let sh='';const A=(i,l,v,c)=>{if(v!=null)sh+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">${i} ${l}</span><span class="font-mono text-sm font-bold ${c}">${fmtNum(v)}</span></div>`};
A('🏢','Sirket',s.companies,'text-white');A('📊','Finansal',s.financials,'text-sky-400');
if(s.disclosures!=null){sh+=`<div class="flex justify-between py-1 border-t border-dark-700/20 pt-1.5 mt-1"><span class="text-dark-500 text-xs">📢 Bildirim</span><span class="font-mono text-sm font-bold text-emerald-400">${fmtNum(s.disclosures)}</span></div>`;
if(s.disclosure_categories&&Object.keys(s.disclosure_categories).length>0){const cats=Object.entries(s.disclosure_categories).sort((a,b)=>b[1]-a[1]).slice(0,8);const cc={Temettu:'text-amber-400',Sermaye:'text-orange-400',Geri_Alim:'text-rose-400',Yeni_Is:'text-emerald-300',IPO:'text-purple-400',Finansman:'text-sky-300',Buyuklenme:'text-cyan-400',Yatirim:'text-teal-400',Dava:'text-rose-300',Ortaklik:'text-pink-400',Diger:'text-dark-600'};sh+=`<div class="grid grid-cols-2 gap-x-3 gap-y-0.5 mt-1">`;cats.forEach(([c,n])=>{const cl=cc[c]||'text-dark-400';const p=s.disclosures>0?Math.round(n/s.disclosures*100):0;sh+=`<div class="flex justify-between text-[11px]"><span class="${cl}">${c.replace(/_/g,' ')}</span><span class="font-mono ${cl} font-semibold">${fmtNum(n)} <span class="text-dark-600 font-normal">${p}%</span></span></div>`});sh+=`</div>`}}
A('🎯','Kurumsal',s.corporate_actions,'text-amber-400');A('💰','Gerialim',s.share_buybacks,'text-rose-400');A('🏆','IPO',s.ipo_data,'text-purple-400');
A('👥','Ortaklik',s.shareholders,'text-pink-400');A('💵','Nakit Akis',s.cashflows,'text-emerald-300');A('👔','Yonetim',s.management,'text-indigo-400');
A('🏭','Bagli Ortaklik',s.subsidiaries,'text-teal-400');A('📋','Portfoy',s.portfolio_reports,'text-cyan-300');A('📝','Dipnot',s.financial_notes,'text-orange-300');
A('💹','Fiyat',s.stock_prices,'text-emerald-400');A('🔍','Detay',s.disclosure_details,'text-cyan-400');
A('📊','Endeks',s.index_members,'text-blue-400');A('🏦','Takas',s.settlements,'text-amber-300');
if(sh)sh=`<div class="mt-3 p-3 rounded-xl bg-dark-950/50 border border-dark-700/20">${sh}</div>`;

let ts='';
if(s.funds!=null){ts=`<div class="mt-3 p-3 rounded-xl bg-dark-950/50 border border-dark-700/20"><div class="flex justify-between py-1"><span class="text-dark-500 text-xs">💹 Fon</span><span class="font-mono text-sm font-bold text-purple-400">${fmtNum(s.funds)}</span></div>`;
if(s.prices!=null)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">💹 Fiyat Kaydi</span><span class="font-mono text-sm font-bold text-cyan-400">${fmtNum(s.prices)}</span></div>`;
if(s.groups!=null)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">📂 Grup</span><span class="font-mono text-xs text-purple-300">${fmtNum(s.groups)}</span></div>`;
if(s.types!=null)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">📂 Alt Tip</span><span class="font-mono text-xs text-purple-300">${fmtNum(s.types)}</span></div>`;
if(s.announcements!=null)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">📢 Duyuru</span><span class="font-mono text-xs text-purple-300">${fmtNum(s.announcements)}</span></div>`;
if(s.request_count>0){ts+=`<div class="flex justify-between py-1 border-t border-dark-700/20 pt-1.5 mt-1"><span class="text-dark-500 text-xs">🌐 Istekler</span><span class="font-mono text-sm font-bold text-white">${fmtNum(s.request_count)}</span></div>`;if(s.slowdown_factor>1)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">🐌 Yavaslama</span><span class="font-mono text-sm font-bold text-amber-400">${s.slowdown_factor.toFixed(1)}x</span></div>`;if(s.total_errors>0)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">❌ Hatalar</span><span class="font-mono text-sm font-bold text-rose-400">${fmtNum(s.total_errors)}</span></div>`}
if(s.total_funds>0){ts+=`<div class="flex justify-between py-1 border-t border-dark-700/20 pt-1.5 mt-1"><span class="text-dark-500 text-xs">📋 Toplam Fon</span><span class="font-mono text-sm font-bold text-white">${fmtNum(s.total_funds)}</span></div>`;if(s.details_updated)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">  ├ Detay</span><span class="font-mono text-xs text-sky-400">${fmtNum(s.details_updated)}</span></div>`;if(s.funds_with_prices)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">  ├ Fiyat Olan</span><span class="font-mono text-xs text-cyan-400">${fmtNum(s.funds_with_prices)}</span></div>`;if(s.prices_inserted)ts+=`<div class="flex justify-between py-1"><span class="text-dark-500 text-xs">  └ Fiyat Kaydi</span><span class="font-mono text-xs text-emerald-400">${fmtNum(s.prices_inserted)}</span></div>`}ts+=`</div>`}

let act='';const cur=s.current_module||s.current_fund;if(cur&&scraping)act=`<div class="mt-3 p-2.5 rounded-lg" style="background:${svc.colorBg};border:1px solid ${svc.color}33"><div class="flex items-center gap-2 text-xs"><span class="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span><span class="text-dark-500">Su an:</span><span class="mono text-white font-semibold">${cur}</span></div></div>`;

const bl=s.ban_level||0,bd=s.ban_detected||false,t429=s.total_429s||0,bcd=s.ban_cooldown_until;
let banBadge='',banDetail='';
if(bl>=2||bd){let cd='';if(bcd){const r=Math.max(0,Math.ceil((new Date(bcd)-Date.now())/1000));if(r>0)cd=` ${Math.floor(r/60)}dk${r%60}s`}banBadge=`<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse">🚨 BAN${cd}</span>`;banDetail=`<div class="mt-2 p-2 rounded-lg border border-red-500/30" style="background:rgba(220,38,38,0.08)"><div class="flex items-center gap-2 text-[11px]"><span class="text-red-400">🚨</span><span class="text-red-300/80">${s.ban_message||'IP engellendi'}</span></div><div class="flex gap-3 mt-1.5 text-[10px] text-red-400/60"><span>429: <b class="text-red-300">${t429}</b></span><span>Son: <b class="text-red-300">${s.last_429_time?new Date(s.last_429_time).toLocaleTimeString('tr-TR'):'-'}</b></span>${s.slowdown_factor>1?`<span>Yavaslama: <b class="text-orange-300">${s.slowdown_factor.toFixed(1)}x</b></span>`:''}</div></div>`}
else if(bl>=1||t429>0)banBadge=`<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">⚠️ ${t429}x 429</span>`;

return`<div class="glass-strong fade-up p-5" style="border-left:3px solid ${svc.color}"><div class="flex items-start justify-between mb-3"><div class="flex items-center gap-3"><span class="text-2xl">${svc.icon}</span><div><div class="flex items-center gap-2 flex-wrap"><h3 class="font-bold text-white text-base">${svc.name}</h3>${badge} ${banBadge}</div><p class="text-xs text-dark-500 mt-0.5">${svc.desc}</p></div></div><label class="toggle" title="${running?'Durdur':'Baslat'}"><input type="checkbox" ${running?'checked':''} onchange="toggleService('${svc.key}',this.checked)"><span class="toggle-track"></span><span class="toggle-thumb"></span></label></div><div class="flex items-center gap-4 text-xs mb-3"><div class="flex items-center gap-1.5 text-dark-500"><span>⏰</span><span>${svc.schedule}</span></div><div class="flex items-center gap-1.5 text-dark-400"><span>Son calisma:</span>${lrHtml}</div></div>${lrDetail}${banDetail}${sh}${ts}${act}<div class="flex items-center gap-2 mt-3 pt-3 border-t border-dark-700/30"><button onclick="restartService('${svc.key}')" class="btn btn-slate">🔄 Yeniden Baslat</button><button onclick="triggerScrape('${svc.key}')" class="btn btn-cyan" ${scraping?'disabled style="opacity:0.5"':''}>⚡ Simdi Veri Cek</button><button onclick="showLogs('${svc.key}')" class="btn btn-slate ml-auto">🖥️ Loglar</button><a href="http://localhost:${svc.port}/docs" target="_blank" class="btn btn-slate">📖 API</a></div></div>`}

// ═══ PROGRESS BARS ═══
const SVC_META={kap_worker:{name:'KAP Worker',icon:'📈',cls:'kap',color:'#0ea5e9'},tefas_worker:{name:'TEFAS Worker',icon:'💹',cls:'tefas',color:'#8b5cf6'},market_data_worker:{name:'Market Data',icon:'🌍',cls:'market',color:'#06b6d4'}};
function fmtEta(s){if(!s||s<=0)return'';if(s<60)return`${Math.ceil(s)}s`;if(s<3600)return`${Math.floor(s/60)}dk ${Math.ceil(s%60)}s`;return`${Math.floor(s/3600)}sa ${Math.floor((s%3600)/60)}dk`}
function renderProgressBar(key,pct,eta,phase,detail){
    const m=SVC_META[key]||{name:key,icon:'⚙️',cls:'market',color:'#64748b'};
    const done=pct>=100;
    const active=pct>0&&pct<100;
    const fillCls=done?`${m.cls} done`:m.cls;
    const pulseCls=done?'done':m.cls;
    let etaHtml='';
    if(active&&eta>0)etaHtml=`<span class="text-dark-500 text-[11px]"><span class="text-dark-600">Kalan:</span> <span class="text-white font-semibold font-mono">${fmtEta(eta)}</span></span>`;
    else if(done)etaHtml=`<span class="text-emerald-400 text-[11px] font-semibold">✅ Tamamlandı</span>`;
    else if(pct===0)etaHtml=`<span class="text-dark-600 text-[11px]">Beklemede</span>`;
    let detailHtml='';
    if(detail)detailHtml=`<div class="text-[10px] text-dark-500 mt-0.5 font-mono truncate">${esc(detail)}</div>`;
    return`<div class="progress-container">
        <div class="progress-header">
            <div class="flex items-center gap-2">
                <span class="text-sm">${m.icon}</span>
                <span class="text-xs font-bold text-white">${m.name}</span>
                <span class="progress-pulse ${pulseCls}"></span>
                <span class="text-[11px] font-mono font-bold" style="color:${m.color}">${pct}%</span>
            </div>
            <div class="flex items-center gap-3">
                ${etaHtml}
            </div>
        </div>
        <div class="progress-track">
            <div class="progress-fill ${fillCls}${active?' active':''}" style="width:${pct}%"></div>
        </div>
        <div class="flex justify-between items-center mt-1">
            <span class="text-[10px] text-dark-500">${phase||'—'}</span>
            ${detailHtml}
        </div>
    </div>`;
}
async function refreshProgress(){
    const data=await api('GET','/api/progress');
    if(!data)return;
    const el=document.getElementById('progress-bars');
    if(!el)return;
    let html='';
    for(const [key,meta] of Object.entries(SVC_META)){
        const p=data[key];
        if(!p)continue;
        const detail=p.current_fund||p.current||'';
        html+=renderProgressBar(key,p.percent||0,p.eta_seconds||0,p.phase||'—',detail);
    }
    el.innerHTML=html;
}

async function refreshAll(){
    // Parallel fetch all data — don't let one slow endpoint block everything
    const promises = [
        loadSchedules(),
        api('GET','/api/stats'),
        refreshProgress(),
        ...SERVICES.map(s=>api('GET',`/api/service-status/${s.key}`).then(d=>({key:s.key,data:d})).catch(()=>({key:s.key,data:null}))),
    ];
    const [schedResult, stats, progressResult, ...statusResults] = await Promise.allSettled(promises);
    
    // Docker badge
    const ct = statusResults.find(r=>r.status==='fulfilled')?.value?.data;
    const db=document.getElementById('docker-badge');
    if(db) db.className='badge badge-idle';
    
    // Service cards
    const statuses={};
    statusResults.forEach(r=>{if(r.status==='fulfilled'&&r.value)statuses[r.value.key]=r.value.data});
    document.getElementById('services-container').innerHTML=SERVICES.map(s=>renderServiceCard(s,statuses[s.key])).join('');
    
    // Global stats
    const sv = stats.status==='fulfilled' ? stats.value : null;
    if(sv)document.getElementById('global-stats').innerHTML=`
        <div class="stat-chip"><div class="font-mono text-xl font-extrabold text-white">${fmtNum(sv.kap?.companies)}</div><div class="text-[10px] text-dark-500 uppercase tracking-wider mt-1">Sirket</div></div>
        <div class="stat-chip"><div class="font-mono text-xl font-extrabold text-sky-400">${fmtNum(sv.kap?.financials)}</div><div class="text-[10px] text-dark-500 uppercase tracking-wider mt-1">Finansal</div></div>
        <div class="stat-chip"><div class="font-mono text-xl font-extrabold text-emerald-400">${fmtNum(sv.kap?.disclosures)}</div><div class="text-[10px] text-dark-500 uppercase tracking-wider mt-1">Bildirim</div></div>
        <div class="stat-chip"><div class="font-mono text-xl font-extrabold text-amber-400">${fmtNum(sv.kap?.corporate_actions)}</div><div class="text-[10px] text-dark-500 uppercase tracking-wider mt-1">Kurumsal</div></div>
        <div class="stat-chip"><div class="font-mono text-xl font-extrabold text-purple-400">${fmtNum(sv.tefas?.funds)}</div><div class="text-[10px] text-dark-500 uppercase tracking-wider mt-1">Fon</div></div>
        <div class="stat-chip"><div class="font-mono text-xl font-extrabold text-cyan-400">${fmtNum(sv.tefas?.prices)}</div><div class="text-[10px] text-dark-500 uppercase tracking-wider mt-1">Fiyat</div></div>`;
}

// ═══ ACTIONS ═══
async function toggleService(k,s){toast(`${k} ${s?'baslatiliyor':'durduruluyor'}...`);await api('POST',`/api/containers/${k}/${s?'start':'stop'}`);setTimeout(refreshAll,2000)}
async function restartService(k){toast(`${k} yeniden baslatiliyor...`);await api('POST',`/api/containers/${k}/restart`);setTimeout(refreshAll,3000)}
async function triggerScrape(k){toast(`${k} veri cekimi baslatiliyor...`);await api('POST',`/api/containers/${k}/trigger`);setTimeout(refreshAll,2000)}
function showLogs(k){document.getElementById('log-select').value=k;fetchLogs()}

// ═══ LOGS ═══
async function fetchLogs(){const k=document.getElementById('log-select').value;const d=await api('GET',`/api/containers/${k}/logs?tail=60`);const t=document.getElementById('terminal');if(!d||!d.logs){t.innerHTML='<div class="text-dark-600">Log bulunamadi</div>';return}t.innerHTML=d.logs.split('\n').filter(l=>l.trim()).map(l=>{let c='log-info';if(/error|FAILED|Traceback/i.test(l))c='log-error';else if(/SUCCESS|DONE|COMPLETE|TAMAMLANDI/i.test(l))c='log-success';else if(/WARN/i.test(l))c='log-warn';return`<div class="${c}">${esc(l)}</div>`}).join('');t.scrollTop=t.scrollHeight}

// ═══ FLOW LOGS ═══
async function fetchFlowLogs(){const k=document.getElementById('flow-log-select').value;const urls=k==='all'?['/api/containers/kap_worker/logs?tail=30','/api/containers/tefas_worker/logs?tail=30','/api/containers/market_data_worker/logs?tail=30']:[`/api/containers/${k}/logs?tail=60`];let all='';for(const u of urls){const d=await api('GET',u);if(d&&d.logs)all+=d.logs+'\n'}const t=document.getElementById('flow-terminal');if(!all.trim()){t.innerHTML='<div class="text-dark-600">Veri akisi bekleniyor...</div>';return}t.innerHTML=all.split('\n').filter(l=>l.trim()).map(l=>{let c='log-info';if(/error|FAILED|Traceback/i.test(l))c='log-error';else if(/SUCCESS|DONE|COMPLETE/i.test(l))c='log-success';else if(/WARN/i.test(l))c='log-warn';return`<div class="${c}">${esc(l)}</div>`}).join('');t.scrollTop=t.scrollHeight}

async function refreshActivity(){const stats=await api('GET','/api/stats');if(!stats)return;const el=document.getElementById('activity-stats');if(!el)return;el.innerHTML=`
    <div class="flex justify-between items-center"><span class="text-dark-500 text-xs">📈 KAP</span><span class="badge badge-running text-[10px]">${fmtNum(stats.kap?.disclosures||0)} bildirim</span></div>
    <div class="flex justify-between items-center"><span class="text-dark-500 text-xs">💹 TEFAS</span><span class="badge badge-running text-[10px]">${fmtNum(stats.tefas?.prices||0)} fiyat</span></div>
    <div class="flex justify-between items-center"><span class="text-dark-500 text-xs">🌍 Market</span><span class="badge badge-running text-[10px]">${fmtNum(stats.market?.total||0)} veri</span></div>`;
const ru=document.getElementById('recent-updates');if(!ru)return;const svcs=[{k:'kap_worker',n:'KAP',c:'#0ea5e9'},{k:'tefas_worker',n:'TEFAS',c:'#8b5cf6'},{k:'market_data_worker',n:'Market',c:'#06b6d4'}];let html='';for(const s of svcs){const st=await api('GET',`/api/service-status/${s.k}`);if(st&&st.last_run)html+=`<div class="flex items-center gap-2 text-xs"><span class="w-2 h-2 rounded-full" style="background:${s.c}"></span><span class="text-dark-400">${s.n}</span><span class="text-white font-mono">${formatDateTime(st.last_run)}</span></div>`}ru.innerHTML=html||'<div class="text-dark-600 text-xs">Veri yok</div>';
const bo=document.getElementById('ban-overview');if(!bo)return;let bhtml='';for(const s of [{k:'tefas_worker',n:'TEFAS',c:'#8b5cf6'},{k:'kap_worker',n:'KAP',c:'#0ea5e9'}]){const st=await api('GET',`/api/service-status/${s.k}`);if(!st)continue;const bl=st.ban_level||0;const clr=bl>=2?'text-rose-400':bl>=1?'text-amber-400':'text-emerald-400';const lbl=bl>=2?'🚨 BAN':bl>=1?'⚠️ Uyari':'✅ Normal';bhtml+=`<div class="flex items-center justify-between py-1"><span class="text-dark-500 text-xs">${s.n}</span><span class="text-xs font-bold ${clr}">${lbl}</span></div>`}bo.innerHTML=bhtml||'<div class="text-dark-600 text-xs">Ban verisi yok</div>'}

// ═══ HISTORY ═══
async function refreshHistory(){const d=await api('GET','/api/pipeline/runs?limit=15');const tb=document.getElementById('history-body');if(!d||!d.runs||!d.runs.length){tb.innerHTML='<tr><td colspan="5" class="text-center text-dark-600 py-6">Henuz islem kaydi yok</td></tr>';return}tb.innerHTML=d.runs.map(r=>{const sc=r.status==='SUCCESS'?'text-emerald-400':r.status==='FAILED'?'text-rose-400':'text-amber-400';const si=r.status==='SUCCESS'?'✅':r.status==='FAILED'?'❌':'⏳';let dur='—';if(r.started_at&&r.finished_at){const s=(new Date(r.finished_at)-new Date(r.started_at))/1000;dur=s<60?`${s.toFixed(1)}s`:`${(s/60).toFixed(1)}dk`}return`<tr><td class="text-dark-400 text-xs">${r.service_name}</td><td class="font-mono text-xs">${r.module_name}</td><td class="${sc} text-xs font-semibold">${si} ${r.status}</td><td class="text-right font-mono text-xs">${fmtNum(r.records_inserted)}</td><td class="text-dark-500 text-xs font-mono">${dur}</td></tr>`}).join('')}

// ═══ TOAST ═══
function toast(m,t='info'){const c={success:'bg-emerald-600',error:'bg-rose-600',info:'bg-cyan-600',warning:'bg-amber-600'};const e=document.createElement('div');e.className=`fixed bottom-4 right-4 ${c[t]} text-white px-4 py-2.5 rounded-lg shadow-xl z-50 fade-up text-sm font-medium`;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),3000)}

// ═══ TABS ═══
let currentTab='services';
function showTab(t){currentTab=t;['services','dataflow','funds','fund-holdings','market','kap','schedule','technical','screener','macro','calendar','buffett','us','api'].forEach(p=>{const e=document.getElementById('page-'+p);if(e)e.style.display=p===t?'':'none'});document.querySelectorAll('.nav-tab,.tab-link').forEach(e=>e.classList.remove('active'));const el=document.getElementById('tab-'+t);if(el)el.classList.add('active');if(t==='funds')loadFundList();if(t==='fund-holdings')loadFundHoldings();if(t==='kap'){loadKapDisclosures();loadKapCategories()}if(t==='schedule')loadSchedule();if(t==='market')loadMarketData();if(t==='dataflow')fetchFlowLogs();if(t==='macro')loadMacroDefault();if(t==='calendar')loadCalendar();if(t==='api')loadApiPage()}

// ═══ KAP MODULES ═══
async function triggerKapModule(m){const b=document.getElementById(`kap-mod-${m}`);if(!b)return;const info=KAP_MODULES.find(x=>x.id===m);toast(`${info?.name||m} calistiriliyor...`);b.style.borderColor='#06b6d4';b.style.opacity='0.6';b.innerHTML=`<div class="text-2xl mb-1 animate-spin">⏳</div><div class="text-xs font-bold text-cyan-400">Calisiyor...</div>`;const r=await api('POST',`/api/kap/scrape/${m}`);if(r&&r.status==='started')toast(`${info?.name||m} baslatildi`,'success');else toast(`Hata: ${r?.message||'Baglanti yok'}`,'error');setTimeout(()=>{b.style.borderColor='';b.style.opacity='';renderKapModules();refreshAll()},4000)}
async function triggerKapAll(){toast('Tum KAP modulleri calistiriliyor...');document.getElementById('kap-all-btn').disabled=true;const r=await api('POST','/api/containers/kap_worker/trigger');if(r&&r.status==='started')toast('KAP baslatildi','success');else toast(`Hata: ${r?.message||'Bilinmeyen'}`,'error');setTimeout(()=>{document.getElementById('kap-all-btn').disabled=false;refreshAll()},5000)}

// ═══ KAP DATA ═══
let kapDiscOffset=0,kapComOffset=0,kapCorpOffset=0,kapBbOffset=0,kapIpoOffset=0;const KAPS=100;
function showKapTab(t){['disclosures','companies','corporate','buybacks','ipo'].forEach(p=>{const e=document.getElementById('kap-'+p);if(e)e.style.display=p===t?'':'none'});document.querySelectorAll('#page-kap .tab-link').forEach(e=>e.classList.remove('active'));const el=document.getElementById('ktab-'+t);if(el)el.classList.add('active');if(t==='companies')loadKapCompanies();if(t==='corporate')loadKapCorporate();if(t==='buybacks')loadKapBuybacks();if(t==='ipo')loadKapIpo()}
async function loadKapCategories(){const d=await api('GET','/api/kap/disclosure-categories');if(!d)return;const s=document.getElementById('kap-cat-filter');s.innerHTML='<option value="">Tum Kategoriler</option>';d.categories.sort((a,b)=>b.count-a.count).forEach(c=>{const o=document.createElement('option');o.value=c.name;o.textContent=`${c.name} (${fmtNum(c.count)})`;s.appendChild(o)})}
async function loadKapDisclosures(){const cat=document.getElementById('kap-cat-filter').value,sym=document.getElementById('kap-sym-filter').value,days=document.getElementById('kap-days-filter').value;let url=`/api/kap/disclosures?limit=${KAPS}&offset=${kapDiscOffset}&days=${days}`;if(cat)url+=`&category=${encodeURIComponent(cat)}`;if(sym)url+=`&symbol=${encodeURIComponent(sym)}`;const d=await api('GET',url);if(!d)return;const tb=document.getElementById('kap-disc-body');document.getElementById('kap-disc-count').textContent=`Toplam: ${fmtNum(d.total)} | ${kapDiscOffset+1}-${Math.min(kapDiscOffset+KAPS,d.total)}`;if(!d.data||!d.data.length){tb.innerHTML='<tr><td colspan="5" class="text-center text-dark-600 py-6">Sonuc yok</td></tr>';return}tb.innerHTML=d.data.map(x=>{const cl=x.is_catalyst?'text-amber-400 font-bold':'text-dark-400';const dt=x.publish_date?new Date(x.publish_date).toLocaleDateString('tr-TR'):'—';const lk=x.source_url?`<a href="${x.source_url}" target="_blank" class="text-sky-400 hover:underline">${esc((x.title||'').slice(0,80))}</a>`:esc((x.title||'').slice(0,80));return`<tr><td class="font-mono text-sky-400 font-semibold">${esc(x.symbol||'')}</td><td class="max-w-md truncate">${lk}</td><td class="${cl} text-xs">${x.is_catalyst?'⚡':''}${esc(x.category||'')}</td><td class="text-xs text-dark-500">${dt}</td><td class="text-center">${x.is_catalyst?'⚡':''}</td></tr>`}).join('')}
function kapDiscPage(d){kapDiscOffset=Math.max(0,kapDiscOffset+d*KAPS);loadKapDisclosures()}
async function loadKapCompanies(){const s=document.getElementById('kap-com-search').value;let url=`/api/kap/companies?limit=${KAPS}&offset=${kapComOffset}`;if(s)url+=`&search=${encodeURIComponent(s)}`;const d=await api('GET',url);if(!d)return;const tb=document.getElementById('kap-com-body');document.getElementById('kap-com-count').textContent=`Toplam: ${fmtNum(d.total)} | ${kapComOffset+1}-${Math.min(kapComOffset+KAPS,d.total)}`;if(!d.data||!d.data.length){tb.innerHTML='<tr><td colspan="4" class="text-center text-dark-600 py-6">Sonuc yok</td></tr>';return}tb.innerHTML=d.data.map(c=>`<tr class="cursor-pointer hover:bg-dark-700/50" onclick="openCompanyDetail('${esc(c.ticker)}')"><td class="font-mono text-sky-400 font-semibold">${esc(c.ticker)}</td><td class="text-white text-sm">${esc(c.company_name||'—')}</td><td class="text-dark-400 text-xs">${esc(c.sector||'—')}</td><td class="text-dark-400 text-xs">${esc(c.market||'—')}</td></tr>`).join('')}
function kapComPage(d){kapComOffset=Math.max(0,kapComOffset+d*KAPS);loadKapCompanies()}

// ═══ COMPANY DETAIL ═══
function closeCompanyDetail(){document.getElementById('company-detail-overlay').style.display='none'}

async function openCompanyDetail(ticker){
  const overlay=document.getElementById('company-detail-overlay');
  overlay.style.display='block';
  document.getElementById('cd-ticker').textContent=ticker;
  document.getElementById('cd-name').textContent='Yukleniyor...';
  ['cd-price-card','cd-financials','cd-cashflow','cd-shareholders','cd-management','cd-disclosures','cd-corporate','cd-subsidiaries','cd-ipo'].forEach(id=>{const e=document.getElementById(id);if(e)e.style.display='none'});

  const d=await api('GET',`/api/kap/company/${ticker}`);
  if(!d||!d.found){document.getElementById('cd-name').textContent='Sirket bulunamadi';return}

  const co=d.company||{};
  document.getElementById('cd-name').textContent=co.company_name||ticker;

  // Price card
  const p=d.price||{};
  if(p.price){
    document.getElementById('cd-price-card').style.display='';
    document.getElementById('cd-price').textContent=`${p.price.toFixed(2)} TL`;
    document.getElementById('cd-mc').textContent=p.market_cap?fmtBig(p.market_cap):'—';
    document.getElementById('cd-pe').textContent=p.pe_ratio?p.pe_ratio.toFixed(1):'—';
    document.getElementById('cd-pb').textContent=p.pb_ratio?p.pb_ratio.toFixed(2):'—';
    document.getElementById('cd-div').textContent=p.dividend_yield?(p.dividend_yield.toFixed(2)+'%'):'—';
    const chg=p.day_change_pct||0;
    const chgEl=document.getElementById('cd-chg');
    chgEl.textContent=chg?`${chg>0?'+':''}${chg.toFixed(2)}%`:'—';
    chgEl.className=`text-xl font-bold ${chg>0?'text-emerald-400':chg<0?'text-rose-400':'text-dark-400'}`;
  }

  // Financials
  if(d.financials&&d.financials.length){
    document.getElementById('cd-financials').style.display='';
    document.getElementById('cd-fin-body').innerHTML=d.financials.map(f=>`<tr>
      <td class="font-mono">${f.year}/${f.period}</td>
      <td class="font-mono text-sky-400">${f.revenue?fmtBig(f.revenue):'—'}</td>
      <td class="font-mono ${f.net_profit>0?'text-emerald-400':'text-rose-400'}">${f.net_profit?fmtBig(f.net_profit):'—'}</td>
      <td class="font-mono text-amber-400">${f.ebitda?fmtBig(f.ebitda):'—'}</td>
      <td class="font-mono text-dark-400">${f.total_assets?fmtBig(f.total_assets):'—'}</td>
      <td class="font-mono text-rose-300">${f.total_debts?fmtBig(f.total_debts):'—'}</td>
      <td class="font-mono text-emerald-300">${f.equity?fmtBig(f.equity):'—'}</td>
    </tr>`).join('')
  }

  // Cash flows
  if(d.cashflows&&d.cashflows.length){
    document.getElementById('cd-cashflow').style.display='';
    document.getElementById('cd-cf-body').innerHTML=d.cashflows.map(cf=>`<tr>
      <td class="font-mono">${cf.year}/${cf.period}</td>
      <td class="font-mono ${cf.operating_cash_flow>0?'text-emerald-400':'text-rose-400'}">${cf.operating_cash_flow?fmtBig(cf.operating_cash_flow):'—'}</td>
      <td class="font-mono text-sky-400">${cf.investing_cash_flow?fmtBig(cf.investing_cash_flow):'—'}</td>
      <td class="font-mono text-amber-400">${cf.financing_cash_flow?fmtBig(cf.financing_cash_flow):'—'}</td>
      <td class="font-mono ${cf.net_change>0?'text-emerald-400':'text-rose-400'}">${cf.net_change?fmtBig(cf.net_change):'—'}</td>
    </tr>`).join('')
  }

  // Shareholders
  document.getElementById('cd-shareholders').style.display='';
  if(d.shareholders&&d.shareholders.length){
    document.getElementById('cd-sh-body').innerHTML=d.shareholders.map(s=>`<tr>
      <td class="text-white">${esc(s.holder_name||'')}</td>
      <td class="font-mono text-sky-400">${s.share_ratio_percent?s.share_ratio_percent.toFixed(1)+'%':'—'}</td>
      <td class="text-dark-400">${s.is_qualified?'⭐':''}${esc(s.holder_type||'')}</td>
    </tr>`).join('')
  }else{
    document.getElementById('cd-sh-body').innerHTML='<tr><td colspan="3" class="text-center text-dark-600 py-6 text-xs">Ortak verisi icin KAP Selenium scraper gerekli</td></tr>';
  }

  // Management
  document.getElementById('cd-management').style.display='';
  if(d.management&&d.management.length){
    document.getElementById('cd-mg-body').innerHTML=d.management.map(m=>`<tr>
      <td class="text-white">${esc(m.name||'')}</td>
      <td class="text-dark-400">${esc(m.title||'')}</td>
      <td class="text-sky-400">${esc(m.member_type||'')}</td>
    </tr>`).join('')
  }else{
    document.getElementById('cd-mg-body').innerHTML='<tr><td colspan="3" class="text-center text-dark-600 py-6 text-xs">Yonetim verisi icin KAP Selenium scraper gerekli</td></tr>';
  }

  // Disclosures
  if(d.disclosures&&d.disclosures.length){
    document.getElementById('cd-disclosures').style.display='';
    document.getElementById('cd-disc-body').innerHTML=d.disclosures.map(dr=>`<tr>
      <td class="text-dark-500 whitespace-nowrap">${dr.publish_date?new Date(dr.publish_date).toLocaleDateString('tr-TR'):'—'}</td>
      <td class="text-white max-w-lg truncate">${esc((dr.title||'').slice(0,100))}</td>
      <td class="text-dark-400">${esc(dr.category||'')}</td>
    </tr>`).join('')
  }

  // Buybacks
  if(d.buybacks&&d.buybacks.length){
    document.getElementById('cd-buybacks').style.display='';
    document.getElementById('cd-bb-body').innerHTML=d.buybacks.map(b=>`<tr>
      <td class="font-mono text-amber-400">${b.total_budget_tl?fmtBig(b.total_budget_tl)+' TL':'—'}</td>
      <td class="font-mono text-sky-400">${b.max_shares?fmtNum(b.max_shares):'—'}</td>
      <td class="font-mono text-emerald-400">${b.total_bought_shares?fmtNum(b.total_bought_shares):'—'}</td>
      <td class="font-mono text-dark-400">${b.capital_ratio_percent?b.capital_ratio_percent.toFixed(2)+'%':'—'}</td>
      <td class="font-mono text-purple-400">${b.avg_buyback_price?b.avg_buyback_price.toFixed(2)+' TL':'—'}</td>
    </tr>`).join('')
  }

  // Corporate actions
  if(d.corporate_actions&&d.corporate_actions.length){
    document.getElementById('cd-corporate').style.display='';
    document.getElementById('cd-corp-body').innerHTML=d.corporate_actions.map(ca=>`<div class="flex justify-between py-1 border-b border-dark-700/20"><span>${esc(ca.action_type||'')}</span><span class="font-mono text-amber-400">${ca.gross_per_share?ca.gross_per_share.toFixed(2)+' TL/hisse':'—'}</span></div>`).join('')
  }

  // Subsidiaries
  if(d.subsidiaries&&d.subsidiaries.length){
    document.getElementById('cd-subsidiaries').style.display='';
    document.getElementById('cd-sub-body').innerHTML=d.subsidiaries.map(s=>`<div class="flex justify-between py-1 border-b border-dark-700/20"><span>${esc(s.name||'')}</span><span class="font-mono text-sky-400">${s.share_percent?s.share_percent.toFixed(1)+'%':'—'}</span></div>`).join('')
  }

  // IPO
  if(d.ipo&&d.ipo.length){
    document.getElementById('cd-ipo').style.display='';
    document.getElementById('cd-ipo-body').innerHTML=d.ipo.map(i=>`<div class="flex justify-between py-1 border-b border-dark-700/20"><span>${esc(i.ipo_date||'')}</span><span class="font-mono text-amber-400">${i.ipo_price?i.ipo_price.toFixed(2)+' TL':'—'}</span></div>`).join('')
  }

  // Price History Chart
  if(d.price_history&&d.price_history.length){
    document.getElementById('cd-price-chart').style.display='';
    window._chartData=d.price_history;
    window._chartRange='1Y';
    drawPriceChart(d.price_history,'1Y');
  }else{
    document.getElementById('cd-price-chart').style.display='none';
  }
}

function fmtBig(v){if(!v)return'—';if(Math.abs(v)>=1e12)return(v/1e12).toFixed(1)+'T';if(Math.abs(v)>=1e9)return(v/1e9).toFixed(1)+'B';if(Math.abs(v)>=1e6)return(v/1e6).toFixed(1)+'M';if(Math.abs(v)>=1e3)return(v/1e3).toFixed(1)+'K';return v.toFixed(0)}

// ═══ PRICE CHART ═══
let _chartDataAll=[], _chartRange='1Y';
function setChartRange(r){_chartRange=r;drawPriceChart(_chartDataAll,r);document.querySelectorAll('.chart-range-btn').forEach(b=>{b.classList.toggle('active',b.dataset.range===r)})}

function drawPriceChart(data,range){
  if(!data||!data.length)return;
  const canvas=document.getElementById('cd-chart-canvas');
  if(!canvas)return;
  const container=canvas.parentElement;
  const dpr=window.devicePixelRatio||1;
  const W=container.clientWidth;
  const H=container.clientHeight;
  canvas.width=W*dpr;canvas.height=H*dpr;
  canvas.style.width=W+'px';canvas.style.height=H+'px';
  const ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);

  // Filter data by range
  const now=new Date(data[data.length-1].trade_date);
  let daysBack=365;
  if(range==='1M')daysBack=30;
  else if(range==='3M')daysBack=90;
  else if(range==='6M')daysBack=180;
  const cutoff=new Date(now);cutoff.setDate(cutoff.getDate()-daysBack);
  let filtered=data.filter(d=>new Date(d.trade_date)>=cutoff);
  if(filtered.length<2){filtered=data.slice(-30);}

  const closes=filtered.map(d=>d.close).filter(v=>v!=null);
  if(!closes.length)return;
  const minP=Math.min(...closes)*0.98;
  const maxP=Math.max(...closes)*1.02;
  const rangeP=maxP-minP||1;
  const padL=60,padR=15,padT=15,padB=30;
  const chartW=W-padL-padR;
  const chartH=H-padT-padB;
  const n=filtered.length;

  // Clear
  ctx.clearRect(0,0,W,H);

  // Grid lines
  ctx.strokeStyle='rgba(255,255,255,0.06)';
  ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const y=padT+chartH*(1-i/4);
    ctx.beginPath();ctx.moveTo(padL,y);ctx.lineTo(W-padR,y);ctx.stroke();
    ctx.fillStyle='rgba(255,255,255,0.35)';ctx.font='10px monospace';ctx.textAlign='right';
    ctx.fillText((minP+rangeP*i/4).toFixed(1),padL-5,y+3);
  }

  // Date labels
  const labelCount=Math.min(6,n);
  ctx.fillStyle='rgba(255,255,255,0.35)';ctx.font='10px monospace';ctx.textAlign='center';
  for(let i=0;i<labelCount;i++){
    const idx=Math.floor(i*(n-1)/(labelCount-1));
    const x=padL+idx*chartW/(n-1);
    const dt=new Date(filtered[idx].trade_date);
    ctx.fillText(dt.toLocaleDateString('tr-TR',{day:'2-digit',month:'short'}),x,H-5);
  }

  // Determine color based on price direction
  const firstClose=closes[0];
  const lastClose=closes[closes.length-1];
  const isUp=lastClose>=firstClose;
  const lineColor=isUp?'#22c55e':'#ef4444';
  const gradTop=isUp?'rgba(34,197,94,0.3)':'rgba(239,68,68,0.3)';
  const gradBot=isUp?'rgba(34,197,94,0.01)':'rgba(239,68,68,0.01)';

  // Area gradient
  const grad=ctx.createLinearGradient(0,padT,0,padT+chartH);
  grad.addColorStop(0,gradTop);grad.addColorStop(1,gradBot);
  ctx.beginPath();
  ctx.moveTo(padL,padT+chartH);
  for(let i=0;i<n;i++){
    const x=padL+i*chartW/(n-1);
    const v=filtered[i].close;
    const y=padT+chartH*(1-(v-minP)/rangeP);
    ctx.lineTo(x,y);
  }
  ctx.lineTo(padL+chartW,padT+chartH);
  ctx.closePath();
  ctx.fillStyle=grad;ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle=lineColor;ctx.lineWidth=2;ctx.lineJoin='round';
  for(let i=0;i<n;i++){
    const x=padL+i*chartW/(n-1);
    const v=filtered[i].close;
    const y=padT+chartH*(1-(v-minP)/rangeP);
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  }
  ctx.stroke();

  // Volume bars (bottom 15%)
  const vols=filtered.map(d=>d.volume||0);
  const maxVol=Math.max(...vols)||1;
  const volH=chartH*0.15;
  ctx.globalAlpha=0.25;
  for(let i=0;i<n;i++){
    const x=padL+i*chartW/(n-1);
    const bh=volH*(vols[i]/maxVol);
    const by=padT+chartH-bh;
    ctx.fillStyle=filtered[i].close>=(filtered[i>0?i-1:i].close||0)?'#22c55e':'#ef4444';
    ctx.fillRect(x-chartW/n/2,by,chartW/n,bh);
  }
  ctx.globalAlpha=1;

  // Crosshair tooltip on hover
  canvas.onmousemove=function(e){
    const rect=canvas.getBoundingClientRect();
    const mx=e.clientX-rect.left;
    const tooltip=document.getElementById('cd-chart-tooltip');
    if(mx<padL||mx>W-padR){tooltip.classList.add('hidden');return;}
    const idx=Math.round((mx-padL)/chartW*(n-1));
    if(idx<0||idx>=n){tooltip.classList.add('hidden');return;}
    const d=filtered[idx];
    const x=padL+idx*chartW/(n-1);
    // Crosshair line
    drawPriceChart(filtered,range);
    ctx.strokeStyle='rgba(255,255,255,0.3)';ctx.lineWidth=1;ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(x,padT);ctx.lineTo(x,padT+chartH);ctx.stroke();
    ctx.setLineDash([]);
    // Dot
    const y=padT+chartH*(1-(d.close-minP)/rangeP);
    ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fillStyle=lineColor;ctx.fill();
    ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();
    // Tooltip
    tooltip.classList.remove('hidden');
    tooltip.style.left=(x+10)+'px';
    tooltip.style.top=(y-30)+'px';
    const chg=idx>0?(d.close-filtered[idx-1].close):0;
    const chgPct=idx>0?((chg/filtered[idx-1].close)*100):0;
    tooltip.innerHTML=`<div class="font-bold text-white">${new Date(d.trade_date).toLocaleDateString('tr-TR')}</div><div class="flex gap-2 mt-1"><span class="text-dark-400">Kapanis:</span><span class="text-sky-400 font-mono">${d.close.toFixed(2)}</span></div><div class="flex gap-2"><span class="text-dark-400">Acilis:</span><span class="font-mono">${(d.open||0).toFixed(2)}</span></div><div class="flex gap-2"><span class="text-dark-400">En Dusuk:</span><span class="font-mono">${(d.low||0).toFixed(2)}</span></div><div class="flex gap-2"><span class="text-dark-400">En Yuksek:</span><span class="font-mono">${(d.high||0).toFixed(2)}</span></div><div class="flex gap-2"><span class="text-dark-400">Hacim:</span><span class="font-mono">${fmtBig(d.volume||0)}</span></div>${idx>0?`<div class="flex gap-2"><span class="text-dark-400">Degisim:</span><span class="font-mono ${chg>=0?'text-emerald-400':'text-rose-400'}">${chg>=0?'+':''}${chgPct.toFixed(2)}%</span></div>`:''}`;
  };
  canvas.onmouseleave=function(){drawPriceChart(filtered,range);document.getElementById('cd-chart-tooltip').classList.add('hidden')};
  _chartDataAll=data;
}

// Redraw chart on resize
window.addEventListener('resize',()=>{if(_chartDataAll.length)drawPriceChart(_chartDataAll,_chartRange)});

async function loadKapCorporate(){const d=await api('GET',`/api/kap/corporate-actions?limit=${KAPS}&offset=${kapCorpOffset}`);if(!d)return;const tb=document.getElementById('kap-corp-body');document.getElementById('kap-corp-count').textContent=`Toplam: ${fmtNum(d.total)} | ${kapCorpOffset+1}-${Math.min(kapCorpOffset+KAPS,d.total)}`;if(!d.data||!d.data.length){tb.innerHTML='<tr><td colspan="8" class="text-center text-dark-600 py-6">Veri yok</td></tr>';return}tb.innerHTML=d.data.map(c=>`<tr><td class="text-white text-sm">${esc(c.ticker||c.company_name||'—')}</td><td class="text-dark-400 text-xs">${esc(c.action_type||'—')}</td><td class="font-mono text-amber-400">${c.gross_per_share?c.gross_per_share.toFixed(2):'—'}</td><td class="font-mono text-emerald-400">${c.net_per_share?c.net_per_share.toFixed(2):'—'}</td><td class="font-mono text-sky-400">${c.yield_percent?c.yield_percent.toFixed(2)+'%':'—'}</td><td class="text-dark-400 text-xs">${c.ex_date||'—'}</td><td class="text-dark-400 text-xs">${c.payment_date||'—'}</td><td class="text-dark-400 text-xs">${esc(c.status||'—')}</td></tr>`).join('')}
function kapCorpPage(d){kapCorpOffset=Math.max(0,kapCorpOffset+d*KAPS);loadKapCorporate()}

async function loadKapBuybacks(){const d=await api('GET',`/api/kap/buybacks?limit=${KAPS}&offset=${kapBbOffset}`);if(!d)return;const tb=document.getElementById('kap-bb-body');document.getElementById('kap-bb-count').textContent=`Toplam: ${fmtNum(d.total)} | ${kapBbOffset+1}-${Math.min(kapBbOffset+KAPS,d.total)}`;if(!d.data||!d.data.length){tb.innerHTML='<tr><td colspan="6" class="text-center text-dark-600 py-6">Veri yok</td></tr>';return}tb.innerHTML=d.data.map(b=>`<tr><td class="text-white text-sm">${esc(b.ticker||b.company_name||'—')}</td><td class="font-mono text-amber-400">${b.total_budget?fmtNum(b.total_budget)+' TL':'—'}</td><td class="font-mono text-sky-400">${b.max_shares?fmtNum(b.max_shares):'—'}</td><td class="font-mono text-emerald-400">${b.total_bought_shares?fmtNum(b.total_bought_shares):'—'}</td><td class="font-mono text-dark-400">${b.capital_ratio_percent?b.capital_ratio_percent.toFixed(2)+'%':'—'}</td><td class="font-mono text-purple-400">${b.avg_price?b.avg_price.toFixed(2)+' TL':'—'}</td></tr>`).join('')}
function kapBbPage(d){kapBbOffset=Math.max(0,kapBbOffset+d*KAPS);loadKapBuybacks()}

async function loadKapIpo(){const d=await api('GET',`/api/kap/ipo?limit=${KAPS}&offset=${kapIpoOffset}`);if(!d)return;const tb=document.getElementById('kap-ipo-body');document.getElementById('kap-ipo-count').textContent=`Toplam: ${fmtNum(d.total)} | ${kapIpoOffset+1}-${Math.min(kapIpoOffset+KAPS,d.total)}`;if(!d.data||!d.data.length){tb.innerHTML='<tr><td colspan="8" class="text-center text-dark-600 py-6">Veri yok</td></tr>';return}tb.innerHTML=d.data.map(i=>`<tr><td class="text-white text-sm">${esc(i.company_name||'—')}</td><td class="font-mono text-amber-400">${i.ipo_price?i.ipo_price.toFixed(2)+' TL':'—'}</td><td class="font-mono text-sky-400">${i.discount_ratio?i.discount_ratio.toFixed(1)+'%':'—'}</td><td class="text-dark-400 text-xs">${esc(i.distribution_type||'—')}</td><td class="font-mono text-emerald-400">${i.use_of_funds_investment_pct?i.use_of_funds_investment_pct.toFixed(1)+'%':'—'}</td><td class="font-mono text-purple-400">${i.use_of_funds_r_d_pct?i.use_of_funds_r_d_pct.toFixed(1)+'%':'—'}</td><td class="font-mono text-sky-300">${i.use_of_funds_working_capital_pct?i.use_of_funds_working_capital_pct.toFixed(1)+'%':'—'}</td><td class="font-mono text-rose-400">${i.use_of_funds_debt_pct?i.use_of_funds_debt_pct.toFixed(1)+'%':'—'}</td></tr>`).join('')}
function kapIpoPage(d){kapIpoOffset=Math.max(0,kapIpoOffset+d*KAPS);loadKapIpo()}

// ═══ FUND DETAIL ═══
let currentFundCode=null;
async function loadFundList(){const d=await api('GET','/api/funds');if(!d||!d.funds)return;const s=document.getElementById('fund-select');s.innerHTML=`<option value="">Fon seciniz... (${d.total} fon)</option>`;d.funds.filter(f=>f.price_count>0).forEach(f=>{const o=document.createElement('option');o.value=f.code;o.textContent=`${f.code} — ${f.title||f.code} (${f.kind}) [${fmtNum(f.price_count)} kayit]`;s.appendChild(o)})}
async function loadFundHoldings(){const d=await api('GET','/api/fund-holdings');if(!d||!d.funds){toast('Veri yok','warning');return}const stats=d.summary||{};document.getElementById('fund-holdings-stats').innerHTML=`<div class="bg-gradient-to-br from-purple-500/20 to-purple-600/5 border border-purple-500/30 rounded-xl p-3"><div class="text-[10px] font-medium text-purple-400 opacity-70">Toplam Fon (Hisseli)</div><div class="text-lg font-bold text-white">${fmtNum(stats.total_with_stock||0)}</div></div><div class="bg-gradient-to-br from-amber-500/20 to-amber-600/5 border border-amber-500/30 rounded-xl p-3"><div class="text-[10px] font-medium text-amber-400 opacity-70">Kaldircili (>%100)</div><div class="text-lg font-bold text-white">${fmtNum(stats.leveraged||0)}</div></div><div class="bg-gradient-to-br from-emerald-500/20 to-emerald-600/5 border border-emerald-500/30 rounded-xl p-3"><div class="text-[10px] font-medium text-emerald-400 opacity-70">Ort. Hisse Orani</div><div class="text-lg font-bold text-white">${(stats.avg_stock_pct||0).toFixed(1)}%</div></div>`;window._fundHoldingsData=d.funds;renderFundHoldings(d.funds)}function renderFundHoldings(funds){const filter=document.getElementById('fh-filter').value;const search=(document.getElementById('fh-search').value||'').toLowerCase();let filtered=funds;if(filter==='leveraged')filtered=funds.filter(f=>f.stock_pct>100);else if(filter==='aggressive')filtered=funds.filter(f=>f.stock_pct>50&&f.stock_pct<=100);else if(filter==='moderate')filtered=funds.filter(f=>f.stock_pct>20&&f.stock_pct<=50);if(search)filtered=filtered.filter(f=>(f.code||'').toLowerCase().includes(search)||(f.title||'').toLowerCase().includes(search));const tb=document.getElementById('fh-body');if(!filtered.length){tb.innerHTML='<tr><td colspan="7" class="text-center text-dark-600 py-8">Sonuc yok</td></tr>';return}tb.innerHTML=filtered.slice(0,200).map(f=>{const pct=f.stock_pct||0;const pctColor=pct>150?'text-rose-400':pct>100?'text-amber-400':pct>50?'text-emerald-400':'text-sky-400'; const mc=f.market_cap?fmtBig(f.market_cap):'—'; return`<tr class="hover:bg-dark-700/30"><td class="font-mono text-purple-400 font-semibold">${esc(f.code||'')}</td><td class="text-white text-xs max-w-[200px] truncate">${esc((f.title||'').slice(0,50))}</td><td class="text-dark-400 text-xs">${esc(f.category||f.fund_group||'—')}</td><td class="text-right font-mono font-bold ${pctColor}">${pct.toFixed(1)}%</td><td class="text-right font-mono text-dark-400">${f.current_price?f.current_price.toFixed(4):'—'}</td><td class="text-right font-mono text-dark-400">${mc}</td><td class="text-right font-mono text-dark-400">${f.investor_count?fmtNum(f.investor_count):'—'}</td></tr>`}).join('')}
document.getElementById('fh-filter')?.addEventListener('change',()=>{if(window._fundHoldingsData)renderFundHoldings(window._fundHoldingsData)});document.getElementById('fh-search')?.addEventListener('input',()=>{if(window._fundHoldingsData)renderFundHoldings(window._fundHoldingsData)});

async function loadFundDetail(){const c=document.getElementById('fund-select').value;if(!c){toast('Fon secin','warning');return}currentFundCode=c;document.getElementById('fund-empty').style.display='none';document.getElementById('fund-info').style.display='';const d=await api('GET',`/api/funds/${c}`);if(!d){toast('Veri alinamadi','error');return}const f=d.fund,st=d.stats,prices=d.prices||[];
document.getElementById('fund-title').textContent=`${f.code} — ${f.title||f.code}`;document.getElementById('fund-subtitle').textContent=`Tur: ${f.kind} | ${fmtNum(st.total_records)} kayit | ${st.first_date||'?'} — ${st.last_date||'?'}`;document.getElementById('fund-title-card').style.display='';
document.getElementById('fund-stats-grid').innerHTML=[{l:'Son Fiyat',v:st.last_price?st.last_price.toFixed(4)+' TL':'—',c:'text-white'},{l:'Toplam Getiri',v:st.total_return_pct!=null?'%'+st.total_return_pct.toFixed(2):'—',c:st.total_return_pct>=0?'text-emerald-400':'text-rose-400'},{l:'Yillik Getiri',v:st.annualized_return_pct!=null?'%'+st.annualized_return_pct.toFixed(2):'—',c:st.annualized_return_pct>=0?'text-emerald-400':'text-rose-400'},{l:'Min',v:st.min_price?st.min_price.toFixed(4):'—',c:'text-rose-300'},{l:'Max',v:st.max_price?st.max_price.toFixed(4):'—',c:'text-emerald-300'},{l:'Ortalama',v:st.avg_price?st.avg_price.toFixed(4):'—',c:'text-sky-300'},{l:'lk Fiyat',v:st.first_price?st.first_price.toFixed(4):'—',c:'text-dark-300'},{l:'Kayit',v:fmtNum(st.total_records),c:'text-purple-300'}].map(s=>`<div class="stat-chip"><div class="font-mono text-sm font-bold ${s.c}">${s.v}</div><div class="text-[9px] text-dark-500 uppercase tracking-wider mt-1">${s.l}</div></div>`).join('');
const tb=document.getElementById('fund-price-body');document.getElementById('table-count').textContent=`${fmtNum(prices.length)} kayit`;let pp=null;tb.innerHTML=prices.slice().reverse().slice(0,200).map(p=>{const pr=p.price;let ch='—',cc='text-dark-500';if(pp&&pr){const pc=((pr/pp)-1)*100;ch=(pc>=0?'+':'')+pc.toFixed(2)+'%';cc=pc>=0?'text-emerald-400':'text-rose-400'}let ff='—';if(st.first_price&&pr&&st.first_price>0){ff=(((pr/st.first_price)-1)*100);ff=(ff>=0?'+':'')+ff.toFixed(2)+'%'}pp=pr;return`<tr><td class="font-mono text-dark-300">${p.date}</td><td class="text-right font-mono text-white font-semibold">${pr?pr.toFixed(4):'—'}</td><td class="text-right font-mono ${cc}">${ch}</td><td class="text-right font-mono text-dark-500">${ff}</td></tr>`}).join('');
loadFundChart(365)}
async function loadFundChart(days){if(!currentFundCode)return;const d=await api('GET',`/api/funds/${currentFundCode}/chart?days=${days}`);if(!d||!d.data)return;const canvas=document.getElementById('price-chart'),ctx=canvas.getContext('2d'),W=canvas.parentElement.clientWidth-40;canvas.width=W;canvas.height=220;ctx.clearRect(0,0,W,220);const pts=d.data;if(pts.length<2){ctx.fillStyle='#64748b';ctx.font='14px system-ui';ctx.textAlign='center';ctx.fillText('Yeterli veri yok',W/2,110);return}const prices=pts.map(p=>p.price).filter(p=>p!=null),mn=Math.min(...prices),mx=Math.max(...prices),rng=mx-mn||1,pad=30,cW=W-pad*2,cH=170;ctx.strokeStyle='rgba(51,65,85,0.3)';ctx.lineWidth=1;for(let i=0;i<=4;i++){const y=pad+(cH/4)*i;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(W-pad,y);ctx.stroke();ctx.fillStyle='#475569';ctx.font='10px ui-monospace';ctx.textAlign='right';ctx.fillText((mx-(rng/4)*i).toFixed(2),pad-4,y+3)}const lc=pts[pts.length-1]?.price>=pts[0]?.price?'#34d399':'#f87171';ctx.strokeStyle=lc;ctx.lineWidth=2;ctx.beginPath();pts.forEach((p,i)=>{if(p.price==null)return;const x=pad+(i/(pts.length-1))*cW,y=pad+((mx-p.price)/rng)*cH;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});ctx.stroke();ctx.lineTo(pad+cW,pad+cH);ctx.lineTo(pad,pad+cH);ctx.closePath();ctx.fillStyle=lc+'15';ctx.fill();ctx.fillStyle='#475569';ctx.font='10px ui-monospace';ctx.textAlign='center';[0,Math.floor(pts.length/4),Math.floor(pts.length/2),Math.floor(pts.length*3/4),pts.length-1].forEach(i=>{if(!pts[i])return;ctx.fillText(pts[i].date.slice(5),pad+(i/(pts.length-1))*cW,pad+cH+15)});document.getElementById('chart-range').textContent=`Son ${days} gun | ${fmtNum(pts.length)} veri`}

// ═══ MARKET DATA ═══
async function loadMarketData(){const d=await api('GET','/api/market-data');if(!d)return;const fx=document.getElementById('fx-rates'),cr=document.getElementById('crypto-rates'),cm=document.getElementById('commodity-rates');if(d.fx&&d.fx.length)fx.innerHTML=d.fx.map(r=>`<div class="flex justify-between items-center py-2 px-3 rounded-lg bg-dark-950/50"><div><div class="text-xs text-dark-400">${esc(r.name||r.symbol)}</div><div class="font-mono text-white font-bold">${r.value?Number(r.value).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}</div></div><div class="text-[10px] text-dark-600">${r.symbol||''}</div></div>`).join('')||'<div class="text-dark-600 text-xs">Veri yok</div>';
if(d.crypto&&d.crypto.length)cr.innerHTML=d.crypto.map(r=>`<div class="flex justify-between items-center py-2 px-3 rounded-lg bg-dark-950/50"><div><div class="text-xs text-dark-400">${esc(r.name||r.symbol)}</div><div class="font-mono text-white font-bold">${r.value?Number(r.value).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}</div></div><div class="text-[10px] text-dark-600">${r.symbol||''}</div></div>`).join('')||'<div class="text-dark-600 text-xs">Veri yok</div>';
if(d.commodities&&d.commodities.length)cm.innerHTML=d.commodities.map(r=>`<div class="flex justify-between items-center py-2 px-3 rounded-lg bg-dark-950/50"><div><div class="text-xs text-dark-400">${esc(r.name||r.symbol)}</div><div class="font-mono text-white font-bold">${r.value?Number(r.value).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}</div></div><div class="text-[10px] text-dark-600">${r.symbol||''}</div></div>`).join('')||'<div class="text-dark-600 text-xs">Veri yok</div>';const vi=document.getElementById('vap-indicators');if(d.indicators&&d.indicators.length&&vi){const catColors={Puan:'from-purple-500/20 to-purple-600/5 border-purple-500/30 text-purple-400','%':'from-sky-500/20 to-sky-600/5 border-sky-500/30 text-sky-400','Trilyon ₺':'from-amber-500/20 to-amber-600/5 border-amber-500/30 text-amber-400','Kişi':'from-emerald-500/20 to-emerald-600/5 border-emerald-500/30 text-emerald-400','Adet':'from-rose-500/20 to-rose-600/5 border-rose-500/30 text-rose-400'};vi.innerHTML=d.indicators.map(ind=>{const c=catColors[ind.category]||'from-dark-700/20 to-dark-600/5 border-dark-500/30 text-dark-400';const v=typeof ind.value==='number'?ind.value.toLocaleString('tr-TR',{maximumFractionDigits:2}):ind.value;return`<div class="bg-gradient-to-br ${c} border rounded-xl p-3 transition-all hover:scale-[1.02]"><div class="text-[10px] font-medium opacity-70 mb-1">${esc(ind.name)}</div><div class="text-lg font-bold font-mono">${v}</div><div class="text-[10px] opacity-50">${esc(ind.category||'')}</div></div>`}).join('')}}

// ═══ SCHEDULE ═══
async function loadSchedule(){const d=await api('GET','/api/schedule');if(d&&d.schedule){const kap=d.schedule.kap_worker||{},tef=d.schedule.tefas_worker||{};document.getElementById('kap-enabled').checked=kap.enabled!==false;document.getElementById('kap-mode').value=kap.mode||'daily';document.getElementById('kap-time').value=`${String(kap.hour||2).padStart(2,'0')}:${String(kap.minute||0).padStart(2,'0')}`;document.getElementById('kap-interval').value=kap.interval_minutes||60;toggleInterval('kap');document.getElementById('tefas-enabled').checked=tef.enabled!==false;document.getElementById('tefas-mode').value=tef.mode||'daily';document.getElementById('tefas-time').value=`${String(tef.hour||3).padStart(2,'0')}:${String(tef.minute||0).padStart(2,'0')}`;document.getElementById('tefas-interval').value=tef.interval_minutes||60;document.getElementById('tefas-years').value=tef.years_back||5;toggleInterval('tefas')}
const nr=await api('GET','/api/schedule/next-runs');const c=document.getElementById('next-runs-container');if(nr&&nr.next_runs)c.innerHTML=Object.entries(nr.next_runs).map(([k,info])=>{const n=k==='kap_worker'?'📈 KAP Worker':k==='market_data_worker'?'🌍 Market Data':'💹 TEFAS Worker';const clr=k==='kap_worker'?'#0ea5e9':k==='market_data_worker'?'#06b6d4':'#8b5cf6';let sh;if(!info.enabled||!info.next_run)sh='<span class="badge badge-idle"><span class="w-1.5 h-1.5 rounded-full bg-dark-500"></span> Kapali / Manuel</span>';else{const nd=new Date(info.next_run),df=(nd-Date.now())/1000;let ts;if(df<60)ts=`${Math.floor(df)} sn sonra`;else if(df<3600)ts=`${Math.floor(df/60)} dk sonra`;else ts=`${nd.toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'})} (${Math.floor(df/3600)} sa sonra)`;sh=`<span class="badge badge-running"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> ${ts}</span>`}return`<div class="glass-strong p-4" style="border-left:3px solid ${clr}"><div class="flex items-center justify-between"><div><div class="font-bold text-white text-sm">${n}</div><div class="text-xs text-dark-500 mt-1">${info.label||info.mode||'?'}</div></div>${sh}</div></div>`}).join('')}
function toggleInterval(p){const m=document.getElementById(p+'-mode').value,tg=document.getElementById(p+'-time-group'),ig=document.getElementById(p+'-interval-group');if(m==='interval'){tg.style.display='none';ig.style.display=''}else if(m==='daily'){tg.style.display='';ig.style.display='none'}else{tg.style.display='none';ig.style.display='none'}}
async function saveSchedule(){const kt=document.getElementById('kap-time').value.split(':'),tt=document.getElementById('tefas-time').value.split(':');const schedule={kap_worker:{enabled:document.getElementById('kap-enabled').checked,mode:document.getElementById('kap-mode').value,hour:parseInt(kt[0])||2,minute:parseInt(kt[1])||0,interval_minutes:parseInt(document.getElementById('kap-interval').value)||60},tefas_worker:{enabled:document.getElementById('tefas-enabled').checked,mode:document.getElementById('tefas-mode').value,hour:parseInt(tt[0])||3,minute:parseInt(tt[1])||0,interval_minutes:parseInt(document.getElementById('tefas-interval').value)||60,years_back:parseInt(document.getElementById('tefas-years').value)||5}};try{const r=await fetch('/api/schedule',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({schedule})});const res=await r.json();if(res.status==='ok'){toast('Zamanlama kaydedildi!','success');loadSchedule();await loadSchedules();refreshAll()}else toast('Hata: '+(res.message||''),'error')}catch(e){toast('Kaydetme hatasi','error')}}

// ═══ INIT ═══
document.getElementById('log-select').addEventListener('change',fetchLogs);
document.getElementById('auto-log').addEventListener('change',function(){if(this.checked)logTimer=setInterval(fetchLogs,3000);else clearInterval(logTimer)});
let logTimer=setInterval(fetchLogs,3000);
showTab('services');refreshAll();fetchLogs();refreshHistory();refreshActivity();refreshProgress();

// ═══ TEKNIK ANALIZ ═══
async function loadTechnical(){const tk=document.getElementById('tech-ticker').value.trim().toUpperCase();const pd=document.getElementById('tech-period').value;if(!tk)return;const r=await api('GET',`/api/technical/${tk}?period=${pd}`);if(!r||r.error){alert(r?.error||'Hata');return}document.getElementById('tech-result').classList.remove('hidden');const sig=r.overall_signal||'';const banner=document.getElementById('tech-signal-banner');const isBuy=sig.includes('AL');banner.className=`rounded-xl p-4 mb-4 text-center font-bold text-lg ${isBuy?'bg-green-500/10 text-green-400 border border-green-500/20':'bg-red-500/10 text-red-400 border border-red-500/20'}`;banner.textContent=`${sig} — ${tk} ${r.price} TL`;
const ind=document.getElementById('tech-indicators');ind.innerHTML=[{l:'RSI',v:r.rsi?.value,cl:r.rsi?.value>70?'text-red':r.rsi?.value<30?'text-green':'text-white',sub:r.rsi?.signal},{l:'MACD',v:r.macd?.histogram?.toFixed(3),cl:r.macd?.histogram>0?'text-green':'text-red',sub:r.macd?.signal_text},{l:'BB Konum',v:r.bollinger?.position,cl:'text-amber',sub:r.bollinger?.upper?`Ust:${r.bollinger.upper}`:''},{l:'Supertrend',v:r.supertrend?.direction,cl:r.supertrend?.direction==='Yukselis'?'text-green':'text-red',sub:r.supertrend?.value},{l:'PP',v:r.pivots?.PP,cl:'text-cyan',sub:`R1:${r.pivots?.R1} S1:${r.pivots?.S1}`},{l:'SMA20',v:r.moving_averages?.sma_20,cl:'text-purple',sub:`EMA12:${r.moving_averages?.ema_12}`},{l:'Trend',v:r.trend,cl:r.trend==='Yukselis'?'text-green':'text-red',sub:''}].map(x=>`<div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px] uppercase">${x.l}</div><div class="font-bold text-sm ${x.cl}">${x.v??'—'}</div><div class="text-[10px] text-dark-500">${x.sub}</div></div>`).join('');
// Draw chart
if(r.chart_data){drawTechChart(r.chart_data,'tech-chart','closes','Fiyat');drawTechChart(r.chart_data,'tech-rsi-chart','closes','RSI+')}
// Pivots
const pv=r.pivots||{};document.getElementById('tech-pivots').innerHTML=`<div class="grid grid-cols-2 gap-1 text-xs">${Object.entries(pv).map(([k,v])=>`<div class="flex justify-between"><span class="text-dark-500">${k}</span><span class="font-mono ${k.startsWith('R')?'text-red':k.startsWith('S')?'text-green':'text-cyan'}">${v}</span></div>`).join('')}</div>`;
// MA
const ma=r.moving_averages||{};document.getElementById('tech-ma').innerHTML=`<div class="grid grid-cols-2 gap-1 text-xs">${Object.entries(ma).map(([k,v])=>`<div class="flex justify-between"><span class="text-dark-500">${k.toUpperCase()}</span><span class="font-mono text-white">${v??'—'}</span></div>`).join('')}</div>`;
// Supertrend
const st=r.supertrend||{};document.getElementById('tech-supertrend').innerHTML=`<div class="text-center p-4 rounded-lg ${st.direction==='Yukselis'?'bg-green-500/10 border border-green-500/20':'bg-red-500/10 border border-red-500/20'}"><div class="text-2xl font-bold ${st.direction==='Yukselis'?'text-green':'text-red'}">${st.direction}</div><div class="text-dark-500 text-xs mt-1">Deger: ${st.value??'—'}</div></div>`}
function drawTechChart(cd,canvasId,key,label){const c=document.getElementById(canvasId);if(!c||!cd[key])return;const ctx=c.getContext('2d');const W=c.width=c.parentElement.clientWidth-32;const H=c.height=200;const vals=cd[key].filter(v=>v!=null);if(!vals.length)return;const mx=Math.max(...vals),mn=Math.min(...vals);ctx.clearRect(0,0,W,H);ctx.strokeStyle='#22d3ee';ctx.lineWidth=2;ctx.beginPath();vals.forEach((v,i)=>{const x=i/(vals.length-1)*W;const y=H-(v-mn)/(mx-mn||1)*H;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});ctx.stroke()}

// ═══ SCREENER ═══
async function loadScreener(){const preset=document.getElementById('screener-preset').value;document.getElementById('screener-body').innerHTML='<tr><td colspan="6" class="text-center py-4 text-dark-500">Taranıyor...</td></tr>';const r=await api('GET',`/api/screener/${preset}`);if(!r)return;document.getElementById('screener-count').textContent=`${r.count} hisse bulundu (${r.scanned} tarandi)`;if(!r.results||!r.results.length){document.getElementById('screener-body').innerHTML='<tr><td colspan="6" class="text-center py-4 text-dark-600">Sonuc yok</td></tr>';return}document.getElementById('screener-body').innerHTML=r.results.map(x=>`<tr class="border-b border-dark-700/20 hover:bg-dark-800/30"><td class="font-mono text-sky-400 font-semibold py-2">${esc(x.ticker)}</td><td class="text-right font-mono">${x.price?.toFixed(2)}</td><td class="text-right ${x.change_pct>0?'text-green':'text-red'}">${x.change_pct>0?'+':''}${x.change_pct}%</td><td class="text-right font-mono">${x.rsi?.toFixed(1)??'—'}</td><td class="text-right font-mono ${x.macd>0?'text-green':'text-red'}">${x.macd?.toFixed(3)??'—'}</td><td class="text-right text-dark-500">${fmtNum(x.volume)}</td></tr>`).join('')}

// ═══ MAKRO VERI ═══
async function loadMacroDefault(){loadInflation('tufe');loadFx()}
async function loadInflation(type){document.querySelectorAll('[id^=inf-]').forEach(b=>b.classList.remove('bg-white/10'));document.getElementById(`inf-${type}`).classList.add('bg-white/10');document.getElementById('inflation-body').innerHTML='<tr><td colspan="3" class="text-center py-4 text-dark-500">Yukleniyor...</td></tr>';const r=await api('GET',`/api/macro/inflation?type=${type}&limit=24`);if(!r||!r.data)return;document.getElementById('inflation-stats').innerHTML=[{l:'Son Yillik',v:r.latest_yearly,cl:'text-red',s:'%'},{l:'Son Aylik',v:r.latest_monthly,cl:'text-amber',s:'%'},{l:'Kayit',v:r.data.length,cl:'text-white',s:''},{l:'Kaynak',v:'TCMB',cl:'text-dark-500',s:''}].map(x=>`<div class="bg-dark-950/50 rounded p-2 text-center"><div class="text-dark-500 text-[10px]">${x.l}</div><div class="font-bold ${x.cl}">${x.v??'—'}${x.s}</div></div>`).join('');document.getElementById('inflation-body').innerHTML=r.data.map(d=>`<tr class="border-b border-dark-700/20"><td class="py-1 text-dark-400">${d.date}</td><td class="text-right font-mono text-red">${d.yearly!=null?d.yearly.toFixed(2)+'%':'—'}</td><td class="text-right font-mono text-amber">${d.monthly!=null?d.monthly.toFixed(2)+'%':'—'}</td></tr>`).join('')}
async function loadFx(){document.getElementById('fx-body').innerHTML='<div class="text-center py-4 text-dark-500 text-xs">Yukleniyor...</div>';const r=await api('GET','/api/macro/fx');if(!r||!r.rates)return;document.getElementById('fx-body').innerHTML=r.rates.map(x=>`<div class="flex justify-between py-1.5 border-b border-dark-700/20 text-xs"><span class="text-white font-medium">${esc(x.name)}</span><span class="font-mono text-cyan">${x.buy?.toFixed(4)??'—'}</span></div>`).join('')}

// ═══ EKONOMIK TAKVIM ═══
async function loadCalendar(){const sel=document.getElementById('cal-countries');const countries=Array.from(sel.selectedOptions).map(o=>o.value).join(',');const period=document.getElementById('cal-period').value;document.getElementById('cal-body').innerHTML='<tr><td colspan="7" class="text-center py-4 text-dark-500">Yukleniyor...</td></tr>';const r=await api('GET',`/api/macro/calendar?countries=${countries}&period=${period}`);if(!r||!r.events)return;document.getElementById('cal-count').textContent=`${r.total} olay`;const impCl={high:'bg-red-500/15 text-red',medium:'bg-amber-500/15 text-amber',low:'bg-dark-700/30 text-dark-500'};document.getElementById('cal-body').innerHTML=r.events.map(e=>`<tr class="border-b border-dark-700/20 hover:bg-dark-800/30"><td class="py-1.5 text-dark-400">${e.date} ${e.time||''}</td><td class="font-semibold ${e.country_code==='TR'?'text-cyan':e.country_code==='US'?'text-amber':'text-dark-400'}">${e.country_code||'?'}</td><td class="max-w-xs truncate">${esc(e.event_name)}</td><td class="text-center"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${impCl[e.importance]||''}">${e.importance}</span></td><td class="text-right font-mono text-green">${e.actual||'—'}</td><td class="text-right font-mono text-dark-400">${e.forecast||'—'}</td><td class="text-right font-mono text-dark-500">${e.previous||'—'}</td></tr>`).join('')}

// ═══ BUFFETT DEGERLEME ═══
async function loadBuffett(){const tk=document.getElementById('buffett-ticker').value.trim().toUpperCase();if(!tk)return;document.getElementById('buffett-result').classList.remove('hidden');document.getElementById('buffett-rating').innerHTML='<div class="text-dark-500">Yukleniyor...</div>';const r=await api('GET',`/api/buffett/${tk}`);if(!r||r.error){document.getElementById('buffett-rating').innerHTML=`<div class="text-red-400">${r?.error||'Hata'}</div>`;return}
// Rating banner
const rating=r.rating||'NOTR';const isGood=rating.includes('AL');document.getElementById('buffett-rating').className=`rounded-xl p-4 mb-4 text-center font-bold text-lg ${isGood?'bg-green-500/10 text-green-400 border border-green-500/20':'bg-red-500/10 text-red-400 border border-red-500/20'}`;document.getElementById('buffett-rating').innerHTML=`${rating} — ${tk} ${r.price} TL | Buffett Skoru: ${r.buffett_score}/100`;
// Key metrics
const m=r.key_ratios||{};document.getElementById('buffett-metrics').innerHTML=[{l:'OE Yield',v:r.oe_yield+'%',cl:r.oe_yield>10?'text-green':r.oe_yield>5?'text-amber':'text-red'},{l:'Guvenli Marj',v:r.safety_margin+'%',cl:r.safety_margin>30?'text-green':r.safety_margin>0?'text-amber':'text-red'},{l:'ROE',v:m.roe+'%',cl:m.roe>15?'text-green':'text-white'},{l:'Piyasa Degeri',v:r.market_cap+'B',cl:'text-cyan'}].map(x=>`<div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px] uppercase">${x.l}</div><div class="font-bold text-sm ${x.cl}">${x.v}</div></div>`).join('');
// Owner Earnings
const oe=r.owner_earnings||{};document.getElementById('buffett-oe').innerHTML=`<div class="space-y-1 text-xs"><div class="flex justify-between"><span class="text-dark-500">Net Kâr</span><span class="font-mono">${fmtNum(oe.net_income)} TL</span></div><div class="flex justify-between"><span class="text-dark-500">Amortisman</span><span class="font-mono">${fmtNum(oe.depreciation)} TL</span></div><div class="flex justify-between"><span class="text-dark-500">CapEx</span><span class="font-mono">${fmtNum(oe.capex)} TL</span></div><div class="flex justify-between border-t border-dark-700/30 pt-1 mt-1"><span class="text-white font-bold">Owner Earnings</span><span class="font-mono font-bold text-green">${fmtNum(oe.value)} TL</span></div></div>`;
// DCF
const dcf=r.dcf||{};document.getElementById('buffett-dcf').innerHTML=`<div class="space-y-1 text-xs"><div class="flex justify-between"><span class="text-dark-500">Nominal Oran</span><span class="font-mono">%${dcf.nominal_rate}</span></div><div class="flex justify-between"><span class="text-dark-500">Enflasyon</span><span class="font-mono">%${dcf.inflation}</span></div><div class="flex justify-between"><span class="text-dark-500">Reel Oran</span><span class="font-mono">%${dcf.real_rate}</span></div><div class="flex justify-between"><span class="text-dark-500">Buyume Orani</span><span class="font-mono">%${dcf.growth_rate}</span></div><div class="flex justify-between"><span class="text-dark-500">Tahmini Periyot</span><span class="font-mono">${dcf.forecast_years} yil</span></div><div class="flex justify-between border-t border-dark-700/30 pt-1 mt-1"><span class="text-white font-bold">Ic Deger (Hisse)</span><span class="font-mono font-bold text-cyan">${fmtNum(dcf.intrinsic_per_share)} TL</span></div></div>`;
// Ratios
const ratios=[{l:'ROE',v:m.roe},{l:'ROA',v:m.roa},{l:'F/K',v:m.pe_ratio},{l:'PD/DD',v:m.pb_ratio},{l:'Kar Marji',v:m.profit_margins},{l:'Operasyonel Marj',v:m.operating_margins},{l:'Gelir Buyumesi',v:m.revenue_growth},{l:'Temettu Verimi',v:m.dividend_yield}];document.getElementById('buffett-ratios').innerHTML=ratios.map(x=>`<div class="flex justify-between py-1 text-xs"><span class="text-dark-500">${x.l}</span><span class="font-mono ${x.v&&x.v>15?'text-green':'text-white'}">${x.v!=null?(typeof x.v==='number'?x.v.toFixed(1):x.v):'—'}${typeof x.v==='number'?'%':''}</span></div>`).join('')}

// ═══ ABD PIYASASI ═══
async function loadUS(){const tk=document.getElementById('us-ticker').value.trim().toUpperCase();if(!tk)return;document.getElementById('us-data').innerHTML='<div class="text-center py-4 text-dark-500">Yukleniyor...</div>';const r=await api('GET',`/api/us-stock/${tk}`);if(!r||r.error){document.getElementById('us-data').innerHTML=`<div class="text-center py-4 text-red-400">${r?.error||'Hata'}</div>`;return}document.getElementById('us-data').innerHTML=`<div class="grid grid-cols-2 sm:grid-cols-4 gap-3"><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">FIYAT</div><div class="font-bold text-cyan">${r.price} ${r.currency}</div><div class="text-[10px] text-dark-500">${esc(r.name||'')}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">SEKTOR</div><div class="font-bold text-white text-xs">${esc(r.sector||'—')}</div><div class="text-[10px] text-dark-500">${esc(r.industry||'')}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">F/K</div><div class="font-bold text-amber">${r.pe?.toFixed(1)||'—'}</div><div class="text-[10px] text-dark-500">52H: ${r['52w_high']||'—'}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">ROE</div><div class="font-bold ${r.roe>15?'text-green':'text-white'}">${r.roe?.toFixed(1)||'—'}%</div><div class="text-[10px] text-dark-500">Beta: ${r.beta||'—'}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">PD/DD</div><div class="font-bold text-white">${r.pb?.toFixed(2)||'—'}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">TEMETTU</div><div class="font-bold text-green">%${r.dividend_yield?.toFixed(2)||'0'}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">PIYASA DEGERI</div><div class="font-bold text-cyan">${r.market_cap?(r.market_cap/1e9).toFixed(1)+'B':'—'}</div></div><div class="bg-dark-950/50 rounded-lg p-3 text-center"><div class="text-dark-500 text-[10px]">52H DUSUK</div><div class="font-bold text-white">${r['52w_low']||'—'}</div></div></div>`}

setInterval(refreshAll,10000);setInterval(refreshHistory,20000);setInterval(refreshActivity,15000);
setInterval(refreshProgress,3000); // Progress barlari her 3 sn guncelle

// ═══ API PAGE ═══
const API_BASE_URL = window.location.origin;

async function loadApiPage() {
  // Set public URL
  document.getElementById('api-public-url').textContent = API_BASE_URL;
  document.getElementById('api-code-url').textContent = API_BASE_URL;
  document.getElementById('api-code-url-js').textContent = API_BASE_URL;

  // Load stats
  const schema = await api('GET', '/api/export/schema');
  if (schema && schema.tables) {
    let totalCols = 0;
    let totalRows = 0;
    Object.values(schema.tables).forEach(cols => totalCols += cols.length);
    document.getElementById('api-stat-tables').textContent = schema.total_tables || Object.keys(schema.tables).length;
    document.getElementById('api-stat-columns').textContent = totalCols;
  }

  // Load data distribution chart
  loadApiDataChart();
  loadApiEndpointDocs();
}

async function loadApiDataChart() {
  const container = document.getElementById('api-chart-tables');
  container.innerHTML = '<div class="text-dark-500 text-xs">Yukleniyor...</div>';

  // Get row counts from the bulk endpoint
  const tables = [
    { name: 'companies', label: 'Sirketler', color: 'bg-cyan-500' },
    { name: 'financials', label: 'Finansal', color: 'bg-emerald-500' },
    { name: 'disclosures', label: 'Bildirimler', color: 'bg-purple-500' },
    { name: 'shareholders', label: 'Ortaklar', color: 'bg-amber-500' },
    { name: 'management', label: 'Yonetim', color: 'bg-rose-500' },
    { name: 'subsidiaries', label: 'Bagli Ortaklik', color: 'bg-blue-500' },
    { name: 'cashflows', label: 'Nakit Akis', color: 'bg-indigo-500' },
    { name: 'funds', label: 'TEFAS Fonlari', color: 'bg-violet-500' },
    { name: 'fund_prices', label: 'Fon Fiyatlari', color: 'bg-fuchsia-500' },
    { name: 'fund_allocations', label: 'Fon Dagalimlari', color: 'bg-pink-500' },
    { name: 'prices', label: 'Guncel Fiyat', color: 'bg-teal-500' },
    { name: 'price_history', label: 'Fiyat Gecmisi', color: 'bg-cyan-600' },
    { name: 'settlement', label: 'Takas', color: 'bg-emerald-600' },
    { name: 'buybacks', label: 'Geri Alim', color: 'bg-orange-500' },
    { name: 'ipo', label: 'IPO', color: 'bg-yellow-500' },
    { name: 'index', label: 'Endeks', color: 'bg-lime-500' }
  ];

  // Get counts from schema/stats
  const stats = await api('GET', '/api/stats');
  const counts = {};
  if (stats) {
    if (stats.companies) counts.companies = stats.companies;
    if (stats.financials) counts.financials = stats.financials;
    if (stats.disclosures) counts.disclosures = stats.disclosures;
    if (stats.shareholders) counts.shareholders = stats.shareholders;
    if (stats.management) counts.management = stats.management;
    if (stats.subsidiaries) counts.subsidiaries = stats.subsidiaries;
    if (stats.cashflows) counts.cashflows = stats.cashflows;
    if (stats.funds) counts.funds = stats.funds;
    if (stats.fund_prices) counts.fund_prices = stats.fund_prices;
    if (stats.fund_allocations) counts.fund_allocations = stats.fund_allocations;
    if (stats.settlement) counts.settlement = stats.settlement;
    if (stats.buybacks) counts.buybacks = stats.buybacks;
    if (stats.ipo) counts.ipo = stats.ipo;
    if (stats.price_history) counts.price_history = stats.price_history;
  }

  // Also get stock prices count
  if (!counts.prices) counts.prices = 0;
  if (!counts.index) counts.index = 0;

  // Find max for scaling
  const allCounts = tables.map(t => counts[t.name] || 0);
  const maxCount = Math.max(...allCounts, 1);

  container.innerHTML = tables.map(t => {
    const count = counts[t.name] || 0;
    const pct = Math.min((count / maxCount) * 100, 100);
    return `<div class="flex items-center gap-3">
      <div class="w-28 text-xs text-dark-400 truncate">${t.label}</div>
      <div class="flex-1 h-5 bg-dark-900/50 rounded-full overflow-hidden">
        <div class="h-full ${t.color} rounded-full transition-all duration-700" style="width:${pct}%"></div>
      </div>
      <div class="w-20 text-right font-mono text-xs text-white">${fmtNum(count)}</div>
    </div>`;
  }).join('');

  // Update stat chips
  document.getElementById('api-stat-records').textContent = fmtNum(Object.values(counts).reduce((a,b) => a+b, 0));
}

function loadApiEndpointDocs() {
  const container = document.getElementById('api-docs');
  const endpoints = [
    {
      method: 'GET', path: '/api/export/companies', desc: 'Tum BIST sirketleri',
      params: [],
      returns: 'ticker, company_name, sector, market, is_active',
      count: '1,014 sirket'
    },
    {
      method: 'GET', path: '/api/export/search?q={query}', desc: 'Sirket ara (ticker veya isim)',
      params: ['q (zorunlu): Arama terimi', 'limit (opsiyonel): Maks sonuc (varsayilan: 20)'],
      returns: 'ticker, company_name, sector, market',
      count: 'Degisken'
    },
    {
      method: 'GET', path: '/api/export/all/{ticker}', desc: 'Bir varligin TUM verileri (7 veri seti)',
      params: ['ticker (zorunlu): Hisse kodu (THYAO, ASELS)'],
      returns: 'company, financials (28 alan), disclosures (50), shareholders, management, subsidiaries, cashflows',
      count: 'Degisken'
    },
    {
      method: 'GET', path: '/api/export/financials/{ticker}', desc: 'Finansal tablolar (gelir, kar, oranlar)',
      params: ['ticker (zorunlu): Hisse kodu'],
      returns: 'revenue, gross_profit, ebitda, net_profit, pe_ratio, pb_ratio, roe, roa (28 alan)',
      count: 'Degisken'
    },
    {
      method: 'GET', path: '/api/export/funds', desc: 'TEFAS fon listesi',
      params: ['limit (opsiyonel): Maks fon (varsayilan: 100)'],
      returns: 'code, title, kind (YAT/EMK/BYF), current_price, market_cap, investor_count',
      count: '2,598 fon'
    },
    {
      method: 'GET', path: '/api/export/fund/{code}', desc: 'Fon detay + fiyat gecmisi',
      params: ['code (zorunlu): Fon kodu (TCD, GGS)'],
      returns: 'code, title, kind, current_price, market_cap, price_history[]',
      count: 'Degisken'
    },
    {
      method: 'GET', path: '/api/export/bulk', desc: 'TEK istekte TUM tablolar (2.2M+ satir)',
      params: ['tables (opsiyonel): Tablo listesi', 'limit_per_table (opsiyonel): Maks satir'],
      returns: 'companies, financials, disclosures, shareholders, management, subsidiaries, cashflows, buybacks, ipo, funds, fund_prices, fund_allocations, prices, price_history, settlement, index',
      count: '2,246,822 toplam'
    },
    {
      method: 'GET', path: '/api/export/bulk/csv', desc: 'TUM tablolar CSV ZIP olarak',
      params: ['tables (opsiyonel): Tablo listesi'],
      returns: '16 CSV dosyasi iceren ZIP',
      count: '2,246,822 toplam'
    },
    {
      method: 'GET', path: '/api/export/csv/{table}', desc: 'Tek tabloyu CSV olarak indir',
      params: ['table (zorunlu): Tablo adi'],
      returns: 'CSV dosyasi',
      count: 'Degisken'
    },
    {
      method: 'GET', path: '/api/export/schema', desc: 'DB semasi (43 tablo, 335 sutun)',
      params: [],
      returns: 'Tum tablolar ve sutun tipleri',
      count: '43 tablo'
    }
  ];

  container.innerHTML = endpoints.map(ep => {
    const methodColor = ep.method === 'GET' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30';
    return `<div class="bg-dark-950/50 rounded-xl p-4 border border-dark-700/30">
      <div class="flex items-center gap-3 mb-2">
        <span class="px-2 py-0.5 rounded-md text-[10px] font-bold border ${methodColor}">${ep.method}</span>
        <code class="text-cyan-400 text-sm font-mono">${ep.path}</code>
        <span class="ml-auto text-[10px] text-dark-500">${ep.count}</span>
      </div>
      <p class="text-xs text-dark-400 mb-2">${ep.desc}</p>
      ${ep.params.length ? `<div class="text-[10px] text-dark-500 mb-1">Parametreler:</div><div class="text-[11px] text-dark-400 space-y-0.5">${ep.params.map(p => `<div>• ${p}</div>`).join('')}</div>` : ''}
      <div class="text-[10px] text-dark-500 mt-2">Donen alanlar: <span class="text-dark-300">${ep.returns}</span></div>
    </div>`;
  }).join('');
}

// ══════════════════════════════════════════════════════════════
// API PLAYGROUND — Enhanced Interactive Tester
// ══════════════════════════════════════════════════════════════

let apiLastResponse = '';
let apiHistory = [];

function setEndpoint(path) {
  document.getElementById('api-url-input').value = path;
  document.getElementById('api-method').value = path.includes('search') || path.includes('all') ? 'GET' : 'GET';
  runApiPlayground();
}

function showApiTab(tab) {
  ['headers','body','history','curl'].forEach(t => {
    const el = document.getElementById('api-panel-'+t);
    if(el) el.style.display = t === tab ? '' : 'none';
    const btn = document.getElementById('api-tab-'+t);
    if(btn) {
      btn.className = t === tab 
        ? 'text-[10px] px-3 py-1 rounded-lg bg-cyan-500/20 text-cyan-400 transition-all'
        : 'text-[10px] px-3 py-1 rounded-lg bg-dark-700/50 text-dark-400 hover:text-white transition-all';
    }
  });
}

function parseHeaders() {
  const raw = document.getElementById('api-headers').value.trim();
  const headers = {};
  raw.split('\n').forEach(line => {
    const [k,...v] = line.split(':');
    if(k && v.length) headers[k.trim()] = v.join(':').trim();
  });
  return headers;
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function runApiPlayground() {
  const method = document.getElementById('api-method').value;
  const urlPath = document.getElementById('api-url-input').value.trim();
  const output = document.getElementById('api-explorer-output');
  const infoEl = document.getElementById('api-response-info');
  const headers = parseHeaders();
  const body = document.getElementById('api-body').value.trim();

  if(!urlPath) { output.innerHTML = '<div class="text-red-400">URL bos olamaz!</div>'; return; }

  const fullUrl = urlPath.startsWith('http') ? urlPath : API_BASE_URL + urlPath;
  
  // Loading
  output.innerHTML = '<div class="text-cyan-400 animate-pulse">⏳ ' + method + ' ' + escapeHtml(fullUrl) + ' gonderiliyor...</div>';
  infoEl.textContent = 'Istek gonderiliyor...';
  document.getElementById('api-run-btn').disabled = true;

  const startTime = Date.now();
  try {
    const opts = { method, headers };
    if(method === 'POST' && body) {
      opts.body = body;
      if(!headers['Content-Type']) headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(fullUrl, opts);
    const elapsed = Date.now() - startTime;
    const statusColor = response.ok ? 'emerald' : 'red';
    const statusIcon = response.ok ? '✅' : '❌';

    if(!response.ok) {
      const errText = await response.text();
      output.innerHTML = `<div class="text-red-400 mb-2">${statusIcon} HTTP ${response.status} ${response.statusText} — ${elapsed}ms</div><pre class="text-dark-400 text-xs">${escapeHtml(errText.substring(0,3000))}</pre>`;
      infoEl.textContent = `HTTP ${response.status} — ${elapsed}ms`;
      apiLastResponse = errText;
      addToApiHistory(method, fullUrl, response.status, elapsed);
      return;
    }

    const contentType = response.headers.get('content-type') || '';
    if(contentType.includes('application/json')) {
      const data = await response.json();
      const jsonStr = JSON.stringify(data, null, 2);
      const lines = jsonStr.split('\n').length;
      const size = (new Blob([jsonStr]).size / 1024).toFixed(1);
      const truncated = jsonStr.length > 8000;
      const displayJson = truncated ? jsonStr.substring(0,8000) : jsonStr;

      // Syntax highlight
      const highlighted = displayJson
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"([^"]+)"(?=\s*:)/g, '<span style="color:#c084fc">"$1"</span>')
        .replace(/: "([^"]*)"/g, ': <span style="color:#34d399">"$1"</span>')
        .replace(/: (\d+\.?\d*)/g, ': <span style="color:#fbbf24">$1</span>')
        .replace(/: (true|false|null)/g, ': <span style="color:#f472b6">$1</span>');

      output.innerHTML = `<div class="mb-2 flex items-center gap-3">
        <span class="text-${statusColor}-400 font-bold">${statusIcon} HTTP ${response.status}</span>
        <span class="text-dark-500 text-xs">${elapsed}ms</span>
        <span class="text-dark-500 text-xs">${size}KB</span>
        <span class="text-dark-500 text-xs">${lines} satir</span>
      </div><pre class="text-dark-300 text-xs font-mono" style="white-space:pre-wrap;word-break:break-all">${highlighted}${truncated ? '<span class="text-dark-600">\n\n... (8KB kesildi, toplam ' + jsonStr.length + ' bayt)\n</span>' : ''}</pre>`;
      infoEl.textContent = `✅ HTTP ${response.status} — ${elapsed}ms — ${size}KB — ${lines} satir`;
      apiLastResponse = jsonStr;
    } else {
      const blob = await response.blob();
      output.innerHTML = `<div class="text-emerald-400 mb-2">✅ ${response.status} — ${elapsed}ms — ${contentType}</div><div class="text-dark-400 text-xs">Binary: ${blob.size} bayt</div>`;
      infoEl.textContent = `✅ HTTP ${response.status} — ${elapsed}ms — Binary`;
      apiLastResponse = '(binary)';
    }

    document.getElementById('api-copy-btn').style.display = '';
    document.getElementById('api-download-btn').style.display = '';
    addToApiHistory(method, fullUrl, response.status, elapsed);
  } catch(e) {
    output.innerHTML = `<div class="text-red-400">❌ Hata: ${escapeHtml(e.message)}</div><div class="text-dark-500 text-xs mt-2">Network hatasi veya CORS sorunu olabilir.</div>`;
    infoEl.textContent = '❌ ' + e.message;
    addToApiHistory(method, fullUrl, 0, Date.now()-startTime);
  }
  document.getElementById('api-run-btn').disabled = false;
}

function addToApiHistory(method, url, status, time) {
  apiHistory.unshift({ method, url: url.replace(API_BASE_URL,''), status, time, ts: new Date().toLocaleTimeString() });
  if(apiHistory.length > 50) apiHistory.pop();
  renderApiHistory();
}

function renderApiHistory() {
  const el = document.getElementById('api-history-list');
  if(!el) return;
  el.innerHTML = apiHistory.map(h => {
    const sc = h.status >= 200 && h.status < 400 ? 'text-emerald-400' : h.status === 0 ? 'text-red-400' : 'text-amber-400';
    return `<div class="flex items-center gap-2 py-1 px-2 rounded hover:bg-dark-700/30 cursor-pointer" onclick="setEndpoint('${h.url}')">
      <span class="text-[10px] font-bold w-12 ${h.method==='GET'?'text-emerald-400':'text-amber-400'}">${h.method}</span>
      <span class="text-[10px] font-mono text-dark-300 flex-1 truncate">${h.url}</span>
      <span class="text-[10px] ${sc}">${h.status || 'ERR'}</span>
      <span class="text-[10px] text-dark-500">${h.time}ms</span>
      <span class="text-[10px] text-dark-600">${h.ts}</span>
    </div>`;
  }).join('') || '<div class="text-dark-600 text-xs">Henuz istek yok...</div>';
}

function clearApiOutput() {
  document.getElementById('api-explorer-output').innerHTML = '<div class="text-dark-600">Temizlendi...</div>';
  document.getElementById('api-response-info').textContent = 'Yanit bekleniyor...';
  document.getElementById('api-copy-btn').style.display = 'none';
  document.getElementById('api-download-btn').style.display = 'none';
}

function copyApiResponse() {
  navigator.clipboard.writeText(apiLastResponse);
  toast('Yanit kopyalandi!', 'success');
}

function downloadApiResponse() {
  const blob = new Blob([apiLastResponse], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'api_response_' + Date.now() + '.json';
  a.click();
}

function importCurl() {
  const raw = document.getElementById('api-curl-input').value.trim();
  if(!raw) return;
  // Parse curl
  const methodMatch = raw.match(/-X\s+(\w+)/);
  const urlMatch = raw.match(/["']?(https?:\/\/[^\s"']+)["']?/);
  const headerMatches = [...raw.matchAll(/-H\s+["']([^"']+)["']/g)];
  const bodyMatch = raw.match(/-d\s+["'](.+?)["']$/m);

  if(urlMatch) {
    const url = urlMatch[1].replace(API_BASE_URL, '');
    document.getElementById('api-url-input').value = url;
  }
  if(methodMatch) document.getElementById('api-method').value = methodMatch[1];
  if(headerMatches.length) {
    document.getElementById('api-headers').value = headerMatches.map(m => m[1]).join('\n');
  }
  if(bodyMatch) document.getElementById('api-body').value = bodyMatch[1];
  showApiTab('headers');
  toast('cURL import edildi!', 'success');
}

function copyApiUrl() {
  navigator.clipboard.writeText(API_BASE_URL);
  toast('URL kopyalandi!', 'success');
}
