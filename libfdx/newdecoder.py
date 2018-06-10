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
# Copyright (C) 2017-2018 Lasse Karstensen
#
"""
FDX decoder
"""
import doctest
import json
import logging
import unittest
import struct

from binascii import hexlify, unhexlify
from datetime import datetime
from pprint import pprint
from sys import argv, stdin, stdout, stderr
from time import sleep, time


import fdx_types

# Index handlers on import.
handlers = {}
for fdxtype in dir(fdx_types):
    obj = getattr(fdx_types, fdxtype)
    if hasattr(obj, "mtype"):
        handlers[obj.mtype] = obj

class ParseError(Exception):
    pass

def FDXMessage(msg):
    """
    Decode the contents of an FDX sentence.
    """
    assert isinstance(msg, bytes)
    if 0:
        print("Raw message for decoding is: %s -- %i" % (hexlify(msg), len(msg)))
    assert msg[-1] == 0x81
    if len(msg) < 2:
        raise ParseError("Short message: %s" % hexlify(msg))

    fdxclass = handlers.get(msg[0])
    if fdxclass is None:
        raise NotImplementedError(msg[0])

    if msg[1] > 75:  # Arbitrary
        raise ParseError("Suspiciously long message: %s" % hexlify(msg))

#    if msg[1] != fdxclass.mlen + 4:
#        raise ParseError("Incorrect size on message: %s" % hexlify(msg))

    return fdxclass.unpack(msg)

class FDXDecodeTest(unittest.TestCase):
    def test_simple(self):
#        r = FDXMessage(unhexlify("21 04 25 ff ff 00 00 00 81".replace(" ", "")))
        r = FDXMessage(unhexlify("02 03 01 0f 1b 00 14 81".replace(" ", "")))
        print(r)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
