import csv
import time
import psutil
from datetime import datetime, timezone
from tqdm import tqdm


def collect_sample(state):
    current_time = time.time()

    # 1. CPU Metrics
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    cpu_percent = sum(per_core) / len(per_core)
    cpu_percent_max = max(per_core)
    cpu_percent_min = min(per_core)
    freq = psutil.cpu_freq()

    # 2. Memory Metrics
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # 3. Disk Metrics
    disk_io = psutil.disk_io_counters()
    disk_usage = psutil.disk_usage("C:\\")

    # 4. Network Metrics
    net_io = psutil.net_io_counters()

    # Wrt to disk & network, these are lifetime counters, so
    # we convert manually into per-second rates following this formula:
    # rate = (current_value - previous_value) / (current_time - previous_time)
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
        time_between_samples = current_time - state["prev_time"]

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

    state["prev_time"] = current_time
    state["prev_disk"] = disk_io
    state["prev_net"] = net_io

    return {
        "ts_iso_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ts_unix": current_time,
        "cpu_percent": cpu_percent,
        "cpu_percent_max": cpu_percent_max,
        "cpu_percent_min": cpu_percent_min,
        "cpu_frequency_mhz": freq.current,
        "cpu_count": psutil.cpu_count(),
        "memory_used": mem.used,
        "memory_available": mem.available,
        "memory_percent": mem.percent,
        "memory_total": mem.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
        "disk_read_bytes_per_s": disk_read_bps,
        "disk_write_bytes_per_s": disk_write_bps,
        "disk_read_ops_per_s": disk_read_ops,
        "disk_write_ops_per_s": disk_write_ops,
        "disk_usage_percent_c": disk_usage.percent,
        "net_bytes_sent_per_s": net_sent_bps,
        "net_bytes_recv_per_s": net_recv_bps,
        "net_packets_sent_per_s": net_sent_pps,
        "net_packets_recv_per_s": net_recv_pps,
    }


def run_monitor(output_path, total_duration, sampling_interval):

    print(
        f"[MONITOR] Started. Total Duration: {total_duration}s, with sampling interval: {sampling_interval}s."
    )

    # Warm-up call so first real cpu_percent() is not biased
    # Source: https://psutil.readthedocs.io/en/latest/#psutil.cpu_percent
    psutil.cpu_percent(interval=0.1, percpu=True)

    state = {"prev_time": None, "prev_disk": None, "prev_net": None}

    current_time = time.time()
    next_deadline = current_time + sampling_interval

    with open(output_path, "w", newline="", encoding="utf-8") as f:

        # Init state & define CSV header
        first = collect_sample(state)
        writer = csv.DictWriter(f, fieldnames=list(first.keys()))
        writer.writeheader()
        writer.writerow(first)
        f.flush()

        progress_bar = tqdm(
            total=total_duration, desc="Monitoring", unit="s", dynamic_ncols=True
        )
        last_second = 0
        samples = 1

        while True:
            sample_start_time = time.time()
            if sample_start_time - current_time >= total_duration:
                break

            # Address drift issue, by sleeping only necessary time until next deadline
            sleep_for = next_deadline - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)

            # Collect & persist next sample
            row = collect_sample(state)
            writer.writerow(row)
            f.flush()
            samples += 1

            # Update progress bar
            current_second = int(time.time() - current_time)
            delta = current_second - last_second
            if delta > 0:
                progress_bar.update(delta)
                last_second = current_second

            next_deadline += sampling_interval

        progress_bar.close()

    print(f"[MONITOR] Completed. Samples collected: {samples}.")
