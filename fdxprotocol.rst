FDX protocol specification
==========================

Protocol
--------

Message format
~~~~~~~~~~~~~~

Based on packet dumps from a Garmin gWind setup:

* byte 0-2: source and/or packet type.
* bytes 3-n: data.
* byte n-1: always 0x81

Messages are varying. Between 6 and 9 bytes (inclusive) being the most common sizes.

::
	$ cut -f2 snippet | sort | uniq -c | sort -n -k2
	      4 2
	     12 3
	     42 4
	     31 5
	   1889 6
	   2455 7
	   7031 8
	   6293 9
	    749 10
	    748 12
	    747 13


I have no information on size or shape of configuration frames.


Sorted list of messages
=======================

This is a list of messages seen broadcasted out on the GND10 USB port.


"00 02 02" (7 bytes) - desc: emptymsg0
-------------------------------------

If no DST200, body always 0xffff0081.
With DST200, body always 0x00000081.

2Hz update rate.

Also seen seldomly: 0x00111181, 0x0a000a81

$ grep empty z
2016-08-17 19:05:32.177000 ('emptymsg0', {'fault': 'unexpected body (got 00111181, expected 0xffff0081 or 0x00000081'})
2016-08-17 19:25:43.148000 ('emptymsg0', {'fault': 'unexpected body (got 00111181, expected 0xffff0081 or 0x00000081'})

Guesswork: likely navigation-sensitive since 2Hz update rate.

Most likely not: a N|S|W|E indicator, since canracing regatta dumps does not contain enough changes.

TODO: Need a absolute-timestamped lengthy dump with state transitions to continue analysis. Not clear where
it originates, except that it is not from the GPS.


"03 01 02" (6 Bytes) - desc: emptymsg1
--------------------------------------

Previously "windmsg0". 

Always "03 01 02 00 00 81". Present if DST200 is missing. Not present if wind sensor is missing. Unknown use. Arrival rate 0.5Hz.

Update: appears to be a xx == yy situation here as well.

"07 03 04" (8 bytes) name: dst200depth
--------------------------------------

Previously: dst200msg3

Update rate 3Hz, but data only changes at 1Hz. (3 identical in row)

Body always 0xffff000081 if DST200 not connected.

Example of non-empty: 0x920c009e81

Origin likely DST200.

Based on empty format, guessing 16 bit values.

Value output for 16bit integer * 0.001 seems to fit.
Guess is is STW (uint16) and next is depth (uint16).

Needs verification.


"08 01 09" (6 Bytes) - name: static1s
-------------------------------------

Pattern:
"08 01 09 xx yy 81"

xx: values seen: 14, 15 16 or 7f.
yy: set to identical value as xx.

Without DST200, only 7f7f as value was seen.
Without DST200 or wind, only 7f7f as value was seen.

Arrival rate 1Hz.

Guesswork: 0x14 == 20. 0x16 == 22. 0x7f==127. No idea.


"09 01 08" (6 bytes) - name: windsignal
---------------------------------------

Previously "gnd10msg0".

::
    1 ('0x090108', 'gnd10msg0', {'rawbody': '5c5c81', 'value': 92})
    3 ('0x090108', 'gnd10msg0', {'rawbody': '606081', 'value': 96})
  340 ('0x090108', 'gnd10msg0', {'rawbody': '616181', 'value': 97})
  428 ('0x090108', 'gnd10msg0', {'rawbody': '626281', 'value': 98})
  125 ('0x090108', 'gnd10msg0', {'rawbody': '636381', 'value': 99})
   29 ('0x090108', 'gnd10msg0', {'rawbody': '646481', 'value': 100})


Pattern:
"09 01 08 xx yy 81"

xx: values 5e..63 seen.
yy: always identical to xx. Not a checksum.

Arrival rate 1Hz.

Present when wind sensor is available. Did not disappear with disconnected dst200.

Guesswork: Signal strength?

Attempts at covering the receiver unit with metal did not give any change in value. May not have
done a thorough job, bring foil and/or a cooking tin next time.


"12 04 16" group (9B) - desc: winddup
-------------------------------------

