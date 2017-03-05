#!/usr/bin/env python
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
# Copyright (C) 2016-2017 Lasse Karstensen
#
"""
FDX decoder
"""
from __future__ import print_function

import doctest
import json
import logging
import unittest
from binascii import hexlify
from datetime import datetime
from math import degrees, radians, isnan
from pprint import pprint
from sys import argv, stdin, stdout, stderr
from time import sleep, time

from LatLon23 import LatLon, Latitude, Longitude
from bitstring import BitArray

from .dumpreader import dumpreader
from .nxbdump import nxbdump

class DataError(Exception):
    pass

class FailedAssumptionError(Exception):
    pass

def fahr2celcius(temp):
    assert type(temp) in [float, int]
    assert temp < 150
    return (temp - 32) * (5/9.)

def checklength(pdu, speclen):
    "pdu is hex encoded, 4 bits per char."
    assert type(pdu) == str
    assert type(speclen) == int

    assert len(pdu) >= 3*2
    assert len(pdu) % 2 == 0

    if len(pdu)/2 != speclen:
        raise DataError("mtype=0x%s: Incorrect length, expected %s. (got %s) - body: %s" %
                        (pdu[:3*2], speclen, len(pdu)/2, pdu[3*2:]))
    return BitArray(hex=pdu[3*2:-1*2])


def intdecoder(body, width=8, signed=False):
    assert type(body) == BitArray
    assert width % 8 == 0
    assert width in [8, 16]  # for now, due to fmt.
    fmt = "%03i"
    if width == 16:
        fmt = "%06i"

    s = []
    for idx in range(0, body.len, width):
        value = body[idx:idx+width]
        s += [fmt % (value.intle if signed else value.uintle)]
    return [("ints", " ".join(s)), ('strbody', body.hex)]


def FDXDecode(pdu):
    assert type(pdu) == str

    if " " in pdu:
        pdu = pdu.replace(" ", "")

    if pdu[-2:] != '81':
        raise DataError("missing tailer")

    if len(pdu) < 6:
        raise DataError("short message <6 bytes")

    mtype = int(pdu[:6], 16)
    strbody = pdu[6:]
    assert len(strbody) % 2 == 0
    # This is bit confusing, as pdu has 4 bits per char,
    # so this is half of the strlen of the pdu.
    # Warranted because we use mlen from the spec to find the right
    # message parser.
    mlen = len(pdu) / 2

#    print mtype, mlen, strbody

    # Some random messages seen in dump, remove clutter.
    skiplist = [0x811504, 0xb2e000, 0x0e008f,
                0x0c008d, 0xc70a2f, 0xc70a92]
    if mtype in skiplist:
        if len(strbody) > 1*2:  # Small backstop measure.
            raise FailedAssumptionError("body should be small (got '%s')" % strbody)
        return

    if 0:
        body = BitArray(hex=pdu[6:])
        print(hex(mtype), body)

    if mtype == 0x000202:
        mdesc = "emptymsg0"
        keys = []
        if strbody not in ['ffff0081', '00000081']:
            keys = [('fault', "unexpected body (got %s, expected 0xffff0081 or 0x00000081" %
                     (strbody))]
