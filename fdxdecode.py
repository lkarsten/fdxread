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
# Copyright (C) 2016 Lasse Karstensen
#
"""
Garmin GND10 protocol decoder.

Decode the bitstream seen from the Garmin GND10 USB port.
"""
import json
import logging
import unittest
import serial
from binascii import hexlify
from datetime import datetime
from math import degrees, radians
from pprint import pprint
from sys import argv, stdin, stdout, stderr
from time import sleep, time

from LatLon import LatLon, Latitude, Longitude
from bitstring import BitArray

from olddumpformat import dumpreader

class DataError(Exception):
    pass

class FailedAssumptionError(Exception):
    pass

class FDXError(Exception):
    pass

def fahr2celcius(temp):
    assert type(temp) in [float, int]
    assert temp < 150
    return (temp - 32) * (5/9.)

def fahr2kelvin(temp):
    assert type(temp) in [float, int]
    assert temp < 150
    return (temp + 459.67) * (5/9.)

def knots2m(knots):
    """knots => m/s

    >>> knots2m(10)
    5.144444444444445
    """
    return knots * (1852.0/3600)

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

    if pdu[-2:] != '81':
        raise DataError("missing tailer")

    if " " in pdu:
        raise DataError("Whitespace in message")

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
        print hex(mtype), body

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

        keys += [('environment.wind.angleApparent', radians(awa))]
        keys += [('environment.wind.speedApparent', knots2m(windspeed))]


    elif mtype == 0x020301:
        mdesc = "dst200depth2"
        if strbody in ['ffff000081', '0000000081']:
            return
        body = checklength(pdu, 8)

        depth = body[0:16].uintle
        if depth == 2**16-1:
            depth = float("NaN")
        keys = [('depth', "%.2f" % (depth * 0.01))]

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

        keys += [('environment.depth.belowTransducer', depth * 0.01)]

    elif mtype == 0x080109:
        mdesc = "static1s"  # ex windmsg0, stalemsg0
        body = checklength(pdu, 6)
        xx = body[0:8].uintle
        yy = body[8:16].uintle
        keys = [('value', xx)]
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
        keys = [('value', xx)]

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
        keys += [('environment.outside.pressure', pressure)]

        yy = strbody[4:6]  # save us a bitwise lookup.
        if yy != 'ff':
            keys += [("fault", "yy is 0x%s, expected 0xff" % yy)]
        null = strbody[6:8]   # body[24:32].uintle  # zz
        if null != '00':
            keys += [("fault", "null is 0x%s, expected 0x00" % null)]
        temp = body[32:40].uintle  # zz
        keys += [('temp_f?', "%.2f" % temp)]
        keys += [('temp_c', fahr2celcius(temp))]
        keys += [('environment.outside_temperature', fahr2kelvin(temp))]

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
        lat = Latitude(degree=body[0:8].uintle, minute=body[8:24].uintle * 0.001)
        lon = Longitude(degree=body[24:32].uintle, minute=body[32:48].uintle * 0.001)
        # where is fix information? none, 2d, 3d?
        # hdop? elevation?
        keys = intdecoder(body[48:], width=8)

        # The gnd10-faked gps position message is 0x00000000000010001081, which
        # makes the last octet and the third last octet stand out.
        keys += [("fix1", body[48:56].uintle)]
        keys += [("null", body[56:64].uintle)]
        keys += [("elevation", body[64:72].uintle)]  # in feet

        keys += [("pos", LatLon(lat, lon).to_string())]
        keys += [("navigation.position.latitude", str(lat))]
        keys += [("navigation.position.longitude", str(lon))]
        #keys += [("gmapspos", "https://www.google.com/maps?ie=UTF8&hq&q=%s,%s+(Point)&z=11" % (lat, lon))]

    elif mtype == 0x210425:
        mdesc = "gpscog"
        body = checklength(pdu, 9)
        keys = intdecoder(body, width=8)
        #keys = [('xx', body[0:8].uintle)]
        #keys += [('XX', body[8:16].uintle)]
        #keys += [('yy', body[16:24].uintle)]
        sog = body[0:16].uintle
        if sog in [0, 255]:
            sog = float("NaN")

        cog = body[24:32].uintle
        if cog in [0, 255]:
            cog = float("NaN")

        # Scale the values.
        cog *= 360/255.
        sog *= 0.01

        keys += [('cog', cog)]
        keys += [('sog', sog)]

        keys += [('navigation.courseOverGroundTrue', radians(cog))]
        keys += [('navigation.speedOverGroundTrue', knots2m(sog))]

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
            keys = [("utctime", ts.isoformat())]
            keys += [("what?", body[56:64].uintle)]
            keys += [("navigation.datetime.value", ts.isoformat())]

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
    keys = dict(keys)
    keys["mtype"] = "%06x" % mtype
    keys["mdesc"] = mdesc
    return keys

