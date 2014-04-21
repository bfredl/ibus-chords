from keysymdef import special, sym2ucs
specialname = {sym: name for (name,sym) in special.items()}
ucs2sym = {ucs: sym for (sym,ucs) in sym2ucs.items()}

def islatin(nbr):
        return 0x20 <= nbr < 0x80 or 0xa0 <= nbr < 0x0100
# convert either a unicode char or a named special symbol
def desc_to_keysym(string):
    if len(string) == 1:
        ucs = ord(string)
        if islatin(ucs):
            return ucs
        return ucs2sym.get(ucs,0x01000000+ucs)
    return special.get(string, 0)

# True if character, False if special
def keysym_desc(sym):
    if islatin(sym):
        return True, chr(sym)
    elif (sym & 0xff000000) == 0x01000000:
        return True, chr(sym & 0x00ffffff)
    elif sym in sym2ucs:
        return True, chr(sym2ucs[sym])
    elif sym in specialname:
        return False, specialname[sym]
    else:
        return False, 'Unknown'
