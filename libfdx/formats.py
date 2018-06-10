#!/usr/bin/env python
# .- coding: utf-8 -.
#
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
#  Copyright (C) 2016-2017 Lasse Karstensen
#
"""
Output format transforms.
"""
from __future__ import print_function

import json
import logging
import unittest
from datetime import datetime
from decimal import Decimal
from operator import xor
from math import radians, degrees
from pprint import pprint, pformat
from sys import argv, stdin, stdout, stderr
from os import linesep

from LatLon23 import LatLon, Latitude, Longitude


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


# Original from https://stackoverflow.com/questions/11875770/
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return "{0:.3}".format(obj)
    elif isinstance(obj, Latitude):
        return float(obj.to_string("D"))
    elif isinstance(obj, Longitude):
        return float(obj.to_string("D"))
    raise TypeError("Type %s not serializable" % type(obj))


class format_json(object):
    def __init__(self, devmode=False):
        self.devmode = devmode

    def filter(self, s):
        assert isinstance(s, dict)
        for key in ["mdesc", "ints", "strbody", "null", "xx", "yy", "u1", "u2",
                    "fix1", "what?"]:
            if key in s:
                del s[key]
        for key in sorted(s.keys()):
            if key.startswith("maybe"):
                del s[key]
            elif key.startswith("not_"):
                del s[key]
            elif key.startswith("unknown"):
                del s[key]

        return s or None

    def handle(self, s):
        assert type(s) == dict
        if not self.devmode:
            s = self.filter(s)

        if s is None:
            return None

        if self.devmode:
            mdesc = s["mdesc"]
            del s["mdesc"]
            return "%s\t%s" % (mdesc, json.dumps(s, default=json_serial)) + linesep

        return json.dumps(s, default=json_serial) + linesep


class TestFormatters(unittest.TestCase):
    def test_json(self):
        formatter = format_json()
        msg = {"mdesc": "environment", "airpressure": 101.42, "temp_c": 21.0}
        r = formatter.handle(msg)
        assert isinstance(r, str)
        assert r.endswith("\n")
        assert json.loads(r)


if __name__ == "__main__":
    unittest.main()