Previously: windmsg4
Wind related.
Output as 0xffff00000081 if wind is not connected.
3Hz update rate.

Suspiciously close value-wise to gnd10msg3::

  ('0x010405', 'gnd10msg3', {'strbody': 'a100b0b3a281', 'twa?': '9.225', 'AWA?': '263.561', 'ints': '000161 046000 000162'})
  ('0x120416', 'windmsg4', {'strbody': 'a100b1b3a381', 'ints': '000161 046001 000163'})

Guesswork: this is the original fdxbridge message, and the gnd10 takes the data and produces gnd10msg3
from it, either with some floating point rounding errors, or some other calculation unknown so far.

Ignoring this and prioritizing work on gnd10msg3.



"13 02 11" (7 bytes) - name: gpsping
------------------------------------

Previously called: env0

Updates every 4 seconds (0.25Hz)

Pattern: "xx 01 yy 81"
xx increase means yy decrease?

::
     506 ('0x130211', 'env0', {'maybe': 424, 'ints': '168 001 169', 'rawbody': 'a801a981'})
    1277 ('0x130211', 'env0', {'maybe': 425, 'ints': '169 001 168', 'rawbody': 'a901a881'})
     651 ('0x130211', 'env0', {'maybe': 426, 'ints': '170 001 171', 'rawbody': 'aa01ab81'})


If GND10-only dataset, always set to 0x00000081.
If GND10+wind, always set to 0x00000081.
If GND10+GPS, always set to 0xa901a881.

Guesswork: Is it "i'm still alive" from the gps?


"15 04 11" group (9B) desc: gnd10msg2
-------------------------------------

Pattern:
"15 04 11 xx yy ff zz ss 81"

xx: all values seen.
yy: all values seen.
zz: mostly ff, but a few of: 16, 24, 43, 7c, a7.
SS: checksum?

2Hz update rate.

Does not seem course-related, or boat-speed related. First 16bits alwaays around 58000, second
is 0xffff. Last 8 also unknown. Jumps around a lot.
1471711732.06 ('0x150411', 'gnd10msg2', {'rawbody': '7ce3ffff9f81', 'ints': '058236 065535 000159'})


"1c 03 1f" (8 bytes) name: wind40s
-----------------------------------

Previously: windmsg5
Updates every 40 seconds.

Not present in GND10-only. Present with disconnected DST200.
Not present in GND10+GPS dataset.

Most likely origin is wind sensor.

Guesswork: Slow rate so most likely either environmental or management.

::
    $ sort z | uniq -c | sort -rn
      25 ('0x1c031f', 'windmsg5', {'strbody': '161c242e81', 'ints': '022 028 036 046'})
      17 ('0x1c031f', 'windmsg5', {'strbody': '181c242081', 'ints': '024 028 036 032'})
      16 ('0x1c031f', 'windmsg5', {'strbody': '1a1c242281', 'ints': '026 028 036 034'})
      14 ('0x1c031f', 'windmsg5', {'strbody': '1b1c242381', 'ints': '027 028 036 035'})
      14 ('0x1c031f', 'windmsg5', {'strbody': '171c242f81', 'ints': '023 028 036 047'})
      12 ('0x1c031f', 'windmsg5', {'strbody': '181ca4a081', 'ints': '024 028 164 160'})
      12 ('0x1c031f', 'windmsg5', {'strbody': '171ca4af81', 'ints': '023 028 164 175'})
      11 ('0x1c031f', 'windmsg5', {'strbody': '191c242181', 'ints': '025 028 036 033'})
       6 ('0x1c031f', 'windmsg5', {'strbody': '151c242d81', 'ints': '021 028 036 045'})
       2 ('0x1c031f', 'windmsg5', {'strbody': '191ca4a181', 'ints': '025 028 164 161'})
       1 ('0x1c031f', 'windmsg5', {'strbody': '1a1ca4a281', 'ints': '026 028 164 162'})
       1 ('0x1c031f', 'windmsg5', {'strbody': '181da4a181', 'ints': '024 029 164 161'})
       1 ('0x1c031f', 'windmsg5', {'strbody': '171da4ae81', 'ints': '023 029 164 174'})

