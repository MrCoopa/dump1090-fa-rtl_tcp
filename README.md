# dump1090-fa (RTL-TCP + tar1090)

[![Upstream: FlightAware dump1090](https://img.shields.io/badge/upstream-FlightAware%2Fdump1090-blue.svg)](https://github.com/flightaware/dump1090)
[![Web UI: tar1090](https://img.shields.io/badge/webui-wiedehopf%2Ftar1090-orange.svg)](https://github.com/wiedehopf/tar1090)
[![Docker Support](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](#-docker--rtl-tcp-quickstart)
[![License: GPL v2](https://img.shields.io/badge/license-GPL%20v2-green.svg)](LICENSE)

> [!NOTE]
> **Branch Information (`tar1090`):**  
> Dieser Branch kombiniert **dump1090-fa** (inklusive nativem **RTL-TCP**-Netzwerk-Client) mit dem modernen und feature-reichen Web-Interface **[tar1090 von wiedehopf](https://github.com/wiedehopf/tar1090)** sowie der dazugehörigen Flugzeugdatenbank (**[tar1090-db](https://github.com/wiedehopf/tar1090-db)**).
> 
> **Verfügbare Branches im Repository:**
> - **[`main`](https://github.com/MrCoopa/dump1090-fa-rtl_tcp/tree/main):** Minimalistisches Image mit Standard SkyAware Webkarte auf Alpine Linux (~37 MB).
> - **[`debian`](https://github.com/MrCoopa/dump1090-fa-rtl_tcp/tree/debian):** Standard Debian 13 (Trixie) Basis.
> - **[`tar1090`](https://github.com/MrCoopa/dump1090-fa-rtl_tcp/tree/tar1090) (dieser Branch):** dump1090-fa + tar1090 Dashboard (Flugpfadhistorie, Heatmaps, Flugzeugsilhouetten und erweiterte Filter).

---

## ✈️ Highlights von tar1090 in diesem Image

- **Modernes Dashboard:** Flüssige Vektor- und Kartendarstellung basierend auf OpenLayers.
- **Flugpfad-Historie & Heatmaps:** Kontinuierliche Speicherung von Flugbewegungen via integriertem `tar1090.sh` Hintergrund-Dienst.
- **Flugzeugdatenbank & Silhouetten:** Flugzeugtypen, Betreiberlogos und Silhouetten direkt auf der Karte.
- **Parallele Weboberflächen:** 
  - `http://localhost:8080/` oder `http://localhost:8080/tar1090/` zeigt das **tar1090**-Interface.
  - `http://localhost:8080/skyaware/` steht weiterhin für die klassische FlightAware-Karte bereit.
- **Volle RTL-TCP Integration:** Empfang über das Netzwerk von jedem Remote-RTL-SDR/Raspberry Pi.

---

## 🐳 Docker & RTL-TCP Quickstart

### 1. docker-compose.yml anpassen

```yaml
services:
  dump1090:
    build: .
    image: dump1090-tar1090:latest
    container_name: dump1090-tar1090
    restart: unless-stopped
    ports:
      - "8080:8080"   # tar1090 Webkarte (http://localhost:8080/)
      - "30003:30003" # BaseStation / SBS Output
      - "30005:30005" # Beast Binary Output
      - "30002:30002" # Raw Output
    environment:
      - RTL_TCP_IP=192.168.1.100   # IP des RTL-TCP Servers
      - RTL_TCP_PORT=1234          # Port des RTL-TCP Servers (Standard: 1234)
      - LAT=52.5200                # Empfänger-Breitengrad (optional)
      - LON=13.4050                # Empfänger-Längengrad (optional)
      - SITE_NAME=MeineStation     # Name der Empfangsstation auf der Karte
      - GAIN=max                   # Tuner Gain (max, auto oder dB z.B. 49.6)
      - AGGRESSIVE=true            # 2-Bit CRC Fehlerkorrektur (--fix-2bit)
      - INTERVAL=8                 # Intervall (Sekunden) für Track-Snapshots
      - HISTORY_SIZE=450           # Snapshots für Verlauf (450 * 8s = 1 Stunde)
```

### 2. Container starten

```bash
docker compose up -d
```

### 3. Webkarte öffnen

Öffne **`http://localhost:8080/`** im Browser.

---

## ⚙️ Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `RTL_TCP_IP` | - | IP-Adresse des entfernten `rtl_tcp` Servers |
| `RTL_TCP_PORT` | `1234` | Port des entfernten `rtl_tcp` Servers |
| `DEVICE_INDEX` | - | Lokaler USB RTL-SDR Index (falls kein RTL-TCP verwendet wird) |
| `LAT` | - | Breitengrad der Empfänger-Position (setzt auch Ringzentrum in tar1090) |
| `LON` | - | Längengrad der Empfänger-Position |
| `SITE_NAME` | - | Anzeigename der Station in tar1090 |
| `GAIN` | `max` | Verstärkung des Tuners in dB, `max` oder `auto` |
| `ENABLE_AGC` | `0` | Digital AGC aktivieren (`1` oder `true`) |
| `FREQ` | `1090000000` | Empfangsfrequenz in Hz |
| `PPM` | `0` | Frequenzkorrektur in PPM |
| `AGGRESSIVE` / `FIX_2BIT` | `0` | Aktiviert 2-Bit CRC Korrektur |
| `INTERVAL` | `8` | Snapshot-Intervall in Sekunden für tar1090 Track-History |
| `HISTORY_SIZE` | `450` | Anzahl der History-Snapshots |
| `ENABLE_TAR1090` | `1` | `0` schaltet den tar1090 History-Daemon ab |

---

## 🛠️ Manuelles Bauen des Docker-Images

```bash
docker build -t dump1090-tar1090:latest .
```

Container ausführen:
```bash
docker run -d \
  --name dump1090-tar1090 \
  -p 8080:8080 \
  -p 30005:30005 \
  -p 30003:30003 \
  -e RTL_TCP_IP=192.168.1.100 \
  -e RTL_TCP_PORT=1234 \
  -e LAT=52.5200 \
  -e LON=13.4050 \
  dump1090-tar1090:latest
```
