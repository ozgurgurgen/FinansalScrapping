"""
KAP Subsidiaries share_percent scraper — Playwright-based
=========================================================
Replaces old subsidiary records with fresh data from KAP /genel/ pages.
"""
import sqlite3, sys, io, os, time, random, json, asyncio, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DB_PATH = str(Path(__file__).parent / 'finance.db')
PROGRESS_FILE = str(Path(__file__).parent / 'subs_share_progress.json')
KAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kap-pipeline')
PERMA_FILE = os.path.join(KAP_DIR, 'kap_permaplinks.json')


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        return json.loads(open(PROGRESS_FILE, encoding='utf-8').read())
    return {"done": [], "updated": 0, "replaced": 0, "errors": 0}


def save_progress(state):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)


def parse_turkish_number(text):
    if not text:
        return None
    text = text.strip().replace(' ', '').replace('%', '')
    if '.' in text and ',' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


async def scrape_company_subs(page, permalink):
    """Scrape subsidiary data from KAP GENERAL info page."""
    url = f"https://www.kap.org.tr/tr/sirket-bilgileri/genel/{permalink}"
    try:
        resp = await page.goto(url, timeout=25000, wait_until='domcontentloaded')
        if resp and resp.status != 200:
            return []
        await page.wait_for_timeout(random.randint(3000, 5000))

        html = await page.content()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        results = []
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            header_cells = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
            header_text = ' '.join(header_cells)

            if 'ticaret' in header_text and ('payı' in header_text or 'pay' in header_text):
                pct_col = None
                for idx, h in enumerate(header_cells):
                    if ('payı' in h or 'pay' in h) and '%' in h:
                        pct_col = idx
                        break
                if pct_col is None:
                    continue

                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) <= pct_col:
                        continue
                    name = cells[0].get_text(strip=True)
                    if not name or len(name) < 3:
                        continue
                    pct_text = cells[pct_col].get_text(strip=True)
                    pct = parse_turkish_number(pct_text)
                    if pct is not None and 0 < pct <= 100:
                        results.append({"name": name, "pct": pct})
                break
        return results
    except Exception as e:
        print(f"  Error: {str(e)[:80]}")
        return []


async def main():
    from playwright.async_api import async_playwright

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    perma_links = {}
    if os.path.exists(PERMA_FILE):
        with open(PERMA_FILE, encoding='utf-8') as f:
            perma_links = json.load(f)

    # Get ALL companies (not just those with missing share_percent)
    # Because we need to replace old data too
    rows = c.execute("""
        SELECT DISTINCT co.id, co.ticker
        FROM kap_companies co
        WHERE co.is_active = 1
    """).fetchall()

    total = len(rows)
    state = load_progress()
    remaining = [(r[0], r[1]) for r in rows if r[1] not in state["done"]]
    print(f"Total active companies: {total}, remaining: {len(remaining)}")

    if not remaining:
        print("All done!")
        db.close()
        return

    MAX_PER_RUN = 100
    run_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        ctx = await browser.new_context(
            user_agent=f'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(125,131)}.0.0.0 Safari/537.36',
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
            viewport={"width": 1440, "height": 900}
        )
        page = await ctx.new_page()

        for company_id, ticker in remaining:
            if run_count >= MAX_PER_RUN:
                print(f"\nRun limit ({MAX_PER_RUN}). Restart to continue.")
                break

            pl = perma_links.get(str(company_id), {})
            perma = pl.get('permaLink', '') if isinstance(pl, dict) else ''
            if not perma:
                state["done"].append(ticker)
                run_count += 1
                continue

            print(f"[{run_count+1}/{len(remaining)}] {ticker}...", end=" ", flush=True)

            results = await scrape_company_subs(page, perma)

            if results:
                # Delete old subsidiaries for this company
                c.execute("DELETE FROM kap_subsidiaries WHERE company_id = ?", (company_id,))
                deleted = c.rowcount

                # Insert fresh data from KAP
                inserted = 0
                for res in results:
                    # Determine relation_type from percentage
                    if res['pct'] >= 50:
                        rt = 'subsidiary'
                    elif res['pct'] >= 20:
                        rt = 'affiliate'
                    else:
                        rt = 'investment'

                    c.execute("""
                        INSERT INTO kap_subsidiaries (company_id, name, share_percent, relation_type, created_at)
                        VALUES (?, ?, ?, ?, datetime('now'))
                    """, (company_id, res['name'], res['pct'], rt))
                    inserted += 1

                db.commit()
                state["replaced"] += deleted
                state["updated"] += inserted
                print(f"replaced {deleted} -> inserted {inserted}")
            else:
                print("no data")
                # Still mark as done so we don't retry
                state["done"].append(ticker)
                db.commit()

            state["done"].append(ticker)
            save_progress(state)
            run_count += 1

            # Anti-ban delay
            delay = random.uniform(3.0, 7.0)
            if run_count % 15 == 0:
                delay = random.uniform(15.0, 30.0)
                print(f"  Cooling down {delay:.0f}s...")
            time.sleep(delay)

            if run_count % 40 == 0 and run_count > 0:
                await ctx.close()
                ctx = await browser.new_context(
                    user_agent=f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(125,131)}.0.0.0 Safari/537.36',
                    locale='tr-TR', timezone_id='Europe/Istanbul'
                )
                page = await ctx.new_page()

        await browser.close()
    db.close()
    print(f"\nDone: {state['updated']} inserted, {state['replaced']} old deleted, {len(state['done'])} companies processed")


if __name__ == "__main__":
    asyncio.run(main())
