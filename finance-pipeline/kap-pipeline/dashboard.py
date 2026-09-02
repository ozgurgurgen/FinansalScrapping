"""
KAP Pipeline Dashboard v4
"""

import os, sys, time, json, threading, queue
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")
sys.path.insert(0, os.path.dirname(__file__))

from database import (
    init_db, get_session, Company, Financial, Disclosure,
    OrderBacklog, CorporateAction, ShareBuyback, IpoData,
    Shareholder, PipelineRun,
)
from scheduler import SCHEDULE, run_module_by_id, get_next_runs, JOB_MAP

st.set_page_config(page_title="KAP Pipeline", page_icon="\u26a1", layout="wide")

def sf(val):
    if val is None: return None
    try: return float(val)
    except: return None

@st.cache_resource
def get_s():
    init_db()
    return get_session()

def cnt(q): return q.count()
def tc(val):
    v = sf(val)
    if v is None: return "-"
    if abs(v) >= 1e12: return f"{v/1e12:.1f} T"
    if abs(v) >= 1e9: return f"{v/1e9:.1f} Mrd"
    if abs(v) >= 1e6: return f"{v/1e6:.0f} Mn"
    if abs(v) >= 1e3: return f"{v/1e3:.0f} B"
    return f"{v:.0f}"
def pct(val):
    v = sf(val)
    return f"{v*100:.1f}%" if v is not None else "-"

