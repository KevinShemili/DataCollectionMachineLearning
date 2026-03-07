import time
import csv
import psutil
from datetime import datetime

output_file = "telemetry_verify.csv"
duration = 120  # seconds to log
interval = 1  # sample every 1 second

prev_net = psutil.net_io_counters()
prev_disk = psutil.disk_io_counters()
prev_time = time.time()

with open(output_file, "w", newline="") as f:

    writer = csv.writer(f)
    writer.writerow(
        [
            "timestamp",
            "disk_read_MBps",
            "disk_write_MBps",
            "net_sent_MBps",
            "net_recv_MBps",
        ]
    )

    start = time.time()

    while True:

        time.sleep(interval)

        now = time.time()
        dt = now - prev_time

        net = psutil.net_io_counters()
        disk = psutil.disk_io_counters()

        disk_read = (disk.read_bytes - prev_disk.read_bytes) / dt
        disk_write = (disk.write_bytes - prev_disk.write_bytes) / dt
        net_sent = (net.bytes_sent - prev_net.bytes_sent) / dt
        net_recv = (net.bytes_recv - prev_net.bytes_recv) / dt

        writer.writerow(
            [
                datetime.utcnow().isoformat(),
                disk_read / (1024 * 1024),
                disk_write / (1024 * 1024),
                net_sent / (1024 * 1024),
                net_recv / (1024 * 1024),
            ]
        )

        prev_disk = disk
        prev_net = net
        prev_time = now

        if now - start > duration:
            break

print("Telemetry written to:", output_file)
