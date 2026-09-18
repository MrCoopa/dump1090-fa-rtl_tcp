# dump1090-tar1090-readsb

[![Upstream: FlightAware dump1090](https://img.shields.io/badge/upstream-FlightAware%2Fdump1090-blue.svg)](https://github.com/flightaware/dump1090)
[![Decoder: wiedehopf/readsb](https://img.shields.io/badge/decoder-wiedehopf%2Freadsb-green.svg)](https://github.com/wiedehopf/readsb)
[![Web UI: wiedehopf/tar1090](https://img.shields.io/badge/webui-wiedehopf%2Ftar1090-orange.svg)](https://github.com/wiedehopf/tar1090)
[![Metrics: wiedehopf/graphs1090](https://img.shields.io/badge/metrics-wiedehopf%2Fgraphs1090-purple.svg)](https://github.com/wiedehopf/graphs1090)
[![Docker Support](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](#-docker-quickstart)
[![License: GPL v2](https://img.shields.io/badge/license-GPL%20v2-green.svg)](LICENSE)

**Languages / Sprachen:** [🇬🇧 English](#-english) • [🇩🇪 Deutsch](#-deutsch)

---

<a name="-english"></a>
# 🇬🇧 English

A high-performance **All-in-One ADS-B Receiver, Decoder, and Visualization Container** based on Alpine Linux.

This project combines state-of-the-art decoders (**readsb** and **dump1090-fa with native RTL-TCP client support**) with the modern vector flight-tracking map **tar1090**, the bundled offline aircraft database **tar1090-db**, the long-term performance statistics suite **graphs1090**, and the classic **SkyAware** interface.

---

### 📑 Table of Contents (English)

- [Key Features](#-key-features)
- [Architecture & Data Flow](#-architecture--data-flow)
- [Docker Quickstart](#-docker-quickstart)
  - [Scenario A: Direct USB RTL-SDR Dongle](#scenario-a-direct-usb-rtl-sdr-dongle-raspberry-pi)
  - [Scenario B: Remote SDR via RTL-TCP](#scenario-b-remote-sdr-via-rtl-tcp-network)
- [Web Interfaces (Port 8080)](#-web-interfaces-port-8080)
- [Detailed Configuration (Environment Variables)](#-detailed-configuration-environment-variables)
- [Network Ports & Data Streams](#-network-ports--data-streams)
- [Range Analysis (Rangemap & HeyWhatsThat)](#-range-analysis-rangemap--heywhatsthat)
- [Feeder Integration](#-feeder-integration)
- [Troubleshooting & Tips](#-troubleshooting--tips)
- [Credits & Acknowledgments](#-credits--acknowledgments)

---

### 🚀 Key Features

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

### 🏗 Architecture & Data Flow

```
[ RTL-SDR USB Dongle ] ───► readsb ───┬─► /run/adsb-data/ ──┬─► Lighttpd (:8080) ──► tar1090 & SkyAware
                                      │   (aircraft.json)   │
[ Remote rtl_tcp ] ────► dump1090-fa ─┘   (stats.json)      ├─► collectd / rrdtool ─► graphs1090
                         (Bridge Mode)                      │
                                                            └─► TCP Feed Ports (:30005, :30003, :30002)
```

---

### 🐳 Docker Quickstart

#### Scenario A: Direct USB RTL-SDR Dongle (Raspberry Pi)

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

#### Scenario B: Remote SDR via RTL-TCP (Network)

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

### 🌐 Web Interfaces (Port 8080)

| URL | Description |
|---|---|
| **`http://<IP>:8080/`** or **`/tar1090/`** | **tar1090 Live Map:** Fluid vector map showing tracked aircraft, range rings, silhouettes, airline filters, and track history replay. |
| **`http://<IP>:8080/graphs1090/`** | **graphs1090 Dashboard:** Detailed historical graphs (messages/sec, aircraft count, range, signal strength, CPU, temperature, RAM, disk I/O). |
| **`http://<IP>:8080/skyaware/`** | **FlightAware SkyAware:** Classic FlightAware web interface. |
| **`http://<IP>:8080/data/aircraft.json`** | **REST JSON API:** Real-time aircraft positions and metadata for custom integrations. |
| **`http://<IP>:8080/data/stats.json`** | **REST JSON API:** Real-time decoder statistics and metrics. |

---

### ⚙️ Detailed Configuration (Environment Variables)

#### 1. Decoder Selection
| Variable | Default | Options | Description |
|---|---|---|---|
| `DECODER` | `readsb` | `readsb`, `dump1090` | Primary decoder engine. `readsb` enables auto-gain, range outlines, and highest throughput. `dump1090` uses the classic FlightAware engine. |

#### 2. Tuner & Hardware Settings
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

#### 3. Station Location & Maximum Range
| Variable | Default | Description |
|---|---|---|
| `LAT` | `52.5200` | Latitude of your antenna in decimal degrees. Required for distance calculations, range rings, and reception outlines. |
| `LON` | `13.4050` | Longitude of your antenna in decimal degrees. |
| `SITE_NAME` | `My-Station` | Station label shown on the tar1090 map. |
| `MAX_RANGE` | `300` | Maximum plausible reception range in nautical miles (NM). Targets beyond this threshold are discarded. |
| `RANGE_OUTLINE_HOURS` | `24` | Duration in hours for which readsb accumulates reception data to draw the real-world range outline polygon. |

#### 4. HeyWhatsThat (Terrain Horizon & Line of Sight)
| Variable | Default | Description |
|---|---|---|
| `HEYWHATSTHAT_ID` | - | Panorama ID generated at *[heywhatsthat.com](http://www.heywhatsthat.com/)*. Downloads and renders the theoretical terrain-limited line of sight on tar1090. |
| `HEYWHATSTHAT_ALTS` | `3048,9144,12192` | Altitude contours in meters for the panorama rings (defaults to 10,000 ft, 30,000 ft, 40,000 ft). |
| `FORCE_HEYWHATSTHAT_DOWNLOAD` | `0` | Force redownload of `upintheair.json` on container start (`1` or `true`). |

#### 5. tar1090 History & Track Replay
| Variable | Default | Description |
|---|---|---|
| `ENABLE_TAR1090` | `1` | Enable the tar1090 background track history daemon (`0` to disable). |
| `INTERVAL` | `8` | Time in seconds between trajectory snapshots (e.g. `8` = snapshot every 8 seconds). |
| `HISTORY_SIZE` | `450` | Number of snapshots stored in the ring buffer (450 * 8s = 3600s = 1 hour of history). |
| `CHUNK_SIZE` | `60` | Aggregation size for compressed history chunk files. |

#### 6. graphs1090 (Metrics & Long-Term Stats)
| Variable | Default | Description |
|---|---|---|
| `ENABLE_GRAPHS1090` | `1` | Enable `collectd` daemon and RRD graph generation (`0` to disable). |
| `GRAPHS1090_COLORSCHEME` | `default` | Color theme for graphs (e.g. `default`, `dark`, `light`). |
| `GRAPHS1090_RANGE` | `nautical` | Unit for distance plots (`nautical`, `metric`, or `statute`). |

---

### 📡 Network Ports & Data Streams

| Port | Protocol | Format | Direction | Purpose |
|---|---|---|---|---|
| **`8080`** | TCP / HTTP | Web / JSON | Output | tar1090, graphs1090, SkyAware & JSON APIs |
| **`30005`** | TCP | Beast Binary | Output | Standard feed port for ADS-B Exchange, FR24, FlightAware, VRS |
| **`30003`** | TCP | BaseStation / SBS | Output | Human-readable CSV/text stream for loggers and scripts |
| **`30002`** | TCP | Raw / AVR | Output | Unparsed hexadecimal Mode-S packets |
| **`30004`** | TCP | Beast Binary | Input | Ingest external Beast streams into the local decoder |
| **`30001`** | TCP | Raw / AVR | Input | Ingest external raw AVR packets |

---

### 🗺 Range Analysis (Rangemap & HeyWhatsThat)

#### Real-World Reception Horizon & Polar Plot by Altitude (VRS-Style)
The container continuously records the azimuth and maximum distance of all received aircraft:
* **Two Independent Toggleable Overlays (in Layer Switcher under "Overlays"):**
  * ☑️ **`actual range outline`**: The classic single-line perimeter polygon of maximum reception range across all altitudes (`outline.json`).
  * ☑️ **`altitude range rings (by flight level)`**: The multi-layer polar plot binned into 5 altitude layers:
    * 🟡 **0 – 4,999 ft** (Low altitude, local airfield patterns & initial climb/descent - Yellow)
    * 🟢 **5,000 – 9,999 ft** (Terminal approach & mid-low flight levels - Green)
    * 🩵 **10,000 – 19,999 ft** (Intermediate cruise / regional flights - Cyan)
    * 🔵 **20,000 – 29,999 ft** (Upper cruise - Blue)
    * 🟣 **30,000+ ft** (High altitude long-range jet cruise - Magenta / Violet)
* **Semi-Transparent Shaded Polygons:** The altitude layers are rendered as filled polygons in **tar1090's official altitude color scale** (`ColorByAlt`), subtly shaded so that underlying map details (streets, cities, terrain) remain fully visible.
* **Interactive Live Transparency Slider:** An opacity slider (`5%` to `80%`) appears right below the checkbox in the Layer Switcher menu. Adjustments apply in real time without reloading and are saved in `localStorage`.
* **Persistence:** Polar range points are continuously saved to `./graphs1090-data/polar_range_state.json` so your historical coverage is immediately restored upon container restarts.
* **Rolling Window:** Configurable via `POLAR_RANGE_HOURS=24` (or `RANGE_OUTLINE_HOURS=24`).

#### Theoretical Terrain Coverage (HeyWhatsThat)
To evaluate how mountains, buildings, or local topology obstruct your antenna:
1. Visit [heywhatsthat.com](http://www.heywhatsthat.com/) and create a "New Panorama" at your antenna coordinates and height above ground.
2. Note the generated ID from the URL (e.g. `ABCDEF12`).
3. Set the environment variable in your `docker-compose.yml`: `HEYWHATSTHAT_ID=ABCDEF12`

---

### 🛰 Feeder Integration & MLAT Return Feed

This container exposes standard ADS-B network streams and supports **bi-directional feeding** (sending local ADS-B data out, and receiving calculated MLAT aircraft back into your local map):

* **Beast Binary Output (Port `30005`):** Connect feeder clients (Flightradar24, FlightAware, RadarBox, OpenSky, etc.) to port `30005`.
* **Beast Binary Input (Port `30004`):** Feeders supporting MLAT (e.g., *airplanes.live*, *adsb.fi*, *ADS-B Exchange*) push calculated Multilateration aircraft positions back into this port so they are rendered live on your own `tar1090` map!

#### Recommended Companion Container: [docker-airplaneslive-feeder](https://github.com/MrCoopa/docker-airplaneslive-feeder)

You can run the dedicated, lightweight `airplanes.live` feeder (Debian 13 Trixie Slim) directly alongside this container in `docker-compose.yml`:

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
      - "8080:8080"
      - "30004:30004"   # Beast Input (Incoming MLAT return feed)
      - "30005:30005"   # Beast Output
      - "30003:30003"
      - "30002:30002"
    environment:
      - DECODER=readsb
      - DEVICE_INDEX=1
      - LAT=${LAT:-50.1234}
      - LON=${LON:-8.1234}
      - SITE_NAME=${SITE_NAME:-My-Station}
      - ENABLE_POLAR_RANGE=true
      - POLAR_RANGE_HOURS=24

  # airplanes.live ADS-B & MLAT Feeder:
  airplaneslive:
    build: https://github.com/MrCoopa/docker-airplaneslive-feeder.git#main
    container_name: airplaneslive-feeder
    restart: unless-stopped
    depends_on:
      - adsb
    environment:
      - BEAST_HOST=adsb
      - BEAST_PORT=30005
      - LAT=${LAT:-50.1234}
      - LON=${LON:-8.1234}
      - ALT=${ALT:-180m}
      - USER=${SITE_NAME:-My-Station}
      - ENABLE_MLAT=true
      - MLAT_RESULTS_HOST=adsb
      - MLAT_RESULTS_PORT=30004
    volumes:
      - airplaneslive-data:/var/lib/airplaneslive

volumes:
  airplaneslive-data:
```

---

### 🔧 Troubleshooting & Tips

1. **USB RTL-SDR Dongle Not Detected:** Blacklist the default DVB TV tuner driver on the host in `/etc/modprobe.d/blacklist-rtl.conf`:
   ```bash
   blacklist dvb_usb_rtl28xxu
   blacklist rtl2832
   blacklist rtl2830
   ```
2. **graphs1090 Shows Empty Curves Initially:** `collectd` records data points every 60 seconds. It takes approximately **1 to 2 minutes** after container start before graphs render continuous lines.
3. **Preserving Historical Graphs:** Ensure `./graphs1090-data:/var/lib/collectd/rrd` is mounted in `docker-compose.yml` to preserve long-term metrics across updates.

---

### 🙏 Credits & Acknowledgments

This all-in-one container builds upon the groundbreaking work of leading open-source contributors in the ADS-B community:

* **[FlightAware](https://github.com/flightaware/dump1090):** The creators and maintainers of **`dump1090-fa`** and **`SkyAware`**, setting the industry standard for ADS-B Mode-S demodulation and decoding (originally pioneered by Salvatore Sanfilippo / *antirez*).
* **[wiedehopf](https://github.com/wiedehopf):** The brilliant developer and maintainer behind the modern ADS-B tracking ecosystem:
  * **[`readsb`](https://github.com/wiedehopf/readsb):** High-performance Mode-S decoder with auto-gain, range outline polygons, and minimal resource usage.
  * **[`tar1090`](https://github.com/wiedehopf/tar1090):** The feature-rich, ultra-smooth web tracking map with track history and replay.
  * **[`tar1090-db`](https://github.com/wiedehopf/tar1090-db):** The comprehensive offline aircraft database and silhouette catalog.
  * **[`graphs1090`](https://github.com/wiedehopf/graphs1090):** The complete performance statistics and RRD graphing suite.

---
---

<a name="-deutsch"></a>
# 🇩🇪 Deutsch

Ein hochperformanter **All-in-One ADS-B Empfangs-, Decoder- und Visualisierungs-Container** auf Basis von Alpine Linux.

Dieses Projekt vereint die beiden führenden Decoder (**readsb** und **dump1090-fa mit nativem RTL-TCP Support**) mit der modernen Flugzeug-Vektorkarte **tar1090**, der Offline-Flugzeugdatenbank **tar1090-db**, dem Langzeit-Statistik-Dashboard **graphs1090** und der klassischen **SkyAware**-Oberfläche.

---

### 📑 Inhaltsverzeichnis (Deutsch)

- [Haupt-Features](#-haupt-features-de)
- [Architektur & Funktionsweise](#-architektur--funktionsweise-de)
- [Docker Quickstart](#-docker-quickstart-de)
  - [Szenario A: Lokaler RTL-SDR USB-Dongle (Raspberry Pi)](#szenario-a-lokaler-rtl-sdr-usb-dongle-raspberry-pi-de)
  - [Szenario B: Entferntes SDR via RTL-TCP (Netzwerk)](#szenario-b-entferntes-sdr-via-rtl-tcp-netzwerk-de)
- [Web-Oberflächen (Port 8080)](#-web-oberfl%C3%A4chen-port-8080-de)
- [Detaillierte Konfiguration (Umgebungsvariablen)](#-detaillierte-konfiguration-umgebungsvariablen-de)
- [Netzwerkports & Schnittstellen](#-netzwerkports--schnittstellen-de)
- [Reichweitenanalyse (Rangemap & HeyWhatsThat)](#-reichweitenanalyse-rangemap--heywhatsthat-de)
- [Feeder-Integration](#-feeder-integration-de)
- [Fehlerbehebung & Tipps](#-fehlerbehebung--tipps-de)
- [Danksagung & Credits](#-danksagung--credits-de)

---

<a name="-haupt-features-de"></a>
### 🚀 Haupt-Features

* **Dual-Decoder-Engine:**
  * **readsb (Standard):** Extrem schneller, nativer C-Decoder mit minimalem Speicherverbrauch, Auto-Gain und Echtzeit-Rangemaps.
  * **dump1090-fa:** Original FlightAware-Decoder mit integrierter **RTL-TCP Client-Erweiterung**.
  * **Hybride RTL-TCP Demodulator-Bridge:** Beim Empfang über ein Netzwerk-SDR (`RTL_TCP_IP`) übernimmt dump1090 automatisch die Demodulation und speist die Daten lokal via Beast-Stream in readsb ein. Sämtliche High-End-Features (Rangemap, Flugdatenbank, etc.) stehen somit auch für Netzwerk-SDRs zur Verfügung!
* **Drei integrierte Weboberflächen auf Port `8080`:**
  * **tar1090:** Modernste OpenLayers-Kartenansicht mit Flugverlauf, Replay, Silhouetten, Airline-Logos und Höhenprofilen.
  * **graphs1090:** Detaillierte RRD-Performancestatistiken (Flugzeuge, Nachrichten/s, Reichweite, Signalpegel, CPU, Pi-Temperatur, RAM, Disk-I/O).
  * **SkyAware:** Das klassische FlightAware Interface als alternative Ansicht.
* **Flugzeug-Datenbank offline integriert:** Enthält `tar1090-db` mit Flugzeugtypen, Registrierungen, Betreiber-Logos und Silhouetten ohne externe Internetabfragen während des Betriebs.
* **Track-Historie & Replay:** Konfigurierbarer Hintergrund-Daemon speichert Flugbewegungen im RAM/Disk für zeitversetztes Abspielen auf der Karte.
* **Gelände- und Maximalreichweiten-Polygone:**
  * Live-Aufzeichnung der tatsächlich empfangenen Maximalreichweite (Range Outline).
  * Automatische Einbindung theoretischer Sichtlinien von *HeyWhatsThat*.
* **Offene Feeder-Schnittstellen:** Volle Kompatibilität mit Beast (30005), BaseStation/SBS (30003), Raw (30002) und Beast-In (30004).
* **Schlank & Ressourcenschonend:** Minimales Alpine-Linux-Image (~130 MB) mit Multi-Stage Build.

---

<a name="-architektur--funktionsweise-de"></a>
### 🏗 Architektur & Funktionsweise

```
[ RTL-SDR USB-Dongle ] ───► readsb ───┬─► /run/adsb-data/ ──┬─► Lighttpd (:8080) ──► tar1090 & SkyAware
                                      │   (aircraft.json)   │
[ Remote rtl_tcp ] ──► dump1090-fa ───┘   (stats.json)      ├─► collectd / rrdtool ─► graphs1090
                       (Bridge-Mode)                        │
                                                            └─► TCP-Ports (:30005, :30003, :30002)
```

---

<a name="-docker-quickstart-de"></a>
### 🐳 Docker Quickstart

#### Szenario A: Lokaler RTL-SDR USB-Dongle (Raspberry Pi)

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
      - "8080:8080"   # Webkarten & Dashboard
      - "30003:30003" # BaseStation / SBS Output
      - "30005:30005" # Beast Binary Output
      - "30002:30002" # Raw Output
    environment:
      - DECODER=readsb
      - DEVICE_INDEX=0             # Index des USB-Sticks (0, 1, ...)
      - LAT=52.5200                # Dein Breitengrad
      - LON=13.4050                # Dein Längengrad
      - SITE_NAME=Meine-Station    # Stationsname auf der Karte
      - GAIN=auto                  # auto (readsb Auto-Gain), max oder z.B. 49.6
      - RANGE_OUTLINE_HOURS=24     # Zeitfenster für Reichweiten-Polygon in Stunden
      - AGGRESSIVE=true            # 2-Bit CRC Korrektur
```

Starten mit:
```bash
docker compose up -d
```

#### Szenario B: Entferntes SDR via RTL-TCP (Netzwerk)

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
      - RTL_TCP_IP=192.168.1.50    # IP des rtl_tcp Servers
      - RTL_TCP_PORT=1234          # Port (Standard: 1234)
      - LAT=52.5200
      - LON=13.4050
      - SITE_NAME=Meine-Station
      - GAIN=max
      - RANGE_OUTLINE_HOURS=24
```

---

<a name="-web-oberfl%C3%A4chen-port-8080-de"></a>
### 🌐 Web-Oberflächen (Port 8080)

| URL | Beschreibung |
|---|---|
| **`http://<IP>:8080/`** oder **`/tar1090/`** | **tar1090 Hauptkarte:** Flüssige Darstellung aller empfangenen Flugzeuge, Reichweiten-Ringe, Silhouetten, Filter und Track-Replay. |
| **`http://<IP>:8080/graphs1090/`** | **graphs1090 Dashboard:** Performance-Metriken (Nachrichtenrate, Flugzeuge, Reichweite, Signalpegel, CPU, RAM, Pi-Temperatur, Disk I/O). |
| **`http://<IP>:8080/skyaware/`** | **FlightAware SkyAware:** Die traditionelle Kartenoberfläche von FlightAware. |
| **`http://<IP>:8080/data/aircraft.json`** | **REST JSON API:** Aktuelle Flugzeugliste in Echtzeit für eigene Skripte. |
| **`http://<IP>:8080/data/stats.json`** | **REST JSON API:** Decoder- und Signalstatistiken. |

---

<a name="-detaillierte-konfiguration-umgebungsvariablen-de"></a>
### ⚙️ Detaillierte Konfiguration (Umgebungsvariablen)

#### 1. Decoder-Auswahl
| Variable | Standard | Mögliche Werte | Beschreibung |
|---|---|---|---|
| `DECODER` | `readsb` | `readsb`, `dump1090` | Bestimmt den Hauptdecoder. `readsb` bietet erweiterte Rangemaps und Auto-Gain; `dump1090` ist der klassische Decoder. |

#### 2. Empfänger-Hardware & Signal-Tuning
| Variable | Standard | Beschreibung |
|---|---|---|
| `DEVICE_INDEX` | `0` | USB-Geräte-Index oder Seriennummer für direkten RTL-SDR USB-Betrieb. |
| `RTL_TCP_IP` | - | IP-Adresse des entfernten `rtl_tcp` Servers (aktiviert automatisch die Demodulator-Bridge). |
| `RTL_TCP_PORT` | `1234` | Port des entfernten `rtl_tcp` Servers. |
| `GAIN` | `auto` / `max` | Tuner-Verstärkung: `auto` (dynamischer Auto-Gain in readsb), `max` (maximal möglicher Gain) oder fixer dB-Wert (z. B. `49.6`, `43.4`, `36.4`). |
| `ENABLE_AGC` | `0` | Aktiviert die digitale automatische Verstärkungsregelung des RTL2832U (`1` oder `true`). |
| `PPM` | `0` | Frequenzkorrektur des Oszillators in PPM. |
| `FREQ` | `1090000000` | Empfangsfrequenz in Hz (Standard: 1090 MHz). |
| `AGGRESSIVE` | `true` | Aktiviert die 2-Bit CRC-Fehlerkorrektur für Mode-S Nachrichten (`--fix-2bit`). Erhöht die Anzahl erkannter Flugzeuge bei schwachen Signalen. |

#### 3. Stationsstandort & Reichweite
| Variable | Standard | Beschreibung |
|---|---|---|
| `LAT` | `52.5200` | Breitengrad deiner Antenne (Dezimalgrad). Notwendig für Entfernungsberechnungen, Reichweitenringe und Rangemap. |
| `LON` | `13.4050` | Längengrad deiner Antenne (Dezimalgrad). |
| `SITE_NAME` | `Meine-Station` | Anzeigename deiner Empfangsstation auf der tar1090-Karte. |
| `MAX_RANGE` | `300` | Maximale Reichweitengrenze in nautischen Meilen (NM). Signale außerhalb werden verworfen. |
| `RANGE_OUTLINE_HOURS` | `24` | Zeitfenster in Stunden, für das readsb das reale Reichweiten-Polygon aufzeichnet und in tar1090 anzeigt. |

#### 4. HeyWhatsThat (Geländeüberdeckung & Sichtlinien)
| Variable | Standard | Beschreibung |
|---|---|---|
| `HEYWHATSTHAT_ID` | - | Panorama-ID von *[heywhatsthat.com](http://www.heywhatsthat.com/)*. Lädt die theoretische Geländesichtlinie deiner Antenne herunter und blendet sie als Kontur ein. |
| `HEYWHATSTHAT_ALTS` | `3048,9144,12192` | Höhenschichten in Metern für das Panorama (Standard: 10.000 ft, 30.000 ft, 40.000 ft). |
| `FORCE_HEYWHATSTHAT_DOWNLOAD` | `0` | Erzwingt den erneuten Download des Profils beim Containerstart (`1` oder `true`). |

#### 5. tar1090 Track-Historie & Karten-Features
| Variable | Standard | Beschreibung |
|---|---|---|
| `ENABLE_TAR1090` | `1` | Aktiviert den Hintergrunddienst für Flugpfad-Historie (`0` deaktiviert den Verlauf). |
| `INTERVAL` | `8` | Intervall in Sekunden zwischen Track-Snapshots (z. B. `8` = alle 8 Sekunden ein Wegpunkt). |
| `HISTORY_SIZE` | `450` | Anzahl der gespeicherten Snapshots im Ringspeicher (450 * 8 s = 3600 s = 1 Stunde Historie). |
| `CHUNK_SIZE` | `60` | Bündelungsgröße für komprimierte Historien-Dateien. |

#### 6. graphs1090 (Statistiken & Dashboards)
| Variable | Standard | Beschreibung |
|---|---|---|
| `ENABLE_GRAPHS1090` | `1` | Aktiviert `collectd` und den RRD-Graph-Generator (`0` zum Deaktivieren). |
| `GRAPHS1090_COLORSCHEME` | `default` | Farbschema der Graphen (z. B. `default`, `dark`, `light`). |
| `GRAPHS1090_RANGE` | `nautical` | Entfernungseinheit für Reichweitengraphen (`nautical`, `metric` oder `statute`). |

---

<a name="-netzwerkports--schnittstellen-de"></a>
### 📡 Netzwerkports & Schnittstellen

| Port | Protokoll | Format | Typ | Verwendungszweck |
|---|---|---|---|---|
| **`8080`** | TCP / HTTP | Web / JSON | Out | tar1090, graphs1090, SkyAware & JSON APIs |
| **`30005`** | TCP | Beast Binary | Out | Standard-Feed für ADS-B Exchange, FR24, FlightAware, VRS |
| **`30003`** | TCP | BaseStation / SBS | Out | Klartext-Meldungen für Logging und Auswerteskripte |
| **`30002`** | TCP | Raw / AVR | Out | Rohe Hex-Nachrichten |
| **`30004`** | TCP | Beast Binary | In | Einspeisung externer Beast-Daten in den lokalen Decoder |
| **`30001`** | TCP | Raw / AVR | In | Einspeisung roher AVR-Daten |

---

<a name="-reichweitenanalyse-rangemap--heywhatsthat-de"></a>
### 🗺 Reichweitenanalyse (Rangemap & HeyWhatsThat)

#### Reale Empfangsreichweite & Höhen-Polarplot (VRS-Style)
Der Container zeichnet kontinuierlich auf, in welcher Richtung und Entfernung Flugzeuge tatsächlich empfangen wurden:
* **Zwei unabhängig wählbare Ebenen (im Ebenen-Menü unter „Overlays“):**
  * ☑️ **`actual range outline`**: Die klassische einfarbige Gesamtkontur der maximalen Reichweite über alle Höhen hinweg (`outline.json`).
  * ☑️ **`altitude range rings (by flight level)`**: Der 5-schichtige Höhen-Polarplot nach Vorbild Virtual Radar Server (VRS):
    * 🟡 **0 – 4.999 ft** (Boden-, Platzrunden- & Nahbereich - Gelb)
    * 🟢 **5.000 – 9.999 ft** (An- und Abflüge / tiefe Reiseflughöhen - Grün)
    * 🩵 **10.000 – 19.999 ft** (Mittlere Höhen / Regionalverkehr - Cyan)
    * 🔵 **20.000 – 29.999 ft** (Hohe Reiseflughöhen - Blau)
    * 🟣 **30.000+ ft** (Maximale Reiseflughöhe Langstrecken-Jets - Magenta / Violett)
* **Halbtransparent ausgemalte Flächen:** Die Höhenzonen werden als echte Polygone mit sanfter, transparenter Flächenfüllung in der **originalen tar1090-Höhenfarbskala** (`ColorByAlt`) gerendert. Straßen, Städte und Flugspuren bleiben optimal lesbar.
* **Stufenloser Transparenz-Schieberegler (Slider):** Direkt unter der Checkbox im Ebenen-Menü befindet sich ein Schieberegler (`5 %` bis `80 %`), mit dem du die Deckkraft der Flächenfüllung in Echtzeit anpassen kannst. Der Wert wird im Browser (`localStorage`) gespeichert.
* **Persistenz:** Die Datenpunkte werden kontinuierlich in `./graphs1090-data/polar_range_state.json` gesichert, sodass dein Reichweitenprofil auch nach einem Neustart des Containers sofort vollständig erhalten bleibt.
* **Zeitfenster:** Anpassbar über `POLAR_RANGE_HOURS=24` (oder `RANGE_OUTLINE_HOURS=24`).

#### Theoretische Geländereichweite (HeyWhatsThat)
1. Erstelle auf [heywhatsthat.com](http://www.heywhatsthat.com/) ein Panorama an deinem Antennenstandort mit deiner Antennenhöhe über Grund.
2. Kopiere die generierte ID aus der Adresszeile (z. B. `ABCDEF12`).
3. Trage die Variable in deiner `docker-compose.yml` ein: `HEYWHATSTHAT_ID=ABCDEF12`

---

<a name="-feeder-integration-de"></a>
### 🛰 Feeder-Integration & MLAT-Rückkanal

Dieser Container stellt standardisierte Netzwerk-Datenströme bereit und unterstützt **bidirektionales Feeden** (Senden lokaler ADS-B Daten und gleichzeitiges Empfangen berechneter MLAT-Flugzeuge):

* **Beast Binary Output (Port `30005`):** Verbinde externe Feeder (Flightradar24, FlightAware, RadarBox, etc.) mit Port `30005`.
* **Beast Binary Input (Port `30004`):** Feeder mit MLAT-Unterstützung (*airplanes.live*, *adsb.fi*, etc.) speisen berechnete Multilaterations-Positionen über diesen Port direkt zurück in dein lokales `tar1090`!

#### Empfohlener Begleit-Container: [docker-airplaneslive-feeder](https://github.com/MrCoopa/docker-airplaneslive-feeder)

Du kannst den leichtgewichtigen `airplanes.live`-Feeder (Debian 13 Trixie Slim) direkt als zweiten Dienst in deine `docker-compose.yml` einbinden:

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
      - "8080:8080"
      - "30004:30004"   # Beast Input (MLAT-Rückkanal auf deine Karte)
      - "30005:30005"   # Beast Output
      - "30003:30003"
      - "30002:30002"
    environment:
      - DECODER=readsb
      - DEVICE_INDEX=1
      - LAT=${LAT:-50.1234}
      - LON=${LON:-8.1234}
      - SITE_NAME=${SITE_NAME:-Meine-Station}
      - ENABLE_POLAR_RANGE=true
      - POLAR_RANGE_HOURS=24

  # airplanes.live ADS-B & MLAT Feeder:
  airplaneslive:
    build: https://github.com/MrCoopa/docker-airplaneslive-feeder.git#main
    container_name: airplaneslive-feeder
    restart: unless-stopped
    depends_on:
      - adsb
    environment:
      - BEAST_HOST=adsb
      - BEAST_PORT=30005
      - LAT=${LAT:-50.1234}
      - LON=${LON:-8.1234}
      - ALT=${ALT:-180m}
      - USER=${SITE_NAME:-Meine-Station}
      - ENABLE_MLAT=true
      - MLAT_RESULTS_HOST=adsb
      - MLAT_RESULTS_PORT=30004
    volumes:
      - airplaneslive-data:/var/lib/airplaneslive

volumes:
  airplaneslive-data:
```

---

<a name="-fehlerbehebung--tipps-de"></a>
### 🔧 Fehlerbehebung & Tipps

1. **USB RTL-SDR Dongle wird nicht erkannt:** Erstelle auf dem Host `/etc/modprobe.d/blacklist-rtl.conf`:
   ```bash
   blacklist dvb_usb_rtl28xxu
   blacklist rtl2832
   blacklist rtl2830
   ```
   Danach Host neu starten.
2. **graphs1090 zeigt kurz nach Start leere Diagramme:** `collectd` speichert Messwerte im 60-Sekunden-Takt. Nach **1 bis 2 Minuten** erscheinen die ersten Linien.
3. **Persistenz der Langzeitdaten:** Stelle sicher, dass `./graphs1090-data:/var/lib/collectd/rrd` gemountet ist, damit Messwerte über Wochen und Monate erhalten bleiben.

---

<a name="-danksagung--credits-de"></a>
### 🙏 Danksagung & Credits (Die Entwickler)

Dieser All-in-One Container basiert auf der fantastischen Arbeit führender Open-Source-Entwickler der ADS-B Community:

* **[FlightAware](https://github.com/flightaware/dump1090):** Die Erfinder und Betreiber von **`dump1090-fa`** und der **`SkyAware`**-Oberfläche (aufbauend auf dem ursprünglichen dump1090 von Salvatore Sanfilippo / *antirez*), die seit Jahren den Goldstandard für Mode-S Demodulation und Dekodierung setzen.
* **[wiedehopf](https://github.com/wiedehopf):** Für seine herausragenden Entwicklungen und unermüdliche Pflege des modernen ADS-B Stacks:
  * **[`readsb`](https://github.com/wiedehopf/readsb):** Der extrem performante C-Decoder mit Auto-Gain, Reichweiten-Polygonen (Rangemaps) und minimalem Speicherbedarf.
  * **[`tar1090`](https://github.com/wiedehopf/tar1090):** Die hochmoderne, flüssige Webkarte mit Verlaufshistorie, Replay und Filtern.
  * **[`tar1090-db`](https://github.com/wiedehopf/tar1090-db):** Die umfangreiche Offline-Datenbank für Flugzeugtypen, Betreiberlogos und Silhouetten.
  * **[`graphs1090`](https://github.com/wiedehopf/graphs1090):** Das detaillierte RRDtool-Statistik- und Performance-Dashboard.

---

## 📄 License / Lizenz

This project is licensed under the **GNU General Public License v2.0 (GPL-2.0)**. See the [LICENSE](LICENSE) file for details.
