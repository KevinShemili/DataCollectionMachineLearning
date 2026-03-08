import csv
import time
import psutil
from datetime import datetime, timezone
from tqdm import tqdm


def collect_sample(state):
    sample_start_time = time.time()

    # 1. Disk Metrics
    disk_io = psutil.disk_io_counters()
    disk_usage = psutil.disk_usage("C:\\")

    # 2. Network Metrics
    net_io = psutil.net_io_counters()

    # Disk & network are lifetime counters, so
    # we convert manually into per-second rates following the formula:
    # rate = (current_value - previous_value) / (sample_start_time - previous_time)
    # Source: https://psutil.readthedocs.io/en/latest/#psutil.net_io_counters
    if (
        state["prev_time"] is None
    ):  # Means this is first sample, so no previous state exists
        disk_read_bps = 0.0
        disk_write_bps = 0.0
        disk_read_ops = 0.0
        disk_write_ops = 0.0
        net_sent_bps = 0.0
        net_recv_bps = 0.0
        net_sent_pps = 0.0
        net_recv_pps = 0.0
    else:
        time_between_samples = sample_start_time - state["prev_time"]

        disk_read_bps = (disk_io.read_bytes - state["prev_disk"].read_bytes) / time_between_samples  # type: ignore
        disk_write_bps = (disk_io.write_bytes - state["prev_disk"].write_bytes) / time_between_samples  # type: ignore
        disk_read_ops = (disk_io.read_count - state["prev_disk"].read_count) / time_between_samples  # type: ignore
        disk_write_ops = (disk_io.write_count - state["prev_disk"].write_count) / time_between_samples  # type: ignore

        net_sent_bps = (
            net_io.bytes_sent - state["prev_net"].bytes_sent
        ) / time_between_samples
        net_recv_bps = (
            net_io.bytes_recv - state["prev_net"].bytes_recv
        ) / time_between_samples
        net_sent_pps = (
            net_io.packets_sent - state["prev_net"].packets_sent
        ) / time_between_samples
        net_recv_pps = (
            net_io.packets_recv - state["prev_net"].packets_recv
        ) / time_between_samples

    # Set the fields for the next iteration
    state["prev_time"] = sample_start_time
    state["prev_disk"] = disk_io
    state["prev_net"] = net_io

    return {
        # Timestamp
        "ts_unix": sample_start_time,
        # Disk
        "disk_read_bytes_per_s": disk_read_bps,
        "disk_write_bytes_per_s": disk_write_bps,
        "disk_read_ops_per_s": disk_read_ops,
        "disk_write_ops_per_s": disk_write_ops,
        "disk_usage_percent_c": disk_usage.percent,
        # Network
        "net_bytes_sent_per_s": net_sent_bps,
        "net_bytes_recv_per_s": net_recv_bps,
        "net_packets_sent_per_s": net_sent_pps,
        "net_packets_recv_per_s": net_recv_pps,
    }


def run_monitor(output_path, total_duration, sampling_interval):

    print(
        f"[MONITOR] Started. Total Duration: {total_duration}s, with sampling interval: {sampling_interval}s."
    )

    state = {"prev_time": None, "prev_disk": None, "prev_net": None}

    monitor_start_time = time.time()
    next_sampling_deadline = monitor_start_time + sampling_interval

    with open(output_path, "w", newline="", encoding="utf-8") as f:

        # Init state & define CSV header
        first_sample = collect_sample(state)
        writer = csv.DictWriter(f, fieldnames=list(first_sample.keys()))
        writer.writeheader()
        writer.writerow(first_sample)
        f.flush()
        samples = 1

        # Update progress bar
        progress_bar = tqdm(
            total=total_duration, desc="Monitoring", unit="s", dynamic_ncols=True
        )
        last_second = 0

        while True:
            sample_start_time = time.time()
            if sample_start_time - monitor_start_time >= total_duration:
                break

            # Address drift issue, by sleeping only necessary time until next deadline
            sleep_for = next_sampling_deadline - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)

            # Collect & persist next sample
            row = collect_sample(state)
            writer.writerow(row)
            f.flush()
            samples += 1

            # Update progress bar
            current_second = int(time.time() - monitor_start_time)
            delta = current_second - last_second
            if delta > 0:
                progress_bar.update(delta)
                last_second = current_second

            next_sampling_deadline += sampling_interval

        progress_bar.close()

    print(f"[MONITOR] Completed. Samples collected: {samples}.")
