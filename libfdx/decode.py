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
from decimal import Decimal
from math import degrees, radians, isnan
from pprint import pprint
from sys import argv, stdin, stdout, stderr
from time import sleep, time

from LatLon23 import LatLon, Latitude, Longitude
from bitstring import BitArray


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
    # Hex-encode our carefully de-encoded bytes(), to avoid refactoring
    # the whole world in one sitting.
    assert isinstance(pdu, bytes)

    if hasattr(pdu, "hex"):
        pdu = pdu.hex()
    else:
        pdu = hexlify(pdu)

    assert isinstance(pdu, str)
    assert pdu.isalnum()

    if pdu[-2:] != '81':
        raise DataError("missing tailer")

    if len(pdu) < 5*2:
        raise DataError("short message <5 bytes: %s" % pdu)

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
        """01 04 05 - wsi0 (9 bytes, 3 Hz)

        If only GND10 (no wind or dst200), always 0xffff00000081.
        When the wind box has crashed/browned out, the body is: ffff00000081

        Doing turns and watching the AWA? counter, it does seem to follow reported AWA,
        I think it is the right bitfield, but the scaling is wrong. Revisit.

        6 or 8 byte versions of this message exists. These are ignored because they are not
        very common (26 out of ~3400 in baker set), and the blah.has_key() logic is infectiuous
        to the client code. A wsi0 message should always have three attributes.
        """
        mdesc = "wsi0"
        body = checklength(pdu, 9)

        windspeed = body[0:16].uintle
        if windspeed == 2**16-1:
            windspeed = float('NaN')
        windspeed *= 0.01

        awa = body[16:32].uintle * (360.0 / 2**16)

        keys += [('awa', Decimal(awa))]
        keys += [('aws_lo', body[32:46].uintle * 0.01)]
        keys += [('aws_hi', Decimal(windspeed))]


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

        In no-dst200-attached dumps: "02 03 01" + "6b yy nn 6a 81", nn is
        always zero, and yy is usually 0x00, 0x01 or 0x02.

        Is there a field that defines mode in here? They come in chunks
        of 
        169 001 000 168
        016 021 000 005
        016 021 000 005 (again)
        010 000 000 010
        016 021 000 005 (repeats)

        In the short form, the two first octets are clearly related:
        {"ints": "246 155", "strbody": "f69b81", "xx": 246, "mode": 155, "zero": 0, "yy": 0, "rest": 0, "mdesc": "dst200temp"}
        {"ints": "249 155", "strbody": "f99b81", "xx": 249, "mode": 155, "zero": 0, "yy": 0, "rest": 0, "mdesc": "dst200temp"}
        {"ints": "253 155", "strbody": "fd9b81", "xx": 253, "mode": 155, "zero": 0, "yy": 0, "rest": 0, "mdesc": "dst200temp"}
        {"ints": "000 156", "strbody": "009c81", "xx": 0, "mode": 156, "zero": 0, "yy": 0, "rest": 0, "mdesc": "dst200temp"}
        {"cog": 245.64705882352942, "sog": 0.02, "unknown": 39, "strbody": "02008bae2781", "mdesc": "gpscog"}
        {"ints": "001 156", "strbody": "019c81", "xx": 1, "mode": 156, "zero": 0, "yy": 0, "rest": 0, "mdesc": "dst200temp"}
        {"ints": "001 156", "strbody": "019c81", "xx": 1, "mode": 156, "zero": 0, "yy": 0, "rest": 0, "mdesc": "dst200temp"}

        (increasing from 254 155 onto 000 156 and proceeding upwards.)
        """
        mdesc = "dst200temp"

        if strbody in ['ffff000081', '0000000081']:
            return

        # print(len(pdu))
        body = checklength(pdu, None)
        keys = intdecoder(body, width=16)

        if len(strbody) == 6:   # Baker short form
            keys += [('internal_temperature', body[0:16].uintle * 0.001), ]
            keys += [('inttempC', fahr2celcius(body[0:16].uintle * 0.001)), ]
        elif len(strbody) == 10:   # long form
            keys += [('xx', body[0:16].uintle), ]
            keys += [('yy', body[16:32].uintle), ]

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

        middle = body[8:16].uintle
        if middle not in [0xff, 0x00]:
            raise FailedAssumptionError(mdesc, "Middle char not 0xff or 0x00, but %s" % str(body[8:16]))
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

        middle = body[8:16].uintle
        if middle not in [0xff, 0xfe]:
            raise FailedAssumptionError(mdesc, "Middle char not 0xff or 0xfe, but %s" % str(body[8:16]))


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
        """11 02 13 - windstale (7 bytes)

        Either be a WSI or GND10 artifact.

        Always one of these two:
          10175 00000081
            250 ffff0081
        """
        mdesc = "windstale"
        if strbody in ["00000081", "ffff0081"]:
            return
        else:
            raise FailedAssumptionError(mdesc, "Non-static body seen: %s" % strbody)

    elif mtype == 0x120416:
        mdesc = "wsi1"
        body = checklength(pdu, 9)
        keys = intdecoder(body, width=16)

    elif mtype == 0x130211:
        mdesc = "gpsping"
        body = checklength(pdu, 7)
        keys = intdecoder(body)
        keys += [("maybe", body[0:16].uintle)]

    elif mtype == 0x150411:
        """15 04 11 - gnd10msg2 (9 bytes, 2 Hz)

        In the Baker set, the values seen on 6 and 8 byte fit the sequence before
        and after, so most likely it is the same data being sent only with the
        last data missing. Cutoff after 16+16+8 supports size estimates.

        On GND10: Does not seem course-related, or boat-speed related. First 16bits alwaays around 58000, second
        is 0xffff. Last 8 also unknown. Jumps around a lot.
        1471711732.06 ('0x150411', 'gnd10msg2', {'rawbody': '7ce3ffff9f81', 'ints': '058236 065535 000159'})
        In Baker set, second word is not 0xffff.
        """
        mdesc = "gnd10msg2"
        body = checklength(pdu, 9)

        keys += [("u1", body[0:16].uintle)]
        keys += [("u2", body[16:32].uintle)]
        keys += [("uint8", body[32:40].uintle)]

    elif mtype == 0x170512:
        mdesc = "static2s_two"
        if strbody != '0080ffffff7f81':
            keys = [('fault', "Non-static body seen. (got %s, expected %x)" %
                              (strbody, 0x0080ffffff7f81))]
        else:
            return   # no use in logging it. static.

    elif mtype == 0x1a041e:
        """1a 04 1e - environment (9 bytes, 2 Hz)
        Previously: windmsg6, airpressure

        Present with DST200 disconnected. Not present in GND10+GPS dataset. Likely source is wind instrument.

        This message often arrives in a continuous chunk with the same other messages:
        ```
        0.029750        10      230526 ffff 0000 8080 81
        0.000000        9       010405 9501 0d82 1b 81
        0.000000        7       110213 0000 0081
        0.000000        9       120416 9401 1d82 0a 81
        0.000000        9       1a041e 9c27 ff00 44 81
        0.000000        12      240723 0839 331b 0718 0006 81
        0.000000        9       150411 24e1 ffff c5 81
        ```
        Note gnd10msg2 (0x150411) appears as well.

        Pattern: 1a041e xx27 ffyy zz 81".
            xx: values 7a..85 seen.
            yy: values 00, 7f and 40 seen. (only)
            zz: checksom? no clear pattern. values a2 up to df, non-continuous.

        Example body: "df27 ff00 07 81"
        Pattern seem to be: "xxxx yy zzZZ 81".
        Does not vary a whole lot, yy is often 0xff.

        xx is likely air pressure in pascals.
        zz is a flag of sorts. 0x00, 0x40 and x07f seen.
        ZZ seem to may be temperature in fahrenheit, when the flag is 0x00.
        """
        mdesc = "environment"

        if strbody == 'ffffff40bf81':
            return   # XXX: NaN instead?

        body = checklength(pdu, 9)
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
        keys = intdecoder(body[48:64], width=8)

        if strbody == "00000000000010001081":
            keys += [("elevation", float("NaN")),
                     ("lat", float("NaN")),
                     ("lon", float("NaN")),
                    ]
        else:
            # 3b5bc70aa5b3e0005b81
            # lat---      what
            #       LON---    EL

            # XXX: where is the fix information? none, 2d, 3d? Where is hdop?
            lat = Latitude(degree=body[0:8].uintle,
                           minute=body[8:24].uintle * 0.001)
            lon = Longitude(degree=body[24:32].uintle,
                            minute=body[32:48].uintle * 0.001)

            keys += [("elevation", feet2meter(body[64:72].uintle))]
            keys += [("lat", lat), ("lon", lon)]

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

    elif mtype == 0x300131:
        """30 01 31 - baker_lima (very seldom)

        Unknown 6 byte message.

        The two body octets are equal in all observed messages.

        Timing: 4 messages seen in quick succession, different data. Another 12s
        later, then quiet for two minutes. New chunk of 4 in 2s, quiet for
        about a minute, then one last.

        In the GND10 dumps, this message appears every 16-25 minutes.

        Theory: some sort of "i'm alive" or "brightness is n" broadcast?
        """
        mdesc = "baker_lima"
        body = checklength(pdu, 6)
        keys = intdecoder(body)
        if strbody[0:2] != strbody[2:4]:
            raise FailedAssumptionError(mdesc, "xx != yy (got %s, expect %s)"
                                        % (strbody[2:4], strbody[0:2]))

    elif mtype == 0x32093b:
        """32 09 3b - conf_able (11 bytes, non-periodic)

        Seen in the Baker data set. Suspected to be related to manual calibration.

        Only value seen: 04045a4aff000081
        """
        mdesc = "conf_able"
        body = checklength(pdu, 11)
        keys = intdecoder(body)

        if strbody != "04045a4aff000081":
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (strbody, "04045a4aff000081"))


    elif mtype == 0x310938:
        mdesc = "windmsg7"
        body = checklength(pdu, 14)
        keys = intdecoder(body)


    elif mtype == 0x350336:
        mdesc = "windmsg8"
        body = checklength(pdu, 8)
        keys = intdecoder(body)

    elif mtype == 0x370136:
        """37 01 36 - baker_kilo (n Hz)

        Unknown 6 byte message from the Baker data set.

        Always 000081.
        """
        mdesc = "baker_kilo"
        if strbody == "000081":
            pass
        else:
            raise FailedAssumptionError(mdesc, "got %s, expected %s"
                                        % (middle, "000081"))

    elif mtype == 0x3d122f:
        """3d 12 2f - conf_easy (23 bytes, not periodic)

        Seen in the Baker data set. Strongly suspected to be related to manual calibration
        or configuration of an NX2 server.

        Values seen:
          3d122f 2700 0000 0000 0000 0000 0000 0000 0000 0000 27 81
          3d122f 2700 327b ad01 d976 a050 4c41 5400 0000 0000 c4 81
          3d122f 2700 3276 b001 797b a043 5552 523f 504f 5300 15 81

        Observation: these are the same payloads that are seen on conf_dog/0x3e122c.

          3e122c 2700 0000 0000 0000 0000 0000 0000 0000 0000 27 81
          3e122c 2700 327b ad01 d976 a050 4c41 5400 0000 0000 c4 81


        """
        mdesc = "conf_easy"
        body = checklength(pdu, 23)
        keys = intdecoder(body, width=8)


    elif mtype == 0x3e122c:
        """3e 12 2c - conf_dog (23 bytes, not periodic)
        (skipping _baker and _charlie in army/navy phonetics due to baker prefix already in use)

        Seen in the Baker data set. Strongly suspected to be related to manual calibration
        or configuration of an NX2 server.

        Values seen:
          3e122c 2700 0000 0000 0000 0000 0000 0000 0000 0000 27 81
          3e122c 2700 327b ad01 d976 a050 4c41 5400 0000 0000 c4 81
          3e122c 2700 3276 b001 797b a043 5552 523f 504f 5300 15 81


        """
        mdesc = "conf_dog"
        body = checklength(pdu, 23)
        keys = intdecoder(body, width=8)


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
        raise NotImplementedError("No handler for %i byte 0x%06x: %s"
                                  % (mlen, mtype, pdu))

    keys += [('strbody', strbody)]
    keys += [('mdesc', mdesc)]
    return dict(keys)


def _b(s):
    from binascii import unhexlify
    s = s.replace(" ", "")
    return unhexlify(s)


class FDXDecodeTest(unittest.TestCase):
    def test_simple(self):
        with self.assertRaises(DataError):
            FDXDecode(_b("81"))

        with self.assertRaises(DataError):
            FDXDecode(_b("81 81"))

        r = FDXDecode(_b("24 07 23 0f 1b 17 11 08 18 00 02 81"))
        assert isinstance(r["utctime"], datetime)
        assert r["utctime"].isoformat() == "2016-08-17T15:27:23"

    def test_gps_position(self):
        r = FDXDecode(_b("20 08 28 00 00 00 00 00 00 10 00 10 81"))  # No lock
        self.assertEqual(r["mdesc"], "gpspos")
        assert isnan(r["lat"])
        assert isnan(r["lon"])

        r = FDXDecode(_b("20 08 28 3b 21 c3 0a ff 8e e0 00 42 81"))  # Position
        self.assertEqual(r["mdesc"], "gpspos")
        assert isinstance(r["lat"], Latitude)
        assert isinstance(r["lon"], Longitude)
        self.assertAlmostEqual(float(r["lat"].to_string("D")), 59.83255)
        self.assertAlmostEqual(float(r["lon"].to_string("D")), 10.6101166667)

    def test_gps_cogsog(self):
        r = FDXDecode(_b("21 04 25 ff ff 00 00 00 81"))  # No lock
        self.assertEqual(r["mdesc"], "gpscog")
        assert isnan(r["cog"])
        assert isnan(r["sog"])

        r = FDXDecode(_b("21 04 25 0c 01 66 7e 15 81 "))  # Steaming ahead
        self.assertEqual(int(r["cog"]), 177)
        self.assertEqual(r["sog"], 2.68)

        # gpstime
        r = FDXDecode(_b("24 07 23 11 26 1f 0f 08 18 00 37 81"))
        self.assertEqual(r["mdesc"], "gpstime")
        assert isinstance(r["utctime"], datetime)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    doctest.testmod()
    unittest.main()