class GND10decoder(object):
    stream = None
    n_msg = 0
    n_errors = 0
    stream = None

    last_yield = None

    # Seconds
    read_timeout = 0.3
    reset_sleep = 2

    def __init__(self, serialport):
        self.serialport = serialport

    def __del__(self):
        if self.stream is not None:
            self.stream.close()

    def open(self):
        self.stream = serial.Serial(port=self.serialport,
                                    timeout=self.read_timeout)
        assert self.stream is not None

    def close(self):
        if self.stream is not None:
            self.stream.close()
            del self.stream
        self.stream = None

    def recvmsg(self):
        buf = bytearray()
        empty_reads = 0

        while True:
            while self.stream is None:
                try:
                    self.open()
                except serial.serialutil.SerialException as e:
                    if e.errno in [2, 16] or "[Errno 6] Device not configured" in e.message:
                        logging.warning(e.strerror)
                        self.close()
                        if self.last_yield < (time() + self.read_timeout):
                            now = time()
                            if self.last_yield > (now - 0.05):  # Pace the iterator if nothing is working.
                                sleep(0.05)
                            self.last_yield = now
                            yield None
                        sleep(self.reset_sleep)   # Retry opening the port in a while
                        continue
                    else:
                        logging.error("errno: %s message: %s all: %s" % (e.errno, e.message, str(e)))
                        raise

            try:
                chunk = self.stream.read(1)  # Inefficient but easily understood.
            except serial.serialutil.SerialException as e:
                if e.errno in [2, 16] or "[Errno 6] Device not configured" in e.message:
                    self.close()
                    # No sleep, the one in the port open loop will be used.
                    continue
                else:
                    logging.error("errno: %s message: %s all: %s" % (e.errno, e.message, str(e)))
                    raise

            assert chunk is not None

            if len(chunk) == 0:
                empty_reads += 1
                logging.info("serial read timeout after %.3f seconds" %
                             self.stream.timeout)
                if empty_reads > 4:  # Non-magic
                    logging.info("Excessive empty reads, resetting port")
                    self.close()
                continue
            self.empty_reads = 0

            assert len(chunk) > 0
            buf.append(chunk)
            #print len(chunk), self.n_msg, self.n_errors

            if 0x81 in buf:
                #print "trying to decode %i bytes" % len(buf)
                try:
                    fdxmsg = FDXDecode(hexlify(buf))
                except (DataError, FailedAssumptionError, NotImplementedError) as e:
                    # This class concerns itself with the readable only.
                    logging.warning("Ignoring exception: %s" % str(e))
                    self.n_errors += 1
                else:
                    if fdxmsg is not None:
                        self.n_msg += 1
                        self.last_yield = time()
                        assert isinstance(fdxmsg, dict)
                        yield fdxmsg

                buf = bytearray()

def skfilter(msg):
    """
    Filter a dictionary to only include Signal K attributes.
    """
    if msg is None:
        return

    assert isinstance(msg, dict)
    for k in msg.keys():
        # Shortened to avoid "vessels.self" on all keys. Fix when neccessary.
        if k.startswith("environment") or k.startswith("navigation"):
            continue
        del msg[k]

    if len(msg) == 0:
        return None
    return msg