Pattern looks to be:
"1c 03 1f xx XX yy YY 81"

xx: 8 bit value? values from 0x0f to 0x17 seen.
XX: 8 bit flag? values 0x1c and 0x1d seen.
xx and XX has indications of not being connected.
yy is a flag of sorts, only 0x24 and 0xa4 seen.
YY: yy/flag-dependent 8bit value.

Guesswork: Battery / charging status of mast-top wind sensor? (overcast vs sunny)
Weak suspicion due to: xx seem to decline slowly later in the evening. 0x1e (==30) at 17:30, 0x17 (==23) at 20:00.


"17 05 12" (10 bytes) name: static2s_two
----------------------------------------

Previously: gnd10msg5
Seen every 2 seconds. (0.5Hz)

Always 0x0080ffffff7f81.

Present in GND10-only dataset. Most likely management. Not interesting.


"21 04 25" group (9 bytes) - desc: gpscog
-----------------------------------------

Previously: windmsg2_2hz

Present when wind and DST200 are disconnected.
Either GND10-synthed or from gps.

::
    21 04 25 1a 02 40 0f 57 81
    21 04 25 36 02 7b 10 5f 81
    21 04 25 32 02 f1 0f ce 81
    21 04 25 11 02 4a 10 49 81

When the unit has just turned on and presumably doesn't have link:

{"mdesc": "gpscog", "ints": "012 000 030 000 018", "ts": "2016-08-17T17:26:59.662000", "mtype": "210425", "cog": 0, "strbody": "0c001e001281"}


Pattern: "21 04 25 xx xx yy YY SS 81"
xx: speed over ground (SOG) in knots, 16bit unsigned integer.
yy: unknown
YY: course over ground (COG), uint8. [0..255] scaled up by (360./255) gives degrees.
SS: unknown. checksum?


"23 05 26" (10 bytes) name: static2s
-------------------------------------

Previously: gnd10msg4

Updates every 2 seconds. (0.5Hz)
Body is always: 0xffff0000808081

Present in dumps with only GND10 connected. Likely origin GND10.

Not interesting.


"2c 02 2e" (7 bytes) - desc: dst200msg0
-----------------------------------------

Not present when DST200 was missing => depth, stw or temperature related.

::
    2c 02 2e 03 02 01 81
    2c 02 2e 04 02 06 81
    2c 02 2e 05 02 07 81
    ..
    2c 02 2e 0f 02 0d 81
    2c 02 2e 10 0f 1f 81
    2c 02 2e 11 0f 1e 81
    2c 02 2e 12 0f 1d 81

The last five frames all arrived at 1471282680.568. No delay between. Initialization message?

Pattern: "2c 02 2e xx yy zz 81"
xx: counts from 0x03..0x0f, wraps to 0x10 ..
yy: values 02 and 0f seen. when xx <= 0x0f is it 0x02, above 0x0f. 
zz: more well behaved than usual, almost counting. could be checksum still.


"2d 05 28" (10 bytes) - desc: service0
--------------------------------------

Seen hourly. 1168-1438s between.

Body always 0x02038600139481.

Unknown use.

Service discovery?


"24 07 23" group. (12B) desc: gpsmsg0
-------------------------------------

Pattern:
"24 07 23 0x xx xx 1b 07 18 00 yz 81".

x xx xx: went from "8 38 2a" to "a 24 01" in long dumps.

[section removed]

It wraps after 3b, so for the byte fields only 6 of 8 bits (& 0x3b) are in use.
Still unknown if all 4 bits are in use in the nibble field.

Why is this MSB left, when the 13 byte example is MSB right?

y:  there are 16 subsequent frames with a value of y in (0,1,2,3).
z appears to be some sort of checksum. no clear pattern.

1Hz update rate.

If the GPS is not connected, the sequence counter keeps going up but everything else is static:
0.029881 ('0x240723', 'gpsmsg0', {'rawbody': '0013391f0cfd00c481', 'uints': '036 007 035 000 019 057 031 012 253 000 196'})


