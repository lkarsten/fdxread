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
#  Copyright (C) 2016 Lasse Karstensen
#
"""
Scan save files (.nxb) from Nexus Race and output the bitstream
in our regular hexdump format.

References:
* http://www.nexusmarine.se/support/info-and-reg-nexus-software/software-download/
* http://www.chicagomarineelectronics.com/NX2_FDX.htm

Author: Lasse Karstensen <lasse.karstensen@gmail.com>, August 2016
"""
from __future__ import print_function

from pprint import pprint
from sys import argv
from os.path import exists

from bitstring import BitArray

def hexd(data):
    """
    >>> hexd(BitArray(hex="0x1ff"))
    '1f f'
    """
    assert type(data) == BitArray
    s = []
    for i in range(0, data.len, 8):
        s += ["%s%s" % (data[i:i+4].hex, data[i+4:i+8].hex)]
    return " ".join(s)

def nxbdump(inputfile):
    with open(inputfile, "r") as fp:
        stream = BitArray(fp)
        while True:
            idx = stream.find('0x81', bytealigned=True)
            if not idx:
                break
            pdu = stream[:idx[0]+8]
            #print "pdu is: ", hexd(pdu)
            stream = stream[idx[0]+8:]
            yield (0.0, len(pdu) // 8, hexd(pdu))


if __name__ == "__main__":
    if len(argv) < 2 or not exists(argv[-1]):
        print("Usage: %s savefile.nxb" % argv[0])
        exit(1)

    for record in nxbdump(argv[1]):
        try:
            print("%s\t%s\t%s" % (record))
        except IOError:
            exit()
