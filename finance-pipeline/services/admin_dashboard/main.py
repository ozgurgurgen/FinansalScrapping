"""
Admin Dashboard — Central Orchestrator Backend
===============================================
Manages Docker containers via Docker Engine API.
Provides service status, live logs, start/stop/restart control.

Endpoints:
  GET  /                          — Dashboard UI
  GET  /api/containers            — List all containers with status
  GET  /api/containers/{name}     — Single container details
  POST /api/containers/{name}/{action} — start/stop/restart
  POST /api/containers/{name}/trigger  — Trigger scrape
  GET  /api/containers/{name}/logs     — Live logs (last N lines)
  GET  /api/stats                      — Overall stats
  GET  /api/pipeline/runs              — Pipeline run history
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, date
from typing import Optional

import requests
try:
    import docker
except ImportError:
    docker = None
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory for shared_db
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Ensure DATABASE_URL defaults to PostgreSQL if not set
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://admin:admin123@localhost:5432/finance_platform"

from sqlalchemy import func as sqlfunc
from shared_db.models import (
    Base, engine, SessionLocal,
    KapCompany, KapFinancial, KapDisclosure, KapCorporateAction,
    TefasFund, TefasFundPrice, TefasFundAllocation, PipelineRun,
    MarketIndicator, MarketRate, CommodityPrice, CryptoPrice,
    KapShareholder, KapCashFlow, KapManagement, KapSubsidiary,
    KapPortfolioReport, KapFinancialNote, BistStockPrice,
    DisclosureDetail, IndexConstituent, SettlementData,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ADMIN] %(message)s")
logger = logging.getLogger(__name__)

# Docker client — only if docker package is available
docker_client = None
DOCKER_AVAILABLE = False
if docker is not None and (os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_API_VERSION")):
    try:
        docker_client = docker.from_env(timeout=3)
        DOCKER_AVAILABLE = True
        logger.info("Docker socket connected")
    except Exception as e:
        logger.info(f"Docker not available: {e}")
else:
    logger.info("Running in local mode (no Docker)")

# Service container name mapping
SERVICE_CONTAINERS = {
    "kap_worker": "kap_worker_service",
    "tefas_worker": "tefas_worker_service",
    "market_data_worker": "market_data_worker_service",
    "admin_dashboard": "admin_dashboard_service",
    "postgres_db": "pipeline_db",
}

# Service API URLs (inside Docker network)
SERVICE_URLS = {
    "kap_worker": "http://localhost:8001",
    "tefas_worker": "http://localhost:8002",
    "market_data_worker": "http://localhost:8003",
}

# KAP module definitions
KAP_MODULES = {
    "seed": {"name": "Sirket Listesi", "icon": "🏢", "desc": "BIST sirket listesini ceker"},
    "financials": {"name": "Mali Tablolar", "icon": "📊", "desc": "Finansal tablo verilerini ceker"},
    "disclosures": {"name": "Bildirim Akisi", "icon": "📢", "desc": "KAP bildirimlerini ceker"},
    "corporate": {"name": "Kurumsal Islem", "icon": "🎯", "desc": "Temettu/sermaye islemleri"},
    "buybacks": {"name": "Geri Alim", "icon": "💰", "desc": "Pay geri alim programlari"},
    "ipo": {"name": "IPO", "icon": "🏆", "desc": "Halka arz verileri"},
    "ownership": {"name": "Ortaklik", "icon": "👥", "desc": "Ortaklik yapisi / pay sahipleri"},
    "cashflow": {"name": "Nakit Akis", "icon": "💵", "desc": "Nakit akis tablosu"},
    "management": {"name": "Yonetim Kurulu", "icon": "👔", "desc": "YK uyeleri, CEO"},
    "subsidiaries": {"name": "Bagli Ortaklik", "icon": "🏭", "desc": "Istirak ve bagli ortakliklar"},
    "portfolio": {"name": "Portfoy Raporu", "icon": "📋", "desc": "Portfoy dagilim raporlari"},
    "notes": {"name": "Dipnotlar", "icon": "📝", "desc": "Finansal dipnotlar"},
    "prices": {"name": "BIST Fiyat", "icon": "💹", "desc": "Guncel hisse fiyatlari"},
    "disclosure_details": {"name": "Bildirim Detay", "icon": "🔍", "desc": "Ihale, blok satis parse"},
    "index_settlement": {"name": "Endeks & Takas", "icon": "📊", "desc": "XU100 uyeleri, takas oranlari"},
    "selenium": {"name": "Selenium KAP", "icon": "🤖", "desc": "Sirket sayfasi scrape (anti-ban)"},
    "disclosures": {"name": "Bildirim Akisi", "icon": "📢", "desc": "KAP bildirimlerini ceker"},
    "corporate": {"name": "Kurumsal Islemler", "icon": "🎯", "desc": "Temettu ve sermaye islemlerini isler"},
    "buybacks": {"name": "Geri Alim", "icon": "💰", "desc": "Pay geri alim programlarini isler"},
    "ipo": {"name": "IPO", "icon": "🏆", "desc": "Halka arz verilerini isler"},
}

# ══════════════════════════════════════════════════════════════════════════════
# API KEY AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════
import secrets

# API Keys stored in env or generated
API_KEY = os.environ.get("FINANCE_API_KEY", "fbkey-" + secrets.token_hex(16))
API_KEY_ALT = os.environ.get("FINANCE_API_KEY_ALT", "fbkey-" + secrets.token_hex(16))

# Endpoints that require API key (export endpoints)
# Dashboard UI endpoints are public, data export endpoints require auth
EXPORT_PREFIX = "/api/export"

# Endpoints that skip auth (dashboard internal, health checks)
AUTH_SKIP_PATHS = [
    "/",
    "/api/containers",
    "/api/stats",
    "/api/pipeline",
    "/static",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
]

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

def verify_api_key(request: StarletteRequest):
    """FastAPI dependency — checks X-API-Key header for export endpoints."""
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if not api_key:
        api_key = request.query_params.get("api_key")
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
    if not api_key or (api_key != API_KEY and api_key != API_KEY_ALT):
        raise HTTPException(status_code=401, detail={
            "error": "Unauthorized",
            "message": "Geçersiz veya eksik API anahtarı. X-API-Key header'ı veya Authorization: Bearer <key> ile gönderin.",
            "hint": "Header: X-API-Key: your-api-key",
        })
    return api_key

# For convenience, create a Depends object
from fastapi import Depends as _Depends
depends_auth = _Depends(verify_api_key)

app = FastAPI(title="Admin Dashboard", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(_dir, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(_dir, "templates")), name="static")

logger.info(f"🔑 API Keys: Primary={API_KEY[:12]}... Alt={API_KEY_ALT[:12]}...")


# ══════════════════════════════════════════════════════════════════════════════
# DOCKER CONTAINER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def _get_container(name: str):
    """Get a Docker container by name."""
    if not DOCKER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Docker not available")
    try:
        return docker_client.containers.get(name)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")


def _container_info(container) -> dict:
    """Extract container info dict."""
    return {
        "name": container.name,
        "short_id": container.short_id,
        "status": container.status,  # running, exited, paused, etc.
        "image": str(container.image.tags[0]) if container.image.tags else "unknown",
        "created": container.attrs.get("Created", ""),
        "started_at": container.attrs.get("State", {}).get("StartedAt", ""),
        "ports": container.ports,
        "is_running": container.status == "running",
    }


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

# Cache for /api/containers (avoid hammering workers every 3s)
_containers_cache = {"data": None, "ts": 0}
_CONTAINERS_CACHE_TTL = 8  # seconds — matches dashboard refresh interval

import concurrent.futures

@app.get("/api/containers")
def list_containers():
    """List all pipeline containers with their status. Cached for 5s."""
    now = time.time()
    if _containers_cache["data"] and (now - _containers_cache["ts"]) < _CONTAINERS_CACHE_TTL:
        return _containers_cache["data"]

    all_keys = list(SERVICE_URLS.keys()) + [k for k in SERVICE_CONTAINERS if k not in SERVICE_URLS]

    def _check_service(service_key):
        container_name = SERVICE_CONTAINERS.get(service_key, service_key)
        is_running = False
        stats = None
        image = "not built"
        status_str = "unknown"

        if service_key in SERVICE_URLS:
            try:
                resp = requests.get(f"{SERVICE_URLS[service_key]}/health", timeout=2)
                if resp.status_code == 200:
                    is_running = True
                    status_str = "running (local)"
                    image = "local process"
            except Exception:
                pass
            if is_running:
                try:
                    resp = requests.get(f"{SERVICE_URLS[service_key]}/api/status", timeout=3)
                    if resp.status_code == 200:
                        stats = resp.json()
                except Exception:
                    pass
        elif DOCKER_AVAILABLE:
            try:
                container = docker_client.containers.get(container_name)
                info = _container_info(container)
                is_running = info["is_running"]
                image = info["image"]
                status_str = info["status"]
            except Exception:
                pass

        return {
            "name": container_name,
            "service_key": service_key,
            "status": status_str,
            "is_running": is_running,
            "image": image,
            "stats": stats,
        }

    # Fetch all services in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_check_service, k): k for k in all_keys}
        for fut in concurrent.futures.as_completed(futures, timeout=8):
            try:
                results.append(fut.result())
            except Exception:
                k = futures[fut]
                results.append({"name": k, "service_key": k, "status": "error", "is_running": False, "image": "error", "stats": None})
    # Sort results to match original order
    key_order = {k: i for i, k in enumerate(all_keys)}
    results.sort(key=lambda r: key_order.get(r["service_key"], 99))
    resp = {"containers": results, "docker_available": DOCKER_AVAILABLE}
    _containers_cache["data"] = resp
    _containers_cache["ts"] = time.time()
    return resp


@app.get("/api/containers/{service_key}")
def get_container(service_key: str):
    """Get details for a specific service container."""
    container_name = SERVICE_CONTAINERS.get(service_key)
    if not container_name:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_key}")
    container = _get_container(container_name)
    info = _container_info(container)
    info["service_key"] = service_key
    return info


@app.post("/api/containers/{service_key}/{action}")
def control_container(service_key: str, action: str):
    """Start, stop, or restart a container."""
    if action not in ("start", "stop", "restart"):
        raise HTTPException(status_code=400, detail="Action must be start, stop, or restart")

    container_name = SERVICE_CONTAINERS.get(service_key)
    if not container_name:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_key}")

    container = _get_container(container_name)
    try:
        getattr(container, action)()
        time.sleep(1)  # Brief wait for state change
        container.reload()
        return {
            "status": "success",
            "message": f"{container_name} {action} successful",
            "new_status": container.status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{service_key}/trigger")
def trigger_scrape(service_key: str):
    """Trigger a manual scrape on the target service."""
    if service_key not in SERVICE_URLS:
        raise HTTPException(status_code=404, detail=f"No API for service: {service_key}")
    try:
        resp = requests.post(f"{SERVICE_URLS[service_key]}/api/scrape/now", timeout=10)
        return resp.json()
    except requests.ConnectionError:
        return {"status": "error", "message": f"Cannot connect to {service_key}. Is it running?"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/kap/scrape/{module}")
def trigger_kap_module(module: str):
    """Trigger a specific KAP module."""
    if module not in KAP_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}. Valid: {list(KAP_MODULES.keys())}")
    try:
        resp = requests.post(f"{SERVICE_URLS['kap_worker']}/api/scrape/{module}", timeout=10)
        return resp.json()
    except requests.ConnectionError:
        return {"status": "error", "message": "KAP Worker is running degil"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/tefas/scrape/now")
def trigger_tefas_scrape(years: int = 5):
    """Trigger TEFAS full scrape."""
    try:
        resp = requests.post(f"{SERVICE_URLS['tefas_worker']}/api/scrape/now?years={years}", timeout=10)
        return resp.json()
    except requests.ConnectionError:
        return {"status": "error", "message": "TEFAS Worker is running degil"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/containers/{service_key}/logs")
def get_logs(service_key: str, tail: int = 100):
    """Get logs — first try Docker, then fall back to worker API /api/logs."""
    # Try Docker container logs
    container_name = SERVICE_CONTAINERS.get(service_key)
    if DOCKER_AVAILABLE and container_name:
        try:
            container = docker_client.containers.get(container_name)
            logs = container.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
            return {"logs": logs, "container": container_name, "source": "docker"}
        except docker.errors.NotFound:
            pass
        except Exception:
            pass

    # Fall back to worker API /api/logs endpoint
    if service_key in SERVICE_URLS:
        try:
            resp = requests.get(f"{SERVICE_URLS[service_key]}/api/logs", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                log_lines = data.get("logs", [])
                # Take last N lines
                if isinstance(log_lines, list):
                    log_lines = log_lines[-tail:]
                return {"logs": "\n".join(log_lines) if isinstance(log_lines, list) else str(log_lines), "container": service_key, "source": "worker_api"}
        except Exception:
            pass

    return {"logs": "Servis calismiyor veya log bulunamadi", "container": service_key, "source": "none"}


@app.get("/api/tunnel-status")
def get_tunnel_status():
    """Check Cloudflare tunnel status."""
    import subprocess, re
    result = {"active": False, "url": None, "pid": None}
    try:
        # Check if cloudflared is running
        proc = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/FO", "CSV"], 
                           capture_output=True, text=True, timeout=5)
        if "cloudflared.exe" in proc.stdout:
            # Extract PID
            lines = proc.stdout.strip().split('\n')
            for line in lines[1:]:
                if 'cloudflared' in line.lower():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        result["pid"] = parts[1].strip('"')
                        result["active"] = True
                        break
            
            # Read tunnel URL from log
            log_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tunnel_err.log")
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', content)
                    if match:
                        result["url"] = match.group(0)
    except Exception as e:
        logger.info(f"Tunnel check error: {e}")
    return result


@app.get("/api/stats")
def get_stats():
    """Overall database and service statistics."""
    db = SessionLocal()
    try:
        def _cnt(model):
            try:
                return db.query(sqlfunc.count()).select_from(model).scalar() or 0
            except:
                return 0

        stats = {
            "kap": {
                "companies": _cnt(KapCompany),
                "financials": _cnt(KapFinancial),
                "disclosures": _cnt(KapDisclosure),
                "corporate_actions": _cnt(KapCorporateAction),
                "shareholders": _cnt(KapShareholder),
                "management": _cnt(KapManagement),
                "subsidiaries": _cnt(KapSubsidiary),
                "cashflows": _cnt(KapCashFlow),
                "financial_notes": _cnt(KapFinancialNote),
                "portfolio_reports": _cnt(KapPortfolioReport),
                "disclosure_details": _cnt(DisclosureDetail),
                "bist_prices": _cnt(BistStockPrice),
                "index_members": _cnt(IndexConstituent),
                "settlement": _cnt(SettlementData),
            },
            "tefas": {
                "funds": _cnt(TefasFund),
                "prices": _cnt(TefasFundPrice),
                "allocations": _cnt(TefasFundAllocation),
            },
            "market": {
                "indicators": _cnt(MarketIndicator),
                "rates": _cnt(MarketRate),
                "commodities": _cnt(CommodityPrice),
                "crypto": _cnt(CryptoPrice),
            },
            "pipeline_runs": _cnt(PipelineRun),
            "docker_available": DOCKER_AVAILABLE,
            "timestamp": datetime.utcnow().isoformat(),
        }
        # Add raw-table counts (no ORM models)
        try:
            from sqlalchemy import text
            for tbl, key in [('share_buybacks', 'share_buybacks'), ('ipo_data', 'ipo_data')]:
                result = db.execute(text(f'SELECT COUNT(*) FROM {tbl}')).scalar()
                stats['kap'][key] = result or 0
        except:
            pass
        return stats
    finally:
        db.close()


@app.get("/api/pipeline/runs")
def get_pipeline_runs(limit: int = 50):
    """Get recent pipeline run history."""
    db = SessionLocal()
    try:
        runs = db.query(PipelineRun).order_by(
            PipelineRun.started_at.desc()
        ).limit(limit).all()
        return {
            "runs": [
                {
                    "id": r.id,
                    "service_name": r.service_name,
                    "module_name": r.module_name,
                    "status": r.status,
                    "records_processed": r.records_processed,
                    "records_inserted": r.records_inserted,
                    "error_message": r.error_message,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in runs
            ]
        }
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# FUND DETAILS (TEFAS deep-dive)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/funds")
def list_funds():
    """List all funds with price record counts."""
    db = SessionLocal()
    try:
        funds = db.query(TefasFund).order_by(TefasFund.code).all()
        result = []
        for f in funds:
            price_count = db.query(sqlfunc.count()).select_from(TefasFundPrice).filter(
                TefasFundPrice.fund_id == f.id
            ).scalar() or 0
            result.append({
                "id": f.id, "code": f.code, "title": f.title, "kind": f.kind,
                "price_count": price_count,
            })
        return {"funds": result, "total": len(result)}
    finally:
        db.close()


@app.get("/api/funds/{code}")
def get_fund_detail(code: str):
    """Get detailed fund info + all price history."""
    db = SessionLocal()
    try:
        fund = db.query(TefasFund).filter(TefasFund.code == code.upper()).first()
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund {code} not found")

        prices = db.query(TefasFundPrice).filter(
            TefasFundPrice.fund_id == fund.id
        ).order_by(TefasFundPrice.trade_date).all()

        # Build price series
        price_series = []
        for p in prices:
            price_series.append({
                "date": p.trade_date.isoformat() if p.trade_date else None,
                "price": float(p.price) if p.price else None,
            })

        # Compute stats
        if price_series:
            vals = [p["price"] for p in price_series if p["price"] is not None]
            first_price = vals[0] if vals else None
            last_price = vals[-1] if vals else None
            min_price = min(vals) if vals else None
            max_price = max(vals) if vals else None
            avg_price = sum(vals) / len(vals) if vals else None
            total_return = ((last_price / first_price - 1) * 100) if first_price and last_price and first_price > 0 else None
            annualized = None
            if total_return is not None and len(vals) > 1:
                years = len(vals) / 252  # approximate trading days
                if years > 0:
                    annualized = ((last_price / first_price) ** (1 / years) - 1) * 100
        else:
            first_price = last_price = min_price = max_price = avg_price = total_return = annualized = None

        return {
            "fund": {
                "code": fund.code, "title": fund.title, "kind": fund.kind,
            },
            "stats": {
                "total_records": len(price_series),
                "first_date": price_series[0]["date"] if price_series else None,
                "last_date": price_series[-1]["date"] if price_series else None,
                "first_price": first_price,
                "last_price": last_price,
                "min_price": min_price,
                "max_price": max_price,
                "avg_price": round(avg_price, 6) if avg_price else None,
                "total_return_pct": round(total_return, 2) if total_return else None,
                "annualized_return_pct": round(annualized, 2) if annualized else None,
            },
            "prices": price_series,
        }
    finally:
        db.close()


@app.get("/api/funds/{code}/chart")
def get_fund_chart(code: str, days: int = 365):
    """Get last N days of price data for charting."""
    db = SessionLocal()
    try:
        fund = db.query(TefasFund).filter(TefasFund.code == code.upper()).first()
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund {code} not found")

        from datetime import timedelta
        cutoff = date.today() - timedelta(days=days)
        prices = db.query(TefasFundPrice).filter(
            TefasFundPrice.fund_id == fund.id,
            TefasFundPrice.trade_date >= cutoff,
        ).order_by(TefasFundPrice.trade_date).all()

        return {
            "code": fund.code,
            "days": days,
            "data": [{
                "date": p.trade_date.isoformat(),
                "price": float(p.price) if p.price else None,
            } for p in prices],
        }
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE STATUS (real-time from worker APIs)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/service-status/{service_key}")
def get_service_status(service_key: str):
    """Fetch real-time status from the worker service API."""
    if service_key not in SERVICE_URLS:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_key}")

    # Check if container is running
    container_name = SERVICE_CONTAINERS.get(service_key)
    is_running = False
    if container_name and DOCKER_AVAILABLE:
        try:
            container = docker_client.containers.get(container_name)
            is_running = container.status == "running"
        except docker.errors.NotFound:
            pass
    elif service_key in SERVICE_URLS:
        # For local mode, check if port is responding
        try:
            r = requests.get(f"{SERVICE_URLS[service_key]}/health", timeout=2)
            is_running = r.status_code == 200
        except Exception:
            pass

    # Fetch status from worker API
    stats = {}
    try:
        resp = requests.get(f"{SERVICE_URLS[service_key]}/api/status", timeout=3)
        if resp.status_code == 200:
            stats = resp.json()
    except Exception:
        pass

    # Use worker's own running flag if available, fall back to port-alive check
    if "running" not in stats:
        stats["running"] = is_running
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS CALCULATION — Percent, Phase, ETA for each service
# ══════════════════════════════════════════════════════════════════════════════

KAP_MODULE_ORDER = [
    "seed", "financials", "disclosures", "corporate", "buybacks",
    "ipo", "ownership", "cashflow", "management", "subsidiaries",
    "portfolio", "notes", "prices", "disclosure_details",
    "index_settlement", "selenium"
]

def _calc_kap_progress(stats: dict) -> dict:
    """Calculate KAP worker progress percentage, phase, ETA."""
    if not stats.get("running") and not stats.get("scraping"):
        return {"percent": 0, "phase": "Durduruldu", "eta_seconds": 0, "modules_completed": 0, "total_modules": len(KAP_MODULE_ORDER)}
    modules_done = stats.get("modules_completed", 0)
    total = len(KAP_MODULE_ORDER)
    current_phase = stats.get("current_module", stats.get("phase", ""))
    percent = round((modules_done / total) * 100) if total > 0 else 0
    # ETA: estimate remaining modules * avg_time_per_module (60s each)
    remaining = total - modules_done
    eta_seconds = remaining * 60  # rough estimate
    phase_name = ""
    if current_phase:
        mod_info = KAP_MODULES.get(current_phase, {})
        phase_name = f"{mod_info.get('icon', '')} {mod_info.get('name', current_phase)}"
    return {
        "percent": min(percent, 99),
        "phase": phase_name or "Başlatılıyor...",
        "eta_seconds": eta_seconds,
        "modules_completed": modules_done,
        "total_modules": total,
        "current_module": current_phase,
    }


def _calc_tefas_progress(stats: dict) -> dict:
    """Calculate TEFAS worker progress percentage, phase, ETA."""
    if not stats.get("scraping") and not stats.get("running"):
        return {"percent": 0, "phase": "Durduruldu", "eta_seconds": 0, "current": "", "total": 0}
    phase = stats.get("phase", "")
    total_funds = stats.get("total_funds", 2591)
    details_updated = stats.get("details_updated", 0)
    funds_with_prices = stats.get("funds_with_prices", 0)
    request_count = stats.get("request_count", 0)
    if phase == "details":
        percent = round((details_updated / total_funds) * 100) if total_funds > 0 else 0
        current = f"Detay {details_updated}/{total_funds}"
        remaining = total_funds - details_updated
        eta_seconds = int(remaining * 5)  # ~5s per fund detail
    elif phase == "prices":
        # Details done = 50%, prices = remaining 50%
        detail_pct = 50
        price_pct = round((funds_with_prices / total_funds) * 50) if total_funds > 0 else 0
        percent = detail_pct + price_pct
        current = f"Fiyat {funds_with_prices}/{total_funds}"
        remaining = total_funds - funds_with_prices
        eta_seconds = int(remaining * 4)  # ~4s per price fetch
    else:
        percent = 0
        current = stats.get("current_fund", "Başlatılıyor...")
        eta_seconds = 0
    current_fund = stats.get("current_fund", "")
    return {
        "percent": min(percent, 99),
        "phase": f"📊 {phase.upper()}" if phase else "Başlatılıyor...",
        "eta_seconds": eta_seconds,
        "current": current,
        "current_fund": current_fund,
        "total": total_funds,
        "requests": request_count,
    }


def _calc_market_progress(stats: dict) -> dict:
    """Calculate Market Data worker progress."""
    if not stats.get("running"):
        last_status = stats.get("last_status", "")
        if last_status == "SUCCESS":
            return {"percent": 100, "phase": "✅ Tamamlandı", "eta_seconds": 0}
        return {"percent": 0, "phase": "Durduruldu", "eta_seconds": 0}
    return {"percent": 50, "phase": "🌍 Veri çekiliyor...", "eta_seconds": 30}


@app.get("/api/progress")
def get_progress():
    """Get progress info for all services."""
    result = {}
    for svc_key, url in SERVICE_URLS.items():
        stats = {}
        try:
            resp = requests.get(f"{url}/api/status", timeout=3)
            if resp.status_code == 200:
                stats = resp.json()
        except Exception:
            pass
        if svc_key == "kap_worker":
            result[svc_key] = _calc_kap_progress(stats)
        elif svc_key == "tefas_worker":
            result[svc_key] = _calc_tefas_progress(stats)
        elif svc_key == "market_data_worker":
            result[svc_key] = _calc_market_progress(stats)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD UI
# ══════════════════════════════════════════════════════════════════════════════

# ── KAP Data Endpoints ───────────────────────────────────────────────────────

@app.get("/api/kap/companies")
def get_kap_companies(limit: int = 100, offset: int = 0, search: str = ""):
    db = SessionLocal()
    try:
        q = db.query(KapCompany)
        if search:
            q = q.filter(KapCompany.ticker.ilike(f"%{search}%") | KapCompany.company_name.ilike(f"%{search}%"))
        total = q.count()
        items = q.order_by(KapCompany.ticker).offset(offset).limit(limit).all()
        return {
            "total": total, "offset": offset, "limit": limit,
            "data": [{"ticker": c.ticker, "company_name": c.company_name, "sector": c.sector, "market": c.market, "is_active": c.is_active} for c in items]
        }
    finally:
        db.close()


@app.get("/api/kap/company/{ticker}")
def get_company_detail(ticker: str):
    """Get full company profile: price, financials, disclosures, shareholders, management, etc."""
    import sqlite3 as _sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'finance.db')
    db = _sqlite3.connect(db_path)
    db.row_factory = _sqlite3.Row
    c = db.cursor()
    ticker = ticker.upper()
    result = {"ticker": ticker, "found": False}

    # 1. Company info
    c.execute("SELECT * FROM kap_companies WHERE ticker = ?", (ticker,))
    row = c.fetchone()
    if not row:
        db.close()
        return result
    result["found"] = True
    result["company"] = dict(row)

    # 2. Stock price + ratios
    c.execute("SELECT * FROM bist_stock_prices WHERE ticker = ?", (ticker,))
    row = c.fetchone()
    result["price"] = dict(row) if row else None

    # 3. Latest financials
    c.execute("""
        SELECT f.* FROM kap_financials f
        JOIN kap_companies co ON co.id = f.company_id
        WHERE co.ticker = ?
        ORDER BY f.year DESC, f.period DESC LIMIT 4
    """, (ticker,))
    result["financials"] = [dict(r) for r in c.fetchall()]

    # 4. Disclosures (last 20)
    c.execute("""
        SELECT d.disclosure_id, d.title, d.category, d.publish_date, d.source_url, d.is_catalyst
        FROM kap_disclosures d
        JOIN kap_companies co ON co.id = d.company_id
        WHERE co.ticker = ?
        ORDER BY d.publish_date DESC LIMIT 20
    """, (ticker,))
    result["disclosures"] = [dict(r) for r in c.fetchall()]

    # 5. Shareholders
    c.execute("""
        SELECT sh.holder_name, sh.shares_amount, sh.share_ratio_percent, sh.is_qualified, sh.holder_type
        FROM kap_shareholders sh
        JOIN kap_companies co ON co.id = sh.company_id
        WHERE co.ticker = ?
        ORDER BY sh.share_ratio_percent DESC
    """, (ticker,))
    result["shareholders"] = [dict(r) for r in c.fetchall()]

    # 6. Management
    c.execute("""
        SELECT mg.name, mg.title, mg.member_type
        FROM kap_management mg
        JOIN kap_companies co ON co.id = mg.company_id
        WHERE co.ticker = ?
    """, (ticker,))
    result["management"] = [dict(r) for r in c.fetchall()]

    # 7. Cash flows
    c.execute("""
        SELECT cf.year, cf.period, cf.operating_cash_flow, cf.investing_cash_flow,
               cf.financing_cash_flow, cf.net_change, cf.closing_cash
        FROM kap_cashflows cf
        JOIN kap_companies co ON co.id = cf.company_id
        WHERE co.ticker = ?
        ORDER BY cf.year DESC, cf.period DESC LIMIT 4
    """, (ticker,))
    result["cashflows"] = [dict(r) for r in c.fetchall()]

    # 8. Corporate actions
    c.execute("""
        SELECT ca.action_type, ca.gross_per_share, ca.net_per_share, ca.yield_percent,
               ca.ex_date, ca.payment_date, ca.status
        FROM kap_corporate_actions ca
        JOIN kap_companies co ON co.id = ca.company_id
        WHERE co.ticker = ?
        ORDER BY ca.ex_date DESC LIMIT 10
    """, (ticker,))
    result["corporate_actions"] = [dict(r) for r in c.fetchall()]

    # 9. Subsidiaries
    c.execute("""
        SELECT sb.name, sb.share_percent, sb.relation_type
        FROM kap_subsidiaries sb
        JOIN kap_companies co ON co.id = sb.company_id
        WHERE co.ticker = ?
    """, (ticker,))
    result["subsidiaries"] = [dict(r) for r in c.fetchall()]

    # 10. IPO data
    c.execute("SELECT * FROM ipo_data WHERE ticker = ?", (ticker,))
    result["ipo"] = [dict(r) for r in c.fetchall()]

    # 11. Buybacks
    c.execute("""
        SELECT bb.total_budget_tl, bb.max_shares, bb.total_bought_shares,
               bb.capital_ratio_percent, bb.avg_buyback_price
        FROM share_buybacks bb
        JOIN kap_companies co ON co.id = bb.company_id
        WHERE co.ticker = ?
    """, (ticker,))
    result["buybacks"] = [dict(r) for r in c.fetchall()]

    # 12. Index membership
    c.execute("SELECT index_name, weight_pct FROM index_constituents WHERE ticker = ?", (ticker,))
    result["indices"] = [dict(r) for r in c.fetchall()]

    # 13. Price history (last 1 year daily)
    c.execute("""
        SELECT trade_date, open, high, low, close, volume
        FROM bist_price_history
        WHERE ticker = ? AND trade_date >= date('now', '-365 days')
        ORDER BY trade_date ASC
    """, (ticker,))
    result["price_history"] = [dict(r) for r in c.fetchall()]

    db.close()
    return result


@app.get("/api/kap/disclosures")
def get_kap_disclosures(limit: int = 100, offset: int = 0, category: str = "", symbol: str = "", days: int = 30):
    db = SessionLocal()
    try:
        from datetime import timedelta
        q = db.query(KapDisclosure)
        if category:
            q = q.filter(KapDisclosure.category == category)
        if symbol:
            q = q.filter(KapDisclosure.symbol == symbol)
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(KapDisclosure.publish_date >= since)
        total = q.count()
        items = q.order_by(KapDisclosure.publish_date.desc()).offset(offset).limit(limit).all()
        return {
            "total": total, "offset": offset, "limit": limit,
            "data": [{
                "disclosure_id": d.disclosure_id, "symbol": d.symbol, "title": d.title,
                "category": d.category, "publish_date": d.publish_date.isoformat() if d.publish_date else None,
                "source_url": d.source_url, "is_catalyst": d.is_catalyst,
            } for d in items]
        }
    finally:
        db.close()


@app.get("/api/kap/disclosure-categories")
def get_kap_disclosure_categories():
    db = SessionLocal()
    try:
        cats = db.query(KapDisclosure.category, sqlfunc.count()).group_by(KapDisclosure.category).all()
        return {"categories": [{"name": c, "count": n} for c, n in cats]}
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# MARKET DATA — VAP, FX, Crypto, Commodities
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/market-data")
def get_market_data():
    """Return all market data: FX rates, crypto, commodities, VAP indicators."""
    import sqlite3 as _sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'finance.db')
    db = _sqlite3.connect(db_path)
    db.row_factory = _sqlite3.Row
    c = db.cursor()

    result = {"fx": [], "crypto": [], "commodities": [], "indicators": []}

    # FX rates
    try:
        rows = c.execute("SELECT pair as name, rate as value, source as symbol FROM market_rates ORDER BY pair").fetchall()
        result["fx"] = [dict(r) for r in rows]
    except Exception:
        pass

    # Crypto
    try:
        rows = c.execute("SELECT pair as name, price as value, source as symbol FROM crypto_prices ORDER BY pair").fetchall()
        result["crypto"] = [dict(r) for r in rows]
    except Exception:
        pass

    # Commodities
    try:
        rows = c.execute("SELECT name, price as value, unit as symbol FROM commodity_prices ORDER BY name").fetchall()
        result["commodities"] = [dict(r) for r in rows]
    except Exception:
        pass

    # VAP indicators
    try:
        rows = c.execute("SELECT name, value, category FROM market_indicators ORDER BY name").fetchall()
        result["indicators"] = [dict(r) for r in rows]
    except Exception:
        pass

    db.close()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "schedule.json")

DEFAULT_SCHEDULE = {
    "kap_worker": {
        "enabled": True,
        "mode": "daily",  # manual, daily, hourly, interval
        "hour": 2,
        "minute": 0,
        "interval_minutes": 60,
        "modules": ["seed", "disclosures", "corporate", "buybacks", "ipo"],
    },
    "tefas_worker": {
        "enabled": True,
        "mode": "daily",
        "hour": 3,
        "minute": 0,
        "interval_minutes": 60,
        "years_back": 5,
    },
}


def _load_schedule() -> dict:
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SCHEDULE.copy()


def _save_schedule(schedule: dict):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)


@app.get("/api/schedule")
def get_schedule():
    schedule = _load_schedule()
    return {"schedule": schedule}


@app.post("/api/schedule")
def update_schedule(request_body: dict):
    try:
        schedule = _load_schedule()
        for key, val in request_body.get("schedule", {}).items():
            if key in schedule:
                schedule[key].update(val)
            else:
                schedule[key] = val
        _save_schedule(schedule)
        # Reload schedulers on workers
        for svc_key in ["kap_worker", "tefas_worker", "market_data_worker"]:
            if svc_key in SERVICE_URLS:
                try:
                    requests.post(f"{SERVICE_URLS[svc_key]}/api/schedule/reload", timeout=5)
                except Exception:
                    pass
        return {"status": "ok", "schedule": schedule}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/schedule/next-runs")
def get_next_runs():
    """Calculate next run times for each service."""
    from datetime import timedelta
    schedule = _load_schedule()
    now = datetime.utcnow()
    result = {}
    for key, cfg in schedule.items():
        if not cfg.get("enabled"):
            result[key] = {"enabled": False, "next_run": None}
            continue
        mode = cfg.get("mode", "manual")
        if mode == "manual":
            result[key] = {"enabled": True, "mode": "manual", "next_run": None, "label": "Sadece manuel"}
        elif mode == "daily":
            h, m = cfg.get("hour", 2), cfg.get("minute", 0)
            today_next = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if today_next <= now:
                today_next += timedelta(days=1)
            result[key] = {"enabled": True, "mode": "daily", "next_run": today_next.isoformat(), "label": f"Her gun {h:02d}:{m:02d}"}
        elif mode == "hourly":
            mins = cfg.get("interval_minutes", 60)
            next_t = now + timedelta(minutes=mins)
            if mins >= 60:
                hrs = mins // 60
                rem = mins % 60
                label = f"Her {hrs}sa {rem}dk" if rem > 0 else f"Her {hrs} saatte"
            else:
                label = f"Her {mins} dk"
            result[key] = {"enabled": True, "mode": "hourly", "next_run": next_t.isoformat(), "label": label, "interval_minutes": mins}
        elif mode == "interval":
            mins = cfg.get("interval_minutes", 60)
            next_t = now + timedelta(minutes=mins)
            if mins >= 60:
                hrs = mins // 60
                rem = mins % 60
                label = f"Her {hrs}sa {rem}dk" if rem > 0 else f"Her {hrs} saatte"
            else:
                label = f"Her {mins} dk"
            result[key] = {"enabled": True, "mode": "interval", "next_run": next_t.isoformat(), "label": label, "interval_minutes": mins}
        else:
            result[key] = {"enabled": False, "next_run": None}
    return {"next_runs": result}


@app.get("/api/fund-holdings")
def get_fund_holdings():
    """Reverse lookup: which funds have the highest stock allocation"""
    import sqlite3 as _sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'finance.db')
    db = _sqlite3.connect(db_path)
    db.row_factory = _sqlite3.Row
    c = db.cursor()
    
    # Get funds with stock allocation, joined with fund info
    c.execute("""
        SELECT a.code, f.title, f.kind, f.category, f.fund_group,
               a.stock as stock_pct, f.current_price, f.market_cap, 
               f.investor_count, f.price_count
        FROM tefas_fund_allocations a
        JOIN tefas_funds f ON f.code = a.code
        WHERE a.stock > 0
        ORDER BY a.stock DESC
    """)
    funds = [dict(r) for r in c.fetchall()]
    
    # Summary stats
    c.execute("SELECT COUNT(*) FROM tefas_fund_allocations WHERE stock > 100")
    leveraged = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tefas_fund_allocations WHERE stock > 50 AND stock <= 100")
    moderate = c.fetchone()[0]
    c.execute("SELECT AVG(stock) FROM tefas_fund_allocations WHERE stock > 0")
    avg_stock = c.fetchone()[0] or 0
    
    db.close()
    return {
        "funds": funds,
        "summary": {
            "total_with_stock": len(funds),
            "leveraged": leveraged,
            "moderate": moderate,
            "avg_stock_pct": round(avg_stock, 1)
        }
    }


@app.get("/api/fund-holdings/{fund_code}")
def get_fund_detail_holdings(fund_code: str):
    """Get allocation breakdown for a specific fund"""
    import sqlite3 as _sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'finance.db')
    db = _sqlite3.connect(db_path)
    db.row_factory = _sqlite3.Row
    c = db.cursor()
    fund_code = fund_code.upper()
    
    # Get fund info
    c.execute("SELECT * FROM tefas_funds WHERE code = ?", (fund_code,))
    fund = dict(c.fetchone()) if c.fetchone() else None
    if not fund:
        db.close()
        return {"found": False}
    
    # Get allocation breakdown
    c.execute("SELECT * FROM tefas_fund_allocations WHERE code = ?", (fund_code,))
    alloc_row = c.fetchone()
    allocation = {}
    if alloc_row:
        alloc_dict = dict(alloc_row)
        # Convert to list of {name, value} for chart
        allocation = {k: v for k, v in alloc_dict.items() 
                     if v is not None and v != 0 and k not in ('id', 'fund_id', 'code', 'trade_date', 'created_at')}
    
    # Get price history
    c.execute("""
        SELECT trade_date, price, market_cap, investors_count
        FROM tefas_fund_prices
        WHERE code = ? ORDER BY trade_date DESC LIMIT 90
    """, (fund_code,))
    prices = [dict(r) for r in c.fetchall()]
    
    db.close()
    return {"found": True, "fund": fund, "allocation": allocation, "prices": prices}


# ══════════════════════════════════════════════════════════════════════════════
# TECHNICAL ANALYSIS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/technical/{ticker}")
def get_technical(ticker: str, period: str = "3mo"):
    """Teknik analiz: RSI, MACD, Bollinger, Supertrend, Pivot."""
    from services.admin_dashboard.technical_analysis import get_technical_analysis
    return get_technical_analysis(ticker.upper(), period)


@app.get("/api/screener/{preset}")
def run_screener(preset: str):
    """Stock screener: oversold, bullish_momentum, etc."""
    from services.admin_dashboard.technical_analysis import scan_stocks_by_condition, SCANNER_PRESETS
    if preset not in SCANNER_PRESETS:
        raise HTTPException(404, f"Preset '{preset}' bulunamadi. Mevcut: {list(SCANNER_PRESETS.keys())}")
    
    # Get top BIST tickers (largest by market cap for speed)
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'finance.db')
    db = sqlite3.connect(db_path)
    c = db.cursor()
    c.execute('SELECT ticker FROM bist_stock_prices WHERE ticker IS NOT NULL AND market_cap IS NOT NULL ORDER BY market_cap DESC LIMIT 50')
    tickers = [r[0] for r in c.fetchall()]
    db.close()
    
    preset_config = SCANNER_PRESETS[preset]
    results = scan_stocks_by_condition(tickers, preset_config['condition'], preset)
    return {
        'preset': preset,
        'name': preset_config['name'],
        'results': results,
        'count': len(results),
        'scanned': min(len(tickers), 100),
        'timestamp': datetime.now().isoformat(),
    }


@app.get("/api/screener/presets")
def list_screener_presets():
    """List available screener presets."""
    from services.admin_dashboard.technical_analysis import SCANNER_PRESETS
    return {
        k: {'name': v['name'], 'category': v['category']}
        for k, v in SCANNER_PRESETS.items()
    }


# ══════════════════════════════════════════════════════════════════════════════
# TCMB EVDS & MACRO DATA ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/macro/inflation")
def get_inflation(type: str = "tufe", limit: int = 24):
    """TCMB enflasyon verileri: tufe veya ufe."""
    from services.admin_dashboard.macro_data import get_tcmb_inflation
    return get_tcmb_inflation(type, limit)


@app.get("/api/macro/calendar")
def get_calendar(countries: str = "TR,US,EU", period: str = "this_week"):
    """Ekonomik takvim: doviz.com."""
    from services.admin_dashboard.macro_data import get_economic_calendar
    country_list = [c.strip() for c in countries.split(',')]
    return get_economic_calendar(country_list, period)


@app.get("/api/macro/fx")
def get_fx():
    """Doviz kurlari."""
    from services.admin_dashboard.macro_data import get_fx_rates
    return get_fx_rates()


@app.get("/api/macro/bonds")
def get_bonds():
    """Devlet tahvil faizleri."""
    from services.admin_dashboard.macro_data import get_bond_yields
    return get_bond_yields()


# ══════════════════════════════════════════════════════════════════════════════
# ADVANCED ANALYSIS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/buffett/{ticker}")
def get_buffett(ticker: str):
    """Buffett degerleme: Owner Earnings, DCF, Safety Margin."""
    from services.admin_dashboard.advanced_analysis import buffett_analysis
    return buffett_analysis(ticker.upper())


@app.get("/api/sector-comparison/{ticker}")
def get_sector_comp(ticker: str):
    """Sektor karsilastirmasi."""
    from services.admin_dashboard.advanced_analysis import sector_comparison
    return sector_comparison(ticker.upper())


@app.get("/api/analyst/{ticker}")
def get_analyst(ticker: str):
    """Analist derecelendirmeleri + kazanç takvimi."""
    from services.admin_dashboard.advanced_analysis import analyst_data
    return analyst_data(ticker.upper())


@app.get("/api/technical-extended/{ticker}")
def get_extended_tech(ticker: str, period: str = "3mo"):
    """Genisletilmis teknik analiz: ADX, Stochastic, Ichimoku, VWMA, Aroon, CCI."""
    from services.admin_dashboard.advanced_analysis import extended_indicators
    return extended_indicators(ticker.upper(), period)


@app.get("/api/us-stock/{ticker}")
def get_us_stock(ticker: str):
    """ABD hisse analizi (NYSE/NASDAQ)."""
    from services.admin_dashboard.advanced_analysis import us_stock_analysis
    return us_stock_analysis(ticker.upper())


# ══════════════════════════════════════════════════════════════════════════════
# DATA EXPORT API — Diger web uygulamalari icin REST endpointler
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/export/companies")
def export_companies():
    """Tum sirketlerin listesi."""
    db = SessionLocal()
    try:
        rows = db.query(KapCompany).all()
        return [{
            "id": r.id, "ticker": r.ticker, "company_name": r.company_name,
            "sector": r.sector, "market": r.market,
        } for r in rows]
    finally:
        db.close()


@app.get("/api/export/financials/{ticker}")
def export_financials(ticker: str):
    """Belirli bir sirketin finansal verileri (tum donemler)."""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        comp = db.execute(text('SELECT id, company_name FROM kap_companies WHERE ticker = :t'), {'t': ticker.upper()}).fetchone()
        if not comp:
            raise HTTPException(404, f"{ticker} bulunamadi")
        rows = db.execute(text('SELECT * FROM kap_financials WHERE company_id = :cid ORDER BY year DESC, period DESC'), {'cid': comp[0]}).fetchall()
        return {
            "ticker": ticker.upper(), "company_name": comp[1],
            "financials": [dict(r._mapping) for r in rows]
        }
    finally:
        db.close()


@app.get("/api/export/all/{ticker}")
def export_all(ticker: str):
    """Bir varligin TUM verileri tek JSON'da: finansal, bildirim, ortaklar, yonetim."""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        comp = db.execute(text('SELECT * FROM kap_companies WHERE ticker = :t'), {'t': ticker.upper()}).fetchone()
        if not comp:
            raise HTTPException(404, f"{ticker} bulunamadi")
        cid = comp[0]  # id
        fins = db.execute(text('SELECT * FROM kap_financials WHERE company_id = :cid ORDER BY year DESC, period DESC'), {'cid': cid}).fetchall()
        discs = db.execute(text('SELECT * FROM kap_disclosures WHERE company_id = :cid ORDER BY publish_date DESC LIMIT 50'), {'cid': cid}).fetchall()
        sh = db.execute(text('SELECT * FROM kap_shareholders WHERE company_id = :cid'), {'cid': cid}).fetchall()
        mgmt = db.execute(text('SELECT * FROM kap_management WHERE company_id = :cid'), {'cid': cid}).fetchall()
        subs = db.execute(text('SELECT * FROM kap_subsidiaries WHERE company_id = :cid'), {'cid': cid}).fetchall()
        cf = db.execute(text('SELECT * FROM kap_cashflows WHERE company_id = :cid ORDER BY year DESC'), {'cid': cid}).fetchall()
        return {
            "ticker": ticker.upper(),
            "company": dict(comp._mapping),
            "financials": [dict(r._mapping) for r in fins],
            "disclosures": [dict(r._mapping) for r in discs],
            "shareholders": [dict(r._mapping) for r in sh],
            "management": [dict(r._mapping) for r in mgmt],
            "subsidiaries": [dict(r._mapping) for r in subs],
            "cashflows": [dict(r._mapping) for r in cf],
        }
    finally:
        db.close()


