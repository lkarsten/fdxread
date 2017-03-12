FDX reader for Garmin GND10
===========================

This is software to read the FDX protocol data seen on the USB port of Garmin
GND10 gateways.

The GND10 unit is used on boats and translates between Nexus FDX and NMEA2000.

Installation
------------

fdxread requirements are listed in `requirements.txt` and should be installed
using pip.

```
    git clone https://github.com/lkarsten/fdxread.git
    cd fdxread
    virtualenv --system-site-packages venv
    . venv/bin/activate
    pip install -r requirements.txt
```

Tested on Linux and OS X.

Running it
----------

```
    $ ./fdxread -h
    usage: fdxread [-h] [--format fmt] [--seek n] [--pace n] [-v] inputfile

    fdxread - Nexus FDX parser (incl. Garmin GND10)

    positional arguments:
      inputfile      Serial port or file to read from. Examples: /dev/ttyACM0,
                     COM3, ./file.dump

    optional arguments:
      -h, --help     show this help message and exit
      --format fmt   Output mode, default nmea0183. (json, signalk, nmea0183, raw)
      --seek n       Seek this many bytes into file before starting (for files)
      --pace n       Pace reading to n messages per second (for files)
      -v, --verbose  Verbose output

    fdxread is used to read FDX protocol data from Garmin GND10 units.
```


```
	(inside a populated virtualenv, as described above)
	./fdxread /dev/ttyACM0
```

This will read FDX from `/dev/ttyACM0`, and output NMEA0183 to stdout.

To avoid having to muck around with serial ports and locking, I usually run a
[kplex](http://www.stripydog.com/kplex/) TCP server on port 10110, and pipe the
output to it using netcat. That way OpenCPN can read it easily, and I get to
know where I am on the map.


Background information
----------------------

Everything here is deduced from staring at the arriving bytes while
disconnecting some units and motoring in circles. Something was pretty simple to
figure out, some other metrics I'm still not sure is right.

Use at your own risk.

On a side note, I believe this is the only open/freely available document on the
frame format of the `Fast Data eXchange (FDX)` protocol used in Nexus Marine
AB's Nexus products, now owned by Garmin. See `fdxprotocol.rst` and
`libfdx/decode.py` for notes taken while working this out.

License
-------

The contents of this repository is licensed under GNU GPLv2. See the `LICENSE`
file for more information.

Copyright (C) 2016-2017 Lasse Karstensen

