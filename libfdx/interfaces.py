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
from __future__ import print_function

import doctest
import logging
import unittest

from datetime import datetime
from pprint import pprint
from time import time, sleep

import serial

from .decode import FDXDecode, DataError, FailedAssumptionError
from .dumpreader import dumpreader
from .nxbdump import nxbdump


class GND10interface(object):
    stream = None
    n_msg = 0
    n_errors = 0
    stream = None

    last_yield = None

    # Seconds
    read_timeout = 0.3
    reset_sleep = 2

    def __init__(self, serialport, send_modechange=False):
        self.serialport = serialport
        self.send_modechange = send_modechange

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

                # After successful open, send the mode change if asked to.
                if self.send_modechange:
                    try:
                        self.stream.write("$PSILFDX,,R\n".encode("ascii"))
                    except serial.serialutil.SerialException as e:
                        logging.error("errno: %s message: %s all: %s" % (e.errno, e.message, str(e)))
                        self.close()

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


class HEXinterface(object):
    """
    Used for running with test data when the GND10 is not
    connected.

    Interface should be close to GND10interface().
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
        if self.inputfile.endswith(".nxb"):
            reader = nxbdump(self.inputfile)
        else:
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
                    if self.frequency is not None:
                        sleep(1.0/self.frequency)

        #print >>stderr, "File replay completed. n_msg: %s n_errors: %s" % (self.n_msg, self.n_errors)

if __name__ == "__main__":
    unittest.main()