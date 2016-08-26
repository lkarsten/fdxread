#!/usr/bin/env python
# .- coding: utf-8 -.
"""
apt-get install python-serial
"""
from bitstring import BitArray

import serial

if __name__ == "__main__":
    serialdevice = "/dev/ttyACM1"
    ser = serial.Serial(port=serialdevice)  #, baudrate=9600, stopbits=2, parity='O')
    print "Writing .."
    ser.write("$PSILFDX,,R\r\n")
    print "Reading .."
    chunk = ser.read(256)
    chunk = BitArray(auto=chunk)
    print len(chunk), chunk

