import csv
import json


def is_anomaly(time, windows):
    # Given the timestamp of a row, and a list of anomaly windows
    # determine if the row falls within
    for window in windows:
        start = window[0]
        end = window[1]

        if time >= start and time <= end:
            return 1

    return 0


def label_csv(csv_path, log_path, labeled_path):

    # Load JSON log to enable labeling of CSV rows based on anomaly windows
    file = open(log_path, "r", encoding="utf-8")
    try:
        log = json.load(file)
    finally:
        file.close()

    # Build windows
    windows = []
    for injection in log["injections"]:
        injection_start = injection["start_ts_unix"]
        injection_end = injection["end_ts_unix"]
        windows.append((injection_start, injection_end))

    # Read original collected CSV
    file = open(csv_path, "r", newline="", encoding="utf-8")
    try:
        reader = csv.DictReader(file)

        # Obtain original CSV headers & add new label column
        fieldnames = []
        if reader.fieldnames is not None:
            for name in reader.fieldnames:
                fieldnames.append(name)

        if "label" not in fieldnames:
            fieldnames.append("label")

        # Write new labeled CSV
        file_out = open(labeled_path, "w", newline="", encoding="utf-8")

        try:
            writer = csv.DictWriter(file_out, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                time = float(row["ts_unix"])

                label = is_anomaly(time, windows)
                row["label"] = str(label)

                writer.writerow(row)
        finally:
            file_out.close()
    finally:
        file.close()

    print("[LABELER] Done.")


if __name__ == "__main__":

    run_id = "20260308_124042"

    csv_path = "data/dataset/monitoring_" + run_id + ".csv"
    log_path = "data/log/injection_log_" + run_id + ".json"
    labeled_path = "data/labeled/labeled_" + run_id + ".csv"

    label_csv(csv_path, log_path, labeled_path)
