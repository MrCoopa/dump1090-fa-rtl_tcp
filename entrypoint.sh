#!/bin/sh
set -e

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
            # Port is already included in IP string (e.g. 192.168.1.100:1234)
            ARGS="$ARGS --net-rtl-tcp ${RTL_TARGET_IP}"
            ;;
        *)
            # IP and Port separate
            ARGS="$ARGS --net-rtl-tcp ${RTL_TARGET_IP}:${RTL_TARGET_PORT}"
            ;;
    esac
elif [ -n "$DEVICE_INDEX" ]; then
    ARGS="$ARGS --device-index $DEVICE_INDEX"
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

# Networking
if [ "$NET" = "1" ] || [ "$NET" = "true" ] || [ -z "$NET" ]; then
    if [ "$NET" != "0" ] && [ "$NET" != "false" ]; then
        ARGS="$ARGS --net"
    fi
fi

if [ -n "$HTTP_PORT" ]; then
    ARGS="$ARGS --net-http-port $HTTP_PORT"
fi

# Oversample
if [ "$OVERSAMPLE" = "1" ] || [ "$OVERSAMPLE" = "true" ]; then
    ARGS="$ARGS --oversample"
fi

# Append any arguments passed as CMD or extra args
if [ "$1" = "dump1090" ]; then
    shift
fi
ARGS="$ARGS $@"

echo "[dump1090] Starting: /usr/local/bin/dump1090 $ARGS"
exec /usr/local/bin/dump1090 $ARGS
