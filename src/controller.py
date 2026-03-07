import os
import time
import json
import random
import threading

from monitor import run_monitor
from injector import create_payload, run_exfiltration

# CONSTANTS -> Experiment Settings
DURATION_HOURS = 6
SAMPLING_INTERVAL_SECONDS = 1.0

# Random idle duration between anomalies
IDLE_MIN_SECONDS = 180
IDLE_MAX_SECONDS = 480

# Random anomaly duration window
ANOMALY_MIN_SECONDS = 60
ANOMALY_MAX_SECONDS = 240

# Host & Port of malicous receiver
RECEIVER_HOST = "192.168.1.40"
RECEIVER_PORT = 5001

# Target outbound throughput
EXFIL_RATE_MBPS = 30.0

# Size of payload file used to generate disk reads
PAYLOAD_SIZE_MB = 4096

# TCP send chunk size
TCP_CHUNK_MB = 4

DATA_DIR = "data"
UNPROCESSED_DIR = os.path.join(DATA_DIR, "collected")
LOGS_DIR = "logs"


def build_schedule(total_duration):
    # Build a randomized schedule of idle & anomaly periods

    schedule = []
    elapsed = 0

    while elapsed < total_duration:

        idle_duration = random.randint(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
        if elapsed + idle_duration > total_duration:
            idle_duration = total_duration - elapsed
        schedule.append({"type": "idle", "duration_s": idle_duration})
        elapsed = elapsed + idle_duration

        if elapsed >= total_duration:
            break

        anomaly_duration = random.randint(ANOMALY_MIN_SECONDS, ANOMALY_MAX_SECONDS)
        if elapsed + anomaly_duration > total_duration:
            anomaly_duration = total_duration - elapsed
        schedule.append({"type": "exfiltration_tcp_vm", "duration_s": anomaly_duration})
        elapsed = elapsed + anomaly_duration

    return schedule


def run_experiment():

    run_id = time.strftime("%Y%m%d_%H%M%S")
    total_duration = int(DURATION_HOURS * 3600)

    csv_path = "data/dataset/monitoring_" + run_id + ".csv"
    log_path = "data/log/injection_log_" + run_id + ".json"

    print("[CONTROLLER] run_id=" + run_id)
    print("[CONTROLLER] receiver=" + RECEIVER_HOST + ":" + str(RECEIVER_PORT))

    # Build the random schedule
    schedule = build_schedule(total_duration)

    # Start monitor in a separate thread
    monitor_thread = threading.Thread(
        target=run_monitor,
        args=(csv_path, total_duration, SAMPLING_INTERVAL_SECONDS),
        daemon=False,
    )
    monitor_thread.start()

    # Allow monitor to initialize & start writing rows
    time.sleep(2)

    # Prepare payload file
    payload_path = create_payload(PAYLOAD_SIZE_MB)

    injections = []

    # Execute scheduled events
    for event in schedule:
        if event["type"] == "idle":
            time.sleep(event["duration_s"])
            continue

        entry = run_exfiltration(
            total_duration=event["duration_s"],
            rate_mbs=EXFIL_RATE_MBPS,
            payload_path=payload_path,
            host=RECEIVER_HOST,
            port=RECEIVER_PORT,
            chunk_mb=TCP_CHUNK_MB,
        )
        injections.append(entry)

    # Join monitoring thread
    monitor_thread.join()

    # Persist injection log to JSON
    file = open(log_path, "w", encoding="utf-8")
    try:
        json.dump({"run_id": run_id, "injections": injections}, file, indent=2)
    finally:
        file.close()

    print("[CONTROLLER] Finished experiment. Run ID: " + run_id)
    return run_id


if __name__ == "__main__":
    run_experiment()
