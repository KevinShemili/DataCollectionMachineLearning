# This script will run inside of a VM which mimics an external attacker
# The utilization of a VM is so that the network traffic leaves the Windows
# host through its real network interface instead of using loopback (127.0.0.1),
# which would bypass the physical network stack and many operating
# system counters would not reflect realistic network activity
#
# The VM's network adapter is configured in Bridged Mode, in order to
# appear as an independent device on the same LAN

import socket
import time

HOST = "0.0.0.0"  # accept from any NIC
PORT = 5001


def main():
    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind socket to host/port
    sock.bind((HOST, PORT))
    sock.listen(1)

    print(f"[EXFILTRATOR] Listening on: {HOST}:{PORT}")

    while True:

        conn, addr = sock.accept()
        print(f"[EXFILTRATOR] Connection from: {addr}")

        total = 0
        start = time.time()
        last = start

        while True:
            data = conn.recv(1024 * 256)
            if not data:
                break
            total += len(data)

            now = time.time()

            if now - last >= 1.0:
                mbps = (total / (now - start)) / (1024 * 1024)
                print(
                    f"[EXFILTRATOR] Average: {mbps:.2f} MB/s  Total: {total/1024/1024:.1f} MB"
                )
                last = now

        conn.close()
        print("[EXFILTRATOR] Session finished, waiting for next connection")


if __name__ == "__main__":
    main()
