import os
import time
import socket
import tempfile
from datetime import datetime, timezone
import threading
import ctypes
import ctypes.wintypes


# timestamp with second precision
def time_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_payload_pool(size_mb, count):

    payload_paths = []

    for i in range(count):

        name = "dcml_payload_" + str(i) + "_" + str(size_mb) + "mb.bin"

        path = os.path.join(tempfile.gettempdir(), name)

        target = size_mb * 1024 * 1024

        if os.path.exists(path):
            if os.path.getsize(path) == target:
                payload_paths.append(path)
                continue

        block = b"DCML_EXFIL_" * 8192

        file = open(path, "wb")

        try:
            written = 0

            while written < target:

                remaining = target - written

                if remaining >= len(block):
                    chunk = block
                else:
                    chunk = block[:remaining]

                file.write(chunk)

                written = written + len(chunk)

        finally:
            file.close()

        payload_paths.append(path)

    return payload_paths


def disk_reader_worker(payload_paths, stop_flag):

    FILE_FLAG_NO_BUFFERING = 0x20000000
    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3

    read_size = 512 * 1024

    index = 0

    while True:

        if stop_flag["stop"] is True:
            break

        path = payload_paths[index]

        handle = ctypes.windll.kernel32.CreateFileW(
            path, GENERIC_READ, 0, None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )

        buf = ctypes.create_string_buffer(read_size)
        bytes_read = ctypes.wintypes.DWORD(0)

        try:
            while True:

                if stop_flag["stop"] is True:
                    break

                result = ctypes.windll.kernel32.ReadFile(
                    handle, buf, read_size, ctypes.byref(bytes_read), None
                )

                if result == 0 or bytes_read.value == 0:
                    break

                time.sleep(0.002)

        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

        index = index + 1

        if index >= len(payload_paths):
            index = 0


def run_exfiltration(total_duration, rate_mbs, payload_paths, host, port):
    # We want to mimic exfiltration, so what we have done is:
    # 1. Read data from the a file -> Generates disk reads
    # 2. Send data over the network to a malicious receiver -> Generates network traffic
    #   We want injector to create a controlled & steady outbound pattern as much as possible
    #   Sending as fast as possible, will cause bursty patterns, which are less realistic for a steady exfiltration

    # Record start of injection
    start_time_readable = time_now_iso()
    start_time = time.time()

    # Create TCP socket & connect to receiver
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # Convert configured MB/s to bytes/s
    rate_bytes = rate_mbs * 1024 * 1024

    payload_path = payload_paths[0]
    file = open(payload_path, "rb")
    payload_data = file.read()
    file.close()
    payload_size = len(payload_data)

    send_block_size = 4 * 1024 * 1024
    # control disk reader thread
    stop_flag = {"stop": False}

    disk_thread = threading.Thread(
        target=disk_reader_worker, args=(payload_paths, stop_flag)
    )
    disk_thread.start()

    sent = 0
    chunks = 0
    end_time = time.time() + total_duration
    pointer = 0

    try:

        while True:

            now = time.time()

            if now >= end_time:
                break

            send_start = time.time()

            if pointer + send_block_size > payload_size:
                pointer = 0

            block = payload_data[pointer : pointer + send_block_size]

            sock.sendall(block)

            pointer = pointer + send_block_size

            sent = sent + len(block)
            chunks = chunks + 1

            elapsed = time.time() - send_start

            expected = float(len(block)) / float(rate_bytes)

            sleep_for = expected - elapsed

            if sleep_for > 0:
                time.sleep(sleep_for)

    finally:

        stop_flag["stop"] = True

        disk_thread.join()

        try:
            sock.shutdown(socket.SHUT_WR)
        except Exception:
            pass

        sock.close()

    end_iso = time_now_iso()
    end_unix = time.time()

    return {
        "scenario": "exfiltration_tcp_vm",
        "start_ts_iso_utc": start_time_readable,
        "end_ts_iso_utc": end_iso,
        "start_ts_unix": start_time,
        "end_ts_unix": end_unix,
        "duration_s": round(end_unix - start_time, 3),
        "rate_MBps": rate_mbs,
        "bytes_sent": sent,
        "tcp_chunks": chunks,
        "receiver_host": host,
        "receiver_port": port,
    }
