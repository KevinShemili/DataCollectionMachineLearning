import time
import json
import random
import threading

from monitor import run_monitor
from injector import create_payload_pool, run_exfiltration

DURATION_HOURS = 0.1  # total runtime
SAMPLING_INTERVAL_SECONDS = 1.0  # 1 HZ sampling rate
IDLE_MIN_SECONDS = 180  # minimum normal duration - 3 min
IDLE_MAX_SECONDS = 480  # maximum normal duration - 8 min
ANOMALY_MIN_SECONDS = 60  # minimum anomaly duration - 1 min
ANOMALY_MAX_SECONDS = 240  # maximum anomaly duration - 4 min
RECEIVER_HOST = "172.20.10.7"  # ip address of VM
RECEIVER_PORT = 5001  # port number of VM
EXFIL_RATE_MBPS = 40.0  # outbound throughput traget
PAYLOAD_SIZE_MB = 800  # size of trash payloads
PAYLOAD_COUNT = 5  # nummber of payloads


def build_schedule(total_duration):
    # Build a randomized schedule of idle & anomaly periods

    schedule = []
    filled_schedule = 0

    while filled_schedule < total_duration:

        # Generate a random idle duration & add it to schedule
        idle_duration = random.randint(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)

        if filled_schedule + idle_duration > total_duration:
            idle_duration = total_duration - filled_schedule
        schedule.append({"type": "idle", "duration": idle_duration})
        filled_schedule = filled_schedule + idle_duration

        if filled_schedule >= total_duration:
            break

        # Generate a random anomaly duration & add it to schedule
        anomaly_duration = random.randint(ANOMALY_MIN_SECONDS, ANOMALY_MAX_SECONDS)

        if filled_schedule + anomaly_duration > total_duration:
            anomaly_duration = total_duration - filled_schedule
        schedule.append({"type": "anomaly", "duration": anomaly_duration})
        filled_schedule = filled_schedule + anomaly_duration

    return schedule


def run_experiment():

    run_id = time.strftime("%Y%m%d_%H%M%S")
    total_duration = int(DURATION_HOURS * 3600)

    csv_path = "data/dataset/monitoring_" + run_id + ".csv"
    log_path = "data/log/injection_log_" + run_id + ".json"

    print("[CONTROLLER] RUN ID: " + run_id)

    # Build schedule
    schedule = build_schedule(total_duration)

    # Create monitor as a separate thread
    monitor_thread = threading.Thread(
        target=run_monitor,
        args=(csv_path, total_duration, SAMPLING_INTERVAL_SECONDS),
        daemon=False,
    )

    # Write out the trash payload files before monitoring starts,
    # this ensures monitor won't capture payload generation disk writes
    payload_paths = create_payload_pool(PAYLOAD_SIZE_MB, PAYLOAD_COUNT)

    # Start actual monitor thread
    monitor_thread.start()

    # Allow monitor to initialize & start writing rows
    time.sleep(2)

    injections = []

    # Execute scheduled events
    for event in schedule:

        # Sleep if event is idle system
        if event["type"] == "idle":
            time.sleep(event["duration"])
            continue

        # Inject if event is injection
        entry = run_exfiltration(
            total_duration=event["duration"],
            rate_mbs=EXFIL_RATE_MBPS,
            payload_paths=payload_paths,
            host=RECEIVER_HOST,
            port=RECEIVER_PORT,
        )
        injections.append(entry)

    # After scheduling has completed,
    # join monitoring thread
    monitor_thread.join()

    # Persist injection log to JSON, to enable labeling
    file = open(log_path, "w", encoding="utf-8")
    try:
        json.dump({"run_id": run_id, "injections": injections}, file, indent=2)
    finally:
        file.close()

    print("[CONTROLLER] Finished experiment. Run ID: " + run_id)
    return run_id


if __name__ == "__main__":
    run_experiment()
