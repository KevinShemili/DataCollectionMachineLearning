import threading

from monitor import run_monitor
from injector import create_payload_pool, run_exfiltration


def main():

    monitor_duration = 600
    sampling_interval = 1

    attack_duration = 600
    attack_rate_mbs = 40

    payload_size_mb = 800
    payload_count = 5

    receiver_host = "172.20.10.7"
    receiver_port = 5001

    output_csv = "monitor_test.csv"

    print("[TEST] Creating payload pool")

    payload_paths = create_payload_pool(payload_size_mb, payload_count)

    print("[TEST] Payload files created:", payload_paths)

    monitor_thread = threading.Thread(
        target=run_monitor, args=(output_csv, monitor_duration, sampling_interval)
    )

    monitor_thread.start()

    injector_thread = threading.Thread(
        target=run_exfiltration,
        args=(
            attack_duration,
            attack_rate_mbs,
            payload_paths,
            receiver_host,
            receiver_port,
        ),
    )

    injector_thread.start()

    injector_thread.join()

    monitor_thread.join()

    print("[TEST] Completed")


if __name__ == "__main__":
    main()
