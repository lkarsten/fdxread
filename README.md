FDX reader for Garmin GND10
===========================

This is software to read the FDX protocol data seen on the USB port of Garmin
GND10 gateways.

The GND10 unit is used on boats and translates between Nexus FDX and NMEA2000.

Installation
------------

`fdxread` is available from https://pypi.python.org/pypi/fdxread/ and should be installed using pip:

```
$ pip install fdxread
$ fdxread --help  # Should be in $PATH
```

Tested on Linux and OS X, with Python 2.7 and Python 3.6. Goal is that it should
work laptops and on any raspberry pis out there.

Note that on Debian systems you need to run `apt-get install python-dev` first
for the LatLon23 (dependency) module to install/compile correctly. (at least on
my armhf jessie system)

If you don't want to install it globally on the system, you can use a virtualenv
like described in the development section below.


Running it
----------

fdxread will read FDX either from a saved file (.dump/.nxb) or from a
serial port.

It will send output to the terminal (stdout) on the format configured,
normally NMEA0183.

```
$ fdxread /dev/ttyACM0
$FVMWV,268.64,R,0.06,K,A*20
$ZZXDR,P,102.23000,B,Barometer*25
$SDDBT,,f,4.86,m,,F*1C
[ .. output cut .. ]
```

fdxread does not require root permissions. It should not be run under sudo. For
access to devices in `/dev/` the user it runs as should be added to the
`dialout` group. (on Debian/Ubuntu)

There may be parse warnings logged to stderr that clutter the screen. These can be
filtered with console redirection as usual: ` 2>/dev/null`

When reading a saved file it is recommended to add "--pace 5" to slow down the output flow.
A file for testing can be found in the source repository: https://github.com/lkarsten/fdxread/raw/master/dumps/onsdagsregatta-2016-08-24.dump

```
$ fdxread --pace 5 onsdagsregatta-2016-08-24.dump | head -10
WARNING:root:No handler for 6 byte 0x020200: 020200000081
$FVMWV,268.64,R,0.06,K,A*20
$ZZXDR,P,102.23000,B,Barometer*25
$ZZXDR,C,22.22,C,TempDir*13
$SDDBT,,f,4.86,m,,F*1C
$SDVHW,0.0,T,0.0,M,0.00,N,0.0,K*72
$FVMWV,268.64,R,0.06,K,A*20
$SDDBT,,f,4.86,m,,F*1C
$SDVHW,0.0,T,0.0,M,0.00,N,0.0,K*72
$FVMWV,262.14,R,1.08,K,A*22
$SDDBT,,f,4.86,m,,F*1C
```

Using it with OpenCPN and other software
----------------------------------------

For now the best way of running it is to pipe the output to a NMEA multiplexer
using TCP.

I prefer the [kplex](http://www.stripydog.com/kplex/) multiplexer. After
installing it, it can be started with:
`kplex tcp:direction=both,mode=server,address=127.0.0.1,port=10110`

You then pipe the output from fdxread into it using netcat:
```fdxread /dev/ttyACM0 | nc localhost 10110```

Some information on how to set up OpenCPN and the Chrome application
NMEA Sleuth can be found in https://github.com/lkarsten/fdxread/issues/6 .


--help output
-------------

```
usage: fdxread [-h] [--format fmt] [--seek n] [--pace n] [--send-psilfdx] [-v]
               inputfile

fdxread v0.9.1 - Nexus FDX parser (incl. Garmin GND10)

positional arguments:
  inputfile       Serial port or file to read from. Examples: /dev/ttyACM0,
                  COM3, ./file.dump

optional arguments:
  -h, --help      show this help message and exit
  --format fmt    Output mode, default nmea0183. (json, signalk, nmea0183,
                  none, raw)
  --seek n        Seek this many bytes into file before starting (for files)
  --pace n        Pace reading to n messages per second (for files)
  --send-psilfdx  Send initial mode change command to port (for NX2 server)
                  (experimental)
  -v, --verbose   Verbose output

fdxread is used to read FDX protocol data from Garmin GND10 units.
```

Background information
----------------------

Everything here is deduced from staring at the arriving bytes while
disconnecting some units and motoring in circles. Something was pretty simple to
figure out, some other metrics I'm still not sure is right.

Use at your own risk.

On a side note, I believe this is the only open/freely available document on the
format of the [FDX](https://en.wikipedia.org/wiki/Fast_Data_eXchange) protocol.


Development
-----------

The development happens in git on https://github.com/lkarsten/fdxread/

```
    $ git clone https://github.com/lkarsten/fdxread.git
    $ cd fdxread
    $ virtualenv --system-site-packages venv
    $ . venv/bin/activate
    $ pip install -r requirements.txt
```


License
-------

The contents of this repository is licensed under GNU GPLv2. See the `LICENSE`
file for more information.

Copyright (C) 2016-2017 Lasse Karstensen