class HEXdecoder(object):
    """
    Used for running with test data when the GND10 is not
    connected.

    Interface should be close to GND10decoder().
    """
    last_yield = None
    n_msg = 0
    n_errors = 0

    def __init__(self, inputfile, frequency=10.0, seek=0):
        self.inputfile = inputfile
        self.seek = seek
        self.frequency = frequency
        with open(self.inputfile):
            pass  # Catch permission problems early.

    def recvmsg(self):
        reader = dumpreader(self.inputfile, trim=True, seek=self.seek)
        for ts, mlen, frame in reader:
            assert len(frame) > 0
            #print "trying to decode %i bytes: %s" % (len(frame), frame)
            try:
                fdxmsg = FDXDecode(frame)
            except (DataError, FailedAssumptionError, NotImplementedError) as e:
                logging.warning("Ignoring exception: %s" % str(e))
                self.n_errors += 1
            else:
                if fdxmsg is not None:
                    self.n_msg += 1
                    self.last_yield = time()
                    assert isinstance(fdxmsg, dict)
                    yield fdxmsg

                    # Pace the output.
                    sleep(1.0/self.frequency)

        #print >>stderr, "File replay completed. n_msg: %s n_errors: %s" % (self.n_msg, self.n_errors)

def StreamDecoder():
    """
    # At some point this should be able to read from the serial port
    # by itself, to avoid the chaining.
    """
    while True:
        line = stdin.readline()
        if len(line) == 0:
            break
        line = line.strip()
        if len(line) <= 2:
            continue
        if line.startswith("#"):
            continue

        l = line.split("\t", 3)
        #print "'%s'" % line, l
        ts, mlen, pdu = (float(l[0]), int(l[1]), l[2].replace(" ", ""))
        if not pdu[-2:] == '81':
            print >>stderr, "# Skipping invalid input line: %s" % line
            continue

        try:
            res = FDXDecode(pdu)
        except DataError as e:
            print >>stderr, "# DataError: %s %s %s" % (pdu[:3], pdu[3:], str(e))
        except NotImplementedError as e:
            print >>stderr, "# INCOMPLETE: %s" % (str(e))
        except FailedAssumptionError as e:
            print >>stderr, "# FAULT: %s assumption: %s" % (pdu, str(e))
        else:
            if res is not None:
#                print "%.3f %s" % (ts, res)
                try:
                    if ts > 2:
                        ts = datetime.fromtimestamp(ts)
                        #res["ts"] = ts.isoformat()
                        print json.dumps(res)
                    else:
                        print res
                except IOError:
                    return

        try:
            stdout.flush()
        except IOError:
            return

class FDXDecodeTest(unittest.TestCase):
    def test_simple(self):
        with self.assertRaises(DataError):
            FDXDecode("81")

        with self.assertRaises(DataError):
            FDXDecode("81 81")

        r = FDXDecode("24 07 23 0f 1b 17 11 08 18 00 02 81".replace(" ", ""))
        assert r["utctime"] == "2016-08-17T15:27:23"

    def test_hexdecode(self):
        port = HEXdecoder("dumps/onsdagsregatta-2016-08-17.dump", frequency=10, seek=4e4)
        reader = port.recvmsg()
        for msg in reader:
            msg = skfilter(msg)
            if msg is None:
                logging.debug("empty decoded frame")
                continue
            assert type(msg) == dict
            print msg

if __name__ == "__main__":
    if "-v" in argv:
        argv.pop(argv.index("-v"))
        logging.basicConfig(level=logging.DEBUG)

    if len(argv) > 1 and argv[1] == "--test":
        argv.pop(argv.index("--test"))
        import doctest
        doctest.testmod()
        unittest.main()
        exit()

    elif len(argv) > 1 and argv[1] == "--classtest":
        port = GND10decoder("/dev/tty.usbmodem1411")
        for buf in port.recvmsg():
            buf = skfilter(buf)
            if buf is None:
                logging.debug("empty decoded frame")
                continue
            assert type(buf) == dict
            print buf
        print "EXIT: Port closed or empty"

    else:
        StreamDecoder()
