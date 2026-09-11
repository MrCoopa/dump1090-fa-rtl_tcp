// Part of dump1090, a Mode S message decoder for RTLSDR devices.
//
// sdr_rtltcp.c: rtl_tcp network client SDR support
//
// Copyright (c) 2016-2017 Oliver Jowett <oliver@mutability.co.uk>
// Copyright (c) 2017 FlightAware LLC
//
// This file is free software: you may copy, redistribute and/or modify it
// under the terms of the GNU General Public License as published by the
// Free Software Foundation, either version 2 of the License, or (at your
// option) any later version.
//
// This file is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

#include "dump1090.h"
#include "sdr_rtltcp.h"
#include "convert.h"
#include "anet.h"

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <errno.h>

typedef struct {
    char magic[4];
    uint32_t tuner_type;
    uint32_t tuner_gain_count;
} __attribute__((packed)) rtl_tcp_dongle_info_t;

typedef struct {
    uint8_t cmd;
    uint32_t param;
} __attribute__((packed)) rtl_tcp_command_t;

static const int default_r820t_gains[] = {
    0, 9, 14, 27, 37, 77, 87, 125, 144, 157, 166, 197, 207, 229, 254, 280, 297, 328, 338, 364, 372, 386, 402, 421, 434, 439, 445, 480, 496
};

static struct {
    char *host;
    int port;
    int fd;
    int ppm_error;
    bool digital_agc;

    int *gains;
    int gain_steps;
    int gain_index;

    iq_convert_fn converter;
    struct converter_state *converter_state;
} RTLTCP;

static int rtl_tcp_send_cmd(int fd, uint8_t cmd, uint32_t param) {
    rtl_tcp_command_t c;
    c.cmd = cmd;
    c.param = htonl(param);
    ssize_t written = 0;
    unsigned char *p = (unsigned char *)&c;
    while (written < (ssize_t)sizeof(c)) {
        ssize_t n = send(fd, p + written, sizeof(c) - written, 0);
        if (n <= 0) return -1;
        written += n;
    }
    return 0;
}

void rtltcpInitConfig()
{
    RTLTCP.host = NULL;
    RTLTCP.port = 1234;
    RTLTCP.fd = -1;
    RTLTCP.ppm_error = 0;
    RTLTCP.digital_agc = false;
    RTLTCP.gains = NULL;
    RTLTCP.gain_steps = 0;
    RTLTCP.gain_index = -1;
    RTLTCP.converter = NULL;
    RTLTCP.converter_state = NULL;

    // Check environment variables
    char *env_host = getenv("RTL_TCP_IP");
    if (!env_host) env_host = getenv("RTL_TCP_HOST");
    if (!env_host) env_host = getenv("RTL_IP");
    if (!env_host) env_host = getenv("IP");

    if (env_host && env_host[0] != '\0') {
        char *colon = strchr(env_host, ':');
        if (colon) {
            *colon = '\0';
            RTLTCP.host = strdup(env_host);
            RTLTCP.port = atoi(colon + 1);
            *colon = ':';
        } else {
            RTLTCP.host = strdup(env_host);
        }
        // Auto-select RTLTCP mode if environment variable is set
        Modes.sdr_type = SDR_RTLTCP;
    }

    char *env_port = getenv("RTL_TCP_PORT");
    if (!env_port) env_port = getenv("RTL_PORT");
    if (env_port && env_port[0] != '\0') {
        RTLTCP.port = atoi(env_port);
    }
}

void rtltcpShowHelp()
{
    printf("      rtltcp-specific options (use with --device-type rtltcp):\n");
    printf("\n");
    printf("--net-rtl-tcp <host[:port]>  connect to RTL-TCP server (default port 1234)\n");
    printf("--net-rtl-tcp-port <port>    set RTL-TCP server port (default 1234)\n");
    printf("--ppm <correction>           set oscillator frequency correction in PPM\n");
    printf("--enable-agc                 enable digital AGC\n");
    printf("\n");
}

bool rtltcpHandleOption(int argc, char **argv, int *jptr)
{
    int j = *jptr;
    bool more = (j + 1 < argc);

    if ((!strcmp(argv[j], "--net-rtl-tcp") || !strcmp(argv[j], "--rtl-tcp")) && more) {
        char *arg = argv[++j];
        char *colon = strchr(arg, ':');
        if (colon) {
            *colon = '\0';
            free(RTLTCP.host);
            RTLTCP.host = strdup(arg);
            RTLTCP.port = atoi(colon + 1);
            *colon = ':';
        } else {
            free(RTLTCP.host);
            RTLTCP.host = strdup(arg);
        }
        Modes.sdr_type = SDR_RTLTCP;
    } else if (!strcmp(argv[j], "--net-rtl-tcp-port") && more) {
        RTLTCP.port = atoi(argv[++j]);
    } else if (!strcmp(argv[j], "--ppm") && more) {
        RTLTCP.ppm_error = atoi(argv[++j]);
    } else if (!strcmp(argv[j], "--enable-agc")) {
        RTLTCP.digital_agc = true;
    } else {
        return false;
    }

    *jptr = j;
    return true;
}

