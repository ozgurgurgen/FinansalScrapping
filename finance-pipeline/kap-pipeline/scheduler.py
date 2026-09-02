"""
KAP Pipeline Scheduler v3
==========================
"""

import os, sys, argparse, logging
from datetime import datetime, timedelta

os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")
sys.path.insert(0, os.path.dirname(__file__))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import CONFIG
from database import init_db

logger = logging.getLogger("kap_scheduler")

SCHEDULE = [
    {"id": "module1_seed", "name": "Module 1: Sirket Listesi",
     "desc": "BIST sirketleri ve permaLink'leri ceker",
     "frequency": "Haftalik", "time": "Pazar 03:00",
     "cron": {"hour": 3, "minute": 0, "day_of_week": "sun"}, "priority": 1},
    {"id": "module2_financials", "name": "Module 2: Mali Tablolar",
     "desc": "Bilancho ve gelir tablosu verilerini gunceller",
     "frequency": "Gunluk", "time": "Her gun 02:00",
     "cron": {"hour": 2, "minute": 0, "day_of_week": "mon-fri"}, "priority": 2},
    {"id": "module3_live_feed", "name": "Module 3: Canli Akis",
     "desc": "KAP'tan son bildirimleri ceker",
     "frequency": "Her 5 dk", "time": "Piyasa saatleri",
     "interval_minutes": 5, "priority": 3},
    {"id": "module4_corporate", "name": "Module 4: Kurumsal Islemler",
     "desc": "Temettu ve sermaye artirimi",
     "frequency": "Gunluk", "time": "Her gun 02:30",
     "cron": {"hour": 2, "minute": 30, "day_of_week": "mon-fri"}, "priority": 4},
    {"id": "module5_buybacks", "name": "Module 5: Pay Geri Alim",
     "desc": "Geri alim programlari",
     "frequency": "Gunluk", "time": "Her gun 02:30",
     "cron": {"hour": 2, "minute": 30, "day_of_week": "mon-fri"}, "priority": 5},
    {"id": "module6_ipo", "name": "Module 6: Halka Arz",
     "desc": "Halka arz izahname verileri",
     "frequency": "Haftalik", "time": "Pazartesi 03:00",
     "cron": {"hour": 3, "minute": 0, "day_of_week": "mon"}, "priority": 6},
    {"id": "module7_ownership", "name": "Module 7: Ortaklik Yapisi",
     "desc": "Sirket ortaklik yapisini gunceller",
     "frequency": "Gunluk", "time": "Her gun 03:00",
     "cron": {"hour": 3, "minute": 0, "day_of_week": "mon-fri"}, "priority": 7},
]


def _run_module(module_name, func, *args, **kwargs):
    from database import PipelineRun, get_session
    session = get_session()
    run = PipelineRun(module_name=module_name, started_at=datetime.utcnow(), status="RUNNING")
    session.add(run)
    session.commit()
    try:
        count = func(*args, **kwargs)
        run.status = "SUCCESS"
        run.records_processed = count
        run.finished_at = datetime.utcnow()
        run.records_inserted = count
    except Exception as e:
        run.status = "FAILED"
        run.error_message = str(e)[:500]
        run.finished_at = datetime.utcnow()
    finally:
        session.commit()
        session.close()
    return run.status, run.records_processed


def job_module1():
    from module1_seeds import run_module1_seed_data
    return _run_module("module1_seed", run_module1_seed_data, enrich_details=True)

def job_module2():
    from module2_financials import run_module2_financials
    return _run_module("module2_financials", run_module2_financials)

def job_module3():
    from module3_disclosures import run_module3_disclosures
    from_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    to_date = datetime.utcnow().strftime("%Y-%m-%d")
    return _run_module("module3_live_feed", run_module3_disclosures, from_date=from_date, to_date=to_date)

def job_module4():
    from module4_corporate import run_module4_corporate_actions
    return _run_module("module4_corporate", run_module4_corporate_actions)

