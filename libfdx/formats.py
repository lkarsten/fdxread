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


class format_signalk_delta(object):
    """
    Translation between our internal format and Signal K
    delta format.
    """
    def handle(self, s):
        assert type(s) == dict
        r = []
        if s["mdesc"] == "wsi0":
            r += [('environment.wind.angleApparent', radians(s["awa"]))]
            r += [('environment.wind.speedApparent', knots2m(s["aws_lo"]))]
        elif s["mdesc"] == "dst200depth":
            r += [('environment.depth.belowTransducer', s["depth"])]
        elif s["mdesc"] == "environment":
            r += [('environment.outside.pressure', s["airpressure"]),
                  ('environment.outside_temperature',
                   fahr2kelvin(s["temp_f"]))]
        elif s["mdesc"] == "gpspos":
            r += [("navigation.position.latitude", s["lat"]),
                  ("navigation.position.longitude", s["lon"])]
        elif s["mdesc"] == "gpscog":
            r += [('navigation.courseOverGroundTrue', radians(s["cog"])),
                  ('navigation.speedOverGroundTrue', knots2m(s["sog"]))]
        elif s["mdesc"] == "gpstime":
            if isinstance(s["utctime"], datetime):
                r += [("navigation.datetime.value", s["utctime"].isoformat())]

        return dict(r)


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
            return "%s\t%s" % (mdesc, json.dumps(s, default=json_serial))

        return json.dumps(s, default=json_serial)


class TestFormatters(unittest.TestCase):
    def un_isotime(self, s):
        assert isinstance(s, str)
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")

    def test_sk(self):
        formatter = format_signalk_delta()
        r = formatter.handle({"mdesc": "gpspos",
                              "lat": 54.102466, "lon": 10.8079})
        self.assertAlmostEqual(r['navigation.position.longitude'], 10.8079)

        r = formatter.handle({"utctime": self.un_isotime("2017-01-12T19:16:55"),
                              "mdesc": "gpstime"})
        assert r == {'navigation.datetime.value': '2017-01-12T19:16:55'}

        if 0:
            r = formatter.handle({"mdesc": "gpscog", "sog": 0.16, "cog": 344.47})
            pprint(r)

    def test_json(self):
        formatter = format_json()
        msg = {"mdesc": "environment", "airpressure": 101.42, "temp_c": 21.0}
        r = formatter.handle(msg)
        assert isinstance(r, str)
        assert json.loads(r)


if __name__ == "__main__":
    unittest.main()
