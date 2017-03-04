Garmin GND10 connector
======================

This is software to use the USB port on Garmin GND10 gateways.

The GND10 unit is used on boats and translates between Nexus FDX and NMEA2000.
The USB port on it outputs something called FDX, which is reverse engineered here.

Requires python-serial and LatLon23, as specified in requirements.txt. Tested on Linux and OS X.

Running it
----------

Right now the different tools in here should be chained together with unix
pipes. To make it more user friendly down the road this may change, but for the
time being, use::

    $ ./dumpserial.py | ./fdxdecode.py | ./nmeaformat.py 2>/dev/null

This will read binary messages from `/dev/ttyACM0` (default), hexdump it in the format
that ``fdxdecode.py`` expects, and feed it into it. ``fdxdecode.py`` will decode the data fields
and (currently) output a small JSON snippet per line, which ``nmeaformat.py`` will turn into
NMEA0183.

If you want to replay an old hex file::

    $ ./olddumpformat.py dumps/foo.dump  | ./fdxdecode.py  | ./nmeaformat.py 2>/dev/null
    $FVMWV,214.56,R,1.13,K,A,*3
    $SDDBT,,f,5.21,m,,F,*3C
    $SDVHW,0.0,T,0.0,M,0.00,N,0.0,K,*5E
    $FVMWV,214.56,R,1.13,K,A,*3
    [..]

To avoid having to muck around with serial ports and locking, I usually run a kplex_ TCP
server on port 10110, and pipe the output from ``nmeaformat.py`` to it using netcat. That way
OpenCPN can read it easily, and I get to know where I am on the map.

.. _kplex: http://www.stripydog.com/kplex/


Background information
----------------------

Everything here is deduced from staring at the arriving bytes while
disconnecting some units and motoring in circles. Something was pretty simple
to figure out, some other metrics I'm still not sure is right.

Use at your own risk.

On a side note, I believe this is the only open/freely available document on
the packet format of the Fast Data eXchange (FDX) protocol used in Nexus Marine AB's
Nexus products. See ``fdxprotocol.rst`` for notes taken while working this out.

License
-------

The contents of this repository is licensed under GNU GPLv2. See the ``LICENSE`` file for more information.

Copyright (C) 2016-2017 Lasse Karstensen

