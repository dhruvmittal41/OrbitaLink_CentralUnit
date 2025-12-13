#!/usr/bin/env python3
"""
run_all.py — Master controller for Central Unit.
Manages continuous, one-time, and scheduled Python scripts using APScheduler.
"""

import subprocess
import time
import logging
import os
import signal
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# ==========================
# CONFIGURATION
# ==========================
PYTHON_PATH = r"D:\Central_Unit\venv\Scripts\python.exe"
BASE_DIR = r"D:\Central_Unit"
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "run_all.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ==========================
# SCRIPTS
# ==========================

# Continuous (keep alive)
SERVICES = {
    "server": "Server.py",
    "fu_registry": "Fu_Registry.py",
}

# Run once on startup
ONE_TIME_SCRIPTS = [
    "Fetch_TLE.py",
    "Fetch_Sat_Name.py",
    "Scheduler.py",  # This one runs once — not a scheduler anymore
]

# ==========================
# Helper Functions
# ==========================


def start_service(name, script):
    """Start a long-running Python service."""
    try:
        log_path = os.path.join(LOG_DIR, f"{name}.log")
        err_path = os.path.join(LOG_DIR, f"{name}.err")
        logging.info(f"Starting service: {name}")
        process = subprocess.Popen(
            # <-- added -u here
            [PYTHON_PATH, "-u", os.path.join(BASE_DIR, script)],
            stdout=open(log_path, "a"),
            stderr=open(err_path, "a"),
        )
        return process
    except Exception as e:
        logging.error(f"Failed to start service {name}: {e}")
        return None


def run_once(script):
    """Run a Python script once and wait for it to finish."""
    try:
        logging.info(f"Running one-time script: {script}")
        subprocess.run(
            [PYTHON_PATH, os.path.join(BASE_DIR, script)], check=True)
        logging.info(f"Script finished: {script}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Script {script} failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected error running {script}: {e}")


def monitor_services(processes):
    """Continuously monitor running services."""
    for name, process in list(processes.items()):
        if process.poll() is not None:  # process exited
            logging.warning(f"Service {name} crashed. Restarting...")
            processes[name] = start_service(name, SERVICES[name])


# ==========================
# APScheduler Jobs
# ==========================

def run_assigner():
    """Job: Run Assigner.py every 10 minutes."""
    logging.info("🔁 Running scheduled job: Assigner.py")
    try:
        subprocess.run([PYTHON_PATH, os.path.join(
            BASE_DIR, "Assigner.py")], check=True)
        logging.info("✅ Completed scheduled run: Assigner.py")
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Assigner.py failed: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error running Assigner.py: {e}")


# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    logging.info("=== Master Controller started ===")

    # Step 1: Start continuous services
    processes = {}
    for name, script in SERVICES.items():
        processes[name] = start_service(name, script)

    # Step 2: Run one-time scripts
    for script in ONE_TIME_SCRIPTS:
        run_once(script)

    # Step 3: Start APScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_assigner, "interval", minutes=10,
                      next_run_time=datetime.now())
    scheduler.start()
    logging.info("✅ APScheduler started (Assigner runs every 10 mins)")

    # Step 4: Monitor and manage everything
    try:
        while True:
            monitor_services(processes)
            time.sleep(10)
    except KeyboardInterrupt:
        logging.info("Shutdown requested, stopping services and scheduler...")
        scheduler.shutdown(wait=False)
        for p in processes.values():
            if p:
                try:
                    os.kill(p.pid, signal.SIGTERM)
                except Exception:
                    pass
        logging.info("All services stopped gracefully.")
