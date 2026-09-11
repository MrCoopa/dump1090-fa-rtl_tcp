// Part of dump1090, a Mode S message decoder for RTLSDR devices.
//
// sdr_rtltcp.h: rtl_tcp network client SDR support (header)
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

#ifndef SDR_RTLTCP_H
#define SDR_RTLTCP_H

void rtltcpInitConfig();
void rtltcpShowHelp();
bool rtltcpOpen();
void rtltcpRun();
void rtltcpStop();
void rtltcpClose();
bool rtltcpHandleOption(int argc, char **argv, int *jptr);
int rtltcpGetGain();
int rtltcpGetMaxGain();
double rtltcpGetGainDb(int step);
int rtltcpSetGain(int step);

#endif
