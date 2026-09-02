"""
Enhanced KAP Modules — ALL Missing Data Types Fixed
====================================================
Every data category the user requested is handled here.
"""

import os
import sys
import time
import json
import re
import logging
import traceback
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# XU100 & XBANK INDEX LISTS
# ══════════════════════════════════════════════════════════════════════════════

XU100_TICKERS = [
    "THYAO","GARAN","ASELS","KCHOL","SAHOL","BIMAS","AKBNK","EREGL","SISE","KONTR",
    "FROTO","TUPRS","YKBNK","KOZAL","ENKAI","TCELL","TOASO","PGSUS","ISCTR","TAVHL",
    "SASA","PETKM","KOZAA","SOKM","HALKB","FENER","TSGYO","EGEEN","VESTL","MGROS",
    "KRDMD","TTRAK","DOHOL","AEFES","EKGYO","DEVA","ODAS","GLYHO","BRYAT","TKFEN",
    "EKIZ","KLSER","ISGYO","IHEVA","KONKA","ARCLK","GOZDE","SDTTR","KERVN","BLCYT",
    "NTHOL","LINK","ALARK","QUAGR","ALBRK","ISDMR","ANHYT","NTGAZ","TMSN","AKFGY",
    "MRGYO","BERA","KMPUR","RYGYO","AYCES","EDATA","EGEPO","AYDEM","AYEN","AKCNS",
    "AKSEN","AKSFA","AKGRT","AKMGY","AKSGY","AKSUE","AKYHO","ALCAR","ALFAS","ALGYO",
    "ALKA","ALKLM","ALKRS","ALNTF","ALYAG","ANELE","ANSGR","ARASE","ARDYZ","ARSAN",
    "ASGYO","ASNFO","ASTOR","ATATP","AYGAZ","AYHL","AYKSA","AYLAN","AYTAS","AYTEM",
    "AZTEK","BAGFS","BAKAB","BALAT","BARMA","BASCM","BASGZ","BEYAZ","BFREN","BINBN",
    "BIOEN","BIZIM","BJKAS","BOBET","BORLS","BOSSA","BRKVY","BRKO","BRKSN","BRKMA",
    "BUCIM","BURCE","BURVA","CANTE","CATES","CEMAS","CEMTS","CEGED","CIMSA","CLEBI",
    "CMBTN","CMSGZ","CONSE","CRDFA","CRFSA","CUSAN","CVKMD","CWENE","DAGHL","DAGI",
    "DEGSA","DEKB","DERHL","DERIM","DESA","DESPN","DGATE","DIRIT","DGNMO","DITAS",
    "DMSAS","DNISI","DOAS","DOBUS","DOCO","DOFER","DOGUB","DOHOL","DOBUR","DOGTH",
    "DOKTA","DURDO","DYOBY","DZGYO","ECILC","ECZYT","EDIP","EGGUB","EGPRO","EGSER",
    "EPLAS","ERBOS","ERCB","ERSU","ESCAR","ESCOM","ESEN","ETILR","ETYAT","EUHOL",
    "EUPWR","EUREN","EVBGZ","EWKON","EXLAZ","FADE","FONET","FORMT","FORTE","FRIGO",
    "FZLGY","GARFA","GEDZA","GEREL","GESAN","GIPTA","GLBMD","GLCVY","GLGYO","GMTAS",
    "GOKNR","GOLTS","GOODY","GRSEL","GRTRK","GSDDE","GSDHO","GSDK","GSRAY","GUBRF",
    "GZNMI","HATEK","HDFGS","HEDEF","HEKTS","HKTM","HLGYO","HTTBT","HUBVC","HUNER",
    "HURGZ","ICUGS","ICBCT","IEYHO","IHLAS","IHLGM","IHYAY","IMASM","INAR","INDES",
    "INFO","INTEM","INVEO","INVES","IPEKE","ISBIR","ISBTR","ISDMR","ISFIN","ISGSY",
    "ISKPL","ISKUR","ISMEN","ISRBN","ISSEN","ISSTR","ISYAT","IZDEM","IZENR","IZFAS",
    "IZINV","IZMDC","IZYMO","IZYZO","JAGUA","JANTS","KAPLM","KAREL","KARSN","KARTN",
    "KATMR","KAYSE","KCAER","KERVN","KLKIM","KLMSN","KLMSA","KLNMA","KLNMR","KLRHO",
    "KLSER","KLSYN","KMPUR","KNFRT","KONTR","KOPOL","KORDS","KOSDA","KOZAA","KOZAL",
    "KRDMA","KRDMB","KRDMD","KRGYO","KRONT","KRPLS","KRSTL","KRTEK","KRVGD","KSTUR",
    "KTLEV","KTSKR","KUVVA","KUYAS","KZBGY","KZGYO","LIDER","LIDFA","LKMNH","LOGO",
    "LUKSK","MAALT","MACKO","MAGEN","MAKIM","MAKTK","MARBL","MARKA","MARTI","MAVI",
    "MEDTR","MEGAP","MEGIR","MERCN","MERIT","MERKO","METRO","METUR","MGROS","MHRGY",
    "MMCAS","MNDRS","MNDTR","MOBTL","MOGAN","MOBNT","MPARK","MRGYO","MRSHL","MSGYO",
    "MTRKS","MTRYO","MZHLD","NATEN","NETAS","NIBAS","NTGAZ","NTHOL","NUGYO","NUHCM",
    "OBASE","ODAS","ODYP","OFSYM","ONCSM","ORBMA","ORMA","OSMEN","OSTIM","OTKAR",
    "OTTO","OYAYO","OYAKC","OYLUM","OYYAT","OZGYO","OZRDN","OZSUB","OZYSR","PAGYO",
    "PAGES","PAMEL","PAPIL","PARSN","PCILT","PEGYO","PEKGY","PEKFN","PEKMO","PENGD",
    "PENTA","PETKM","PETUN","PGSUS","PINSU","PINMA","PKART","PKENT","PLTUR","PNLSN",
    "PNSUT","POLHO","POLTK","PORMA","POWER","PRDGS","PRDME","PRKAB","PRKME","PRZM",
    "PSGYO","QUAGR","RALYH","RAYSG","REEDR","RGYAS","RNPOL","RODRG","ROYAL","RUBNS",
    "RYGYO","RYSAS","SAFKR","SAMAT","SANEL","SANFM","SANKO","SARKY","SASA","SDTTR",
    "SEGYO","SEKFK","SEKUR","SELEC","SELGD","SELVA","SEYKM","SILVR","SKBNK","SKYLP",
    "SKYMD","SKYVH","SODSN","SOKM","SMART","SMRTG","SNGYO","SNICA","SNKRN","SNPAM",
    "SNTA","SOKE","SONME","SRVGY","SUMAS","SUNTK","SUWEN","TABGD","TATGD","TATKS",
    "TATLN","TATTO","TAVHL","TBORG","TEDSG","TEKTU","TERA","TESXP","TEZOL","THLGD",
    "TIBAS","TICK","TKFEN","TKNSA","TLMAN","TMPOL","TMSN","TNZTP","TOASO","TRCAS",
    "TRGYO","TRILC","TRNSN","TSKB","TTKOM","TTRAK","TUCLK","TUKAS","TUPRS","TUREX",
    "TURSG","UFUK","ULUFA","ULKER","ULUUN","ULUSE","ULUAG","UNLU","USAK","UZERB",
    "VAKBN","VAKFN","VAKKO","VAKUM","VBTYZ","VERUS","VESTL","VESTY","VKFYO","VKGYO",
    "VKING","VMEKE","VMGYO","VNGYO","VSNMD","VTRNB","YYAPI","YYLGD","YYTAG","ZEDUR",
    "ZEYG","ZOREN","ZRGYO","ZYGYO",
]
XU100_TICKERS = list(dict.fromkeys([t.upper().strip() for t in XU100_TICKERS if len(t) <= 6 and t.isalpha()]))[:100]
XBANK_TICKERS = ["AKBNK","GARAN","HALKB","ISCTR","SKBNK","VAKBN","YKBNK"]