#        else:
#            return

    elif mtype == 0x010405:
        mdesc = "gnd10msg3"
        body = checklength(pdu, 9)
        #keys = intdecoder(body, width=16)
        keys = []

        windspeed = body[0:16].uintle
        if windspeed == 2**16-1:
            windspeed = float('NaN')
        windspeed *= 0.01

        awa = body[16:32].uintle * (360.0 / 2**16)

        keys += [('awa', awa)]
        keys += [('aws_hi', windspeed)]
        keys += [('aws_lo', body[32:46].uintle * 0.01)]

    elif mtype == 0x020301:
        mdesc = "dst200depth2"
        if strbody in ['ffff000081', '0000000081']:
            return
        body = checklength(pdu, 8)

        # This is not depth, it jumps around too much.
        depth = body[0:16].uintle
        if depth == 2**16-1:
            depth = float("NaN")
        keys = [('not_depth', depth * 0.01)]

        #stw = body[16:32].uintle
        #if stw == 2**16-1:
        #    stw = float("NaN")
        #keys = [('stw?', "%.2f" % (stw * 0.001))]
        keys += intdecoder(body[16:], width=16)

    elif mtype == 0x030102:
        mdesc = "emptymsg0"
        body = checklength(pdu, 6)
        keys = intdecoder(body)  # XX
        if body.int != 0:
            raise FailedAssumptionError(mdesc, "body should be zero (got %s)" % body)
        return

    elif mtype == 0x070304:
        mdesc = "dst200depth"   # previously "dst200msg3"
        if strbody in ['ffff000081']:
            return
        body = checklength(pdu, 8)
        keys = intdecoder(body, width=16)
        # depth is confirmed identical to onboard display (5.3m.) needs
        # verification on deeper waters.
        depth = body[0:16].uintle
        if depth == 2**16-1:
            depth = float("NaN")

        keys += [('depth', depth * 0.01)]
        keys += [('stw', body[16:24].uintle)]  # maybe
        keys += [('unknown2', body[24:32].uintle)] # quality?

    elif mtype == 0x080109:
        mdesc = "static1s"  # ex windmsg0, stalemsg0
        body = checklength(pdu, 6)
        xx = body[0:8].uintle
        yy = body[8:16].uintle
        keys = [('xx', xx)]
        if xx != yy:
            keys += [('fault', "xx != yy (got %s, expected %s)" % (xx, yy))]

    elif mtype == 0x090108:
        mdesc = "windsignal"
        body = checklength(pdu, 6)
        keys = intdecoder(body, width=8)
        xx = body[0:8].uintle
        yy = body[8:16].uintle
        if xx != yy:
            raise FailedAssumptionError(mdesc, "xx != yy (got %s, expected %s)" % (xx, yy))
        keys = [('xx', xx)]

    elif mtype == 0x110213:
        mdesc = "windstale"
        if strbody == "00000081":
            return
        body = checklength(pdu, 7)
        keys = intdecoder(body, width=8)

    elif mtype == 0x120416:
        mdesc = "winddup"
        return   # data is almost identical to gnd10msg3. less clutter.
        body = checklength(pdu, 9)
        keys = intdecoder(body, width=16)

    elif mtype == 0x130211:
        mdesc = "gpsping"
        body = checklength(pdu, 7)
        keys = intdecoder(body)
        keys += [("maybe", body[0:16].uintle)]

    elif mtype == 0x150411:
        mdesc = "gnd10msg2"
        body = checklength(pdu, 9)
        keys = intdecoder(body, width=16)

        keys += [("u1", body[0:16].uintle)]
        keys += [("u2", body[16:32].uintle)]

    elif mtype == 0x170512:
        mdesc = "static2s_two"
        if strbody != '0080ffffff7f81':
            keys = [('fault', "Non-static body seen. (got %s, expected %x)" %
                                        (strbody, 0x0080ffffff7f81))]
        else:
            return   # no use in logging it. static.

    elif mtype == 0x1a041e:
        mdesc = "environment"

        if strbody == 'ffffff40bf81':
            return   # XXX: NaN instead?

        body = checklength(pdu, 9)
        keys = []
        #keys = intdecoder(body)

        pressure = body[0:16].uintle * 0.01
        keys += [('airpressure', pressure)]

        yy = strbody[4:6]  # save us a bitwise lookup.
        if yy != 'ff':
            keys += [("fault", "yy is 0x%s, expected 0xff" % yy)]
        null = strbody[6:8]   # body[24:32].uintle  # zz
        if null != '00':
            keys += [("fault", "null is 0x%s, expected 0x00" % null)]
        temp = body[32:40].uintle  # zz
        # These are not right. It is never 41 degrees celcius in Norway ;-)
        keys += [('temp_f', temp)]
        keys += [('temp_c', fahr2celcius(temp))]

    elif mtype == 0x1c031f:
        mdesc = "wind40s"
        body = checklength(pdu, 8)
        keys = intdecoder(body)
        xx = body[0:8].uintle
        XX = body[8:16].uintle
        yy = body[8:16].uintle