bool rtltcpOpen()
{
    if (!RTLTCP.host) {
        fprintf(stderr, "rtltcp: No host specified. Use --net-rtl-tcp <host:port> or set RTL_TCP_IP\n");
        return false;
    }

    rtltcpClose();

    fprintf(stderr, "rtltcp: Connecting to %s:%d...\n", RTLTCP.host, RTLTCP.port);
    char err[ANET_ERR_LEN];
    char service[16];
    snprintf(service, sizeof(service), "%d", RTLTCP.port);
    int fd = anetTcpConnect(err, RTLTCP.host, service);
    if (fd == ANET_ERR) {
        fprintf(stderr, "rtltcp: connection error to %s:%d: %s\n", RTLTCP.host, RTLTCP.port, err);
        return false;
    }
    RTLTCP.fd = fd;
    anetTcpNoDelay(err, RTLTCP.fd);

    // Read 12-byte header
    rtl_tcp_dongle_info_t info;
    ssize_t toread = sizeof(info);
    unsigned char *p = (unsigned char *)&info;
    while (toread > 0) {
        ssize_t n = recv(RTLTCP.fd, p, toread, 0);
        if (n <= 0) {
            fprintf(stderr, "rtltcp: error reading header from %s:%d: %s\n", RTLTCP.host, RTLTCP.port, strerror(errno));
            rtltcpClose();
            return false;
        }
        p += n;
        toread -= n;
    }

    if (memcmp(info.magic, "RTL0", 4) != 0) {
        fprintf(stderr, "rtltcp: invalid magic header '%.4s' from %s:%d\n", info.magic, RTLTCP.host, RTLTCP.port);
        rtltcpClose();
        return false;
    }

    uint32_t tuner_type = ntohl(info.tuner_type);
    uint32_t gain_count = ntohl(info.tuner_gain_count);
    fprintf(stderr, "rtltcp: connected to %s:%d (tuner: %u, gain count: %u)\n",
            RTLTCP.host, RTLTCP.port, tuner_type, gain_count);

    // Set sample rate (default 2.4MHz in dump1090-fa)
    if (rtl_tcp_send_cmd(RTLTCP.fd, 0x02, (uint32_t)Modes.sample_rate) < 0) goto config_err;

    // Set frequency
    if (rtl_tcp_send_cmd(RTLTCP.fd, 0x01, (uint32_t)Modes.freq) < 0) goto config_err;

    // Setup gain table
    int numgains = sizeof(default_r820t_gains) / sizeof(default_r820t_gains[0]);
    RTLTCP.gains = malloc((numgains + 1) * sizeof(int));
    if (RTLTCP.gains) {
        memcpy(RTLTCP.gains, default_r820t_gains, sizeof(default_r820t_gains));
        RTLTCP.gains[numgains] = RTLTCP.gains[numgains-1] + 90; // fake entry for auto gain
        RTLTCP.gain_steps = numgains + 1;
    }

    int selected = -1;
    if (Modes.gain == MODES_LEGACY_AUTO_GAIN) {
        selected = numgains;
    } else if (Modes.gain == MODES_DEFAULT_GAIN) {
        selected = numgains - 1;
    } else {
        for (int i = 0; i <= numgains; ++i) {
            if (selected == -1 || fabs(RTLTCP.gains[i]/10.0 - Modes.gain) < fabs(RTLTCP.gains[selected]/10.0 - Modes.gain))
                selected = i;
        }
    }
    rtltcpSetGain(selected);

    // PPM error
    if (RTLTCP.ppm_error != 0) {
        rtl_tcp_send_cmd(RTLTCP.fd, 0x05, (uint32_t)RTLTCP.ppm_error);
    }

    // AGC
    if (RTLTCP.digital_agc) {
        rtl_tcp_send_cmd(RTLTCP.fd, 0x08, 1);
    }

    // Initialize sample converter
    RTLTCP.converter = init_converter(INPUT_UC8,
                                      Modes.sample_rate,
                                      Modes.dc_filter,
                                      &RTLTCP.converter_state);
    if (!RTLTCP.converter) {
        fprintf(stderr, "rtltcp: can't initialize sample converter\n");
        rtltcpClose();
        return false;
    }

    // Set receive timeout
    struct timeval tv;
    tv.tv_sec = 2;
    tv.tv_usec = 0;
    setsockopt(RTLTCP.fd, SOL_SOCKET, SO_RCVTIMEO, (const void*)&tv, sizeof(tv));

    return true;

config_err:
    fprintf(stderr, "rtltcp: failed to send configuration commands to server: %s\n", strerror(errno));
    rtltcpClose();
    return false;
}

