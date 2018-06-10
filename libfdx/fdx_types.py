#!/usr/bin/env python3
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
# Copyright (C) 2018 Lasse Karstensen
#
"""
FDX types.
"""
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

from utils import hexlify_sep, unhexlify_sep

def fahr2celcius(temp):
    assert type(temp) in [float, int]
    assert temp < 150
    return (temp - 32) * (5/9.)


def feet2meter(feet):
    assert type(feet) in [float, int]
    assert feet >= 0
    return feet * 0.3048

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



def compose_header(obj):
    return struct.pack("<BBB", obj.mtype, obj.mlen, 0xff)

def mask_checksum(msg):
    # Mask checksums until that is figured out.
    return msg[:2] + b'\xff' + msg[3:]



class EmptyMessage0(object):
    """
    EmptyMessage0. No idea.
    """
    mtype = 0x02
    mlen = 0xf

    def __repr__(self):
        return "<EmptyMessage0>"

    @classmethod
    def unpack(cls, sentence):
        assert isinstance(sentence, bytes)
        return cls()

    def pack(self):
        raise NotImplementedError()

class WindMessage(object):
    """0x01 04 05 - wsi0 (9 bytes, 3 Hz)

    If only GND10 (no wind or dst200), always 0xffff00000081.
    When the wind box has crashed/browned out, the body is: ffff00000081

    Doing turns and watching the AWA? counter, it does seem to follow reported AWA,
    I think it is the right bitfield, but the scaling is wrong. Revisit.
    """
    mtype = 0x01
    mlen = 0x04
    def __init__(self):
        self.windspeed = float("nan")
        self.awa = float("nan")
        self.aws_lo = float("nan")
        self.aws_hi = float("nan")

    def __repr__(self):
        return "<WindMessage windspeed=%g kts awa=%g dgr aws=%g kts other=%g>" % \
               (self.windspeed, self.awa, self.aws_lo, self.aws_hi)

    @classmethod
    def unpack(cls, sentence):
        assert isinstance(sentence, bytes)
        assert sentence[0] == cls.mtype
        assert len(sentence) == cls.mlen + 5
        obj = cls()
        #print(hexlify_sep(sentence), "  ", len(sentence))
        if sentence[3:7] == bytes(b'\xff\xff\x00\x00'):
            return obj   # Leaving everything at NaN

        windspeed = struct.unpack("<H", sentence[3:5])[0]
        obj.windspeed = windspeed * 0.01

        awa, aws_lo, aws_hi = struct.unpack("<BBB", sentence[5:8])
        obj.awa = degree16(awa)
        obj.aws_lo = aws_lo *  0.01
        return obj

    def pack(self):
        raise NotImplementedError()


class Paddlewheel(object):
    """
# ('msgname', length, fields, finalfunc, 'docstring')
# fields == ((field1, index, size, [castfns]), (field2, ..), ..)
handler = {}
#handler[0x07] = ("dst200depth", 7, (("depth", 0, 2, (nan_uintle, deci)),
#                                  ("stw", 2, 2, (nan_uintle,)),   # maybe
#                                  ("_unknown", 4, 1, (uintle,)) # quality?
#                                 ), None,
    """
    mtype = 0x07
    mlen = 0x03
    def __init__(self):
        self.stw = float("nan")
        self.depth = float("nan")

    def __repr__(self):
        return "<Paddlewheel stw=%gkts depth=%gm" % (self.stw, self.depth)

    @classmethod
    def unpack(cls, sentence):
        assert isinstance(sentence, bytes)
        assert sentence[0] == cls.mtype
        assert len(sentence) == cls.mlen + 5
        obj = cls()
        if sentence[3:7] == bytes(b'\xff\xff\x00\x00'):
            return obj   # Leaving everything at NaN

        depth = struct.unpack("<H", sentence[3:5])[0]
        obj.depth = depth * 0.01

        stw = struct.unpack("<H", sentence[5:7])[0]
        obj.stw = stw * 0.001  # XXX: Verify

        return obj

    def pack(self):
        raise NotImplementedError()



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

#handler[0x20] = ("gpspos", 12, (("lat_degree", 0, 1, (uintle,)), ("lat_minute", 1, 2, (uintle, milli)),
#                              ("lon_degree", 3, 1, (uintle,)), ("lon_minute", 4, 2, (uintle, milli,)),
#                              ("elevation", 8, 1, (uintle, feet2meter)),
#                              #unknown: { index: 9, length: 2 },
#                            ), condense_position,
#     """20 08 28 gpspos
#    # 3b5bc70aa5b3e0005b81
#    # lat---      what
#    #       LON---    EL
#
#    # XXX: where is the fix information? none, 2d, 3d? Where is hdop?
#    Pattern: "20 08 28 3b xx c3 0a yy yy e0 00 zz 81"
#
#    If the GPS is not connected, the body is always: 0x00000000000010001081""")
#

