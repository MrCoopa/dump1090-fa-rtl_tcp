#!/bin/sh
set -e

# Start lighttpd for SkyAware web map
mkdir -p /run/dump1090-fa
lighttpd -f /etc/lighttpd/lighttpd.conf

# If the first argument is an executable not starting with '-', run it
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ] && [ "$1" != "dump1090" ]; then
    exec "$@"
fi

ARGS=""

# RTL-TCP configuration (IP and PORT variables)
RTL_TARGET_IP="${RTL_TCP_IP:-${RTL_TCP_HOST:-${IP}}}"
RTL_TARGET_PORT="${RTL_TCP_PORT:-${PORT:-1234}}"

if [ -n "$RTL_TARGET_IP" ]; then
    case "$RTL_TARGET_IP" in
        *:*)
            ARGS="$ARGS --device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}"
            ;;
        *)
            ARGS="$ARGS --device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}:${RTL_TARGET_PORT}"
            ;;
    esac
elif [ -n "$DEVICE_INDEX" ]; then
    ARGS="$ARGS --device-type rtlsdr --device $DEVICE_INDEX"
fi

# Gain configuration
if [ -n "$GAIN" ]; then
    ARGS="$ARGS --gain $GAIN"
fi

# AGC
if [ "$ENABLE_AGC" = "1" ] || [ "$ENABLE_AGC" = "true" ]; then
    ARGS="$ARGS --enable-agc"
fi

# Frequency
if [ -n "$FREQ" ]; then
    ARGS="$ARGS --freq $FREQ"
fi

# PPM error correction
if [ -n "$PPM" ]; then
    ARGS="$ARGS --ppm $PPM"
fi

# Location
if [ -n "$LAT" ]; then
    ARGS="$ARGS --lat $LAT"
fi
if [ -n "$LON" ]; then
    ARGS="$ARGS --lon $LON"
fi
if [ -n "$MAX_RANGE" ]; then
    ARGS="$ARGS --max-range $MAX_RANGE"
fi

# Aggressive mode / CRC error correction
if [ "$AGGRESSIVE" = "1" ] || [ "$AGGRESSIVE" = "true" ] || [ "$FIX_2BIT" = "1" ] || [ "$FIX_2BIT" = "true" ]; then
    ARGS="$ARGS --fix-2bit"
elif [ "$FIX" = "1" ] || [ "$FIX" = "true" ]; then
    ARGS="$ARGS --fix"
fi

# Networking & JSON output for SkyAware web interface
if [ "$NET" = "1" ] || [ "$NET" = "true" ] || [ -z "$NET" ]; then
    if [ "$NET" != "0" ] && [ "$NET" != "false" ]; then
        ARGS="$ARGS --net --write-json /run/dump1090-fa"
    fi
fi

# Append any arguments passed as CMD or extra args
if [ "$1" = "dump1090" ]; then
    shift
fi
ARGS="$ARGS $@"

echo "[dump1090-fa] Starting: /usr/local/bin/dump1090 $ARGS"
exec /usr/local/bin/dump1090 $ARGS
