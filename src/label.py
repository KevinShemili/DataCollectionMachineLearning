import csv
import json
from datetime import datetime, timezone


def parse_iso_time(time):
    parsed = datetime.fromisoformat(time)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.timestamp()


def is_anomaly(time, windows):

    for window in windows:
        start = window[0]
        end = window[1]

        if time >= start and time <= end:
            return 1

    return 0


def label_csv(csv_path, log_path, labeled_path):

    # Load injection metadata, which will help us with the
    # anomaly's start & end times
    file = open(log_path, "r", encoding="utf-8")
    try:
        log = json.load(file)
    finally:
        file.close()

    # Build list of anomaly time windows
    windows = []
    for injection in log.get("injections", []):
        start = parse_iso_time(injection["start_ts_iso_utc"])
        end = parse_iso_time(injection["end_ts_iso_utc"])
        windows.append((start, end))

    file = open(csv_path, "r", newline="", encoding="utf-8")
    try:
        reader = csv.DictReader(file)
        fieldnames = []

        if reader.fieldnames is not None:
            for name in reader.fieldnames:
                fieldnames.append(name)

        # Add new label column
        if "label" not in fieldnames:
            fieldnames.append("label")

        file_out = open(labeled_path, "w", newline="", encoding="utf-8")
        try:

            writer = csv.DictWriter(file_out, fieldnames=fieldnames)
            writer.writeheader()

            # Label rows
            for row in reader:
                time = float(row["ts_unix"])
                label = is_anomaly(time, windows)
                row["label"] = str(label)
                writer.writerow(row)
        finally:
            file_out.close()
    finally:
        file.close()

    print("[LABELER] Wrote labeled CSV: " + labeled_path)


if __name__ == "__main__":

    csv_path = "data/dataset/monitoring_20260307_173453.csv"
    log_path = "data/log/injection_log_20260307_173453.json"
    labeled_path = "data/labeled/labeled_20260307_173453.csv"

    label_csv(csv_path, log_path, labeled_path)