def job_module5():
    from module5_buybacks import run_module5_buybacks
    return _run_module("module5_buybacks", run_module5_buybacks)

def job_module6():
    from module6_ipo import run_module6_ipo
    return _run_module("module6_ipo", run_module6_ipo)

def job_module7():
    from module7_ownership import run_module7_ownership
    return _run_module("module7_ownership", run_module7_ownership)


JOB_MAP = {
    "module1_seed": job_module1, "module2_financials": job_module2,
    "module3_live_feed": job_module3, "module4_corporate": job_module4,
    "module5_buybacks": job_module5, "module6_ipo": job_module6,
    "module7_ownership": job_module7,
}


def run_module_by_id(module_id):
    """Run a single module by its ID. Returns (status, count)."""
    func = JOB_MAP.get(module_id)
    if not func:
        return "ERROR", 0
    try:
        result = func()
        if isinstance(result, tuple):
            return result
        return "SUCCESS", 0
    except Exception as e:
        return "FAILED", 0


def run_all_now():
    logger.info("=" * 60)
    logger.info("  ILK CALISTIRMA: Tum moduller calisiyor...")
    logger.info("=" * 60)
    for sched in sorted(SCHEDULE, key=lambda x: x["priority"]):
        func = JOB_MAP.get(sched["id"])
        if func:
            logger.info(f"\n[{sched['name']}] Basliyor...")
            try:
                func()
            except Exception as e:
                logger.error(f"  Hata: {e}")
    logger.info("\n  ILK CALISTIRMA TAMAMLANDI!")


def start_scheduler(live_only=False, daily_only=False):
    scheduler = BlockingScheduler(timezone="Europe/Istanbul")
    for sched in SCHEDULE:
        job_id = sched["id"]
        job_func = JOB_MAP.get(job_id)
        if not job_func: continue
        if live_only and job_id != "module3_live_feed": continue
        if daily_only and job_id == "module3_live_feed": continue
        if "interval_minutes" in sched:
            trigger = IntervalTrigger(minutes=sched["interval_minutes"])
        else:
            trigger = CronTrigger(**sched["cron"])
        scheduler.add_job(job_func, trigger, id=job_id, name=sched["name"],
                         max_instances=1, coalesce=True)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def get_next_runs():
    """Calculate next run time for each scheduled job."""
    now = datetime.now()
    results = []
    for sched in SCHEDULE:
        next_dt = None
        if "cron" in sched:
            cron = sched["cron"]
            h = cron.get("hour", 0)
            m = cron.get("minute", 0)
            dow = cron.get("day_of_week")
            next_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_dt <= now:
                next_dt += timedelta(days=1)
            if dow == "mon-fri":
                while next_dt.weekday() >= 5:
                    next_dt += timedelta(days=1)
            elif dow == "sun":
                while next_dt.weekday() != 6:
                    next_dt += timedelta(days=1)
            elif dow == "mon":
                while next_dt.weekday() != 0:
                    next_dt += timedelta(days=1)
        elif "interval_minutes" in sched:
            next_dt = now + timedelta(minutes=sched["interval_minutes"])
        results.append({
            "id": sched["id"], "name": sched["name"],
            "next_run": next_dt.strftime("%d.%m.%Y %H:%M") if next_dt else f"Her {sched.get('interval_minutes',5)} dk",
            "next_dt": next_dt,
        })
    return results


def list_schedule():
    print("\n" + "=" * 70)
    print("  KAP PIPELINE ZAMANLAMA")
    print("=" * 70)
    for s in SCHEDULE:
        print(f"  {s['name']:<30s} {s['frequency']:<20s} {s['time']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--now", action="store_true")
    parser.add_argument("--live-only", action="store_true")
    parser.add_argument("--daily-only", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                       format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    if args.list: list_schedule(); sys.exit(0)
    init_db()
    if args.now: run_all_now(); sys.exit(0)
    run_all_now()
    start_scheduler(live_only=args.live_only, daily_only=args.daily_only)
