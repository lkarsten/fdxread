#!/usr/bin/env python
# .- coding: utf-8 -.
"""
Replay an NMEA data log file.

Used for simulating being at sea, while in fact sitting
comfortably in your office chair!

Author: Lasse Karstensen <lasse.karstensen@gmail.com>, July 2013.
"""
from __future__ import print_function
import socket
import sys
from datetime import datetime
from time import sleep, time

from os.path import realpath, dirname

def log(msg):
    print(datetime.now(), msg)

def usage():
    print("Usage: %s <nmeafile[.gz]>" % sys.argv[0])

def open_input():
    "Open the input file and return a pointer to it"
    if ".gz" in sys.argv[1]:
        import gzip
        inputfile = gzip.open(sys.argv[1])
    else:
        inputfile = open(sys.argv[1])
    return inputfile


def main():
    if len(sys.argv) == 1:
        usage()
        sys.exit(1)

    skipbytes = None
    if len(sys.argv) == 3:
        skipbytes = int(sys.argv[2])

    log("Starting up")

    # The $GPRMC message is time stamped, and from the logs we
    # output it every 2 seconds. Pace our replayed output by this.
    last_GPRMC = None

    Hz = 4.
#    Hz = 10.

    inputfile = None
    sock = None
    try:
        while True:
            if not inputfile:
                inputfile = open_input()
                if skipbytes:
                    print("Forwarding %i bytes" % skipbytes)
                    inputfile.seek(skipbytes)
                    inputfile.readline()

            while sock is None:
                remoteaddr = ("127.0.0.1", 10110)
                log("Connecting socket to %s:%s" % remoteaddr)
                try:
                    if 1:
                        sock = socket.create_connection(remoteaddr)
                    else:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.connect(remoteaddr)
                except socket.error as e:
                    log("Unable to connect: " + str(e))
                    sleep(2)
                    continue
                log("Connected")

            line = inputfile.readline()
            if not line:
                log("We have replayed the entire file, starting over again")
                inputfile = None
                continue

            if line.startswith("!!"):
                continue

            if line.startswith("$GPRMC"):
                now = time()
                if not last_GPRMC:
                    last_GPRMC = now
                else:
                    next_event_in = last_GPRMC - now + 1/Hz
                    last_GPRMC = now
                    if next_event_in > 0:
                        #log("Sleeping for %f secs. (pacing)" % next_event_in)
                        sleep(next_event_in)

            #log("got line: \"%s\"" % line[:-1])
            try:
                sock.send(line)
            except socket.error as e:
                log("write failed: " + str(e))
                sock = None
                sleep(1)

            if 1:
                sys.stdout.write(".")
                sys.stdout.flush()

            # we see about 5 sentences per GPRMC. Double that to make sure we
            # don't fall behind.
            sleep((1/Hz) / 10)
    except KeyboardInterrupt:
        print()
        log("Normal exit")
        sys.exit()


if __name__ == "__main__":
    main()
