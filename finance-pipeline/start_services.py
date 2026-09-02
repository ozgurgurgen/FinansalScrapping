"""Start all finance-pipeline services in background."""
import subprocess
import os
import time
import sys

os.environ['DATABASE_URL'] = 'sqlite:///finance.db'
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Kill ALL existing service processes on our ports
import socket
for port in [8001, 8002, 8003, 3000]:
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                pid = line.strip().split()[-1]
                subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    except: pass
time.sleep(2)

# Clear Python cache
import shutil
for d in ['services/kap_worker/__pycache__', 'services/tefas_worker/__pycache__', 'services/__pycache__']:
    if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)

services = [
    ('TEFAS Worker',       ['python', '-m', 'uvicorn', 'services.tefas_worker.main:app',       '--host', '0.0.0.0', '--port', '8001']),
    ('KAP Worker',         ['python', '-m', 'uvicorn', 'services.kap_worker.main:app',          '--host', '0.0.0.0', '--port', '8002']),
    ('Market Data Worker', ['python', '-m', 'uvicorn', 'services.market_data_worker.main:app',  '--host', '0.0.0.0', '--port', '8003']),
    ('Admin Dashboard',    ['python', '-m', 'uvicorn', 'services.admin_dashboard.main:app',     '--host', '0.0.0.0', '--port', '3000']),
]

procs = []
for name, cmd in services:
    p = subprocess.Popen(cmd, env=os.environ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)  # CREATE_NO_WINDOW
    procs.append((name, p))
    print(f'{name}: PID {p.pid}')
    time.sleep(2)

print('\nAll services started. Waiting for readiness...')
time.sleep(5)

# Quick health check
import urllib.request
ports = [8001, 8002, 8003, 3000]
for i, (name, p) in enumerate(procs):
    port = ports[i]
    try:
        url = f'http://localhost:{port}/health' if port != 3000 else f'http://localhost:{port}/'
        req = urllib.request.urlopen(url, timeout=3)
        print(f'  {name}: OK')
    except Exception as e:
        print(f'  {name}: FAIL ({e})')

# Write PIDs for later cleanup
with open('service_pids.txt', 'w') as f:
    for name, p in procs:
        f.write(f'{name}={p.pid}\n')
print('\nPID file written to service_pids.txt')