@app.get("/api/export/csv/{table}")
def export_csv(table: str):
    """Tabloyu CSV olarak indir."""
    import csv, io as csvio
    ALLOWED = ['kap_companies', 'kap_financials', 'kap_disclosures', 'kap_shareholders',
               'kap_management', 'kap_subsidiaries', 'kap_cashflows', 'tefas_funds',
               'bist_stock_prices', 'bist_price_history', 'share_buybacks', 'ipo_data']
    if table not in ALLOWED:
        raise HTTPException(400, f"Izin verilen tablolar: {ALLOWED}")
    
    db = SessionLocal()
    try:
        from sqlalchemy import text
        result = db.execute(text(f'SELECT * FROM {table}'))
        rows = result.fetchall()
        cols = result.keys()
        
        output = csvio.StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([str(v) if v is not None else '' for v in row])
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename={table}.csv'}
        )
    finally:
        db.close()


# Tablo kisa isim -> tam isim mapping
TABLE_SHORT_TO_FULL = {
    'companies': 'kap_companies', 'financials': 'kap_financials',
    'disclosures': 'kap_disclosures', 'disclosure_details': 'kap_disclosure_details',
    'shareholders': 'kap_shareholders', 'management': 'kap_management',
    'subsidiaries': 'kap_subsidiaries', 'cashflows': 'kap_cashflows',
    'financial_notes': 'kap_financial_notes', 'portfolio_reports': 'kap_portfolio_reports',
    'corporate_actions': 'kap_corporate_actions',
    'buybacks': 'share_buybacks', 'ipo': 'ipo_data',
    'funds': 'tefas_funds', 'fund_prices': 'tefas_fund_prices',
    'fund_allocations': 'tefas_fund_allocations', 'fund_announcements': 'tefas_announcements',
    'prices': 'bist_stock_prices', 'price_history': 'bist_price_history',
    'settlement': 'settlement_data', 'index': 'index_constituents',
    'vap': 'vap_data', 'pipeline_runs': 'pipeline_runs',
}
ALL_TABLES = 'companies,financials,disclosures,shareholders,management,subsidiaries,cashflows,buybacks,ipo,funds,fund_prices,fund_allocations,prices,price_history,settlement,index'

