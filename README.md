# dump1090-tar1090-readsb

[![Upstream: FlightAware dump1090](https://img.shields.io/badge/upstream-FlightAware%2Fdump1090-blue.svg)](https://github.com/flightaware/dump1090)
[![Decoder: readsb](https://img.shields.io/badge/decoder-readsb-green.svg)](https://github.com/wiedehopf/readsb)
[![Web UI: tar1090](https://img.shields.io/badge/webui-tar1090-orange.svg)](https://github.com/wiedehopf/tar1090)
[![Metrics: graphs1090](https://img.shields.io/badge/metrics-graphs1090-purple.svg)](https://github.com/wiedehopf/graphs1090)
[![Docker Support](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](#-docker-quickstart)
[![License: GPL v2](https://img.shields.io/badge/license-GPL%20v2-green.svg)](LICENSE)

A high-performance **All-in-One ADS-B Receiver, Decoder, and Visualization Container** based on Alpine Linux.

This project combines state-of-the-art decoders (**readsb** and **dump1090-fa with native RTL-TCP client support**) with the modern vector flight-tracking map **tar1090**, the bundled offline aircraft database **tar1090-db**, the long-term performance statistics suite **graphs1090**, and the classic **SkyAware** interface.

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [Architecture & Data Flow](#-architecture--data-flow)
- [Docker Quickstart](#-docker-quickstart)
  - [Scenario A: Direct USB RTL-SDR Dongle (Raspberry Pi)](#scenario-a-direct-usb-rtl-sdr-dongle-raspberry-pi)
  - [Scenario B: Remote SDR via RTL-TCP (Network)](#scenario-b-remote-sdr-via-rtl-tcp-network)
- [Web Interfaces (Port 8080)](#-web-interfaces-port-8080)
- [Detailed Configuration (Environment Variables)](#-detailed-configuration-environment-variables)
- [Network Ports & Data Streams](#-network-ports--data-streams)
- [Range Analysis (Rangemap & HeyWhatsThat)](#-range-analysis-rangemap--heywhatsthat)
- [Feeder Integration (ADS-B Exchange, FR24, etc.)](#-feeder-integration)
- [Troubleshooting & Tips](#-troubleshooting--tips)
- [License](#-license)

---

## 🚀 Key Features

* **Dual-Decoder Engine:**
  * **readsb (Default):** Ultra-fast, low-memory C-based decoder supporting dynamic auto-gain, 2-bit CRC error correction, and real-time reception outlines (rangemaps).
  * **dump1090-fa:** Original FlightAware decoder with an integrated **native RTL-TCP client extension**.
  * **Hybrid RTL-TCP Demodulator Bridge:** When connecting to a networked SDR (`RTL_TCP_IP`), dump1090 automatically demodulates the raw I/Q stream and pipes the Beast data locally into readsb. All advanced features (rangemap, offline aircraft database, etc.) remain fully accessible for networked SDRs.
* **Three Integrated Web Interfaces on Port `8080`:**
  * **tar1090:** Smooth OpenLayers-based live map with track trails, historical replay, aircraft silhouettes, airline logos, and vertical altitude profiles.
  * **graphs1090:** Comprehensive RRD performance dashboard tracking message rates, simultaneous aircraft, range, signal strength, CPU usage, Raspberry Pi temperature, memory, and disk/SD-card I/O.
  * **SkyAware:** The classic FlightAware interface for side-by-side comparison or traditional viewing.
* **Offline Aircraft Database Included:** Built-in `tar1090-db` resolves aircraft types, registrations, operator codes, and silhouettes locally without external API lookups during operation.
* **Track History & Replay:** Background daemon records aircraft trajectories in RAM/disk for interactive time-travel playback on the map.
* **Terrain Horizon & Maximum Reception Outlines:**
  * Live dynamic polygon generation of actual antenna reception range (Range Outline).
  * Automatic download and integration of theoretical line-of-sight terrain contours from *HeyWhatsThat*.
* **Standard Feeder Ports:** Full compatibility with Beast (30005), BaseStation/SBS (30003), Raw AVR (30002), and Beast-In (30004).
* **Lightweight & Efficient:** Minimal Alpine Linux runtime image (~130 MB) using a clean multi-stage Docker build.

---

## 🏗 Architecture & Data Flow

```
[ RTL-SDR USB Dongle ] ───► readsb ───┬─► /run/adsb-data/ ──┬─► Lighttpd (:8080) ──► tar1090 & SkyAware
                                      │   (aircraft.json)   │
[ Remote rtl_tcp ] ────► dump1090-fa ─┘   (stats.json)      ├─► collectd / rrdtool ─► graphs1090
                         (Bridge Mode)                      │
                                                            └─► TCP Feed Ports (:30005, :30003, :30002)
```

---

## 🐳 Docker Quickstart

### Scenario A: Direct USB RTL-SDR Dongle (Raspberry Pi)

For local operation with an RTL-SDR USB dongle connected directly to the host (e.g. RTL-SDR v3/v4, FlightAware Pro Stick):

`docker-compose.yml`:
```yaml
services:
  adsb:
    build: .
    image: dump1090-tar1090-readsb:latest
    container_name: adsb-receiver
    restart: unless-stopped
    privileged: true
    devices:
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - ./graphs1090-data:/var/lib/collectd/rrd
    ports:
      - "8080:8080"   # Web map & dashboards
      - "30003:30003" # BaseStation / SBS Output
      - "30005:30005" # Beast Binary Output
      - "30002:30002" # Raw Output
    environment:
      - DECODER=readsb
      - DEVICE_INDEX=0             # RTL-SDR device index (0, 1, ...)
      - LAT=52.5200                # Your station latitude
      - LON=13.4050                # Your station longitude
      - SITE_NAME=My-Station       # Station display name
      - GAIN=auto                  # auto (readsb auto-gain), max, or fixed dB (e.g. 49.6)
      - RANGE_OUTLINE_HOURS=24     # Timeframe for range outline in hours
      - AGGRESSIVE=true            # Enable 2-bit CRC error correction
```

Start the container:
```bash
docker compose up -d
```

---

### Scenario B: Remote SDR via RTL-TCP (Network)

When the RTL-SDR is plugged into a remote machine running `rtl_tcp` on your local network:

`docker-compose.yml`:
```yaml
services:
  adsb:
    build: .
    image: dump1090-tar1090-readsb:latest
    container_name: adsb-receiver
    restart: unless-stopped
    volumes:
      - ./graphs1090-data:/var/lib/collectd/rrd
    ports:
      - "8080:8080"
      - "30003:30003"
      - "30005:30005"
      - "30002:30002"
    environment:
      - DECODER=readsb
      - RTL_TCP_IP=192.168.1.50    # IP of your remote rtl_tcp server
      - RTL_TCP_PORT=1234          # Port (default: 1234)
      - LAT=52.5200
      - LON=13.4050
      - SITE_NAME=My-Station
      - GAIN=max
      - RANGE_OUTLINE_HOURS=24
```

---

## 🌐 Web Interfaces (Port 8080)

All web dashboards and APIs are served through a single optimized Lighttpd instance:

| URL | Description |
|---|---|
| **`http://<IP>:8080/`** or **`/tar1090/`** | **tar1090 Live Map:** Fluid vector map showing tracked aircraft, range rings, silhouettes, airline filters, and track history replay. |
| **`http://<IP>:8080/graphs1090/`** | **graphs1090 Dashboard:** Detailed historical graphs (messages/sec, aircraft count, range, signal strength, CPU, temperature, RAM, disk I/O). |
| **`http://<IP>:8080/skyaware/`** | **FlightAware SkyAware:** Classic FlightAware web interface. |
| **`http://<IP>:8080/data/aircraft.json`** | **REST JSON API:** Real-time aircraft positions and metadata for custom integrations. |
| **`http://<IP>:8080/data/stats.json`** | **REST JSON API:** Real-time decoder statistics and metrics. |

---

## ⚙️ Detailed Configuration (Environment Variables)

### 1. Decoder Selection
| Variable | Default | Options | Description |
|---|---|---|---|
| `DECODER` | `readsb` | `readsb`, `dump1090` | Primary decoder engine. `readsb` enables auto-gain, range outlines, and highest throughput. `dump1090` uses the classic FlightAware engine. |

### 2. Tuner & Hardware Settings
| Variable | Default | Description |
|---|---|---|
| `DEVICE_INDEX` | `0` | USB device index or serial number for direct RTL-SDR dongle use. |
| `RTL_TCP_IP` | - | IP address of a remote `rtl_tcp` server (automatically activates the demodulator bridge). |
| `RTL_TCP_PORT` | `1234` | Port of the remote `rtl_tcp` server. |
| `GAIN` | `auto` / `max` | Tuner gain: `auto` (readsb dynamic auto-gain algorithm), `max`, or a specific dB value (e.g. `49.6`, `43.4`, `36.4`). |
| `ENABLE_AGC` | `0` | Enable RTL2832U digital automatic gain control (`1` or `true`). |
| `PPM` | `0` | Frequency correction for tuner crystal oscillator in PPM. |
| `FREQ` | `1090000000` | Center frequency in Hz (default: 1090 MHz). |
| `AGGRESSIVE` | `true` | Enable 2-bit CRC error correction (`--fix-2bit`). Increases aircraft detection at marginal signal levels. |

### 3. Station Location & Maximum Range
| Variable | Default | Description |
|---|---|---|
| `LAT` | `52.5200` | Latitude of your antenna in decimal degrees. Required for distance calculations, range rings, and reception outlines. |
| `LON` | `13.4050` | Longitude of your antenna in decimal degrees. |
| `SITE_NAME` | `My-Station` | Station label shown on the tar1090 map. |
| `MAX_RANGE` | `300` | Maximum plausible reception range in nautical miles (NM). Targets beyond this threshold are discarded. |
| `RANGE_OUTLINE_HOURS` | `24` | Duration in hours for which readsb accumulates reception data to draw the real-world range outline polygon. |

### 4. HeyWhatsThat (Terrain Horizon & Line of Sight)
| Variable | Default | Description |
|---|---|---|
| `HEYWHATSTHAT_ID` | - | Panorama ID generated at *[heywhatsthat.com](http://www.heywhatsthat.com/)*. Downloads and renders the theoretical terrain-limited line of sight on tar1090. |
| `HEYWHATSTHAT_ALTS` | `3048,9144,12192` | Altitude contours in meters for the panorama rings (defaults to 10,000 ft, 30,000 ft, 40,000 ft). |
| `FORCE_HEYWHATSTHAT_DOWNLOAD` | `0` | Force redownload of `upintheair.json` on container start (`1` or `true`). |

### 5. tar1090 History & Track Replay
| Variable | Default | Description |
|---|---|---|
| `ENABLE_TAR1090` | `1` | Enable the tar1090 background track history daemon (`0` to disable). |
| `INTERVAL` | `8` | Time in seconds between trajectory snapshots (e.g. `8` = snapshot every 8 seconds). |
| `HISTORY_SIZE` | `450` | Number of snapshots stored in the ring buffer (450 * 8s = 3600s = 1 hour of history). |
| `CHUNK_SIZE` | `60` | Aggregation size for compressed history chunk files. |

### 6. graphs1090 (Metrics & Long-Term Stats)
| Variable | Default | Description |
|---|---|---|
| `ENABLE_GRAPHS1090` | `1` | Enable `collectd` daemon and RRD graph generation (`0` to disable). |
| `GRAPHS1090_COLORSCHEME` | `default` | Color theme for graphs (e.g. `default`, `dark`, `light`). |
| `GRAPHS1090_RANGE` | `nautical` | Unit for distance plots (`nautical`, `metric`, or `statute`). |

---

## 📡 Network Ports & Data Streams

The container exposes all standard ADS-B community data ports:

| Port | Protocol | Format | Direction | Purpose |
|---|---|---|---|---|
| **`8080`** | TCP / HTTP | Web / JSON | Output | tar1090, graphs1090, SkyAware & JSON APIs |
| **`30005`** | TCP | Beast Binary | Output | Standard feed port for ADS-B Exchange, FR24, FlightAware, VRS |
| **`30003`** | TCP | BaseStation / SBS | Output | Human-readable CSV/text stream for loggers and scripts |
| **`30002`** | TCP | Raw / AVR | Output | Unparsed hexadecimal Mode-S packets |
| **`30004`** | TCP | Beast Binary | Input | Ingest external Beast streams into the local decoder |
| **`30001`** | TCP | Raw / AVR | Input | Ingest external raw AVR packets |

---

## 🗺 Range Analysis (Rangemap & HeyWhatsThat)

### Real-World Reception Horizon (Range Outline)
Using `readsb`, the container continuously records azimuth and maximum distance of all valid position reports.
* The resulting polygon is dynamically overlaid on the **tar1090** map.
* Configure the rolling observation window using `RANGE_OUTLINE_HOURS=24` (or `48`, `168` for a full week).

### Theoretical Terrain Coverage (HeyWhatsThat)
To evaluate how mountains, buildings, or local topology obstruct your antenna:
1. Visit [heywhatsthat.com](http://www.heywhatsthat.com/) and create a "New Panorama" at your antenna coordinates and height above ground.
2. Note the generated ID from the URL (e.g. `ABCDEF12`).
3. Set the environment variable in your `docker-compose.yml`:
   ```yaml
   environment:
     - HEYWHATSTHAT_ID=ABCDEF12
   ```
4. Upon startup, the container automatically downloads the contour data and overlays the theoretical line-of-sight limits onto tar1090.

---

## 🛰 Feeder Integration

To forward your receiver data to tracking networks like **ADS-B Exchange**, **Flightradar24**, or **RadarBox**, configure their client software to connect to port `30005` (Beast) of this container:

* **Host:** IP address of your container / Raspberry Pi
* **Port:** `30005`
* **Protocol / Format:** `beast_reduced_plus_out` or standard `beast`

---

## 🔧 Troubleshooting & Tips

### 1. USB RTL-SDR Dongle Not Detected
If the host Linux kernel claims the device with the default DVB TV tuner driver, blacklist the kernel modules on the host system in `/etc/modprobe.d/blacklist-rtl.conf`:
```bash
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
```
Then reboot the host machine.

### 2. graphs1090 Shows Empty / Missing Curves Initially
`collectd` records data points every 60 seconds. It takes approximately **1 to 2 minutes** after starting the container before sufficient data points are available for graphs to draw the first continuous lines.

### 3. Preserving Historical Graphs
Ensure that the volume `./graphs1090-data:/var/lib/collectd/rrd` is mounted in `docker-compose.yml`. This keeps your long-term statistics (weeks, months, years) intact across container rebuilds or upgrades.

---

## 📄 License

This project is licensed under the **GNU General Public License v2.0 (GPL-2.0)**. See the [LICENSE](LICENSE) file for details.