# CSS
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 10px 14px; border-left: 3px solid #667eea; }
    .svc-card {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        border-radius: 12px; padding: 16px 20px; color: white; text-decoration: none;
        display: block; transition: transform 0.2s; margin-bottom: 8px;
    }
    .svc-card:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(102,126,234,0.4); }
    .svc-card h3 { margin: 0; font-size: 1rem; }
    .svc-card .url { font-family: monospace; color: #2ed573; font-size: 0.8rem; margin-top: 6px; }
    .status-ok { background: #d4edda; color: #155724; padding: 3px 12px; border-radius: 12px; font-weight: 600; font-size: 0.8rem; }
    .status-wait { background: #fff3cd; color: #856404; padding: 3px 12px; border-radius: 12px; font-weight: 600; font-size: 0.8rem; }
    .status-off { background: #e9ecef; color: #6c757d; padding: 3px 12px; border-radius: 12px; font-weight: 600; font-size: 0.8rem; }
    .stream-box {
        background: #1a1a2e; color: #2ed573; border-radius: 8px; padding: 12px 16px;
        font-family: 'Courier New', monospace; font-size: 0.82rem; line-height: 1.6;
        max-height: 400px; overflow-y: auto; margin: 8px 0;
    }
    .stream-line { margin: 2px 0; }
    .stream-ok { color: #2ed573; }
    .stream-err { color: #ff4757; }
    .stream-info { color: #70a1ff; }
    .stream-warn { color: #ffa502; }
</style>
""", unsafe_allow_html=True)

s = get_s()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# KAP Pipeline")
    st.markdown("---")

    # Servis linkleri
    st.markdown("### Servisler")
    st.link_button("Swagger Docs", "http://localhost:8000/docs", use_container_width=True)
    st.link_button("ReDoc", "http://localhost:8000/redoc", use_container_width=True)
    st.link_button("API Durum", "http://localhost:8000/api/status", use_container_width=True)

    st.markdown("---")
    st.markdown("### Veritabani")
    for label, model in [("Sirket", Company), ("Finansal", Financial),
                         ("Bildirim", Disclosure), ("Kurumsal", CorporateAction)]:
        st.text(f"  {label:12s} {cnt(s.query(model)):>6,}")

    st.markdown("---")
    last = s.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
    if last:
        icon = "OK" if last.status == "SUCCESS" else "X"
        st.caption(f"Son: {last.module_name} ({last.started_at.strftime('%d.%m %H:%M') if last.started_at else '-'})")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: CANLI VERI AKISI
# ══════════════════════════════════════════════════════════════════════════════
def page_live_stream():
    st.markdown("# \U0001f4e1 Canli Veri Akisi")
    st.markdown("Modulleri calistirin, verileri canli olarak izleyin.")

    # Module buttons
    st.markdown("### \U0001f680 Modul Calistir")
    cols = st.columns(4)
    modules = [
        ("module1_seed", "\U0001f3e2 Sirket Cek", "BIST sirket listesi + permaLink"),
        ("module2_financials", "\U0001f4c8 Finansal Cek", "Bilancho & gelir tablosu"),
        ("module3_live_feed", "\U0001f4e1 Bildirim Cek", "KAP bildirimleri"),
        ("module4_corporate", "\U0001f3af Kurumsal", "Temettu & sermaye"),
        ("module5_buybacks", "\U0001f4b0 Geri Alim", "Pay geri alim programlari"),
        ("module6_ipo", "\U0001f3c6 IPO", "Halka arz verileri"),
        ("module7_ownership", "\U0001f465 Ortaklik", "Ortaklik yapisi"),
    ]

    for i, (mod_id, label, desc) in enumerate(modules):
        with cols[i % 4]:
            if st.button(label, key=f"live_{mod_id}", use_container_width=True):
                # Run in placeholder and stream output
                placeholder = st.empty()
                log_lines = []

                log_lines.append(f'<div class="stream-line stream-info">[{datetime.now().strftime("%H:%M:%S")}] {label} baslatiliyor...</div>')
                placeholder.markdown(f'<div class="stream-box">{"".join(log_lines)}</div>', unsafe_allow_html=True)

                # Capture the module execution with simulated progress
                import io, contextlib
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    try:
                        status, count = run_module_by_id(mod_id)
                    except Exception as e:
                        status = "FAILED"
                        count = 0

                output = f.getvalue()
                for line in output.split("\n"):
                    if line.strip():
                        cls = "stream-ok" if "SUCCESS" in line or "complete" in line.lower() else "stream-err" if "ERROR" in line or "FAILED" in line else "stream-info"
                        log_lines.append(f'<div class="stream-line {cls}">{line}</div>')

                if status == "SUCCESS":
                    log_lines.append(f'<div class="stream-line stream-ok">[{datetime.now().strftime("%H:%M:%S")}] TAMAMLANDI - {count} kayit islendi</div>')
                else:
                    log_lines.append(f'<div class="stream-line stream-err">[{datetime.now().strftime("%H:%M:%S")}] BASARISIZ - API erisilemez veya veri yok</div>')

                placeholder.markdown(f'<div class="stream-box">{"".join(log_lines)}</div>', unsafe_allow_html=True)
                st.rerun()

    st.markdown("---")

    # Live log from last runs
    st.markdown("### \U0001f4dc Son Isleme Loglari")
    runs = s.query(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(15).all()
    if runs:
        for r in runs:
            icon = "\u2705" if r.status == "SUCCESS" else "\u274c" if r.status == "FAILED" else "\u23f3"
            time_str = r.started_at.strftime("%d.%m %H:%M:%S") if r.started_at else "-"
            dur = ""
            if r.started_at and r.finished_at:
                d = (r.finished_at - r.started_at).total_seconds()
                dur = f" ({d:.1f}s)"

            color = "#2ed573" if r.status == "SUCCESS" else "#ff4757" if r.status == "FAILED" else "#ffa502"
            msg = r.error_message if r.status == "FAILED" and r.error_message else f"{r.records_processed} kayit islendi"
            if r.status == "SUCCESS" and r.records_processed == 0:
                msg = "Veri bulunamadi (API rate-limit veya bos sonuc)"

            st.markdown(f"""
            <div style="background:#f8f9fa;border-radius:8px;padding:10px 14px;margin:4px 0;border-left:3px solid {color};">
                <span style="font-weight:600;">{icon} {r.module_name}</span>
                <span style="color:#666;font-size:0.85rem;margin-left:12px;">{time_str}{dur}</span>
                <span style="color:#999;font-size:0.85rem;margin-left:12px;">{msg}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Henuz isleme logu yok.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: MODUL DURUMLARI
# ══════════════════════════════════════════════════════════════════════════════
def page_module_status():
    st.markdown("# \u2699\ufe0f Modul Durumlari")

    modules = [
        {"id": "module1_seed", "name": "Module 1: Sirket Listesi", "icon": "\U0001f3e2",
         "model": Company, "desc": "BIST sirketleri, ticker, mkk_id, permaLink cekme",
         "what": "KAP web sitesinden sirket listesi HTML olarak parse edilir",
         "works": True},
        {"id": "module2_financials", "name": "Module 2: Mali Tablolar", "icon": "\U0001f4c8",
         "model": Financial, "desc": "Bilancho, gelir tablosu, rasyolar",
         "what": "Her sirketin finansal bilgi sayfasindaki HTML tablolari parse edilir",
         "works": True},
        {"id": "module3_live_feed", "name": "Module 3: Canli Akis", "icon": "\U0001f4e1",
         "model": Disclosure, "desc": "KAP bildirimleri, kategori etiketleme",
         "what": "byCriteria API + pykap ile tum bildirim turleri cekilir",
         "works": True},
        {"id": "module4_corporate", "name": "Module 4: Kurumsal Islemler", "icon": "\U0001f3af",
         "model": CorporateAction, "desc": "Temettu, bedelli/bedelsiz, sermaye artirimi",
         "what": "Modul 3 bildirimleri uzerinden regex ile veri cikarilir",
         "works": True},
        {"id": "module5_buybacks", "name": "Module 5: Pay Geri Alim", "icon": "\U0001f4b0",
         "model": ShareBuyback, "desc": "Geri alim programlari",
         "what": "Modul 3 bildirimleri uzerinden geri alim verileri cikarilir",
         "works": True},
        {"id": "module6_ipo", "name": "Module 6: IPO", "icon": "\U0001f3c6",
         "model": IpoData, "desc": "Halka arz izahname verileri",
         "what": "Modul 3 bildirimleri uzerinden IPO verileri cikarilir",
         "works": True},
        {"id": "module7_ownership", "name": "Module 7: Ortaklik Yapisi", "icon": "\U0001f465",
         "model": Shareholder, "desc": "Ortaklar, pay oranlari",
         "what": "Sirket bilgi sayfasindaki ortaklik tablosu parse edilir",
         "works": False, "issue": "KAP Next.js'e gecti, eski HTML sayfalari 404 donuyor"},
    ]

    for mod in modules:
        total = cnt(s.query(mod["model"]))
        last_run = s.query(PipelineRun).filter(PipelineRun.module_name == mod["id"]).order_by(PipelineRun.started_at.desc()).first()
        last_status = last_run.status if last_run else None

        # Determine display status
        if total > 0 and mod["works"]:
            badge = '<span class="status-ok">\u2705 AKTIF</span>'
            detail = f"{total:,} kayit veritabaninda"
        elif total > 0 and not mod["works"]:
            badge = '<span class="status-wait">\u26a0\uFE0F KISMI</span>'
            detail = f"{total:,} kayit var ama guncellenemiyor"
        elif last_status == "SUCCESS" and last_run and last_run.records_processed == 0:
            badge = '<span class="status-wait">\u26a0\uFE0F BEKLEMEDE</span>'
            detail = mod.get("issue", "Veri henuz cekilmemis")
        elif last_status == "FAILED":
            badge = '<span class="status-off">\u274c HATALI</span>'
            detail = mod.get("issue", "Son calistirma basarisiz")
        else:
            badge = '<span class="status-off">\u25cb CALISMADI</span>'
            detail = mod.get("issue", "Henuz calistirilmamis")

        st.markdown(f"""
        <div style="background:white;border:1px solid #e9ecef;border-radius:10px;padding:14px 18px;margin:6px 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="font-size:1.1rem;font-weight:600;">{mod['icon']} {mod['name']}</span>
                    <span style="margin-left:8px;">{badge}</span>
                </div>
                <span style="font-size:1.4rem;font-weight:700;">{total:,}</span>
            </div>
            <div style="color:#666;font-size:0.85rem;margin-top:4px;">
                <b>Ne yapar:</b> {mod['desc']}<br>
                <b>Nasil calisir:</b> {mod['what']}<br>
                <b>Durum:</b> {detail}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Dependency diagram
    st.markdown("---")
    st.markdown("### \U0001f517 Modul Bagimliliklari")
    st.code("""
    Module 1 (Sirket)  ──>  PermaLink'ler hazir
         │
         v
    Module 2 (Finansal) ──>  Her sirketin HTML sayfasindan bilanco cekilir  [CALISIYOR]
         │
    Module 3 (Bildirim) ──>  KAP JSON API'dan bildirim listesi cekilir     [RATE-LIMIT]
         │                      │
         v                      v
    Module 4 (Kurumsal)   Module 7 (Ortaklik)    [MODUL 3'E BAGIMLI]
    Module 5 (Geri Alim)                           [MODUL 3'E BAGIMLI]
    Module 6 (IPO)                                  [MODUL 3'E BAGIMLI]
    """, language="text")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: SIRKETLER
# ══════════════════════════════════════════════════════════════════════════════
def page_companies():
    st.markdown("# \U0001f3e2 Sirketler")
    c1, c2 = st.columns([3, 1])
    with c1: search = st.text_input("Ara (ticker)", key="cs")
    with c2: sort_by = st.selectbox("Sirala", ["ticker", "mkk_id"])
    q = s.query(Company)
    if search: q = q.filter(Company.ticker.ilike(f"%{search}%"))
    companies = q.order_by(getattr(Company, sort_by)).all()
    st.info(f"{len(companies)} sirket | PermaLink: {cnt(s.query(Company).filter(Company.mkk_id.isnot(None)))} tane")
    if companies:
        df = pd.DataFrame([{"Ticker": c.ticker, "MKK ID": c.mkk_id} for c in companies])
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    # Detay gosterimi
    st.markdown("---")
    detail_ticker = st.selectbox("Sirket detay goster", [""] + [c.ticker for c in companies[:100]], key="comp_detail")
    if detail_ticker:
        dc = s.query(Company).filter(Company.ticker == detail_ticker).first()
        if dc:
            st.subheader(f"{dc.ticker} (MKK: {dc.mkk_id})")
            fins = s.query(Financial).filter(Financial.company_id == dc.id).order_by(Financial.year.desc(), Financial.period.desc()).all()
            if fins:
                st.subheader(f"Mali Veriler ({len(fins)} donem)")
                fdf = pd.DataFrame([{"Donem": f"{f.year}/{f.period:02d}", "Hasilat": tc(f.revenue),
                                    "Net Kar": tc(f.net_profit), "Brut Marj": pct(f.gross_margin),
                                    "ROE": pct(f.roe)} for f in fins])
                st.dataframe(fdf, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: MALI TABLOLAR
# ══════════════════════════════════════════════════════════════════════════════
def page_financials():
    st.markdown("# \U0001f4c8 Mali Tablolar")
    companies = s.query(Company).filter(Company.financials.any()).order_by(Company.ticker).all()
    if not companies: st.warning("Henuz finansal veri yok."); return
    comp_map = {c.ticker: c for c in companies}
    ticker = st.selectbox("Sirket", list(comp_map.keys()))
    company = comp_map[ticker]
    fins = s.query(Financial).filter(Financial.company_id == company.id).order_by(Financial.year.desc(), Financial.period.desc()).all()
    if not fins: return
    latest = fins[0]
    st.subheader(f"{ticker} — {latest.year}/{latest.period:02d}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Hasilat", tc(latest.revenue) + " TL")
    c2.metric("EBITDA", tc(latest.ebitda) + " TL")
    c3.metric("Net Kar", tc(latest.net_profit) + " TL")
    c4.metric("ROE", pct(latest.roe))
    c5.metric("Cari Oran", f"{sf(latest.current_ratio):.2f}" if sf(latest.current_ratio) else "N/A")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Brut Marj", pct(latest.gross_margin))
    c2.metric("FAVOK Marj", pct(latest.ebitda_margin))
    c3.metric("Net Marj", pct(latest.net_margin))
    c4.metric("ROA", pct(latest.roa))
    st.markdown("---")
    fdf = pd.DataFrame([{"Donem": f"{f.year}/{f.period:02d}", "Hasilat": sf(f.revenue), "Net Kar": sf(f.net_profit),
                         "Brut Marj": (sf(f.gross_margin) or 0)*100, "Net Marj": (sf(f.net_margin) or 0)*100} for f in reversed(fins)])
    col1, col2 = st.columns(2)
    with col1:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=fdf["Donem"], y=fdf["Hasilat"], name="Hasilat", marker_color="#667eea"), secondary_y=False)
        fig.add_trace(go.Scatter(x=fdf["Donem"], y=fdf["Net Kar"], name="Net Kar", line=dict(color="#ff4757", width=2)), secondary_y=True)
        fig.update_layout(height=300, margin=dict(t=30)); st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = go.Figure()
        for n, c in [("Brut Marj", "#2ed573"), ("Net Marj", "#ff4757")]:
            fig.add_trace(go.Scatter(x=fdf["Donem"], y=fdf[n], name=n, line=dict(color=c, width=2)))
        fig.update_layout(height=300, margin=dict(t=30), yaxis_title="%"); st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: ZAMANLAMA
# ══════════════════════════════════════════════════════════════════════════════
def page_schedule():
    st.markdown("# \u23f0 Zamanlama & Siradaki Calismalar")
    next_runs = get_next_runs()
    now = datetime.now()

    rows = []
    for nr in next_runs:
        sched = next(s_ for s_ in SCHEDULE if s_["id"] == nr["id"])
        last_run = s.query(PipelineRun).filter(PipelineRun.module_name == sched["id"]).order_by(PipelineRun.started_at.desc()).first()
        last_status = last_run.status if last_run else None
        last_time = last_run.started_at.strftime("%d.%m %H:%M") if last_run and last_run.started_at else "-"

        if nr["next_dt"]:
            delta = nr["next_dt"] - now
            h, m = int(delta.total_seconds() // 3600), int((delta.total_seconds() % 3600) // 60)
            next_str = f"{nr['next_run']} ({h}sa {m}dk sonra)"
        else:
            next_str = nr["next_run"]

        icon = "\u2705" if last_status == "SUCCESS" else "\u274c" if last_status == "FAILED" else "\u25cb"
        rows.append({
            "Modul": sched["name"],
            "Siklik": sched["frequency"],
            "Zaman": sched["time"],
            "Son Calisma": last_time,
            "Durum": icon,
            "Siradaki": next_str,
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### \U0001f4bb Komutlar")
    st.code("""
python scheduler.py              # Her seyi cek, sonra zamanlayici baslat
python scheduler.py --list       # Zamanlamalari goster
python scheduler.py --now        # Hemen her seyi cek
python scheduler.py --live-only  # Sadece canli akis (5 dk)
    """, language="bash")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: API REFERANS
# ══════════════════════════════════════════════════════════════════════════════
def page_api():
    st.markdown("# \U0001f310 API Referans")
    cols = st.columns(3)
    for i, (name, desc, url) in enumerate([
        ("Swagger Docs", "Interaktif API test", "http://localhost:8000/docs"),
        ("ReDoc", "Renkli dokumantasyon", "http://localhost:8000/redoc"),
        ("API Status", "Sistem durumu JSON", "http://localhost:8000/api/status"),
    ]):
        with cols[i]:
            st.markdown(f"""<a href="{url}" target="_blank" style="text-decoration:none;">
                <div class="svc-card" style="text-align:center;"><h3>{name}</h3><div class="url">{url}</div></div></a>""", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### \U0001f4cb Endpoint'ler")
    ep_df = pd.DataFrame([
        {"Method": "GET", "Endpoint": "/api/status", "Aciklama": "Sistem durumu"},
        {"Method": "GET", "Endpoint": "/api/companies?search=THY", "Aciklama": "Sirket ara"},
        {"Method": "GET", "Endpoint": "/api/financials/{ticker}", "Aciklama": "Mali tablolar"},
        {"Method": "GET", "Endpoint": "/api/financials/latest/{ticker}", "Aciklama": "Son donem"},
        {"Method": "GET", "Endpoint": "/api/financials/compare?tickers=THYAO,ASELS", "Aciklama": "Karsilastir"},
        {"Method": "GET", "Endpoint": "/api/disclosures?days=30", "Aciklama": "Bildirimler"},
        {"Method": "GET", "Endpoint": "/api/corporate-actions", "Aciklama": "Kurumsal islemler"},
        {"Method": "GET", "Endpoint": "/api/shareholders/{ticker}", "Aciklama": "Ortaklik"},
        {"Method": "GET", "Endpoint": "/api/dashboard/summary", "Aciklama": "Dashboard ozeti"},
    ])
    st.dataframe(ep_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7: DIGGER
# ══════════════════════════════════════════════════════════════════════════════
def page_others():
    st.markdown("# \U0001f3af Diger Veriler")
    tab1, tab2, tab3, tab4 = st.tabs(["Kurumsal", "Geri Alim", "IPO", "Ortaklik"])
    def gt(cid):
        c = s.query(Company).filter(Company.id == cid).first()
        return c.ticker if c else str(cid)
    with tab1:
        acts = s.query(CorporateAction).limit(30).all()
        if acts:
            st.dataframe(pd.DataFrame([{"Sirket": gt(a.company_id), "Tip": a.action_type,
                                       "Verim": pct(a.yield_percent)} for a in acts]), use_container_width=True, hide_index=True)
        else: st.info("Veri yok. Module 4 icin once Module 3 calismali.")
    with tab2:
        bbs = s.query(ShareBuyback).limit(30).all()
        if bbs:
            st.dataframe(pd.DataFrame([{"Sirket": gt(b.company_id), "Butce": tc(b.total_budget_tl)} for b in bbs]), use_container_width=True, hide_index=True)
        else: st.info("Veri yok. Module 5 icin once Module 3 calismali.")
    with tab3:
        st.info("Veri yok. Module 6 icin once Module 3 calismali.")
    with tab4:
        st.info("Veri yok. Module 7 icin PermaLink'ler hazir ama veri cekilemiyor.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["Canli Akis", "Modul Durumlari", "Sirketler", "Mali Tablolar", "Zamanlama", "API Referans"])

with tabs[0]: page_live_stream()
with tabs[1]: page_module_status()
with tabs[2]: page_companies()
with tabs[3]: page_financials()
with tabs[4]: page_schedule()
with tabs[5]: page_api()
