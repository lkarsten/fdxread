import logging
import unittest
import py_compile

from fdxdecode import HEXdecoder
from olddumpformat import dumpreader

from glob import glob

class SyntaxTests(unittest.TestCase):
    def test_compiles(self):
        """
        Check syntax on Python files.

        Some of the scripts read from a port or stdin, making testing
        them reasonably a bit harder.
        """
        py_compile.main(glob("*.py"))


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