#        yy = body[16:32].uintle
#        keys = [('xx', xx), ('yy', yy)]
    elif mtype == 0x200828:
        mdesc = "gpspos"
        if mlen < 13:
            return
        body = checklength(pdu, 13)
        # 1471551078.44 ('0x200828', 'gpsmsg1', {'strbody': '3b1ccb0a51b2e000e581', 'uints': '059 028 203 010 081 178 224 000 229'})
        # 0.0 ('0x200828', 'gpspos', {'strbody': '00000000000010001081',    -- # before position lock was attained
        # where is fix information? none, 2d, 3d?
        # hdop? elevation?
        keys = intdecoder(body[48:], width=8)
        if strbody == "00000000000010001081":
            keys += [("elevation", float("NaN")),
                     ("lat", float("NaN")),
                     ("lon", float("NaN")),
                    ]
        else:
            lat = Latitude(degree=body[0:8].uintle, minute=body[8:24].uintle * 0.001)
            lon = Longitude(degree=body[24:32].uintle, minute=body[32:48].uintle * 0.001)
            keys += [("elevation", body[64:72].uintle)]  # in feet
            keys += [("lat", lat), ("lon", lon)]
            #keys += [("gmapspos", "https://www.google.com/maps?ie=UTF8&hq&q=%s,%s+(Point)&z=11" % (lat, lon))]

        # The gnd10-faked gps position message is 0x00000000000010001081, which
        # makes the last octet and the third last octet stand out.
        keys += [("fix1", body[48:56].uintle)]
        keys += [("null", body[56:64].uintle)]

    elif mtype == 0x210425:
        mdesc = "gpscog"
        body = checklength(pdu, 9)
        if strbody == "ffff00000081":  # No GPS lock
            cog = float("NaN")
            sog = float("NaN")
        else:
            cog = body[24:32].uintle
            sog = body[0:16].uintle

        # Something is off with COG, it is 255 too often. Not sure why.
        # Better safe than sorry (== grounded on the rocks)
        if cog == 255:
            cog = float("NaN")

        # Scale the values.
        cog *= 360/255.
        sog *= 0.01

        keys = [('cog', cog), ('sog', sog),
                ('unknown', body[32:].uintle)]

    elif mtype == 0x230526:
        mdesc = "static2s"
        keys = []
        if strbody != 'ffff0000808081':
            keys = [('fault', "Non-static body seen. (got %s, expected %x)" %
                              (strbody, 0xffff0000808081))]
        else:
            # No need to log it if it is the static body.
            return

    elif mtype == 0x240723:
        mdesc = "gpstime"
        body = checklength(pdu, 12)
        try:
            hour = body[0:8].uintle
            minute = body[8:16].uintle
            second = body[16:24].uintle
            day = body[24:32].uintle
            month = body[32:40].uintle

            # This can't be right, can it?? :-)
            year = 1992 + body[40:56].uintle  # XXX: year?? 024 000 == 2016??
            assert year < 3000
            assert year > 2000
            ts = datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)
            keys = [("utctime", ts.isoformat())]   # XXX: Cast to string later
            keys += [("what?", body[56:64].uintle)]

        except (ValueError, AssertionError) as e:
            keys = [('ParseFault', str(e))]

    elif mtype == 0x2c022e:
        mdesc = "dst200msg0"
        body = checklength(pdu, 7)
        keys = intdecoder(body)
    elif mtype == 0x2d0528:
        mdesc = "service0"
        body = checklength(pdu, 10)
        keys = intdecoder(body)
    elif mtype == 0x310938:
        mdesc = "windmsg7"
        body = checklength(pdu, 14)
        keys = intdecoder(body)

    elif mtype == 0x350336:
        mdesc = "windmsg8"
        body = checklength(pdu, 8)
        keys = intdecoder(body)

    elif mtype == 0x700373:
        mdesc = "windmsg3"
        body = checklength(pdu, 8)
        keys = intdecoder(body, width=16)
        keys += [('xx', radians(body[0:16].uintle) * 0.0001)]
        keys += [('yy', radians(body[16:32].uintle) * 0.0001)]

    elif mtype == 0x769e81:
        mdesc = "bootup0"
        body = checklength(pdu, 3)
        keys = intdecoder(body, width=8)
    else:
        raise NotImplementedError("handler for 0x%06x mlen=%s: %s" % (mtype, mlen, pdu))

    keys += [('strbody', strbody)]
    keys += [('mdesc', mdesc)]
    return dict(keys)


class FDXDecodeTest(unittest.TestCase):
    def test_simple(self):
        with self.assertRaises(DataError):
            FDXDecode("81")

        with self.assertRaises(DataError):
            FDXDecode("81 81")

        r = FDXDecode("24 07 23 0f 1b 17 11 08 18 00 02 81")
        assert r["utctime"] == "2016-08-17T15:27:23"

    def test_gps_position(self):
        r = FDXDecode("20 08 28 00 00 00 00 00 00 10 00 10 81")  # No lock
        self.assertEqual(r["mdesc"], "gpspos")
        assert isnan(r["lat"])
        assert isnan(r["lon"])

        r = FDXDecode("20 08 28 3b 21 c3 0a ff 8e e0 00 42 81")  # Some position
        self.assertEqual(r["mdesc"], "gpspos")
        assert isinstance(r["lat"], Latitude)
        assert isinstance(r["lon"], Longitude)
        self.assertAlmostEqual(float(r["lat"].to_string("D")), 59.83255)
        self.assertAlmostEqual(float(r["lon"].to_string("D")), 10.6101166667)

    def test_gps_cogsog(self):
        r = FDXDecode("21 04 25 ff ff 00 00 00 81")  # No lock
        self.assertEqual(r["mdesc"], "gpscog")
        assert isnan(r["cog"])
        assert isnan(r["sog"])

        r = FDXDecode("21 04 25 0c 01 66 7e 15 81 ")  # Steaming ahead
        self.assertEqual(int(r["cog"]), 177)
        self.assertEqual(r["sog"], 2.68)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    doctest.testmod()
    unittest.main()