"20 08 28" (13 byte) desc: gpspos13
-----------------------------------

Pattern: "20 08 28 3b xx c3 0a yy yy e0 00 zz 81"

xx moves from db..ff in dataset. _does not_ change "3b" as would be expected from 12byte message pattern.
yy yy - counter. 00..ff left, 8e..8f seen on right.
zz - checksum?

There are messages starting with the same preamble, which most likely are transmission errors:
```
$ cut -f2- snippet2 | grep "20 08 28 3" | cut -f1 | sort -n | uniq -c | sort -rn
   5866 13
     24 8
     15 5
      6 12
```

If the GPS is not connected, the body is always: 0x00000000000010001081



"31 09 38" (14 bytes) name: windmsg7
------------------------------------

Seen every 1100-1300 seconds.

Body always: 0x04055a22020000ff008481

Not in GND10-only, not in GND10+GPS dataset. Visible when DST200 is disconnected.
Most likely source is wind instrument.

Service discovery?

Not immediately interesting.


"35 03 36" (8 bytes) name: windmsg8
------------------------------------

Seen every 1266-1383 seconds.

Body always: 0x37000f3881

Not in GND10-only, not in GND10+GPS dataset. Visible when DST200 is disconnected.
Most likely source is wind instrument.

Not immediately interesting.


"70 03 73" group (8 bytes) - desc: windmsg3
-------------------------------------------

::
    70 03 73 89 b8 80 b1 81
    70 03 73 89 b4 80 bd 81
    70 03 73 89 b6 80 bf 81

Pattern: "70 03 73 89 xx yy zz SS 81"

xx: all values seen.
yy: 95% is 0x80. Others seen: b9, ba, b6, b8, b7, bb. MSB of xx?
zz: values mostly from a0..bf.

Only present if wind sensor is present.

Guesswork: initial guess was upper and lower wind direction measurement, since b3..b9 is around 180 (degrees). Data
doesn't support it though, because there were upwind sections.

Did a complete 360 while watching it, no clear effect. uint16le of the two values around 46000 the whole round. 6-7kt
wind.


"76 9e 81" group (3B): desc: bootup0
---------------------------------------

Appears to be a bootup/initialization message. Appears 6 times in succession, then nothing. 

Body always empty.

Not present in GND10-only or GND10+GPS dumps. Probable origin is DST200 or windsensor.



Ignored messages
----------------

List of messages seen but deemed as transmission errors.

* 0x811504
* 0xb2e000
* 0x0e008f - always just tailer. every 80-600s.
* 0x0c008d - always just tailer.
* 0xee6c81 - always empty.
* 0x17fd81 - always empty.
* 0xec4281 - always empty.
* 0xc70a2f - just once
* 0xc70a92 - just once

Physical network
================

* multi-talker multi-receiver data bus.

* RS485 based on 9600 baud. 1 start bit, 8 data bits, 1 parity bit.

* Up to 32 senders/receivers.

* Bus consist of 4 wires. Green: +12V, Yellow: Data A, White: Data B, Shield: Ground.

The bus can be extended up to 1000m in length. (supposedly)


Addressing
----------

Each talker has a nexus id.

The unit with the lowest ID on the network is the _bus master_. The bus master
allots time slots to the other talkers.

By default units pick their own nexus id, starting from 16.



Units
-----

* NX2 server
(nexusid 0)
Sometimes NX2 FDX server.


* WSI box
(nexusid 2)

Message length overview
=======================

6 byte messages
---------------

::
    $ cut -f2- snippet-withdepth | grep ^6 | cut -f2 | cut -b-8 | sort | uniq -c | sort -rn
     727 09 01 08
     721 08 01 09
     363 03 01 02
       7 12 04 16
       1 30 01 31
       1 01 04 05

"12 04 16" is a 9 byte message cut short, see below.

7 byte messages
---------------