static void process_rtltcp_block(unsigned char *buf, uint32_t len)
{
    static unsigned dropped = 0;
    static uint64_t sampleCounter = 0;

    sdrMonitor();

    if (Modes.exit) {
        return;
    }

    unsigned samples_read = len / 2;
    if (!samples_read)
        return;

    struct mag_buf *outbuf = fifo_acquire(0 /* don't wait */);
    if (!outbuf) {
        dropped += samples_read;
        sampleCounter += samples_read;
        return;
    }

    outbuf->flags = 0;
    if (dropped) {
        outbuf->flags |= MAGBUF_DISCONTINUOUS;
        outbuf->dropped = dropped;
    }
    dropped = 0;

    outbuf->sampleTimestamp = sampleCounter * 12e6 / Modes.sample_rate;
    sampleCounter += samples_read;

    uint64_t block_duration = 1e3 * samples_read / Modes.sample_rate;
    outbuf->sysTimestamp = mstime() - block_duration;

    unsigned to_convert = samples_read;
    if (to_convert + outbuf->overlap > outbuf->totalLength) {
        to_convert = outbuf->totalLength - outbuf->overlap;
        dropped = samples_read - to_convert;
    }

    RTLTCP.converter(buf, &outbuf->data[outbuf->overlap], to_convert, RTLTCP.converter_state, &outbuf->mean_level, &outbuf->mean_power);
    outbuf->validLength = outbuf->overlap + to_convert;

    fifo_enqueue(outbuf);
}

void rtltcpRun()
{
    unsigned char *read_buf = malloc(MODES_RTL_BUF_SIZE);
    if (!read_buf) {
        fprintf(stderr, "rtltcp: failed to allocate read buffer\n");
        return;
    }

    while (!Modes.exit) {
        if (RTLTCP.fd < 0) {
            if (!rtltcpOpen()) {
                if (Modes.exit) break;
                sleep(5);
                continue;
            }
        }

        ssize_t toread = MODES_RTL_BUF_SIZE;
        unsigned char *p = read_buf;

        while (toread > 0 && !Modes.exit) {
            ssize_t n = recv(RTLTCP.fd, p, toread, 0);
            if (n < 0) {
                if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
                    continue;
                }
                fprintf(stderr, "rtltcp: read error from server: %s\n", strerror(errno));
                rtltcpClose();
                break;
            } else if (n == 0) {
                fprintf(stderr, "rtltcp: connection closed by server\n");
                rtltcpClose();
                break;
            }
            p += n;
            toread -= n;
        }

        if (RTLTCP.fd < 0) {
            sleep(2);
            continue;
        }

        if (Modes.exit) break;

        process_rtltcp_block(read_buf, MODES_RTL_BUF_SIZE);
    }

    free(read_buf);
}

void rtltcpStop()
{
    if (RTLTCP.fd >= 0) {
        shutdown(RTLTCP.fd, SHUT_RDWR);
    }
}

void rtltcpClose()
{
    if (RTLTCP.fd >= 0) {
        close(RTLTCP.fd);
        RTLTCP.fd = -1;
    }

    if (RTLTCP.converter_state) {
        cleanup_converter(RTLTCP.converter_state);
        RTLTCP.converter_state = NULL;
    }
    RTLTCP.converter = NULL;

    free(RTLTCP.gains);
    RTLTCP.gains = NULL;
    RTLTCP.gain_steps = 0;
    RTLTCP.gain_index = -1;
}

int rtltcpGetGain()
{
    return RTLTCP.gain_index;
}

int rtltcpGetMaxGain()
{
    return RTLTCP.gain_steps - 1;
}

double rtltcpGetGainDb(int step)
{
    if (!RTLTCP.gains || step < 0 || step >= RTLTCP.gain_steps)
        return 0.0;
    return RTLTCP.gains[step] / 10.0;
}

int rtltcpSetGain(int step)
{
    if (!RTLTCP.gains || step < 0 || step >= RTLTCP.gain_steps)
        return -1;

    RTLTCP.gain_index = step;

    if (RTLTCP.fd >= 0) {
        if (step == RTLTCP.gain_steps - 1) {
            // Auto gain
            rtl_tcp_send_cmd(RTLTCP.fd, 0x03, 0);
            fprintf(stderr, "rtltcp: tuner AGC enabled\n");
        } else {
            // Manual gain
            rtl_tcp_send_cmd(RTLTCP.fd, 0x03, 1);
            rtl_tcp_send_cmd(RTLTCP.fd, 0x04, (uint32_t)RTLTCP.gains[step]);
            fprintf(stderr, "rtltcp: gain set to %.1f dB\n", RTLTCP.gains[step] / 10.0);
        }
    }

    return step;
}
