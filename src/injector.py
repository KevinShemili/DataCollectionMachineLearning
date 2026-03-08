import os
import time
import socket
import tempfile
import threading
import ctypes
import ctypes.wintypes


def create_payload_pool(size_mb, count):
    # Build a bunch of trash files that will serve as the payloads which will be read
    # by the malicious "exfiltrator".

    payload_paths = []

    for i in range(count):

        name = "dcml_payload_" + str(i) + "_" + str(size_mb) + "mb.bin"

        # Store the files in the system's temp directory
        path = os.path.join(tempfile.gettempdir(), name)

        # Convert from MB to bytes as file operations work in bytes
        size_bytes = size_mb * 1024 * 1024

        # Check if files have alraedy been created
        if os.path.exists(path):
            if os.path.getsize(path) == size_bytes:
                payload_paths.append(path)
                continue

        # This repeated byte block is only used to fill the file until the target size
        # is reached. The exact content does not matter for this project. What matters
        # is that a large file exists on disk and can later be read repeatedly.
        block = b"XYZ" * 20000

        file = open(path, "wb")

        try:
            written = 0

            # Keep writing until file reaches aim size
            while written < size_bytes:
                remaining = size_bytes - written

                # If possible write full block, otherwise trim
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
    # Define a thread which will constantly read the created files

    FILE_FLAG_NO_BUFFERING = 0x20000000
    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3

    # Rather than reading whole file at once, we read in blocks of 512 KB,
    # this is going to yield a consistent disk activity pattern
    # with less bursts
    read_size = 512 * 1024

    # Pass through each of the created trash files
    file_index = 0

    while True:

        if stop_flag["stop"] is True:
            break

        # Pass through each of the created trash files
        path = payload_paths[file_index]

        # Open the file using a low level windows API,
        # this allows us to use the FILE_FLAG_NO_BUFFERING flag which eliminates
        # default windows caching. Thus reads are not dwarfed by RAM & instead hit the disk
        handle = ctypes.windll.kernel32.CreateFileW(
            path, GENERIC_READ, 0, None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        buffer = ctypes.create_string_buffer(read_size)
        bytes_read = ctypes.wintypes.DWORD(0)

        try:
            while True:

                if stop_flag["stop"] is True:
                    break

                # Read the defined read size from the file into the buffer,
                # which will generate the disk activity
                result = ctypes.windll.kernel32.ReadFile(
                    handle, buffer, read_size, ctypes.byref(bytes_read), None
                )

                # Stop reading if 0 bytes read,
                # which means end of the file
                if result == 0 or bytes_read.value == 0:
                    break

                # Add a pause to avoid maximizing disk throughput & keep a sustained,
                # constant pattern
                time.sleep(0.002)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

        file_index = file_index + 1
        if file_index >= len(payload_paths):
            file_index = 0


def run_exfiltration(total_duration, rate_mbs, payload_paths, host, port):
    # We want to mimic exfiltration, so what we have done is:
    # 1. Read data from the a file -> Generates disk reads
    # 2. Send data over a TCP socket to a malicious receiver -> Generates network traffic

    # Start of injection
    injection_start_time = time.time()

    # Create a TCP socket & connect receiver
    # In order to make the scenario realistic, the receiver is an Ubuntu VM
    # The utilization of the VM is important also because it creates real outbound
    # traffic on host, detectable by psutil, and not just a local loopback
    # which would not generate real traffic on the host
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # Convert configured MB/s to bytes/s
    rate_bytes = rate_mbs * 1024 * 1024

    # Use one of the trash payloads we created as the source for the bytes sent
    payload_path = payload_paths[0]
    file = open(payload_path, "rb")

    # Send data in repeated chunks rather than doing one byte at a time or whole file at once,
    # this was aimed at guaranteeing a constant network throughput
    send_block_size = 4 * 1024 * 1024

    # Use to stop disk thread's work
    stop_flag = {"stop": False}

    disk_thread = threading.Thread(
        target=disk_reader_worker, args=(payload_paths, stop_flag)
    )
    disk_thread.start()

    end_time = time.time() + total_duration

    try:
        while True:

            iteration_start_time = time.time()
            if iteration_start_time >= end_time:
                break

            # We need to measure how long one send takes, such that we can later slow down
            # later if needed to maintain a constant rate
            send_start = time.time()

            # Read block size from file,
            # Check if EOF, if yes move to start again
            block = file.read(send_block_size)
            if not block:
                file.seek(0)
                block = file.read(send_block_size)

            # Send block to receiver
            sock.sendall(block)

            # How long sending took
            elapsed = time.time() - send_start

            # How long it should have taken (size / rate)
            expected = float(len(block)) / float(rate_bytes)

            # If was faster sleep for remainder
            # Again the whole purpose is to prevent sending at maximum speed
            # and produce a less bursty pattern
            sleep_for = expected - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        stop_flag["stop"] = True  # stop disk thread
        disk_thread.join()

        try:
            sock.shutdown(socket.SHUT_WR)
        except Exception:
            pass

        sock.close()
        file.close()

    end_unix = time.time()

    # Return the key data needed to describe this anomaly window,
    # this is going to allow us to label later on
    return {
        "start_ts_unix": injection_start_time,
        "end_ts_unix": end_unix,
    }