@app.get("/api/export/bulk")
def export_bulk(tables: str = ALL_TABLES, limit_per_table: int = 0):
    """Tek istekte TÜM tabloların verileri (toplu export).
    tables: virgülle ayrılmış tablo listesi (kisa veya tam isim).
    limit_per_table: 0=sınırsız, >0=her tabloda maks satır.
    """
    db = SessionLocal()
    try:
        from sqlalchemy import text
        
        table_list = [t.strip() for t in tables.split(',')]
        result = {}
        
        for tbl in table_list:
            full_name = TABLE_SHORT_TO_FULL.get(tbl, tbl)
            limit_clause = f" LIMIT {limit_per_table}" if limit_per_table > 0 else ""
            try:
                rows = db.execute(text(f'SELECT * FROM {full_name}{limit_clause}')).fetchall()
                result[tbl] = [dict(r._mapping) for r in rows]
            except Exception as e:
                result[tbl] = {"error": str(e)[:200]}
        
        # Metadata
        result["_meta"] = {
            "tables_requested": table_list,
            "tables_returned": [t for t in table_list if isinstance(result.get(t), list)],
            "row_counts": {t: len(result[t]) if isinstance(result.get(t), list) else 0 for t in table_list},
            "total_rows": sum(len(result[t]) for t in table_list if isinstance(result.get(t), list))
        }
        return result
    finally:
        db.close()


