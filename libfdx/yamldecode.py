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
import yaml
from binascii import hexlify
from datetime import datetime
from decimal import Decimal
from math import degrees, radians, isnan
from pprint import pprint, pformat
from sys import argv, stdin, stdout, stderr
from time import sleep, time
from os.path import exists

from LatLon23 import LatLon, Latitude, Longitude
from bitstring import BitArray


class DataError(Exception):
    pass

class FailedAssumptionError(Exception):
    pass

def _b(s):
    from binascii import unhexlify
    s = s.replace(" ", "")
    return unhexlify(s)

def fahr2celcius(temp):
    assert type(temp) in [float, int]
    assert temp < 150
    return (temp - 32) * (5/9.)


def feet2meter(feet):
    assert type(feet) in [float, int]
    assert feet >= 0
    return feet * 0.3048


class FDXFrame(object):
    def __init__(self):
        pass

    @property
    def name(self):
        return self.framename

def fmt(msg):
    if hasattr(msg, "hex"):
        s = msg.hex()
    s = hexlify(msg)
    return  " ".join([s.decode()[x:x+2] for x in range(0, len(s), 2)])


class FDXProcess(object):
    handlers = {}
    headerlen = []

    def __init__(self, protocolfile):
        self.load_yaml_handlers(protocolfile)

    def load_yaml_handlers(self, protocolfile):
        assert exists(protocolfile)
        with open(protocolfile, "r") as fp:
            parts = yaml.load(fp.read())

        for frametype in parts["frames"]:
            mtype, framedata = list(frametype.items())[0]
            if 0:
                print("0x%06X" % mtype, pformat(framedata))

            if "length" in framedata:
                self.headerlen += [(mtype, framedata["length"])]
            elif "fields" in framedata:
                maxoctets = 0
                length = None
                for field in framedata["fields"]:
                    if field["index"] > maxoctets:
                        maxoctets = field["index"]
                        length = field["length"]
                self.headerlen += [(mtype, maxoctets+length)]
            else:
                logging.warning("No length information for frame type 0x%06X" % mtype)
                continue

            if 0:
                print(self.headerlen[-1])
            assert isinstance(self.headerlen[-1][0], int)
            assert self.headerlen[-1][0] > 0
            assert self.headerlen[-1][0] < 0x999999
            assert self.headerlen[-1][1] < 24

        if 1:
            known = [mtype for mtype, mlen in self.headerlen]
            assert 0x120416 in known  # Making sure



    def lineprotocol(self, reader):
        """
        At some point, buf will contain a valid message and we have
        synchronization.

        junk before our recognized frame should be returned as such.
        """
        buf = bytes()
        for ts, chunk in reader:
            assert isinstance(ts, float)
            assert isinstance(chunk, bytes)
            buf += chunk
            #print("buf is: %s" % fmt(buf))
            frameidx = None
            framelen = 0

            for framehdr, framelen in self.headerlen:
                assert isinstance(framehdr, int)
                assert isinstance(framelen, int)  # Framelen = total length incl 3 byte mtype

                needle = b"\x81" + framehdr.to_bytes(3, byteorder="big")
                startidx = buf.find(needle)
                if startidx == -1:
                    continue

                #logging.debug("needle '%s' found at idx %i" % (fmt(needle), startidx))
                #logging.debug("need %i bytes, have these %i bytes: %s" %
                #              (framelen, len(buf[startidx:]), fmt(buf[startidx:])))

                if len(buf[startidx+1:]) < framelen+1:
                    #logging.debug("need %i bytes plus marker, have %i. Read more."
                    #              % (framelen, len(buf[startidx+1:])))
                    break

                if buf[startidx+framelen+1] != 0x81:
                    #logging.debug("no sync. 0x%02x != 0x81" % (buf[startidx+framelen+1]))
                    continue   # No sync

                frameidx = startidx
                assert buf[frameidx+1:frameidx+4] == framehdr.to_bytes(3, byteorder="big")
                assert len(buf[frameidx+1:]) >= framelen
                break

            if frameidx is not None:
                assert buf[frameidx] == 0x81
                if frameidx > 1:
                    logging.debug("junk" + buf[1:frameidx].decode("ascii"))

                # Skip the initial 0x81
                yield 0.0, buf[frameidx+1:framelen+1]
                buf = buf[frameidx+1+framelen:]

            if len(buf) > 1024:  # Should be suitable.
                logging.error("buf grew, most likely stuck. Resetting to recover")
                buf = bytes()


    def decode_frame(self, frame):
        assert isinstance(frame, bytes)

        def printmsg(msg):
            assert isinstance(frame, bytes)
            print(fmt(msg))

        if len(frame) < 4:
            raise DataError("short message <4 bytes: %s" % fmt(frame))

        # Our usual hex representation, for visual recognition.
        mtype = hexlify(frame[:3])
        body = frame[3:]
        print(fmt(frame), fmt(mtype), len(frame), fmt(body))

        handler = self.handlers.get(mtype)
        if not handler:
            logging.warning("No handler for %i byte 0x%s" % (len(frame), mtype))
            return None
