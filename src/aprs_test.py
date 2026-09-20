#!/usr/bin/env python3

import json
import socket
import tomllib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aprslib


HOST = "noam.aprs2.net"
PORT = 14580

LATITUDE = 38.98361
LONGITUDE = -94.63359
RADIUS_KM = 40

CALLSIGN = "N0CALL"

CONFIG_FILE = Path("stations.toml")
OUTPUT_FILE = Path("aprs-current.geojson")

STALE_MINUTES = 60

FILTER = f"r/{LATITUDE}/{LONGITUDE}/{RADIUS_KM}"

LOGIN = (
    f"user {CALLSIGN} "
    f"pass -1 "
    f"vers qgis-aprs-test 0.4 "
    f"filter {FILTER}"
)


stations = {}
allowed_stations = {}


def utc_now():
    return datetime.now(timezone.utc)


def load_station_config():
    with CONFIG_FILE.open("rb") as f:
        config = tomllib.load(f)

    configured = config.get("stations", {})

    return {
        callsign.upper(): tactical
        for callsign, tactical in configured.items()
    }


def update_station(packet):
    callsign = packet.get("from")

    if not callsign:
        return False

    callsign = callsign.upper()

    # Ignore everything not explicitly listed in stations.toml.
    if callsign not in allowed_stations:
        return False

    latitude = packet.get("latitude")
    longitude = packet.get("longitude")

    if latitude is None or longitude is None:
        return False

    stations[callsign] = {
        "callsign": callsign,
        "tactical": allowed_stations[callsign],
        "latitude": latitude,
        "longitude": longitude,
        "last_seen": utc_now(),
        "course": packet.get("course"),
        "speed": packet.get("speed"),
        "altitude": packet.get("altitude"),
        "symbol": packet.get("symbol"),
        "symbol_table": packet.get("symbol_table"),
        "comment": packet.get("comment", ""),
    }

    return True


def remove_stale_stations():
    cutoff = utc_now() - timedelta(minutes=STALE_MINUTES)

    stale = [
        callsign
        for callsign, station in stations.items()
        if station["last_seen"] < cutoff
    ]

    for callsign in stale:
        del stations[callsign]


def make_feature(station):
    age_seconds = int(
        (utc_now() - station["last_seen"]).total_seconds()
    )

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                station["longitude"],
                station["latitude"],
            ],
        },
        "properties": {
            "callsign": station["callsign"],
            "tactical": station["tactical"],
            "last_seen": station["last_seen"].isoformat(),
            "age_seconds": age_seconds,
            "course": station["course"],
            "speed": station["speed"],
            "altitude": station["altitude"],
            "symbol": station["symbol"],
            "symbol_table": station["symbol_table"],
            "comment": station["comment"],
        },
    }


def write_geojson():
    remove_stale_stations()

    geojson = {
        "type": "FeatureCollection",
        "features": [
            make_feature(station)
            for station in stations.values()
        ],
    }

    temp_file = OUTPUT_FILE.with_suffix(".geojson.tmp")

    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(
            geojson,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    temp_file.replace(OUTPUT_FILE)


def print_station(packet):
    callsign = packet["from"].upper()
    tactical = allowed_stations[callsign]

    latitude = packet.get("latitude")
    longitude = packet.get("longitude")

    now = datetime.now().strftime("%H:%M:%S")

    print(
        f"[{now}] "
        f"{tactical:<12} "
        f"{callsign:<10} "
        f"{latitude:9.5f} "
        f"{longitude:10.5f} "
        f"({len(stations)} stations)"
    )


def main():
    global allowed_stations

    allowed_stations = load_station_config()

    print(f"Loaded {len(allowed_stations)} configured stations:")
    for callsign, tactical in allowed_stations.items():
        print(f"  {callsign:<10} {tactical}")

    print()
    print(f"Connecting to {HOST}:{PORT}")
    print(f"Filter: {FILTER}")
    print(f"Writing: {OUTPUT_FILE.resolve()}")
    print()

    with socket.create_connection(
        (HOST, PORT),
        timeout=10,
    ) as sock:

        sock.settimeout(None)

        stream = sock.makefile(
            "r",
            encoding="latin-1",
            newline="\n",
        )

        greeting = stream.readline().rstrip()
        print(f"SERVER: {greeting}")

        sock.sendall(
            (LOGIN + "\r\n").encode("ascii")
        )

        print()
        print("Receiving configured APRS stations.")
        print("Press Ctrl-C to stop.")
        print()

        write_geojson()

        while True:
            line = stream.readline()

            if not line:
                print("Connection closed by server.")
                break

            line = line.rstrip("\r\n")

            if line.startswith("#"):
                print(f"SERVER: {line}")
                continue

            try:
                packet = aprslib.parse(line)
            except Exception:
                continue

            if update_station(packet):
                write_geojson()
                print_station(packet)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\nDisconnected.")

    except FileNotFoundError:
        print(f"\nConfiguration file not found: {CONFIG_FILE}")

    except OSError as e:
        print(f"\nNetwork error: {e}")