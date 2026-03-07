import os
import time
import socket
import tempfile
from datetime import datetime, timezone


# timestamp with second precision
def time_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_payload(size_mb):
    # Create an arbitrary payload file of a specified size,
    # and store this file in the OS's temporary directory.
    path = os.path.join(
        tempfile.gettempdir(), "dcml_payload_" + str(size_mb) + "mb.bin"
    )

    # Target file size in bytes
    target = size_mb * 1024 * 1024

    # Check if payload already exists
    if os.path.exists(path):
        if os.path.getsize(path) == target:
            return path

    # Repeating block used to fill contents of file
    block = b"DCML_EXFIL_" * 8192  # ~72 KB

    file = open(path, "wb")
    try:
        written = 0
        # Write until we reach aimed target size
        while written < target:
            remaining = target - written

            # Write full blocks when possible,
            # else write a final partial block
            if remaining >= len(block):
                chunk = block
            else:
                chunk = block[:remaining]

            file.write(chunk)

            written = written + len(chunk)
    finally:
        file.close()

    return path


def run_exfiltration(total_duration, rate_mbs, payload_path, host, port, chunk_mb):
    # We want to mimic exfiltration, so what we have done is:
    # 1. Read data from the a file -> Generates disk reads
    # 2. Send data over the network to a malicious receiver -> Generates network traffic
    #   We want injector to create a controlled & steady outbound pattern as much as possible
    #   Sending as fast as possible, will cause bursty patterns, which are less realistic for a steady exfiltration

    # Record start of injection
    start_time_readable = time_now_iso()
    start_time = time.time()

    # Size of each piece of data we send at once
    # Convert to bytes, such that it is compatible with API call
    chunk_bytes = chunk_mb * 1024 * 1024

    # Convert configured MB/s to bytes/s
    rate_bytes = rate_mbs * 1024 * 1024

    # Enforce a speed limit on the sender following seconds = bytes / speed formula
    # Results in a smoother outbound traffic
    target_seconds_per_chunk = float(chunk_bytes) / float(rate_bytes)

    # Create TCP socket & connect to receiver
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    sent = 0
    chunks = 0

    # Open payload file for repeated reads -> Thus generating sustained disk reads activity
    file = open(payload_path, "rb", buffering=0)
    try:
        # Run until defined total duration
        end_time = time.time() + total_duration
        while time.time() < end_time:
            # Read new next chunk every time & if we reach end, turn back to start
            chunk = file.read(chunk_bytes)
            if not chunk:
                file.seek(0)
                chunk = file.read(chunk_bytes)

            # Send chunk down socket & measure how long it takes
            socket_send_time = time.time()
            sock.sendall(chunk)
            sent = sent + len(chunk)
            chunks = chunks + 1

            # Measure how long sending took
            elapsed_socket_send_time = time.time() - socket_send_time

            # Compute time we need to sleep,
            # such that the sending of a chunk, accounting for the time spent transmitting it ~approximates to target_seconds_per_chunk
            # Ensure regular intervals & prevents sender sending at maximum possible speed
            sleep_for = target_seconds_per_chunk - elapsed_socket_send_time
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        try:
            sock.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        sock.close()
        file.close()

    # Record injection end time
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
        "payload_file": payload_path,
        "chunk_mb": chunk_mb,
    }