#            raise NotImplementedError("No handler for %i byte 0x%s" % (len(frame), mtype))

        keys = handler(message)
        assert len(keys) > 0
        return dict(keys)

class FDXProcess_protocol(unittest.TestCase):
    def test_load(self):
        p = FDXProcess()
        p.load_yaml_handlers("../fdx.yaml")

class FDXProcess_line(unittest.TestCase):
    def test_line(self):
        p = FDXProcess()
        p.load_yaml_handlers("../fdx.yaml")
        #reader = nxbdump("../dumps/nexusrace_save/QuickRec.nxb")
        reader = nxbdump("../../s044-gnd10/dumps/baker-J92-jaywalker-2017-03-04.nxb")
        #args.input, seek=args.seek, frequency=args.pace)
        flow = p.lineprotocol(reader)
        while True:
            s = next(flow)
            assert isinstance(s, tuple)
#            print(type(s), s)
            mtype, frame = s
            print("GOT %s: '%s'" % (mtype, fmt(frame)))
        del reader


class FDXProcess_frameTest(unittest.TestCase):
    def setUp(self):
        self.p = FDXProcess()

    def test_simple(self):
        with self.assertRaises(DataError):
            self.p.decode_frame(_b("81"))

        r = self.p.decode_frame(_b("24 07 23 0f 1b 17 11 08 18 00 02"))
        assert isinstance(r["utctime"], datetime)
        assert r["utctime"].isoformat() == "2016-08-17T15:27:23"

    def test_gps_position(self):
        r = self.p.decode_frame(_b("20 08 28 00 00 00 00 00 00 10 00 10"))  # No lock
        self.assertEqual(r["mdesc"], "gpspos")
        assert isnan(r["lat"])
        assert isnan(r["lon"])

        r = self.p.decode_frame(_b("20 08 28 3b 21 c3 0a ff 8e e0 00 42"))  # Position
        self.assertEqual(r["mdesc"], "gpspos")
        assert isinstance(r["lat"], Latitude)
        assert isinstance(r["lon"], Longitude)
        self.assertAlmostEqual(float(r["lat"].to_string("D")), 59.83255)
        self.assertAlmostEqual(float(r["lon"].to_string("D")), 10.6101166667)

    def test_gps_cogsog(self):
        r = self.p.decode_frame(_b("21 04 25 ff ff 00 00 00"))  # No lock
        self.assertEqual(r["mdesc"], "gpscog")
        assert isnan(r["cog"])
        assert isnan(r["sog"])

        r = self.p.decode_frame(_b("21 04 25 0c 01 66 7e 15"))  # Steaming ahead
        self.assertEqual(int(r["cog"]), 177)
        self.assertEqual(r["sog"], 2.68)

        # gpstime
        r = FDXProcess.decode_frame(_b("24 07 23 11 26 1f 0f 08 18 00 37"))
        self.assertEqual(r["mdesc"], "gpstime")
        assert isinstance(r["utctime"], datetime)


if __name__ == "__main__":
    from libfdx.dumpreader import *
    logging.basicConfig(level=logging.DEBUG)
    doctest.testmod()
    unittest.main()
