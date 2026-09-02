"""Quick KAP Pipeline Test — 10 companies only"""
import os
import sys
import logging

os.environ.setdefault("DATABASE_URL", "sqlite:///finance.db")
os.environ.setdefault("KAP_DB_URL", "sqlite:///kap.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "kap-pipeline"))

from database import init_db
init_db()

print("\n=== KAP Pipeline — Quick Test (10 companies) ===\n")

from pipeline import run_full_pipeline

results = run_full_pipeline(
    limit_companies=10,
    skip_modules=["module12_notes"],  # Skip notes for speed
)

print("\n=== RESULTS ===")
for module, count in results.items():
    print(f"  {module}: {count} records")
print("\nDone!")
