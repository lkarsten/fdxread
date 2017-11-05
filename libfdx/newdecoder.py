#!/usr/bin/env python3
# .- coding: utf-8 -.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright (C) 2017 Lasse Karstensen
#
"""
FDX decoder
"""
from __future__ import print_function

import doctest
import json
import logging
import unittest
import struct

from binascii import hexlify, unhexlify
from datetime import datetime
from decimal import Decimal
from math import degrees, radians, isnan
from pprint import pprint
from sys import argv, stdin, stdout, stderr
from time import sleep, time

from LatLon23 import LatLon, Latitude, Longitude
#from bitstring import BitArray

def fahr2celcius(temp):
    assert type(temp) in [float, int]
    assert temp < 150
    return (temp - 32) * (5/9.)


def feet2meter(feet):
    assert type(feet) in [float, int]
    assert feet >= 0
    return feet * 0.3048


def uintle(n):
    #print(type(i), dir(i), i)
    if len(n) == 1:
        return struct.unpack("<B", n)[0]
    elif len(n) == 2:
        return struct.unpack("<H", n)[0]
    elif len(n) == 4:
        return struct.unpack("<I", n)[0]

    raise NotImplementedError(len(n))

def nan_uintle(n):
    assert isinstance(n, bytes)  # Should be first
    n2 = uintle(n)
    if len(n) == 1 and n2 == 2**8-1:
        return float('nan')
    if len(n) == 2 and n2 == 2**16-1:
        return float('nan')
    return n2

def degree8(n):
    assert isinstance(n, (int, float))
    if isnan(n):
        return n

    assert n <= 255
    if n == 255 or n == 0:
        return float('nan')
    return n * 360/255.

def degree16(n):
    assert isinstance(n, (int, float))
    assert n <= 2**16
    if n == (2**16)-1 or n == 0:
        return float('nan')
    return n * 360/(2**16)-1


def deci(i):
    return i * 0.01

def milli(i):
    return i * 0.001


# ('msgname', length, fields, finalfunc, 'docstring')
# fields == ((field1, index, size, [castfns]), (field2, ..), ..)
mtype = [None] * 0xff
#mtype[0x00] = ("emptymsg0", 2, (, ), "undocumented")
mtype[0x01] = ("wsi0", 8, (("windspeed", 0, 2, (nan_uintle, deci)),
                           ("awa", 4, 2, (nan_uintle, degree16)),
                           ('aws_lo', 4, 2, (nan_uintle, deci)),
                           ('aws_hi', 4, 2, (uintle, Decimal)),
                          ), None,
    """0x01 04 05 - wsi0 (9 bytes, 3 Hz)

    If only GND10 (no wind or dst200), always 0xffff00000081.
    When the wind box has crashed/browned out, the body is: ffff00000081

    Doing turns and watching the AWA? counter, it does seem to follow reported AWA,
    I think it is the right bitfield, but the scaling is wrong. Revisit.
    """)

mtype[0x07] = ("dst200depth", 7, (("depth", 0, 2, (nan_uintle, deci)),
                                  ("stw", 2, 2, (nan_uintle,)),   # maybe
                                  ("_unknown", 4, 1, (uintle,)) # quality?
                                 ), None,
    """
    mtype[0x070304:
        mdesc = "dst200depth"   # previously "dst200msg3"
        if strbody in ['ffff000081']:
            return
   """)


def condense_position(fdxmsg):
    fdxmsg["lon"] = Longitude(degree=fdxmsg["lon_degree"], minute=fdxmsg["lon_minute"])
    # This is not optimal, but without fix information it is hard to tell. Don't go sailing
    # near 0,0!
    if fdxmsg["lat_degree"] != 0.0 and fdxmsg["lat_minute"] != 0.0 and fdxmsg["lon_degree"] != 0.0 \
                                                                   and fdxmsg["lon_minute"] != 0.0:
        fdxmsg["lat"] = Latitude(degree=fdxmsg["lat_degree"], minute=fdxmsg["lat_minute"])
        fdxmsg["lon"] = Longitude(degree=fdxmsg["lon_degree"], minute=fdxmsg["lon_minute"])
    else:
        fdxmsg["lat"] = float('NaN')
        fdxmsg["lon"] = float('NaN')
    return fdxmsg

mtype[0x20] = ("gpspos", 12, (("lat_degree", 0, 1, (uintle,)), ("lat_minute", 1, 2, (uintle, milli)),
                              ("lon_degree", 3, 1, (uintle,)), ("lon_minute", 4, 2, (uintle, milli,)),
                              ("elevation", 8, 1, (uintle, feet2meter)),
                              #unknown: { index: 9, length: 2 },
                            ), condense_position,
     """20 08 28 gpspos
    # 3b5bc70aa5b3e0005b81
    # lat---      what
    #       LON---    EL

    # XXX: where is the fix information? none, 2d, 3d? Where is hdop?
    Pattern: "20 08 28 3b xx c3 0a yy yy e0 00 zz 81"

    If the GPS is not connected, the body is always: 0x00000000000010001081""")


def only_utctime(fdxmsg):
    if fdxmsg["year"] > 3000:
        return {"utctime": float('nan')}

    return {"utctime": datetime(**fdxmsg)}


