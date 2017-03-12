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

from binascii import unhexlify
from sys import argv, stderr
from os.path import exists
from pprint import pprint


def readable(s, sep=" "):
    "hexlify with separator"
    assert isinstance(sep, str)
    if hasattr(s, "hex"):  # Python 3
        return sep.join(["%02x" % x for x in s])
    return sep.join(["%02x" % ord(x) for x in s])


def nxbdump(nxbfile):
    """
    Scan save files (.nxb) from Nexus Race and output the bitstream.

    References:
    * http://www.nexusmarine.se/support/info-and-reg-nexus-software/software-download/
    * http://www.chicagomarineelectronics.com/NX2_FDX.htm
    """
    # Use some ram and get on with it.
    content = open(nxbfile, "rb").read()
    assert type(content) == bytes

    lastidx = 0
    while True:
        idx = content[lastidx:].find(b'\x81')
        if idx == -1:
            break

        yield (0.0, content[lastidx:lastidx+idx+1])
        lastidx = lastidx + idx + 1


def dumpreader(inputfile, seek=0):
    fp = open(inputfile, "r")
    if seek != 0:
        fp.seek(seek)

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
            yield (ts, pdu[lastidx:lastidx+idx+1])

            lastidx = lastidx + idx + 1
            if float(ts) < 2.0:  # The format has differential time stamps.
                # Subsequent frames in a single read arrived without delay.
                ts = "0.000000"


if __name__ == "__main__":
    savefile = argv[-1]
    if len(argv) < 2 or not exists(argv[-1]):
        print("Usage: %s savefile.(nxb|fdx|dump)" % argv[0], file=stderr)
        exit(1)

    if ".nxb" in savefile:
        records = nxbdump(savefile)
    else:
        records = dumpreader(savefile)

    for ts, frame in records:
        try:
            print("%s\t%s" % (ts, readable(frame)))
        except IOError:
            exit()