@app.get("/api/export/bulk/csv")
def export_bulk_csv(tables: str = "companies,financials,shareholders,management,subsidiaries,cashflows"):
    """Tek zip'te tüm tabloların CSV'leri."""
    import csv, io as csvio, zipfile
    ALLOWED = ['kap_companies', 'kap_financials', 'kap_disclosures', 'kap_shareholders',
               'kap_management', 'kap_subsidiaries', 'kap_cashflows', 'tefas_funds',
               'tefas_fund_prices', 'tefas_fund_allocations', 'bist_stock_prices',
               'bist_price_history', 'share_buybacks', 'ipo_data', 'settlement_data']
    
    # Kısa isim -> tam tablo adı mapping
    SHORT_TO_FULL = {
        'companies': 'kap_companies', 'financials': 'kap_financials',
        'disclosures': 'kap_disclosures', 'shareholders': 'kap_shareholders',
        'management': 'kap_management', 'subsidiaries': 'kap_subsidiaries',
        'cashflows': 'kap_cashflows', 'funds': 'tefas_funds',
        'fund_prices': 'tefas_fund_prices', 'fund_allocations': 'tefas_fund_allocations',
        'prices': 'bist_stock_prices', 'price_history': 'bist_price_history',
        'buybacks': 'share_buybacks', 'ipo': 'ipo_data', 'settlement': 'settlement_data'
    }
    
    table_list = [t.strip() for t in tables.split(',')]
    full_tables = [SHORT_TO_FULL.get(t, t) for t in table_list]
    
    db = SessionLocal()
    try:
        from sqlalchemy import text
        from fastapi.responses import StreamingResponse
        
        zip_buffer = csvio.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for tbl in full_tables:
                if tbl not in ALLOWED:
                    continue
                try:
                    result = db.execute(text(f'SELECT * FROM {tbl}'))
                    rows = result.fetchall()
                    cols = result.keys()
                    
                    output = csvio.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(cols)
                    for row in rows:
                        writer.writerow([str(v) if v is not None else '' for v in row])
                    
                    zf.writestr(f'{tbl}.csv', output.getvalue())
                except Exception as e:
                    zf.writestr(f'{tbl}_error.txt', str(e))
        
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename=finance_pipeline_export.zip'}
        )
    finally:
        db.close()