class GpsTime(object):
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
"""
    mtype = 0x24
    mlen = 0x7

    def __init__(self):
        self.hour = float("NaN")
        self.minute = float("NaN")
        self.second = float("NaN")

        self.day = float("NaN")
        self.month = float("NaN")
        self.year = float("NaN")

    def __repr__(self):
        return "<GpsTime %4s-%02g-%02g %02g:%02g:%02g>" % \
               (self.year, self.month, self.day,
                self.hour, self.minute, self.second)

    @classmethod
    def from_datetime(cls, dt):
        obj = cls()
        assert isinstance(dt, datetime)
        for key in ["hour", "minute", "second", "year", "month", "day"]:
            setattr(obj, key, getattr(dt, key))
        return obj

    @classmethod
    def unpack(cls, sentence):
        assert isinstance(sentence, bytes)
        obj = cls()
        assert len(sentence) == obj.mlen + 5

        if sentence[3:8] == bytes(b'\xff'*5):
            return obj   # Leaving everything at NaN

        obj.hour, obj.minute, obj.second, obj.day, obj.month = struct.unpack("<BBBBB", sentence[3:8])
        year = struct.unpack("<H", sentence[8:10])[0]
        obj.year = year + 1992
        assert obj.year < 3000
        assert obj.year > 1992
        #self.unknown = sentence[10:11]
        return obj

    def to_datetime(self):
        if isnan(self.hour):
            raise ValueError("not initialized")
        return datetime(year=self.year, month=self.month, day=self.day,
                        hour=self.hour, minute=self.minute, second=self.second)

    def pack(self):
        if isnan(self.hour):
            raise AttributeError("not initialized")
        fdx = compose_header(self)
        fdx += struct.pack("<BBBBB", self.hour, self.minute, self.second, self.day, self.month)
        fdx += struct.pack("<H", self.year-1992)
        fdx += struct.pack("<B", 0xff)  # No idea
        fdx += b'\x81'
        return fdx


class GpsMovement(object):
    """

    """
    mtype = 0x21
    mlen = 0x5

    def __init__(self):
        self.sog = float("NaN")
        self.cog = float("NaN")

    def __repr__(self):
        return "<GpsMovement sog=%gkt cog=%gdgr>" % (self.sog, self.cog)

    @classmethod
    def unpack(cls, sentence):
        assert isinstance(sentence, bytes)
        obj = cls()
        assert len(sentence) == obj.mlen + 4

        if sentence[3:7] == bytes(b'\xff\xff\x00\x00'):
            return obj   # Leaving everything at NaN

        sog, cog = struct.unpack("<HH", sentence[3:7])
        obj.sog = sog * 0.01
        assert obj.sog < 50

        obj.cog = degree16(cog)
        assert obj.cog < 361
        return obj

    def pack(self):
        raise NotImplementedError()



_b = unhexlify_sep

class TypeTests(unittest.TestCase):
    def test_gpstime(self):
        cmp_fmt = "%Y-%m-%d__%H:%M:%s"
        sample_message = mask_checksum(unhexlify_sep("24 07 23 11 26 1f 0f 08 18 00 ff 81"))

        t = GpsTime()
        del t

        # datetime constructor
        then = datetime.now()
        then_gpstime = GpsTime.from_datetime(then)
        assert then.strftime(cmp_fmt) == then_gpstime.to_datetime().strftime(cmp_fmt)

        # fdx constructor
        gpstime_fdx = GpsTime.unpack(sample_message)
        self.assertEqual(sample_message, gpstime_fdx.pack())

        # No time lock
        t = GpsTime.unpack(mask_checksum(unhexlify("240723fffffffffffff8f881")))
        # XXX: The "f8 f8" octets last needs a revisit.
        self.assertTrue(isnan(t.hour))

    def test_gpsmovement(self):
        m = GpsMovement.unpack(mask_checksum(unhexlify_sep("21 04 25 0c 01 66 7e 15 81")))  # Steaming ahead
        self.assertAlmostEqual(m.cog, 176.747802734375)
        self.assertEqual(m.sog, 2.68)

        r = GpsMovement.unpack(mask_checksum(unhexlify_sep("21 04 25 ff ff 00 00 00 81")))  # No lock
        assert isnan(r.cog)
        assert isnan(r.sog)

    def test_windmessage(self):
        sample_message = mask_checksum(unhexlify_sep("01 04 05 be 00 96 b9 91 81"))
        m = WindMessage.unpack(sample_message)
        self.assertTrue(m.windspeed > 0)

        empty_message = mask_checksum(unhexlify("010405ffff00000081"))
        m_empty = WindMessage.unpack(empty_message)
        assert isnan(m_empty.windspeed)

    def test_paddlewheel(self):
        sample_message = mask_checksum(unhexlify_sep("07 03 04 0f 02 00 0d 81"))
        m = Paddlewheel.unpack(sample_message)
        self.assertTrue(m.depth > 0)
        self.assertTrue(m.stw < 30)

        empty_message = mask_checksum(unhexlify_sep("07 03 04 ff ff 00 00 81"))
        m_empty = Paddlewheel.unpack(empty_message)
        assert isnan(m_empty.depth)


    def xtest_gpsposition(self):
        r = FDXMessage(_b("20 08 28 3b 21 c3 0a ff 8e e0 00 42 81"))  # Position
        self.assertEqual(r.fdxmsg["mdesc"], "gpspos")
        assert isinstance(r.fdxmsg["lat"], Latitude)
        assert isinstance(r.fdxmsg["lon"], Longitude)
        self.assertAlmostEqual(float(r.fdxmsg["lat"].to_string("D")), 59.83255)
        self.assertAlmostEqual(float(r.fdxmsg["lon"].to_string("D")), 10.6101166667)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