::
    $ cut -f2- snippet3 | grep ^7 | cut -f2- | cut -b-8 | sort | uniq -c
       3785 00 02 02
	474 13 02 11
	  3 21 04 25

    $ cut -f2- snippet2longer | grep ^7 | cut -f2- | cut -b-8 | sort | uniq -c | sort -rn
      20717 00 02 02
      10425 11 02 13
       2589 13 02 11
	264 07 03 04
	227 02 03 01
	160 2c 02 2e
	125 21 04 25
	 52 01 04 05
	 44 12 04 16
	  8 2f 02 2d
	  1 70 03 73


"07 03 04" and "02 03 01" are handled as 8 byte messages.


8 byte messages
---------------

::
    $ cut -f2- snippet3 | grep ^8 | cut -f2- | cut -b-8 | sort | uniq -c
       9463 02 03 01
       5678 07 03 04

    $ cut -f2- snippet2longer | grep ^8 | cut -f2- | cut -b-8 | sort | uniq -c | sort -rn | head -5
      51457 02 03 01
      30703 07 03 04
      17605 70 03 73
	231 1c 03 1f
	144 12 04 16


Last two assumed to be transmission errors for now. Long tail on 8 bytes, lots of very low freq entries:

::
    $ cut -f2- snippet2longer | grep ^8 | cut -f2- | cut -b-8 | sort | uniq -c | wc -l
    45


9 byte messages
---------------

::
    $ cut -f2- snippet2 | grep ^9 | cut -f2- | cut -b-8 | sort | uniq -c
      17549 01 04 05
      17497 12 04 16
      10838 15 04 11
       2976 1a 04 1e
       2902 21 04 25
    $ cut -f2- snippet3 | grep ^9 | cut -f2- | cut -b-8 | sort | uniq -c
       5678 01 04 05
       5678 12 04 16
	944 21 04 25

"1a 04 1e" and "15 04 11" are not there in the dumps missing wind+dst200, so likely
they contain such data.

10 byte messages
----------------

Where wind+depth+stw (+gps) is available:

::
    $ cut -f2- snippet2 | grep ^10 | cut -f2- | sort | uniq -c | sort -rn
       2956 17 05 12 00 80 ff ff ff 7f 81
       2955 23 05 26 ff ff 00 00 80 80 81
	  5 2e 05 2b 0f 19 3f 00 16 3f 81
	  5 2d 05 28 02 03 86 00 13 94 81

Whereas in the file with only GND10 and GPS19x:

::
    $ cut -f2- snippet3 | grep ^10 | cut -f2- | sort | uniq -c | sort -rn
	946 23 05 26 ff ff 00 00 80 80 81
	946 17 05 12 00 80 ff ff ff 7f 81


These messages are "always" the same, on a moving boat.

Could "17 05 12" or "23 05 26" be display luminosity level?

No other 10 byte messages seen. (that wasn't obvious transmission errors)


11 byte messages
----------------

No messages of length 11 have been seen.


12 byte messages
----------------
Examples:

::
    24 07 23 09 27 05 1b 07 18 00 2f 81
    24 07 23 09 27 06 1b 07 18 00 2c 81
    24 07 23 09 27 07 1b 07 18 00 2d 81
    24 07 23 09 27 08 1b 07 18 00 22 81



13 byte messages
----------------

Initially seen as a 12 byte message, but more frequent in a 13 byte form:

::
    20 08 28 3b db c2 0a c7 8e e0 00 81
    20 08 28 3b 5e cc 0a 58 9a e0 00 81
    20 08 28 3b 61 cc 0a 67 9a e0 00 81
    20 08 28 3b e5 c2 0a cf 8e e0 00 b7 81
    20 08 28 3b e6 c2 0a d0 8e e0 00 ab 81
    20 08 28 3b e7 c2 0a d1 8e e0 00 ab 81
    20 08 28 3b e9 c2 0a d3 8e e0 00 a7 81

In a different dump (no wind/dst200, only gps19x)

::
    20 08 28 3b 1f c3 0a fe 8e e0 00 7d 81
    20 08 28 3b 21 c3 0a ff 8e e0 00 42 81
    20 08 28 3b 22 c3 0a 00 8f e0 00 bf 81
    20 08 28 3b 23 c3 0a 01 8f e0 00 bf 81


