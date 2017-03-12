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
Parse the variety of hexdump dump files (in different formats from evolving
dumpserial.py) and output it to stdout.

Expand to multiple lines if a single read returned multiple frames.

Author: Lasse Karstensen <lasse.karstensen@gmail.com>, August 2016
"""
from __future__ import print_function

import logging

from sys import argv, stderr
from os.path import exists
from pprint import pprint

def dumpreader(inputfile, trim=False, seek=0):
    fp = open(inputfile)
    fp.seek(seek)

    for line in fp.readlines():
        if line.startswith("#"):
            continue

        try:
            ts, mlen, pdu = line.split(None, 2)
        except ValueError as e:
            logging.warning("%s: %s" % (str(e), line))
            raise

        for frame in pdu.split(" 81"):
            frame = frame.strip()
            if frame is "":
                continue

            frame += " 81"

            s = frame.replace(" ", "")
            assert len(s) % 2 == 0

            if trim:
                frame = frame.replace(" ", "")

            yield (ts, len(s) // 2, frame)

            if float(ts) < 2.0:  # The format has differential time stamps.
                # Subsequent frames in a single read arrived without delay.
                ts = "0.000000"


if __name__ == "__main__":
    if len(argv) < 2 or not exists(argv[-1]):
        print("Usage: %s dumpfile.fdx" % argv[0], file=stderr)
        exit(1)

    for record in dumpreader(argv[1]):
        try:
            print("%s\t%s\t%s" % (record))
        except IOError:
            exit()