mtype[0x24] = ("gpstime", 11, (("hour", 0, 1, (uintle,)), ("minute", 1, 1, (uintle,)),
                               ("second", 2, 1, (uintle,)), ("day", 3, 1, (uintle,)),
                               ("month", 4, 1, (uintle,)), ("year", 5, 2, (uintle, lambda x: x+1992)),
                               # unknown: { index: 6, length: 1 },
                             ),
                             only_utctime,
    """24 07 23 - gpstime (1Hz update rate)

    Pattern:
    "24 07 23 0x xx xx 1b 07 18 00 yz 81".

    x xx xx: went from "8 38 2a" to "a 24 01" in long dumps.

    It wraps after 3b, so for the byte fields only 6 of 8 bits (& 0x3b)
    are in use. Still unknown if all 4 bits are in use in the nibble field.

    Why is this MSB left, when the 13 byte example is MSB right?

    y: there are 16 subsequent frames with a value of y in (0,1,2,3).
    z: appears to be some sort of checksum. no clear pattern.

    Common messages:
      24 07 23 ff ff ff 00 00 00 10 ef 81 (nolock1)
      24 07 23 ff ff ff 00 80 80 10 ef 81 (nolock2)
      24 07 23 0e 31 10 16 08 18 00 29 01 09 15 15

    Flaps data alternates between nolock1 and nolock2 during startup.

    If the GPS is not connected, the sequence counter keeps going up but
    everything else is static:
    ('0x240723', 'gpstime', {'rawbody': '0013391f0cfd00c481', 'uints':
     '036 007 035 000 019 057 031 012 253 000 196'})
""")

mtype[0x21] = ("gpscog", 8, (("sog", 0, 2, (nan_uintle, deci)),
			     ("cog", 3, 1, (nan_uintle, degree8))),
                            None,
 	       """
               0x210425:
               """)

def FDXMessage(msg):
    """
    Decode the contents of an FDX message using the structure defined in `mtype`.
    """
    assert isinstance(msg, bytes)
    if 1:
        print("Raw message for decoding is: %s" % hexlify(msg))

    mdef = mtype[msg[0]]
    if mdef is None:
        logging.info("No handler for mtype=%02x" % msg[0])
        return

    assert msg[-1] == 0x81

    if msg[1] > 75:  # Arbitrary
        logging.error("Skipping suspiciously long message: %s" % hexlify(msg))
        return

    if msg[1] != mdef[1] -4:
        logging.error("Incorrect size on message: %s" % hexlify(msg))
        return

#    assert msg[1] == mdef[1] - 4   # Keep the mdef correct for a future lexer.
    fdxmsg = {}

    for name, b, sz, fnlist in mdef[2]:
        assert isinstance(fnlist, tuple)
        assert len(fnlist) > 0
        if 0:
            print("%s %s: " % (mdef[0], name))

        b += 3 # Skip the 3 byte header
        value = msg[b:b+sz]

        if 0:
            print("%s %s: " % (mdef[0], name))
            print(str(fnlist))
            #print(type(value), hexlify(value))

        for fn in fnlist:
            #print("%s %s: Calling %s(%s)" % (mdef[0], name, fn, str(value)))
            value = fn(value)

        if value != msg[b:b+sz]:
            fdxmsg[name] = value

    if callable(mdef[3]):
        # logging.debug("Final function: %s(%s)" % (mdef[3], fdxmsg))
        fdxmsg = mdef[3](fdxmsg)

    fdxmsg["mdesc"] = mdef[0]
    return fdxmsg


def _b(s):
    assert isinstance(s, str)
    if " " in s:
        s = s.replace(" ", "")
    s = unhexlify(s)
    assert s[1] + 5 == len(s)   # Small sanity check
    return s

class FDXDecodeTest(unittest.TestCase):
    def test_simple(self):
        r = FDXMessage(_b("24 07 23 0f 1b 17 11 08 18 00 02 81"))
        assert isinstance(r["utctime"], datetime)
        assert r["utctime"].isoformat() == "2016-08-17T15:27:23"

    def test_gps_position(self):
        r = FDXMessage(_b("20 08 28 00 00 00 00 00 00 10 00 10 81"))  # No lock
        self.assertEqual(r["mdesc"], "gpspos")
        assert isnan(r["lat"])
        assert isnan(r["lon"])

        r = FDXMessage(_b("20 08 28 3b 21 c3 0a ff 8e e0 00 42 81"))  # Position
        self.assertEqual(r["mdesc"], "gpspos")
        assert isinstance(r["lat"], Latitude)
        assert isinstance(r["lon"], Longitude)
        self.assertAlmostEqual(float(r["lat"].to_string("D")), 59.83255)
        self.assertAlmostEqual(float(r["lon"].to_string("D")), 10.6101166667)

    def test_gps_cogsog(self):
        r = FDXMessage(_b("21 04 25 ff ff 00 00 00 81"))  # No lock
        self.assertEqual(r["mdesc"], "gpscog")
        assert isnan(r["cog"])
        assert isnan(r["sog"])

        r = FDXMessage(_b("21 04 25 0c 01 66 7e 15 81"))  # Steaming ahead
        self.assertEqual(int(r["cog"]), 177)
        self.assertEqual(r["sog"], 2.68)

        # gpstime
        r = FDXMessage(_b("24 07 23 11 26 1f 0f 08 18 00 37 81"))
        self.assertEqual(r["mdesc"], "gpstime")
        assert isinstance(r["utctime"], datetime)

        r = FDXMessage(_b("240723fffffffffffff8f881"))
        assert isnan(r["utctime"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    doctest.testmod()
    unittest.main()
