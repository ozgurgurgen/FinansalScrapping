#!/usr/bin/env python3
"""Generate the Finance Pipeline admin dashboard HTML file."""
import pathlib

HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Finance Pipeline — Command Center</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config={darkMode:'class',theme:{extend:{colors:{dark:{950:'#0b0f17',900:'#0f172a',850:'#162032',800:'#1e293b',700:'#334155',600:'#475569',500:'#64748b',400:'#94a3b8',300:'#cbd5e1',200:'#e2e8f0',100:'#f1f5f9'}},fontFamily:{sans:['system-ui','-apple-system','sans-serif'],mono:['ui-monospace','SFMono-Regular','Menlo','Consolas','monospace']}}}}
</script>
<style>
*{scrollbar-width:thin;scrollbar-color:#334155 #0f172a}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:#0f172a}
::-webkit-scrollbar-thumb{background:#334155;border-radius:999px}
body{background:#0b0f17;color:#f1f5f9;font-family:system-ui,-apple-system,sans-serif}
.glass-strong{background:rgba(15,23,42,0.8);backdrop-filter:blur(24px);border:1px solid rgba(51,65,85,0.5);border-radius:16px}
.stat-chip{background:rgba(30,41,59,0.5);border:1px solid rgba(51,65,85,0.3);border-radius:12px;padding:12px 16px;text-align:center;transition:all 0.2s}
.stat-chip:hover{border-color:rgba(99,102,241,0.3);background:rgba(30,41,59,0.7)}
@keyframes pulseRing{0%{transform:scale(1);opacity:.8}100%{transform:scale(2.2);opacity:0}}
.live-dot{position:relative}
.live-dot::after{content:'';position:absolute;inset:-2px;border-radius:50%;border:2px solid currentColor;animation:pulseRing 2s ease-out infinite}
.tab-link{position:relative;color:#64748b;transition:color 0.15s}
.tab-link:hover{color:#94a3b8}
.tab-link.active{color:#06b6d4}
.tab-link.active::after{content:'';position:absolute;bottom:-1px;left:0;right:0;height:2px;background:linear-gradient(90deg,#06b6d4,#8b5cf6);border-radius:2px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:10px;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.15s;border:1px solid transparent}
.btn:active{transform:scale(0.96)}
.btn-cyan{background:rgba(6,182,212,0.15);color:#22d3ee;border-color:rgba(6,182,212,0.3)}
.btn-cyan:hover{background:rgba(6,182,212,0.25)}
.btn-emerald{background:rgba(16,185,129,0.15);color:#34d399;border-color:rgba(16,185,129,0.3)}
.btn-emerald:hover{background:rgba(16,185,129,0.25)}
.btn-rose{background:rgba(244,63,94,0.15);color:#fb7185;border-color:rgba(244,63,94,0.3)}
.btn-rose:hover{background:rgba(244,63,94,0.25)}
.btn-slate{background:rgba(30,41,59,0.6);color:#cbd5e1;border-color:rgba(51,65,85,0.5)}
.btn-slate:hover{background:rgba(51,65,85,0.6)}
.toggle{position:relative;width:40px;height:22px;cursor:pointer}
.toggle input{opacity:0;width:0;height:0}
.toggle-track{position:absolute;inset:0;background:#334155;border-radius:22px;transition:0.3s}
.toggle-thumb{position:absolute;top:2px;left:2px;width:18px;height:18px;background:white;border-radius:50%;transition:0.3s}
.toggle input:checked+.toggle-track{background:#0891b2}
.toggle input:checked+.toggle-track+.toggle-thumb{transform:translateX(18px)}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px}
.badge-running{background:rgba(16,185,129,0.12);color:#34d399;border:1px solid rgba(16,185,129,0.25)}
.badge-stopped{background:rgba(244,63,94,0.12);color:#fb7185;border:1px solid rgba(244,63,94,0.25)}
.badge-scraping{background:rgba(6,182,212,0.12);color:#22d3ee;border:1px solid rgba(6,182,212,0.25)}
.badge-idle{background:rgba(100,116,139,0.12);color:#94a3b8;border:1px solid rgba(100,116,139,0.25)}
.terminal{background:#080c14;border:1px solid rgba(51,65,85,0.3);border-radius:12px;font-family:ui-monospace,Consolas,monospace;font-size:11px;line-height:1.7;color:#64748b;padding:14px;overflow-y:auto;height:340px}
.terminal::-webkit-scrollbar{width:4px}
.terminal::-webkit-scrollbar-thumb{background:#1e293b;border-radius:4px}
.log-error{color:#f87171!important}.log-success{color:#34d399!important}.log-info{color:#38bdf8!important}.log-warn{color:#fbbf24!important}
.data-table{width:100%;border-collapse:collapse}
.data-table th{text-align:left;padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:#475569;border-bottom:1px solid rgba(51,65,85,0.3);font-weight:600}
.data-table td{padding:8px 12px;font-size:13px;border-bottom:1px solid rgba(15,23,42,0.8)}
.data-table tr:hover td{background:rgba(30,41,59,0.3)}
.input-dark{background:rgba(15,23,42,0.8);color:#f1f5f9;border:1px solid rgba(51,65,85,0.4);border-radius:8px;padding:6px 10px;font-size:12px;outline:none;transition:border-color 0.15s}
.input-dark:focus{border-color:rgba(6,182,212,0.5)}
.input-dark::placeholder{color:#475569}
.fade-up{animation:fadeUp .35s ease-out}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
</style>
</head>
<body class="min-h-screen antialiased">
<header class="sticky top-0 z-50 border-b border-dark-700/60" style="background:rgba(11,15,23,0.85);backdrop-filter:blur(20px)">
<div class="max-w-[1440px] mx-auto px-6 py-3 flex items-center justify-between">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-black text-sm" style="background:linear-gradient(135deg,#06b6d4,#8b5cf6)">FP</div>
    <div>
      <h1 class="text-base font-bold text-white tracking-tight flex items-center gap-2">Finance Pipeline <span class="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-cyan-500/15 text-cyan-400 border border-cyan-500/20">v2.0</span></h1>
      <p class="text-[10px] text-dark-500 tracking-widest uppercase">Command Center</p>
    </div>
  </div>
  <div class="flex items-center gap-4">
    <div id="docker-badge" class="badge badge-idle"><span class="w-1.5 h-1.5 rounded-full bg-dark-500"></span> Local</div>
    <div class="h-4 w-px bg-dark-700"></div>
    <span id="clock" class="font-mono text-dark-500 text-xs"></span>
  </div>
</div>
</header>
<nav class="max-w-[1440px] mx-auto px-6 pt-3">
<div class="flex gap-0.5 border-b border-dark-700/50 overflow-x-auto">
  <button onclick="showTab('services')" id="tab-services" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">🖥️ Servisler</button>
  <button onclick="showTab('dataflow')" id="tab-dataflow" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">📡 Veri Akisi</button>
  <button onclick="showTab('funds')" id="tab-funds" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">💰 TEFAS Fonlar</button>
  <button onclick="showTab('market')" id="tab-market" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">🌍 Piyasa</button>
  <button onclick="showTab('kap')" id="tab-kap" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">📈 KAP</button>
  <button onclick="showTab('schedule')" id="tab-schedule" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">⏰ Zamanlama</button>
</div>
</nav>
<main class="max-w-[1440px] mx-auto px-6 py-5 space-y-5">

<!-- SERVICES PAGE -->
<div id="page-services">
<div id="global-stats" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3"></div>
<div id="services-container" class="space-y-4 mt-4"></div>
<div class="glass-strong p-5 mt-4">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center gap-2.5"><span class="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-500/15 text-amber-400 text-sm">⚡</span><div><span class="font-bold text-white text-sm">KAP Modul Yonetimi</span><p class="text-[10px] text-dark-500">Tek tek veya toplu calistir</p></div></div>
    <button onclick="triggerKapAll()" class="btn btn-cyan" id="kap-all-btn">⚡ Tumu Calistir</button>
  </div>
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5" id="kap-modules-grid"></div>
</div>
<div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-4">
  <div class="glass-strong p-5">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2"><span class="text-xs">🖥️</span><span class="font-bold text-white text-sm">Canli Terminal</span></div>
      <div class="flex items-center gap-2">
        <select id="log-select" class="input-dark text-xs py-1"><option value="kap_worker">KAP</option><option value="tefas_worker">TEFAS</option><option value="market_data_worker">Market</option></select>
        <button onclick="fetchLogs()" class="btn btn-slate text-[10px] py-1 px-2">🔄</button>
        <label class="flex items-center gap-1.5 text-[11px] text-dark-500 cursor-pointer"><input type="checkbox" id="auto-log" checked class="rounded"> Auto</label>
      </div>
    </div>
    <div id="terminal" class="terminal"><div class="text-dark-600">Log bekleniyor...</div></div>
  </div>
  <div class="glass-strong p-5">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2"><span class="text-xs">📊</span><span class="font-bold text-white text-sm">Son Islemler</span></div>
      <button onclick="refreshHistory()" class="btn btn-slate text-[10px] py-1 px-2">🔄 Yenile</button>
    </div>
    <div class="overflow-y-auto" style="max-height:300px"><table class="data-table"><thead><tr><th>Servis</th><th>Modul</th><th>Durum</th><th class="text-right">Kayit</th><th>Sure</th></tr></thead><tbody id="history-body"><tr><td colspan="5" class="text-center text-dark-600 py-6">Yukleniyor...</td></tr></tbody></table></div>
  </div>
</div>
</div>

<!-- DATA FLOW PAGE -->
<div id="page-dataflow" style="display:none">
<div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
  <div class="lg:col-span-2 glass-strong p-5">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2.5"><span class="w-8 h-8 rounded-lg flex items-center justify-center bg-cyan-500/15 text-cyan-400 text-sm live-dot">📡</span><div><span class="font-bold text-white text-sm">Canli Veri Akisi</span><p class="text-[10px] text-dark-500">Gercek zamanli veri cekim loglari</p></div></div>
      <div class="flex items-center gap-2">
        <select id="flow-log-select" class="input-dark text-xs py-1"><option value="all">Tum Servisler</option><option value="kap_worker">KAP</option><option value="tefas_worker">TEFAS</option><option value="market_data_worker">Market</option></select>
        <button onclick="fetchFlowLogs()" class="btn btn-slate text-[10px] py-1 px-2">🔄</button>
      </div>
    </div>
    <div id="flow-terminal" class="terminal" style="height:450px"><div class="text-dark-600">Veri akisi bekleniyor...</div></div>
  </div>
  <div class="space-y-4">
    <div class="glass-strong p-5"><div class="flex items-center gap-2 mb-3"><span class="text-sm">📊</span><span class="font-bold text-white text-sm">Aktiflik Ozeti</span></div><div id="activity-stats" class="space-y-3"></div></div>
    <div class="glass-strong p-5"><div class="flex items-center gap-2 mb-3"><span class="text-sm">🕐</span><span class="font-bold text-white text-sm">Son Guncellemeler</span></div><div id="recent-updates" class="space-y-2"></div></div>
    <div class="glass-strong p-5"><div class="flex items-center gap-2 mb-3"><span class="text-sm">⚠️</span><span class="font-bold text-white text-sm">Ban Durumu</span></div><div id="ban-overview"></div></div>
  </div>
</div>
</div>

<!-- FUNDS PAGE -->
<div id="page-funds" style="display:none">
<div class="glass-strong p-5 mb-5">
  <div class="flex items-center gap-4 flex-wrap">
    <div class="flex items-center gap-2"><span class="w-8 h-8 rounded-lg flex items-center justify-center bg-purple-500/15 text-purple-400 text-sm">💰</span><span class="font-bold text-white">Fon Sec:</span></div>
    <select id="fund-select" class="input-dark py-2" style="min-width:280px"><option value="">Fon seciniz...</option></select>
    <button onclick="loadFundDetail()" class="btn btn-cyan">🔍 Gorester</button>
    <div class="ml-auto flex gap-1.5">
      <button onclick="loadFundChart(90)" class="btn btn-slate text-[11px] py-1">3 Ay</button>
      <button onclick="loadFundChart(180)" class="btn btn-slate text-[11px] py-1">6 Ay</button>
      <button onclick="loadFundChart(365)" class="btn btn-slate text-[11px] py-1">1 Yil</button>
      <button onclick="loadFundChart(730)" class="btn btn-slate text-[11px] py-1">2 Yil</button>
      <button onclick="loadFundChart(1825)" class="btn btn-slate text-[11px] py-1">5 Yil</button>
    </div>
  </div>
</div>
<div id="fund-info" style="display:none">
  <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 mb-4" id="fund-stats-grid"></div>
  <div class="glass-strong p-5 mb-4" id="fund-title-card" style="display:none">
    <div class="flex items-center gap-3"><span class="w-10 h-10 rounded-xl flex items-center justify-center bg-purple-500/15 text-purple-400">📊</span><div><h2 id="fund-title" class="text-lg font-bold text-white"></h2><p id="fund-subtitle" class="text-xs text-dark-500 mt-0.5"></p></div></div>
  </div>
  <div class="glass-strong p-5 mb-4">
    <div class="flex items-center justify-between mb-3"><span class="font-bold text-white text-sm">📈 Fiyat Grafigi</span><span id="chart-range" class="text-xs text-dark-500 font-mono"></span></div>
    <canvas id="price-chart" height="220"></canvas>
  </div>
  <div class="glass-strong p-5">
    <div class="flex items-center justify-between mb-3"><span class="font-bold text-white text-sm">📋 Fiyat Gecmisi</span><span id="table-count" class="text-xs text-dark-500"></span></div>
    <div class="overflow-y-auto" style="max-height:400px"><table class="data-table"><thead><tr><th>Tarih</th><th class="text-right">Fiyat (TL)</th><th class="text-right">Degisim</th><th class="text-right">lk Fiyata Gore</th></tr></thead><tbody id="fund-price-body"></tbody></table></div>
  </div>
</div>
<div id="fund-empty" class="glass-strong text-center py-16"><div class="text-5xl mb-3 opacity-40">💰</div><div class="text-dark-500 font-medium">Yukaridan bir fon secin</div><div class="text-xs text-dark-600 mt-1.5">Fiyat gecmisi, grafik ve istatistikler burada gorunecek</div></div>
</div>

<!-- MARKET PAGE -->
<div id="page-market" style="display:none">
<div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
  <div class="glass-strong p-5"><div class="flex items-center gap-2 mb-4"><span class="w-7 h-7 rounded-lg flex items-center justify-center bg-sky-500/15 text-sky-400 text-xs">💱</span><span class="font-bold text-white text-sm">Doviz Kurlari</span></div><div id="fx-rates" class="space-y-2"></div></div>
  <div class="glass-strong p-5"><div class="flex items-center gap-2 mb-4"><span class="w-7 h-7 rounded-lg flex items-center justify-center bg-amber-500/15 text-amber-400 text-xs">₿</span><span class="font-bold text-white text-sm">Kripto Para</span></div><div id="crypto-rates" class="space-y-2"></div></div>
  <div class="glass-strong p-5"><div class="flex items-center gap-2 mb-4"><span class="w-7 h-7 rounded-lg flex items-center justify-center bg-emerald-500/15 text-emerald-400 text-xs">🥇</span><span class="font-bold text-white text-sm">Emtia & Metaller</span></div><div id="commodity-rates" class="space-y-2"></div></div>
</div>
</div>

<!-- KAP PAGE -->
<div id="page-kap" style="display:none">
<div class="flex gap-0.5 border-b border-dark-700/50 mb-5 overflow-x-auto">
  <button onclick="showKapTab('disclosures')" id="ktab-disclosures" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">📢 Bildirimler</button>
  <button onclick="showKapTab('companies')" id="ktab-companies" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">🏢 Sirketler</button>
  <button onclick="showKapTab('corporate')" id="ktab-corporate" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">🎯 Kurumsal</button>
  <button onclick="showKapTab('buybacks')" id="ktab-buybacks" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">💰 Gerialim</button>
  <button onclick="showKapTab('ipo')" id="ktab-ipo" class="tab-link px-4 py-2.5 text-sm font-semibold whitespace-nowrap">🏆 IPO</button>
</div>
<div id="kap-disclosures">
  <div class="glass-strong p-4 mb-4"><div class="flex items-center gap-3 flex-wrap">
    <select id="kap-cat-filter" class="input-dark text-xs py-1.5"><option value="">Tum Kategoriler</option></select>
    <input id="kap-sym-filter" placeholder="Sembol ara..." class="input-dark text-xs py-1.5 w-28">
    <select id="kap-days-filter" class="input-dark text-xs py-1.5"><option value="7">Son 7 gun</option><option value="30" selected>Son 30 gun</option><option value="90">Son 90 gun</option><option value="365">Son 1 yil</option></select>
    <button onclick="loadKapDisclosures()" class="btn btn-cyan text-[11px] py-1">🔍 Ara</button>
  </div></div>
  <div class="glass-strong p-5"><div class="overflow-y-auto" style="max-height:520px"><table class="data-table"><thead><tr><th>Sembol</th><th>Baslik</th><th>Kategori</th><th>Tarih</th><th>Katalizor</th></tr></thead><tbody id="kap-disc-body"><tr><td colspan="5" class="text-center text-dark-600 py-6">Filtre secin ve "Ara" basin</td></tr></tbody></table></div>
  <div class="flex justify-between items-center mt-3 pt-3 border-t border-dark-700/30"><span id="kap-disc-count" class="text-xs text-dark-500"></span><div class="flex gap-1"><button onclick="kapDiscPage(-1)" class="btn btn-slate text-[10px] py-0.5 px-2">⬅</button><button onclick="kapDiscPage(1)" class="btn btn-slate text-[10px] py-0.5 px-2">➡</button></div></div></div>
</div>
<div id="kap-companies" style="display:none">
  <div class="glass-strong p-4 mb-4"><div class="flex items-center gap-3"><input id="kap-com-search" placeholder="Sirket adi veya kodu ara..." class="input-dark text-xs py-1.5 w-48"><button onclick="loadKapCompanies()" class="btn btn-cyan text-[11px] py-1">🔍 Ara</button></div></div>
  <div class="glass-strong p-5"><div class="overflow-y-auto" style="max-height:520px"><table class="data-table"><thead><tr><th>Kod</th><th>Sirket</th><th>Sektor</th><th>Pazar</th></tr></thead><tbody id="kap-com-body"><tr><td colspan="4" class="text-center text-dark-600 py-6">Yukleniyor...</td></tr></tbody></table></div>
  <div class="flex justify-between items-center mt-3 pt-3 border-t border-dark-700/30"><span id="kap-com-count" class="text-xs text-dark-500"></span><div class="flex gap-1"><button onclick="kapComPage(-1)" class="btn btn-slate text-[10px] py-0.5 px-2">⬅</button><button onclick="kapComPage(1)" class="btn btn-slate text-[10px] py-0.5 px-2">➡</button></div></div></div>
</div>
<div id="kap-corporate" style="display:none"><div class="glass-strong p-5"><div class="flex items-center justify-between mb-3"><span class="font-bold text-white text-sm">🎯 Kurumsal Islemler</span><button onclick="loadKapCorporate()" class="btn btn-slate text-[10px] py-1 px-2">🔄 Yenile</button></div><div class="overflow-y-auto" style="max-height:520px"><table class="data-table"><thead><tr><th>Sirket</th><th>Tip</th><th>Brut/Hisse</th><th>Net/Hisse</th><th>Verim</th><th>Hak Kullanim</th><th>Odeme</th><th>Durum</th></tr></thead><tbody id="kap-corp-body"><tr><td colspan="8" class="text-center text-dark-600 py-6">Yukleniyor...</td></tr></tbody></table></div><div class="flex justify-between items-center mt-3 pt-3 border-t border-dark-700/30"><span id="kap-corp-count" class="text-xs text-dark-500"></span><div class="flex gap-1"><button onclick="kapCorpPage(-1)" class="btn btn-slate text-[10px] py-0.5 px-2">⬅</button><button onclick="kapCorpPage(1)" class="btn btn-slate text-[10px] py-0.5 px-2">➡</button></div></div></div></div>
<div id="kap-buybacks" style="display:none"><div class="glass-strong p-5"><div class="flex items-center justify-between mb-3"><span class="font-bold text-white text-sm">💰 Pay Gerialim Programlari</span><button onclick="loadKapBuybacks()" class="btn btn-slate text-[10px] py-1 px-2">🔄 Yenile</button></div><div class="overflow-y-auto" style="max-height:520px"><table class="data-table"><thead><tr><th>Sirket</th><th>Butce</th><th>Azami Pay</th><th>Geri Alinan</th><th>Sermaye %</th><th>Ort. Maliyet</th></tr></thead><tbody id="kap-bb-body"><tr><td colspan="6" class="text-center text-dark-600 py-6">Yukleniyor...</td></tr></tbody></table></div><div class="flex justify-between items-center mt-3 pt-3 border-t border-dark-700/30"><span id="kap-bb-count" class="text-xs text-dark-500"></span><div class="flex gap-1"><button onclick="kapBbPage(-1)" class="btn btn-slate text-[10px] py-0.5 px-2">⬅</button><button onclick="kapBbPage(1)" class="btn btn-slate text-[10px] py-0.5 px-2">➡</button></div></div></div></div>
<div id="kap-ipo" style="display:none"><div class="glass-strong p-5"><div class="flex items-center justify-between mb-3"><span class="font-bold text-white text-sm">🏆 Halka Arz (IPO)</span><button onclick="loadKapIpo()" class="btn btn-slate text-[10px] py-1 px-2">🔄 Yenile</button></div><div class="overflow-y-auto" style="max-height:520px"><table class="data-table"><thead><tr><th>Sirket</th><th>Fiyat</th><th>Iskonto</th><th>Dagitim</th><th>Yatirim %</th><th>Ar-Ge %</th><th>Sermaye %</th><th>Borc %</th></tr></thead><tbody id="kap-ipo-body"><tr><td colspan="8" class="text-center text-dark-600 py-6">Yukleniyor...</td></tr></tbody></table></div><div class="flex justify-between items-center mt-3 pt-3 border-t border-dark-700/30"><span id="kap-ipo-count" class="text-xs text-dark-500"></span><div class="flex gap-1"><button onclick="kapIpoPage(-1)" class="btn btn-slate text-[10px] py-0.5 px-2">⬅</button><button onclick="kapIpoPage(1)" class="btn btn-slate text-[10px] py-0.5 px-2">➡</button></div></div></div></div>
</div>

<!-- SCHEDULE PAGE -->
<div id="page-schedule" style="display:none">
<div class="glass-strong p-5 mb-5">
  <div class="flex items-center justify-between mb-4"><div class="flex items-center gap-2.5"><span class="w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-500/15 text-emerald-400 text-sm">⏰</span><span class="font-bold text-white text-sm">Siradaki Calisma Zamanlari</span></div><button onclick="loadSchedule()" class="btn btn-slate text-[10px] py-1 px-2">🔄 Yenile</button></div>
  <div id="next-runs-container" class="grid grid-cols-1 sm:grid-cols-2 gap-3"><div class="text-dark-600 text-xs">Yukleniyor...</div></div>
</div>
<div class="glass-strong p-5">
  <div class="flex items-center justify-between mb-5"><div class="flex items-center gap-2.5"><span class="w-8 h-8 rounded-lg flex items-center justify-center bg-dark-800 text-sm">⚙️</span><span class="font-bold text-white text-sm">Zamanlama Ayarlari</span></div><button onclick="saveSchedule()" class="btn btn-emerald">💾 Kaydet</button></div>
  <div class="mb-5 p-4 rounded-xl bg-dark-950/50 border border-dark-700/30">
    <div class="flex items-center gap-2 mb-3"><span class="text-sky-400 font-bold text-sm">📈 KAP Worker</span></div>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div><label class="text-[10px] text-dark-500 uppercase tracking-wider">Durum</label><label class="toggle mt-1.5"><input type="checkbox" id="kap-enabled" checked><span class="toggle-track"></span><span class="toggle-thumb"></span></label></div>
      <div><label class="text-[10px] text-dark-500 uppercase tracking-wider">Mod</label><select id="kap-mode" class="input-dark w-full mt-1.5 py-1.5"><option value="manual">Sadece Manuel</option><option value="daily" selected>Her Gun</option><option value="interval">Belirli Aralikla</option></select></div>
      <div id="kap-time-group"><label class="text-[10px] text-dark-500 uppercase tracking-wider">Saat</label><input type="time" id="kap-time" value="02:00" class="input-dark w-full mt-1.5 py-1.5"></div>
      <div id="kap-interval-group" style="display:none"><label class="text-[10px] text-dark-500 uppercase tracking-wider">Aralik (dk)</label><input type="number" id="kap-interval" value="60" min="5" class="input-dark w-full mt-1.5 py-1.5"></div>
    </div>
  </div>
  <div class="p-4 rounded-xl bg-dark-950/50 border border-dark-700/30">
    <div class="flex items-center gap-2 mb-3"><span class="text-purple-400 font-bold text-sm">💹 TEFAS Worker</span></div>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div><label class="text-[10px] text-dark-500 uppercase tracking-wider">Durum</label><label class="toggle mt-1.5"><input type="checkbox" id="tefas-enabled" checked><span class="toggle-track"></span><span class="toggle-thumb"></span></label></div>
      <div><label class="text-[10px] text-dark-500 uppercase tracking-wider">Mod</label><select id="tefas-mode" class="input-dark w-full mt-1.5 py-1.5"><option value="manual">Sadece Manuel</option><option value="daily" selected>Her Gun</option><option value="interval">Belirli Aralikla</option></select></div>
      <div id="tefas-time-group"><label class="text-[10px] text-dark-500 uppercase tracking-wider">Saat</label><input type="time" id="tefas-time" value="03:00" class="input-dark w-full mt-1.5 py-1.5"></div>
      <div id="tefas-interval-group" style="display:none"><label class="text-[10px] text-dark-500 uppercase tracking-wider">Aralik (dk)</label><input type="number" id="tefas-interval" value="60" min="5" class="input-dark w-full mt-1.5 py-1.5"></div>
    </div>
    <div class="mt-3"><label class="text-[10px] text-dark-500 uppercase tracking-wider">Gecmis Yil</label><select id="tefas-years" class="input-dark mt-1.5 py-1.5" style="width:100px"><option value="1">1 Yil</option><option value="2">2 Yil</option><option value="3">3 Yil</option><option value="5" selected>5 Yil</option></select></div>
  </div>
</div>
</div>

</main>
<script src="app.js"></script>
</body>
</html>'''

pathlib.Path('services/admin_dashboard/templates/index.html').write_text(HTML, encoding='utf-8')
print(f"Written {len(HTML)} bytes")
