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


def feet2meter(feet):
    assert type(feet) in [float, int]
    assert feet >= 0
    return feet * 0.3048


def checklength(pdu, speclen):
    "pdu is hex encoded, 4 bits per char."
    assert type(pdu) == str
    assert speclen is None or isinstance(speclen, int)

    assert len(pdu) >= 3*2
    assert len(pdu) % 2 == 0

    if speclen is not None:
        if len(pdu)/2 != speclen:
            raise DataError("mtype=0x%s: Incorrect length %s (got %s) body: %s"
                            % (pdu[:3*2], speclen, len(pdu)/2, pdu[3*2:]))
    return BitArray(hex=pdu[3*2:-1*2])


def intdecoder(body, width=8, signed=False):
    assert type(body) == BitArray
    assert width % 8 == 0
    assert width in [8, 16]  # for now, due to fmt.
    fmt = "%03i"
    if width == 16:
        fmt = "%05i"

    s = []
    for idx in range(0, body.len, width):
        value = body[idx:idx+width]
        s += [fmt % (value.intle if signed else value.uintle)]
    return [("ints", " ".join(s)), ('strbody', body.hex)]

def disect(pdu):
    body = checklength(pdu, None)
    return intdecoder(body)


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
    keys = []
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
            raise FailedAssumptionError("body should be small (got '%s')" %
                                        strbody)
        return

    if 0:
        body = BitArray(hex=pdu[6:])
        print(hex(mtype), body)

    if mtype == 0x000202:
        mdesc = "emptymsg0"
        if strbody in ['ffff0081', '00000081']:
            # No use in cluttering the output.
            return None
        body = checklength(pdu, None)
        keys = intdecoder(body, width=16)

    elif mtype == 0x010405:
        mdesc = "gnd10msg3"
        body = checklength(pdu, 9)
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
        """02 03 01 - dst200temp (8 bytes, 5 Hz update rate)
        Previously: dst200msg1, dst200depth2

        Reduced set of distinct bodies seen when DST200 is disconnected:
           2 '0600000681'})
          10 '0800000881'})
           6 '0a00000a81'})
           4 '0c00000c81'})
           3 '0e00000e81'})
          44 '1015000581'})
          56 '1016000681'})
          25 'a90100a881'})
         350 'ffff000081'})
        Very wide set of values seen with DST200 connected. Origin most
        likely DST200.
        """
        mdesc = "dst200temp"

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
        mdesc = "emptymsg3"
        if len(strbody) == 0:  # Zero data bytes, as seen in early dumps.
            return

        if (len(pdu) / 2 == 6):  # Two data bytes, seen in Baker dataset.
            if strbody in ["000081", "020281"]:
                return  # Nothing to report if always the same.

        body = checklength(pdu, None)
        keys = intdecoder(body)

    elif mtype == 0x050207:
        """05 02 07 - baker_alpha (2-3Hz)

        Unknown 7 byte frame type seen in the Baker data file.

        Pattern 05 02 07 xx ff yy 81
        211 < xx < 259,
        6 < yy < 55. usually jumps in increments of ~10.

        """
        mdesc = "baker_alpha"
        body = checklength(pdu, 7)

        if body[8:16].uintle != 0xff:
            raise FailedAssumptionError(mdesc, "Middle char not 0xff, but %s" % str(body[8:16]))
        keys = intdecoder(body)

    elif mtype == 0x060204:
        """06 02 04 - baker_bravo (n Hz)

        Unknown 7 byte frame type seen in the Baker data file.

        24 ff db 81
        2d ff d2 81
        1a ff e5 81
        10 ff ef 81

        Pattern: 06 02 04 xx ff yy 81

        xx < 100
        160 < yy < 239

        Same ~10 increments as 0x050207.
        """
        mdesc = "baker_bravo"
        body = checklength(pdu, 7)
        keys = intdecoder(body)
        if body[8:16].uintle != 0xff:
            raise FailedAssumptionError(mdesc, "Middle char not 0xff, but %s" % str(body[8:16]))


    elif mtype == 0x070304:
        mdesc = "dst200depth"   # previously "dst200msg3"
        if strbody in ['ffff000081']:
            return
        body = checklength(pdu, 8)
        keys = intdecoder(body, width=16)
        depth = body[0:16].uintle
        if depth == 2**16-1:
            depth = float("NaN")

        keys += [('depth', depth * 0.01)]
        keys += [('stw', body[16:24].uintle)]  # maybe
        keys += [('unknown2', body[24:32].uintle)]  # quality?

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
            raise FailedAssumptionError(mdesc, "xx != yy (got %s, expect %s)"
                                        % (xx, yy))
        keys = [('xx', xx)]


    elif mtype == 0x0a040e:
        """0a 04 0e - baker_echo (0.5 Hz)

        Unknown 9 byte message from the Baker data set.

        Always 00003e023c81.
        """
        mdesc = "baker_echo"
        if strbody == "00003e023c81":
            return
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "00003e023c81"))


    elif mtype == 0x0f040b:
        """0f 04 0b - baker_charlie (1 Hz)

        Unknown 9 byte frame type seen in the Baker data file.

        Always 0f 04 0b 66 53 a6 04 97 81.
        """
        mdesc = "baker_charlie"
        if strbody == "6653a6049781":
            return
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "6653a6049781"))


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

    elif mtype == 0x1f051a:
        """1f 05 1a - baker_foxtrot (1 Hz)

        Unknown 10 byte frame type seen in the Baker data file.

        Always 0000ffff000081.
        """
        mdesc = "baker_foxtrot"
        if strbody == "0000ffff000081":
            return
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "0000ffff000081"))


    elif mtype == 0x200828:
        """20 08 28" gpspos (13 bytes)

        Pattern: "20 08 28 3b xx c3 0a yy yy e0 00 zz 81"

        xx moves from db..ff in dataset. _does not_ change "3b" as would be expected from 12byte message pattern.
        yy yy - counter. 00..ff left, 8e..8f seen on right.
        zz - checksum?

        There are messages starting with the same preamble, which most likely are transmission errors:
        ```
        $ cut -f2- snippet2 | grep "20 08 28 3" | cut -f1 | sort -n | uniq -c | sort -rn
           5866 13
             24 8
             15 5
              6 12
        ```

        If the GPS is not connected, the body is always: 0x00000000000010001081
        """
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
            lat = Latitude(degree=body[0:8].uintle,
                           minute=body[8:24].uintle * 0.001)
            lon = Longitude(degree=body[24:32].uintle,
                            minute=body[32:48].uintle * 0.001)

            keys += [("elevation", feet2meter(body[64:72].uintle))]
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


    elif mtype == 0x220725:
        """22 07 25 - baker_delta (1 Hz)

        Unknown message from the Baker data set.
        Always 220725ffffffffffffffff81.
        """
        mdesc = "baker_delta"
        if strbody == "ffffffffffffffff81":
            return
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "ffffffffffffffff81"))

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
        """24 07 23 - gpstime (12 bytes, 1Hz update rate)

        Pattern:
        "24 07 23 0x xx xx 1b 07 18 00 yz 81".

        x xx xx: went from "8 38 2a" to "a 24 01" in long dumps.

        It wraps after 3b, so for the byte fields only 6 of 8 bits (& 0x3b)
        are in use. Still unknown if all 4 bits are in use in the nibble field.

        Why is this MSB left, when the 13 byte example is MSB right?

        y: there are 16 subsequent frames with a value of y in (0,1,2,3).
        z: appears to be some sort of checksum. no clear pattern.

        Common messages:
          ffffff00000010ef81 (nolock1)
          ffffff00808010ef81 (nolock2)

        Flaps data alternates between nolock1 and nolock2 during startup.

        If the GPS is not connected, the sequence counter keeps going up but
        everything else is static:
        ('0x240723', 'gpstime', {'rawbody': '0013391f0cfd00c481', 'uints':
         '036 007 035 000 019 057 031 012 253 000 196'})
        """
        mdesc = "gpstime"
        body = checklength(pdu, 12)
        if strbody in ["ffffff00000010ef81", "ffffff00808010ef81"]:
            keys = [("utctime", float("NaN"))]
        else:
            hour = body[0:8].uintle
            minute = body[8:16].uintle
            second = body[16:24].uintle
            day = body[24:32].uintle
            month = body[32:40].uintle

            # This can't be right, can it?? :-)
            year = 1992 + body[40:56].uintle  # XXX: year?? 024 000 == 2016??

            try:
                # Hello future readers. I don't care after I'm dead ;-)
                assert year < 2150
                assert year > 2000
                ts = datetime(year=year, month=month, day=day, hour=hour,
                              minute=minute, second=second)

            except AssertionError as e:
                logging.debug("gpstime year is %s -- %s body: %s" %
                              (year, str(e), strbody))
                ts = float("NaN")

            keys = [("utctime", ts)]
            keys += [("unknown", body[56:64].uintle)]


    elif mtype == 0x250421:
        """25 04 21 - baker_juliet (0.5 Hz)

        Unknown 9 byte message from the Baker data set.

        Pattern: xx yy zz 00 ZZ 81
        Seen: ca0d0000c781

        xx jumps from 9 to 185 in one update.
        yy moves slowly, 14 down to 9.
        zz is 0 or 1.
        ZZ is like xx, jumps from 3 to 199.
        """
        mdesc = "baker_juliet"
        body = checklength(pdu, 9)
        keys = intdecoder(body)
        assert strbody[6:8] == "00"
        keys += [("xx", body[0:8].uintle),
                 ("yy", body[8:16].uintle),
                 ("zz", body[16:24].uintle),
                 ("ZZ", body[-8:].uintle)]

    elif mtype == 0x260127:
        """26 01 27 - baker_hotel (0.5 Hz)

        Unknown 6 byte message from the Baker data set.

        Seen: c8c881
        """
        mdesc = "baker_hotel"
        if strbody == "c8c881":
            return
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "c8c881"))

    elif mtype == 0x270225:
        """27 02 25 - baker_golf (0.5 Hz)

        Unknown 7 byte message from the Baker data set. Always 00ffff81.
        """
        mdesc = "baker_golf"
        if strbody == "00ffff81":
            return
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "00ffff81"))


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


    elif mtype == 0x410a4b:
        """41 0a 4b - baker_indian (0.5 Hz)

        Unknown 15 byte message from the Baker data set.

        Pattern: xx00ffffffffffffffffyy81

        xx and yy are equal, valued 120-138.
        """
        mdesc = "baker_indian"
        body = checklength(pdu, 15)
        keys = intdecoder(body)

        middle = strbody[4:-4]
        if middle != "ffffffffffffffff":
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (middle, middle))

        xx = body[0:8].uintle
        yy = body[-8:].uintle
        keys += [("xx", xx)]

        if xx != yy:
            raise FailedAssumptionError(mdesc, "xx != yy (got %s, expect %s)"
                                        % (xx, yy))

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
        raise NotImplementedError("handler for 0x%06x mlen=%s: %s"
                                  % (mtype, mlen, pdu))

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
        assert isinstance(r["utctime"], datetime)
        assert r["utctime"].isoformat() == "2016-08-17T15:27:23"

    def test_gps_position(self):
        r = FDXDecode("20 08 28 00 00 00 00 00 00 10 00 10 81")  # No lock
        self.assertEqual(r["mdesc"], "gpspos")
        assert isnan(r["lat"])
        assert isnan(r["lon"])

        r = FDXDecode("20 08 28 3b 21 c3 0a ff 8e e0 00 42 81")  # Position
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

        # gpstime
        r = FDXDecode("24 07 23 11 26 1f 0f 08 18 00 37 81")
        self.assertEqual(r["mdesc"], "gpstime")
        assert isinstance(r["utctime"], datetime)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    doctest.testmod()
    unittest.main()
