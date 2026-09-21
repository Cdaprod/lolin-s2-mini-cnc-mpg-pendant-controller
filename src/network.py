"""Wi-Fi bootstrap for the ESP32-S2 / CircuitPython."""

import time
import wifi


class NetworkState:
    def __init__(self):
        self.connected = False
        self.ip = None
        self.hostname = None


def connect_wifi(ssid, password, hostname, retries=3):
    state = NetworkState()

    wifi.radio.hostname = hostname
    state.hostname = hostname

    print("[net] hostname:", hostname)
    print("[net] connecting to:", ssid)

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            if not wifi.radio.connected:
                wifi.radio.connect(ssid, password)

            state.connected = bool(wifi.radio.connected)
            state.ip = wifi.radio.ipv4_address

            print("[net] connected")
            print("[net] ip:", state.ip)
            print("[net] gateway:", wifi.radio.ipv4_gateway)
            print("[net] dns:", wifi.radio.ipv4_dns)
            return state

        except Exception as exc:
            last_error = exc
            print("[net] attempt", attempt, "failed:", repr(exc))
            time.sleep(1)

    raise RuntimeError("Wi-Fi connection failed: {}".format(last_error))
