# dump1090-fa (RTL-TCP Fork)

[![Upstream: FlightAware dump1090](https://img.shields.io/badge/upstream-FlightAware%2Fdump1090-blue.svg)](https://github.com/flightaware/dump1090)
[![Docker Support](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](#-docker--rtl-tcp-quickstart)
[![License: GPL v2](https://img.shields.io/badge/license-GPL%20v2-green.svg)](LICENSE)

> [!NOTE]
> **Fork Information:**  
> This project is a specialized fork of FlightAware's official [dump1090 repository](https://github.com/flightaware/dump1090) (`dump1090-fa`).  
> 
> **What this fork adds over upstream `dump1090-fa`:**
> - **Native RTL-TCP Client Support**: Stream raw I/Q samples over the network from a remote RTL-TCP server (e.g. Raspberry Pi with `rtl_tcp` or any networked RTL-SDR dongle) using `--device-type rtltcp`.
> - **Ready-to-use Docker Container**: Multi-stage lightweight container packaging both `dump1090-fa` and the **FlightAware SkyAware Web Map** powered by `lighttpd`.
> - **Zero-Configuration Environment Variables**: Easily configure remote RTL-TCP IP/port, receiver location (`LAT`/`LON`), tuner gain, and aggressive 2-bit CRC error correction via Docker environment variables.

---

### About dump1090-fa

dump1090-fa is a Mode S and ADS-B demodulator and decoder maintained by [FlightAware](https://flightaware.com/). It is the successor to [dump1090-mutability](https://github.com/mutability/dump1090).

It can provide a display of locally received aircraft data in a terminal or via a browser map (SkyAware). Together with [PiAware](https://flightaware.com/adsb/piaware) it can be used to contribute crowd-sourced flight tracking data to FlightAware.

---

## 🐳 Docker & RTL-TCP Quickstart

1. Configure your settings in `docker-compose.yml`:
```yaml
services:
  dump1090:
    build: .
    image: dump1090-fa:latest
    container_name: dump1090-fa
    restart: unless-stopped
    ports:
      - "8080:8080"   # SkyAware Web Map (http://localhost:8080/)
      - "30003:30003" # BaseStation / SBS Output
      - "30005:30005" # Beast Binary Output
      - "30002:30002" # Raw Output
    environment:
      - RTL_TCP_IP=192.168.1.100   # RTL-TCP Server IP
      - RTL_TCP_PORT=1234          # RTL-TCP Server Port
      - LAT=52.5200                # Receiver Latitude
      - LON=13.4050                # Receiver Longitude
      - GAIN=max                   # Tuner Gain (max, auto, or dB value)
      - AGGRESSIVE=true            # 2-bit CRC error correction (--fix-2bit)
```

2. Start the container:
```bash
docker compose up -d
```

3. Open **`http://localhost:8080/`** in your browser to view the live SkyAware map!


## Building under bullseye, buster, or stretch

```bash
$ sudo apt-get install build-essential fakeroot debhelper librtlsdr-dev pkg-config libncurses5-dev libbladerf-dev libhackrf-dev liblimesuite-dev libsoapysdr-dev devscripts
$ ./prepare-build.sh bullseye    # or buster, or stretch
$ cd package-bullseye            # or buster, or stretch
$ dpkg-buildpackage -b --no-sign
```

## Building with limited dependencies

(Supported for bullseye and buster builds only)

The package supports some build profiles to allow building without all
required SDR libraries being present. This will produce a package with
limited SDR support only.

Pass `--build-profiles` to `dpkg-buildpackage` with a comma-separated list of
profiles. The list of profiles should include `custom` and zero or more of
`rtlsdr`, `bladerf`, `hackrf`, `limesdr`, 'soapysdr' depending on what you want:

```bash
$ dpkg-buildpackage -b --no-sign --build-profiles=custom,rtlsdr          # builds with rtlsdr support only
$ dpkg-buildpackage -b --no-sign --build-profiles=custom,rtlsdr,bladerf  # builds with rtlsdr and bladeRF support
$ dpkg-buildpackage -b --no-sign --build-profiles=custom                 # builds with _no_ SDR support (network support only)
```


## Building manually

You can probably just run "make" after installing the required dependencies.
Binaries are built in the source directory; you will need to arrange to
install them (and a method for starting them) yourself.

``make BLADERF=no`` will disable bladeRF support and remove the dependency on
libbladeRF.

``make RTLSDR=no`` will disable rtl-sdr support and remove the dependency on
librtlsdr.

``make HACKRF=no`` will disable HackRF support and remove the dependency on 
libhackrf.

``make LIMESDR=no`` will disable LimeSDR support and remove the dependency on
libLimeSuite.

``make SOAPYSDR=no`` will disable SoapySDR support and remove the dependency on
libSoapySDR.

## Building on OSX

Minimal testing on Mojave 10.14.6, YMMV.

```
$ brew install librtlsdr
$ brew install libbladerf
$ brew install hackrf
$ brew install pkg-config
$ make
```

## Building on FreeBSD

Minimal testing on 12.1-RELEASE, YMMV.

```
# pkg install gmake
# pkg install pkgconf
# pkg install rtl-sdr
# pkg install bladerf
# pkg install hackrf
$ gmake
```

## Generating wisdom files

dump1090-fa uses [starch](https://github.com/flightaware/starch) to build
multiple versions of the DSP code and choose the fastest supported by the
hardware at runtime. The implementations chosen can been seen by running
`dump1090-fa --version`.

The implementations used are controlled by "wisdom files", a list of
implementations to use in order of priority. For each DSP function, the first
implementation listed that's supported by the current hardware is used.
By default dump1090-fa provides compiled-in wisdom for [x86](wisdom.x86),
[ARM 32-bit](wisdom.arm), and [ARM 64-bit](wisdom.aarch64). If the defaults
are not suitable for your hardware or if you're building on a different
architecture, you may want to generate your own external wisdom file.

Ideally, to get stable results, you want to do this on an idle system
with CPU frequency scaling disabled. Running the benchmarks will take
some time (10s of minutes).

### Package installs

Run `/usr/share/dump1090-fa/generate-wisdom`. Wait.

Follow the instructions to copy the resulting wisdom file to `/etc/dump1090-fa/wisdom.local`.

Restart dump1090.

### Manual installs

Run `make wisdom.local`. Wait.

Copy the resulting `wisdom.local` file somewhere appropriate.

Update the dump1090-fa command-line options to include `--wisdom /path/to/wisdom.local`