@app.get("/api/export/search")
def export_search(q: str, limit: int = 20):
    """Ticker veya sirket adinda arama."""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        rows = db.execute(text('SELECT ticker, company_name, sector, market FROM kap_companies WHERE ticker ILIKE :q OR company_name ILIKE :q LIMIT :l'), {'q': f'%{q}%', 'l': limit}).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.get("/api/export/funds")
def export_funds(limit: int = 100):
    """TEFAS fon listesi."""
    db = SessionLocal()
    try:
        rows = db.query(TefasFund).order_by(TefasFund.code).limit(limit).all()
        return [{
            "code": r.code, "title": r.title, "kind": r.kind,
            "current_price": r.current_price, "market_cap": r.market_cap,
            "investor_count": r.investor_count,
        } for r in rows]
    finally:
        db.close()


@app.get("/api/export/fund/{code}")
def export_fund_detail(code: str):
    """TEFAS fon detayi + fiyat gecmisi."""
    db = SessionLocal()
    try:
        fund = db.query(TefasFund).filter(TefasFund.code == code.upper()).first()
        if not fund:
            raise HTTPException(404, f"Fon {code} bulunamadi")
        prices = db.query(TefasFundPrice).filter(TefasFundPrice.fund_id == fund.id).order_by(TefasFundPrice.trade_date).all()
        return {
            "code": fund.code, "title": fund.title, "kind": fund.kind,
            "current_price": fund.current_price, "market_cap": fund.market_cap,
            "investor_count": fund.investor_count,
            "price_history": [{
                "date": p.trade_date.isoformat() if p.trade_date else None,
                "price": p.price, "market_cap": p.market_cap,
                "investors_count": p.investors_count,
            } for p in prices],
        }
    finally:
        db.close()


@app.get("/api/export/apikeys")
def get_api_keys():
    """Mevcut API key'leri goster (dashboard icin). Sadece dashboard UI'dan erisebilir."""
    return {
        "primary_key": API_KEY,
        "alt_key": API_KEY_ALT,
        "usage": {
            "header": "X-API-Key: <key>",
            "bearer": "Authorization: Bearer <key>",
            "query": "?api_key=<key>",
        },
        "note": "Bu key'leri guvenli yerde saklayin. Diger uygulamalara verin.",
    }


@app.get("/api/export/schema")
def export_schema():
    """Veritabani shema bilgisi — platformun ne cekebilecegini gosterir."""
    db = SessionLocal()
    try:
        from sqlalchemy import text, inspect
        insp = inspect(engine)
        tables = {}
        for tbl in insp.get_table_names():
            cols = insp.get_columns(tbl)
            tables[tbl] = [
                {"name": c['name'], "type": str(c['type'])} for c in cols
            ]
        return {"tables": tables, "total_tables": len(tables)}
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=3000)
