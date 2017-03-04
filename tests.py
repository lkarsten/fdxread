import logging
import unittest
from fdxdecode import HEXdecoder
from olddumpformat import dumpreader

from glob import glob

class IntegrationTests(unittest.TestCase):
    def xtest_dumpreader(self):
        "Verify that our hex reader can read all dump files on disk"
        for fdxfile in glob("dumps/*.dump"):
            logging.info("Reading: " + fdxfile)
            stream = dumpreader(fdxfile)
            for res in stream:
                pass  # No output

    def test_nocrash(self):
        "Verify that the FDX decoder can decode all files without hard errors"
        for fdxfile in glob("dumps/*.dump"):
            logging.info("Reading: " + fdxfile)
            stream = HEXdecoder(fdxfile, frequency=None).recvmsg()
            for res in stream:
                pass  # No output


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    unittest.main()
