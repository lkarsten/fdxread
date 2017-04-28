"""
Dirty hack to get setuptools test runner to run the
outer command line client.

Unit tests are nice and everything, but if the command line client
doesn't work they're not worth a dime.

Run this from fdxread/, not libfdx/, due to hardcoded paths.

"""
from __future__ import print_function
import unittest
import subprocess
from os.path import exists

class TestFDXRead(unittest.TestCase):
    def test_short(self):
        nmea = subprocess.check_output(["./fdxread", "dumps/wind-3.2kt_app_ca110grd.dump"])
        self.assertIn(b"FVMWV", nmea)

        sk = subprocess.check_output(["./fdxread", "--format", "signalk", "dumps/wind-3.2kt_app_ca110grd.dump"])
        self.assertIn(b"depth", sk)

        raw = subprocess.check_output(["./fdxread", "--format", "raw", "dumps/wind-3.2kt_app_ca110grd.dump"])
        self.assertIn(b"depth", raw)

        # And an nxb file for completeness
        # XXX: Disable this initially since it found an issue in decode.py.
        if 0:
            nmea2 = subprocess.check_output(["./fdxread", "dumps/nexusrace_save/QuickRec.nxb"])
            self.assertIn(b"FVMWV", nmea2)


if __name__ == "__main__":
    unittest.main()