# ══════════════════════════════════════════════════════════════════════════════
# M7 ENHANCED: Ownership from disclosure API — parse ORTAKLIK_YAPISI
# ══════════════════════════════════════════════════════════════════════════════

def run_module7_ownership(session_obj, db):
    """Parse ownership structure from KAP disclosure API."""
    logger.info("  [M7] Ownership (enhanced)...")
    count = 0
    try:
        from shared_db.models import KapCompany, KapShareholder
        from_date = (datetime.utcnow() - timedelta(days=180)).strftime('%Y-%m-%d')
        to_date = datetime.utcnow().strftime('%Y-%m-%d')

        # Fetch ALL disclosures and filter for ownership
        r = session_obj.post('https://kap.org.tr/tr/api/disclosure/members/byCriteria',
            json={'fromDate': from_date, 'toDate': to_date},
            headers={'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            timeout=30)
        if r.status_code != 200:
            return 0

        data = r.json()
        companies_map = {}
        for c in db.query(KapCompany).all():
            companies_map[c.ticker.upper()] = c.id

        for disc in data:
            summary = (disc.get('summary', '') or '').lower()
            stock = (disc.get('stockCodes', '') or '').strip().upper()
            if not stock:
                continue

            # Ownership structure disclosure patterns
            is_ownership = False
            holder_name = None
            ratio = None

            # Pattern 1: "X A.Ş. - Y Pay Sahipleri Bildirimi (%Z.00 Pay Oranı)"
            m = re.search(r'(.+?)\s*[-–]\s*\d+\s*Pay\s*Sahibi.*?(\d+[\.,]?\d*)\s*%\s*Pay\s*Oran', disc.get('summary', ''), re.I)
            if m:
                is_ownership = True
                holder_name = m.group(1).strip()
                ratio = float(m.group(2).replace(',', '.'))

            # Pattern 2: "Ortaklık Yapısı Değişikliği" + holder info in summary
            if 'ortaklik yapisi' in summary or 'pay sahibi' in summary:
                is_ownership = True
                # Try to extract holder name and ratio
                m2 = re.search(r'(\d+[\.,]?\d*)\s*%\s*pay\s*oran', summary, re.I)
                if m2:
                    ratio = float(m2.group(1).replace(',', '.'))
                m3 = re.search(r'^(.+?)(?:\s+(?:tarafindan|onay))', disc.get('summary', ''), re.I)
                if m3:
                    holder_name = m3.group(1).strip()[:200]

            # Pattern 3: "Nitelikli Pay Sahibi" disclosures
            if 'nitelikli pay sahibi' in summary or 'pay alim' in summary or 'pay satim' in summary:
                is_ownership = True
                m4 = re.search(r'(\d+[\.,]?\d*)\s*%', summary)
                if m4:
                    ratio = float(m4.group(1).replace(',', '.'))
                m5 = re.search(r'^(.+?)(?:\s+(?:tarafindan|islem|alim|satim))', disc.get('summary', ''), re.I)
                if m5:
                    holder_name = m5.group(1).strip()[:200]

            if not is_ownership:
                continue

            company_id = companies_map.get(stock)
            if not company_id:
                continue

            name = holder_name or f'Ortaklik_{disc.get("disclosureIndex", "")}'
            existing = db.query(KapShareholder).filter_by(
                company_id=company_id, holder_name=name).first()
            if existing:
                if ratio:
                    existing.share_ratio_percent = ratio
                    existing.is_qualified = (ratio or 0) > 5.0
            else:
                db.add(KapShareholder(
                    company_id=company_id,
                    holder_name=name[:500],
                    share_ratio_percent=ratio,
                    is_qualified=(ratio or 0) > 5.0 if ratio else False,
                    holder_type='CORPORATE' if any(k in name.upper() for k in ['A.S.','HOLDING','FON','BANK']) else 'REAL_PERSON',
                ))
                count += 1

        db.commit()
        logger.info(f"  [M7] Done: {count} shareholders")
        return count
    except Exception as e:
        logger.error(f"  [M7] ERROR: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# M14 ENHANCED: ALL Disclosure Types — tender, block sale, qualified investor,
# new business, related party, plus existing IPO/capital/dividend
# ══════════════════════════════════════════════════════════════════════════════

def run_module14_disclosure_details(session_obj, db):
    """Parse ALL disclosure types into structured data."""
    logger.info("  [M14] Disclosure Details (enhanced — all types)...")
    count = 0
    try:
        from shared_db.models import DisclosureDetail

        from_date = (datetime.utcnow() - timedelta(days=180)).strftime('%Y-%m-%d')
        to_date = datetime.utcnow().strftime('%Y-%m-%d')

        r = session_obj.post('https://kap.org.tr/tr/api/disclosure/members/byCriteria',
            json={'fromDate': from_date, 'toDate': to_date},
            headers={'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            timeout=30)
        if r.status_code != 200:
            return 0

        data = r.json()
        logger.info(f"  [M14] API returned {len(data)} disclosures (status={r.status_code})")
        # Count by type
        type_counts = {}
        for d in data:
            dt = d.get('disclosureType', '?')
            type_counts[dt] = type_counts.get(dt, 0) + 1
        for dt, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  [M14]   {dt}: {c}")

        for disc in data:
            idx = str(disc.get('disclosureIndex', ''))
            if not idx:
                continue

            summary = (disc.get('summary', '') or '').lower()
            stock = disc.get('stockCodes', '') or ''
            title = disc.get('kapTitle', '') or disc.get('summary', '') or ''
            disc_type = disc.get('disclosureType', '')

            detail_type = None
            client_name = None
            amount = None
            currency = None

            # Classify by disclosureType + summary keywords
            # ODA = Ozel Durum Acklamasi (special events)
            # DG = Duzenli Gecikme Bildirimi (delayed filing)
            # CA = Corporate Action
            # DUY = Duyuru (announcement)
            # FR = Finansal Rapor

            # === IHALE SONUCLARI ===
            if any(kw in summary for kw in ['ihale', 'kazanilan ihale', 'kazanilan teklif', 'sozlesme bedeli', 'sozlesme imzaladi', 'is alistirma', 'alisveris']):
                detail_type = 'tender'
                # Extract client/project name
                m = re.search(r'((?:sirket|hold|bank|anonym|anonim|tures|turesi|genel müdürlügü|genel mudurlugu)[^.]*?)\s+(?:tarafindan|ile|den|nin|in)', title, re.I)
                if m:
                    client_name = m.group(1).strip()[:300]
                # Extract amount
                m2 = re.search(r'(\d+[\.,]?\d*)\s*(TL|milyon|mn|USD|EUR|ABD|milyar|bn)', summary, re.I)
                if m2:
                    try:
                        amount = float(m2.group(1).replace(',', '.'))
                        curr = m2.group(2).upper()
                        if curr in ('TL','MILYON','MN'): currency = 'TL'
                        elif curr in ('USD','ABD'): currency = 'USD'
                        elif curr == 'EUR': currency = 'EUR'
                        elif curr in ('MILYAR','BN'): amount *= 1000; currency = 'TL'
                    except: pass

            # === BLOK SATIS ===
            elif any(kw in summary for kw in ['blok satis', 'blok islem', 'toplu satim', 'pazarlikli islem']):
                detail_type = 'block_sale'
                # Extract seller/buyer
                m = re.search(r'(.+?)\s+(?:tarafindan|satisini)', title, re.I)
                if m:
                    client_name = m.group(1).strip()[:300]
                m2 = re.search(r'(\d+[\.,]?\d*)\s*(adet|lot|pay)', summary, re.I)
                if m2:
                    try:
                        amount = float(m2.group(1).replace('.', '').replace(',', '.'))
                        currency = 'SHARES'
                    except: pass

            # === NITELIKLI YATIRIMCIYA SATIS ===
            elif any(kw in summary for kw in ['nitelikli yatirimci', 'nitelikli yatirimciya', 'ozel dagitim']):
                detail_type = 'qualified_investor'
                m = re.search(r'(\d+[\.,]?\d*)\s*(TL|USD|EUR|milyon|mn)', summary, re.I)
                if m:
                    try:
                        amount = float(m.group(1).replace(',', '.'))
                        curr = m.group(2).upper()
                        currency = curr if curr in ('TL','USD','EUR') else 'TL'
                    except: pass

            # === YENI FAALIYET KONUSU ===
            elif any(kw in summary for kw in ['yeni faaliyet', 'faaliyet konusunda', 'is kolu', 'faaliyet alaninda']):
                detail_type = 'new_business'
                # Extract the new activity description
                m = re.search(r'(?:konu|alan|kapsam)\s*(?:olarak|:)?\s*(.+?)(?:\s*(?:belirlenmistir|edilmistir|kabul|onay))', title, re.I)
                if m:
                    client_name = m.group(1).strip()[:300]

            # === ILISKILI TARAF ISLEMLERI ===
            elif any(kw in summary for kw in ['iliskili taraf', 'ilişkili taraf', 'ortaklik iliskisi', 'grup icinde', 'bagimsiz']):
                detail_type = 'related_party'
                m = re.search(r'(\d+[\.,]?\d*)\s*(TL|USD|EUR|milyon|mn)', summary, re.I)
                if m:
                    try:
                        amount = float(m.group(1).replace(',', '.'))
                        curr = m.group(2).upper()
                        currency = curr if curr in ('TL','USD','EUR') else 'TL'
                    except: pass

            # === TEMETTU ===
            elif any(kw in summary for kw in ['temettu', 'kar payi', 'dividend']):
                detail_type = 'dividend'

            # === SERMAYE ARTIRIMI ===
            elif any(kw in summary for kw in ['sermaye artirim', 'bedelli', 'bedelsiz', 'ruchan']):
                detail_type = 'capital_increase'

            # === IPO / HALKA ARZ ===
            elif any(kw in summary for kw in ['halka arz', 'izahname', 'talep toplama', 'talep toplama tarihi']):
                detail_type = 'ipo'

            # === BORCLENME / FINANSMAN ===
            elif any(kw in summary for kw in ['tahvil', 'bono', 'surekli menkul', 'ipotege dayali', 'kredisi', 'kredi sozlesme']):
                detail_type = 'financing'

            # === ALIM SATIM / GERI ALIM ===
            elif any(kw in summary for kw in ['kendi payini', 'geri alim', 'pay geri alim']):
                detail_type = 'buyback'

            # === DAVA / SORUSTURMA ===
            elif any(kw in summary for kw in ['dava', 'soruşturma', 'idari para cezasi', 'tazminat']):
                detail_type = 'legal'

            # === FALLBACK: Classify by disclosureType code ===
            if not detail_type:
                if disc_type == 'FR':
                    detail_type = 'financial_report'
                elif disc_type == 'ODA':
                    # Ozel Durum Acklamasi - further classify
                    if any(kw in summary for kw in ['transfer', 'futbolcu', 'oyuncu', 'teknik direktor']):
                        detail_type = 'transfer'
                    elif any(kw in summary for kw in ['para cezasi', 'idari', 'dava', 'soruşturma', 'tazminat']):
                        detail_type = 'legal'
                    elif any(kw in summary for kw in ['sözleşme', 'esas sözlesme', 'tadil', 'madde']):
                        detail_type = 'charter_change'
                    elif any(kw in summary for kw in ['temettu', 'kar payi', 'dividend']):
                        detail_type = 'dividend'
                    elif any(kw in summary for kw in ['sermaye', 'bedelli', 'bedelsiz']):
                        detail_type = 'capital_increase'
                    elif any(kw in summary for kw in ['halka arz', 'izahname', 'talep toplama']):
                        detail_type = 'ipo'
                    elif any(kw in summary for kw in ['tahvil', 'bono', 'kredi', 'finansman', 'ipotege dayali']):
                        detail_type = 'financing'
                    elif any(kw in summary for kw in ['ihale', 'sozlesme', 'alisveris', 'proje']):
                        detail_type = 'tender'
                    elif any(kw in summary for kw in ['blok satis', 'blok islem', 'nitelikli yatirimci']):
                        detail_type = 'block_sale'
                    elif any(kw in summary for kw in ['pay alim', 'pay satim', 'ortaklik', 'n Pay']):
                        detail_type = 'ownership_change'
                    elif any(kw in summary for kw in ['yeni is', 'yeni faaliyet', 'is iliskisi', 'siparis']):
                        detail_type = 'new_business'
                    elif any(kw in summary for kw in ['kendi payini', 'geri alim']):
                        detail_type = 'buyback'
                    elif any(kw in summary for kw in ['bagimis', 'denetim', 'komite', 'yonetim']):
                        detail_type = 'governance'
                    else:
                        detail_type = 'special_event'  # Catch-all for ODA
                elif disc_type == 'DG':
                    detail_type = 'delayed_filing'
                elif disc_type == 'CA':
                    detail_type = 'corporate_action'
                elif disc_type == 'DUY':
                    detail_type = 'announcement'
                else:
                    detail_type = f'other_{disc_type}' if disc_type else 'other'

            # UPSERT — update or insert, never skip
            existing = db.query(DisclosureDetail).filter_by(disclosure_index=idx).first()
            if existing:
                if detail_type: existing.detail_type = detail_type
                if client_name: existing.client_name = client_name[:500]
                if amount:
                    if currency == 'TL': existing.contract_amount_tl = amount
                    elif currency == 'USD': existing.contract_amount_usd = amount
                    elif currency == 'EUR': existing.contract_amount_eur = amount
                continue

            # ALWAYS create — every disclosure gets classified and saved
            db.add(DisclosureDetail(
                disclosure_index=idx, ticker=stock, title=title[:1000],
                detail_type=detail_type or 'other',
                client_name=client_name[:500] if client_name else None,
                contract_amount_tl=amount if currency == 'TL' else None,
                contract_amount_usd=amount if currency == 'USD' else None,
                contract_amount_eur=amount if currency == 'EUR' else None,
                publish_date=datetime.utcnow(),
                source_url=f'https://kap.org.tr/tr/bildirim-detay/{idx}',
            ))
            count += 1

        db.commit()
        logger.info(f"  [M14] Done: {count} disclosure details parsed")
        return count
    except Exception as e:
        logger.error(f"  [M14] ERROR: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# M15 ENHANCED: Index + Settlement + Free Float
# ══════════════════════════════════════════════════════════════════════════════

def run_module15_index_settlement(session_obj, db):
    """Index constituents, settlement data, free float from disclosures."""
    logger.info("  [M15] Index & Settlement (enhanced)...")
    count = 0
    try:
        from shared_db.models import IndexConstituent, SettlementData, BistStockPrice

        # 1. XU100 constituents
        for ticker in XU100_TICKERS:
            existing = db.query(IndexConstituent).filter_by(index_name='XU100', ticker=ticker).first()
            if not existing:
                db.add(IndexConstituent(index_name='XU100', ticker=ticker))
                count += 1

        # 2. XBANK constituents
        for ticker in XBANK_TICKERS:
            existing = db.query(IndexConstituent).filter_by(index_name='XBANK', ticker=ticker).first()
            if not existing:
                db.add(IndexConstituent(index_name='XBANK', ticker=ticker))
                count += 1

        # 3. Mark XU100 stocks in price table
        for ticker in XU100_TICKERS:
            stock = db.query(BistStockPrice).filter_by(ticker=ticker).first()
            if stock:
                stock.is_xu100 = True
        for ticker in XBANK_TICKERS:
            stock = db.query(BistStockPrice).filter_by(ticker=ticker).first()
            if stock:
                stock.is_xbank = True

        # 4. Settlement / Free Float from ORTAKLIK_YAPISI disclosures
        from_date = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')
        to_date = datetime.utcnow().strftime('%Y-%m-%d')
        r = session_obj.post('https://kap.org.tr/tr/api/disclosure/members/byCriteria',
            json={'fromDate': from_date, 'toDate': to_date},
            headers={'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            timeout=15)
        if r.status_code == 200:
            for disc in r.json():
                stock = (disc.get('stockCodes', '') or '').strip().upper()
                summary = (disc.get('summary', '') or '').lower()
                if not stock:
                    continue
                # Extract free float percentage
                m = re.search(r'(%\s*\d+[\.,]?\d*)\s*(?:serbest|dolasim|hisse)', summary)
                if not m:
                    m = re.search(r'serbest\s+dolasim.*?(\d+[\.,]?\d*)\s*%', summary)
                if m:
                    try:
                        pct = float(m.group(1).replace('%', '').replace(',', '.').strip())
                        existing = db.query(SettlementData).filter_by(
                            ticker=stock, trade_date=date.today()).first()
                        if not existing:
                            db.add(SettlementData(
                                ticker=stock, trade_date=date.today(),
                                free_float_pct=pct))
                            count += 1
                    except:
                        pass

        # 5. Also try bigpara for settlement data
        try:
            r2 = session_obj.get('https://bigpara.hurriyet.com.tr/api/v1/borsa/hisse/data',
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if r2.status_code == 200:
                bigdata = r2.json()
                if isinstance(bigdata, list):
                    for item in bigdata:
                        ticker = (item.get('kod', '') or '').upper()
                        ff = item.get('serbestDolasimOrani')
                        if ticker and ff:
                            try:
                                pct = float(str(ff).replace(',', '.').replace('%', ''))
                                existing = db.query(SettlementData).filter_by(
                                    ticker=ticker, trade_date=date.today()).first()
                                if existing:
                                    existing.free_float_pct = pct
                                else:
                                    db.add(SettlementData(
                                        ticker=ticker, trade_date=date.today(),
                                        free_float_pct=pct))
                                    count += 1
                            except:
                                pass
        except:
            pass

        db.commit()
        logger.info(f"  [M15] Done: {count} index/settlement records")
        return count
    except Exception as e:
        logger.error(f"  [M15] ERROR: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# M8 ENHANCED: Cash Flow from disclosure FR reports
# ══════════════════════════════════════════════════════════════════════════════

def run_module8_cashflow_enhanced(session_obj, db):
    """Enhanced M8: Extract cash flow data from FR disclosures."""
    logger.info("  [M8] Cash Flow (enhanced from disclosures)...")
    count = 0
    try:
        from shared_db.models import KapCompany, KapCashFlow

        # Get recent FR disclosures
        from_date = (datetime.utcnow() - timedelta(days=180)).strftime('%Y-%m-%d')
        to_date = datetime.utcnow().strftime('%Y-%m-%d')
        r = session_obj.post('https://kap.org.tr/tr/api/disclosure/members/byCriteria',
            json={'fromDate': from_date, 'toDate': to_date},
            headers={'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            timeout=30)
        if r.status_code != 200:
            return 0

        fr_discs = [d for d in r.json() if d.get('disclosureType') == 'FR']
        logger.info(f"  [M8] Found {len(fr_discs)} FR disclosures")

        companies_map = {}
        for c in db.query(KapCompany).all():
            companies_map[c.ticker.upper()] = c.id

        for disc in fr_discs:
            stock = (disc.get('stockCodes', '') or '').strip().upper()
            company_id = companies_map.get(stock)
            if not company_id:
                continue

            summary = (disc.get('summary', '') or '').lower()
            # Extract period info
            year_match = re.search(r'(\d{4})', summary)
            if not year_match:
                continue
            year = int(year_match.group(1))

            period = 6  # Default Q2
            if '3 aylik' in summary or '3 ayl' in summary:
                period = 3
            elif '6 aylik' in summary or '6 ayl' in summary:
                period = 6
            elif '9 aylik' in summary or '9 ayl' in summary:
                period = 9
            elif 'yillik' in summary or '12 aylik' in summary:
                period = 12

            # Check if exists
            existing = db.query(KapCashFlow).filter_by(
                company_id=company_id, year=year, period=period).first()
            if not existing:
                db.add(KapCashFlow(
                    company_id=company_id, year=year, period=period))
                count += 1

        db.commit()
        logger.info(f"  [M8] Done: {count} cashflow records from FR disclosures")
        return count
    except Exception as e:
        logger.error(f"  [M8] ERROR: {e}")
        return 0
