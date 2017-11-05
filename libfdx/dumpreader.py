#!/usr/bin/env python
# .- coding: utf-8 -.
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
#  Copyright (C) 2016-2017 Lasse Karstensen
#
"""
Parse the variety of dump files (in different formats from evolving
dumpserial.py, plus .nxb files) and output it to stdout.

Expand to multiple lines if a single read returned multiple frames.

Author: Lasse Karstensen <lasse.karstensen@gmail.com>, August 2016
"""
from __future__ import print_function

import logging

from binascii import unhexlify, hexlify
from sys import argv, stderr
from os.path import exists
from pprint import pprint


def readable(s, sep=" "):
    "hexlify with separator"
    assert isinstance(sep, str)
    if hasattr(s, "hex"):  # Python 3
        return sep.join(["%02x" % x for x in s])
    return sep.join(["%02x" % ord(x) for x in s])


def nxbdump(nxbfile, seek=0):
    """
    Scan save files (.nxb) from Nexus Race and output the bytestream.

    References:
    * http://www.nexusmarine.se/support/info-and-reg-nexus-software/software-download/
    * http://www.chicagomarineelectronics.com/NX2_FDX.htm
    """
    # Use some ram and get on with it.
    content = open(nxbfile, "rb").read()
    assert type(content) == bytes

    lastidx = seek
    while True:
        idx = content[lastidx:].find(b'\x81')
        if idx == -1:
            break

        yield (0.0, content[lastidx:lastidx+idx+1])
        lastidx = lastidx + idx + 1

def dumpreader(inputfile, seek=0):
    fp = open(inputfile, "r")
    seeklen = 0

    for line in fp:
        if line.startswith("#"):
            continue

        try:
            ts, mlen, pdu = line.split(None, 2)
            assert len(pdu) in [3*int(mlen), int(mlen)]
        except (ValueError, AssertionError) as e:
            logging.warning("dumpreader(): %s: %s" % (str(e), line))
            raise

        pdu = pdu.strip()
        pdu = pdu.replace(" ", "")
        # Decode the hex encoding and give us bytes().
        pdu = unhexlify(pdu)

        lastidx = 0
        while True:
            idx = pdu[lastidx:].find(b'\x81')
            if idx == -1:
                break

            frame = pdu[lastidx:lastidx+idx+1]
            lastidx = lastidx + idx + 1

            if seeklen < seek:
                seeklen += len(frame)
                continue

            ts = float(ts)

            yield (ts, frame)

            if ts < 2.0:  # The format has differential time stamps.
                # Subsequent frames in a single read arrived without delay.
                ts = 0.0

def tokenize(reader):
    """
    Tokenize a data stream into frames using the 0x81 marker and
    embedded frame length.
    """
    buf = bytes()

    for ts, chunk in reader:
        assert isinstance(ts, float)
        assert isinstance(chunk, bytes)
        buf += chunk
        #print("buf is: %s" % hexlify(buf))

        if len(buf) < 4:
            continue

        frameidx = None
        stopidx = None

        for startidx in range(0, len(buf) - 2):
            if buf[startidx] != 0x81:  # No synchronism, skip some bytes.
                continue

            if buf[startidx:].find(b"\x81") < 0:  # No new marker means no complete messages. Read some more.
                logging.debug("No marker in buffer, reading some more")
                break

            # Format: "\x81 sender framelen mnum <pdu> \x81"
            # b'81120416a404c5bfda81'
            #       ll  1122334455

            framelen = int(buf[startidx+2])
            assert framelen > 0
            assert framelen < 255

            stopidx = startidx + framelen + 5
            if stopidx > len(buf[startidx:])-1:
                # This framelen pointed past our buffer, so not correct. Skip until next probable.
                continue

            if 0:
                possible_frame = buf[startidx:stopidx+1]
                print("len=%s %s %s" % (startidx, stopidx, hexlify(possible_frame)))

            if buf[stopidx] == 0x81:  # Most likely we have found a valid frame.
                frameidx = startidx
                break

        if frameidx is not None:
            #logging.debug("Yielding %s" % hexlify(buf[frameidx+1:stopidx]))
            yield ts, buf[startidx+1:stopidx]
            buf = buf[stopidx:]
            frameidx = None
            stopidx = None

        if len(buf) > 1024:  # Should be suitable.
            logging.error("buf grew, most likely stuck. Resetting to recover")
            buf = bytes()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if "python" in argv:
        argv.pop(argv.index("python"))

    if len(argv) < 2 or not exists(argv[1]):
        print("Usage: %s savefile.(nxb|fdx|dump)" % argv[0], file=stderr)
        exit(1)
    savefile = argv[1]

    logging.debug("Reading %s" % savefile)

    seek = 0
    if len(argv) == 3:
        seek = int(argv[2])

    if ".nxb" in savefile:
        reader = nxbdump(savefile, seek=seek)
    else:
        reader = dumpreader(savefile, seek=seek)

    for ts, frame in tokenize(reader):
        try:
            print("%s\t%s" % (ts, readable(frame)))
        except IOError:
            exit()
