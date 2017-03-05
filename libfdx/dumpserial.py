#!/usr/bin/env python
# .- coding: utf-8 -.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation version 2 of the License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#  Copyright (C) 2016 Lasse Karstensen
#
"""
Garmin GND10 "blackbox bridge" data logger.

Read serial data from the usb serial interface provided. You _must_ use the
original Garmin USB cable for it to work. I spent many hours trying to provoke
an output from it only to learn that with the original cable it started sending
data immediately.

My unit presents itself as 091e:0760.

Data format is a 6-12 byte message always ending with 0x81. There is usually
0.02s gap between frames.

I've attempted to change bitrate, stop and parity bits, but it doesn't seem to
make any difference for such a ACM device. (or I don't understand stty, which
is quite possible. Hello 1985!)
"""
from __future__ import print_function
from datetime import datetime
from os.path import exists
from sys import stderr, argv, stdout
from time import time

import serial


def fmt(buf):
    if type(buf) == int:
        return "%02x" % buf
    elif type(buf) == str:
        s = []
        for char in buf:
            s += ["%02x" % ord(char)]
        return " ".join(s)
    else:
        raise NotImplementedError()


def readport(stream, absolute_time=True):
    prevts = time()
    buf = ''
    while True:
        char = stream.read(1)
        if char is None:
            break
        # print "got byte %s" % hex(ord(char))

        now = time()
        delta_t = now - prevts
        prevts = now

        buf += " %02x" % ord(char)

        idx = buf.find("81")
        if idx > -1:
            pdu = buf[:idx+2]
            # print "pdu is: %s" % pdu
            buf = buf[idx+2:]
            yield (now if absolute_time else delta_t, len(pdu), pdu)


if __name__ == "__main__":
    if len(argv) == 2:
        serialdevice = argv[1]
    elif exists("/dev/ttyACM0"):
        serialdevice = "/dev/ttyACM0"
    elif exists("/dev/tty.usbmodem1411"):  # On my laptop
        serialdevice = "/dev/tty.usbmodem1411"
    else:
        print("ERROR: Unable to find a suitable serial device.")
        print("Usage: %s [serialdevice]" % argv[0])
        exit(1)

    print("Using serial device %s" % serialdevice, file=stderr)
    with serial.Serial(port=serialdevice) as ser:
        print("# source: %s" % serialdevice)
        print("# starttime: %s" % datetime.now())
        for record in readport(ser):
            print("%.03f\t%i\t%s" % record)
            stdout.flush()
