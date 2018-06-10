

from binascii import unhexlify

def hexlify_sep(s, sep=" "):
    "hexlify with separator"
    assert isinstance(sep, str)
    if hasattr(s, "hex"):  # Python 3
        return sep.join(["%02x" % x for x in s])
    return sep.join(["%02x" % ord(x) for x in s])

def unhexlify_sep(s, sep=" "):
    assert isinstance(s, str)
    if sep in s:
        s = s.replace(sep, "")
    s = unhexlify(s)
    return s
