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
#  Copyright (C) 2016 Lasse Karstensen
#
"""
Take the output from the fdx decoder and create some rudimentary NMEA0183 from
it.

By feeding this into OpenCPN (via kplex in tcp mode), we
get some visualization.
"""
import json
from operator import xor
from datetime import datetime
from sys import stdin, stdout, stderr
from pprint import pprint, pformat

from LatLon import LatLon, Latitude, Longitude


def checksum(sentence):
    cksum = reduce(xor, (ord(s) for s in sentence[1:-1]))
    return "%s%02X" % (sentence, cksum)


def nmeapos(pos):
    """
    >>> nmeapos(LatLon.LatLon("59.8666333333", "10.7608"))
    ['5952.00', 'N', '1045.65', 'E']
    """
    assert isinstance(pos, LatLon)
    def fmt(p):
        s = p.to_string("%d")
        assert len(s) >= 1
        decmin = float(p.to_string("%M"))
        assert decmin / 10. <= 60
        s += "%.2f" % decmin
        return s

    return [fmt(pos.lat), pos.to_string("H")[0],
            fmt(pos.lon), pos.to_string("H")[1]]


def main():
    gpstime = None
    gpspos = None
    while True:
        line = stdin.readline()
        if len(line) == 0:
            break
        line = line.strip()
        if len(line) <= 2:
            continue
        if line.startswith("#"):
            continue

        # oh yeah!
        try:
            sample = json.loads(line)
        except ValueError:
            print >>stderr, "Invalid JSON: %s" % line
            continue

        assert type(sample) == dict

        if sample["mdesc"] == "dst200depth":
            # $--DBT,x.x,f,x.x,M,x.x,F*hh<CR><LF>
            res = [("$SDDBT", "", "f", "%s" % sample["depth"], "m", "", "F")]
            # $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>

            res += [("$SDVHW", "0.0", "T", "0.0", "M",
                     "%.2f" % sample["stw"], "N", "0.0", "K")]

        elif sample["mdesc"] == "gpstime":
            # Will be used later on.
            gpstime = datetime.strptime(sample["utctime"], "%Y-%m-%dT%H:%M:%S")
            continue

        elif sample["mdesc"] == "gpspos":
            lat = Latitude(sample["pos"][0])
            lon = Longitude(sample["pos"][1])
            gpspos = LatLon(lat, lon)
            continue

        elif sample["mdesc"] == "gpscog":
            if gpstime is None or gpspos is None:
                continue

            rmctuple = ("$GPRMC", gpstime.strftime("%H%M%S"), "A") + \
                    tuple(nmeapos(gpspos)) + \
                    ("%.2f" % sample["sog"],
                    "%.2f" % sample["cog"],
                    gpstime.strftime("%d%m%y"),
                    "0.0",  # magn var
                    "E")
            res += [rmctuple]

            #  $--HDT,x.x,T*hh<CR><LF>
            res += [("$GPHDT", "%.2f" % (sample["cog"]), "T")]

        elif sample["mdesc"] == "gnd10msg3":
            #  $--MWV,x.x,a,x.x,a*hh<CR><LF>
            res = [("$FVMWV",
                    "%.2f" % sample["awa"],
                    "R",  # (R)elative, not (T)rue.
                    "%.2f" % sample["aws_lo"],
                    "K",    # knots
                    "A",   # (valid)
                    )]

        elif sample["mdesc"] == "environment":
            # $IIXDR,P,1.02481,B,Barometer*0D
            # $IIXDR,C,19.52,C,TempAir*3D
            res = [("$ZZXDR",
                    "P", "%.5f" % sample["airpressure"],
                    "B", "Barometer"),
                   ("$ZZXDR",
                    "C", "%.5f" % sample["temp_c"],
                    "C", "TempDir")]
            continue

        else:
            if sample["mdesc"] in ["emptymsg0", "gpsping", "static1s",
                                   "windsignal", "dst200depth2",
                                   "gnd10msg2", "windmsg3", "wind40s"]:
                # Ignore known no-ops.
                pass
            else:
                print >>stderr, "Unhandled: '%s'" % pformat(sample)
            continue

        if type(res) == tuple:
            res = [res]

        for tup in res:
            tup = tup + ("*",)
            nmealine = ",".join(tup)
            print checksum(nmealine)
            stdout.flush()

if __name__ == "__main__":
    main()
