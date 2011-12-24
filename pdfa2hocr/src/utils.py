# -*- coding: utf-8 -*-
"""
Copyright (c) 2010-2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

HOCR_APP_NAME = "pdfa2hocr"
HOCR_APP_VERSION = "0.2"

import imp
#import lppmtobpm
import os
from icu import BreakIterator, Locale
import Image
import tempfile
from ttFontMod import fontToolsUniToString

# string powtorzony num razy
def repeat(string, num):
    res = ""
    for _ in range(0, num):
        res += string
    return res

# czy napis jest poprawnym okresleniem koloru w stylu html
def isHTMLColor(htmlColor):
    if len(htmlColor) != 7:
        return False
    if htmlColor[0] != "#":
        return False
    for c in htmlColor[1:]:
        if not (c in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]):
            return False
    return True

#def rgb(htmlColor): 
#    rs = htmlColor[1:3]
#    gs = htmlColor[3:5]
#   bs = htmlColor[5:7]
#    return (int(rs, 16), int(gs, 16), int(bs, 16))

# klucz pod jakim w slowniku dict jest wartosc v
# (uzywane w TagLib.getPageNoById, gdzie mozemy zalozyc, ze dana wartosc jest
# tylko pod jednym kluczem)
def keyOf(dict, value):
    #print dict
    for (k, v) in dict.iteritems():
        if v == value:
            return k
    return None

# wyjatek z komunikatem o bledzie
# uzywane tylko w jednym miejscu (HOCRStandardMapping._useMappingFromFile)
class MyException(Exception):

    def __init__(self, msg):
        self.__msg = msg
    
    def __str__(self):
        return self.__msg

# laduje dowolny plik .py
# path - sciezka do katalogu w ktorym znajduje sie modul
def loadModule(module, path):
    module = module[:-3]
    #print path, module
    (fp, _, desc) = imp.find_module(module, [path])
    if fp == None:
        fp.close()
        return None
    try:
        # TODO: D wielokrotne ladowanie modulow o tej samej nazwie: co wtedy? 
        module = imp.load_module(module, fp, module + ".py", desc)
    finally:
        fp.close()
    return module

def uniToString(uni):
    return fontToolsUniToString(uni)

# dodaje dwa bounding boxy (None + bounding box = bounding box)
def combine(b0, b1):
    if b1 == None:
        return b0
    if b0 == None:
        return b1
    b00 = min(b1[0], b0[0])
    b01 = min(b1[1], b0[1])
    b02 = max(b1[2], b0[2])
    b03 = max(b1[3], b0[3])
    return [b00, b01, b02, b03]

# zamienia napis na jego reprezentacje szesnastkowa
def hexdump(s):
    res = ""
    i = -1
    for c in s:
        i += 1
        if i % 2 == 0 and i != 0:
            res += " "
        assert(ord(c) < 256)
        hx = hex(ord(c))[2:]
        if len(hx) == 1:
            hx = "0" + hx
        res += hx
    return res

# dzieli tekst na slowa uzywajac ICU
# zwraca liste miejsc podzialu w tekscie
def divideIntoWords(txt, locale):
    loc = Locale.createFromName(locale)
    bi = BreakIterator.createWordInstance(loc)
    #print txt
    bi.setText(txt)
    res = []
    while True:
        try:
            #print bi.next()
            res.append(bi.next())
        except StopIteration:
            return res

# zamienia krotke (a, b, c, d) na liste [a, b, c, d]
def tuple2list(tup):
    if tup == None:
        return tup
    li = [tup[0], tup[1], tup[2], tup[3]]
    return li

# czy nazwa fontu jest nazwa podzbioru fontu (zaczyna sie od[A-Z][A-Z][A-Z][A-Z][A-Z][A-Z]+)
def isSubsetName(name):
    if len(name) < 7:
        return False
    if not(name[0] >= 'A' and name[0] <= 'Z'):
        return False
    if not(name[1] >= 'A' and name[1] <= 'Z'):
        return False
    if not(name[2] >= 'A' and name[2] <= 'Z'):
        return False
    if not(name[3] >= 'A' and name[3] <= 'Z'):
        return False
    if not(name[4] >= 'A' and name[4] <= 'Z'):
        return False
    if not(name[5] >= 'A' and name[5] <= 'Z'):
        return False
    if name[6] != '+':
        return False
    return True

# zamienia obrazek w formacie PBM na obiekt Image pakietu PIL
def pbm2bmp(data):
    (fd, name) = tempfile.mkstemp("__pdfautils")
    os.close(fd)
    f = open(name, "wb")
    f.write(data)
    f.close()
    im = Image.open(name)
    os.remove(name)
    return im
    #(fd, name) = tempfile.mkstemp("__pdfautils")
    #oldstdout = os.dup(1)
    #os.dup2(fd, 1)
    #lppmtobpm.ppm2bmp(data, len(data))
    #os.dup2(oldstdout, 1)
    #os.close(fd)
    #res = ""
    #f = open(name, "rb")
    #for l in f:
    #    res += l
    #f.close()
    #os.remove(name)
    #assert(len(res) > 0)
    #return res

# znajduje bounding boxy slow i indeksy slow (indeks == numer slowa w tekscie
# liczony od zera) ktore zawieraja tylko biale spacje
# zasada dzialania: symuluje dzialanie petli oznaczonej (%%%%) w metodzie
# HOCRExporter.__exportNode (w ktorej sa z kolei wywolywane metody __exportNode
# dla dzieci wezla "textline" wykonujace petle (%%%))
# parametr bboxes - bounding boxy znakow
def generateDivBboxesTextline(divs, bboxes, children, hasFont, font):
    #return bboxes
    res = []
    whites = []
    white = True
    bbox = None
    divind = 0
    ind = 0
    inword = False
    start = True
    for cs in children:
        if not start: # TODO: F potrzebne?
            hasFont = False
        else:
            start = True
        for c in cs.getChildren():
            #print type(c)
            if isinstance(c, unicode):
                for chr in c:
                    if ind in divs:
                        if white:
                            whites.append(divind)
                        res.append(bbox)
                        divind += 1
                        bbox = None
                        white = True
                    if chr != " " and chr != "\n":
                        white = False
                    bbox = combine(bbox, bboxes[ind])
                    ind += 1
                    if not ind in divs:
                        inword = True
                    else:
                        inword = False
            else:
                if hasFont and font.getId() != c.getId() and inword:
                    if white:
                        whites.append(divind)
                    res.append(bbox)
                    divind += 1
                    bbox = None
                    white = True
                hasFont = True
                font = c
    if ind in divs: # chyba zawsze
        if white:
            whites.append(divind)
        res.append(bbox)
    #print divs, len(res), len(divs), len(bboxes)
    #assert(len(divs) == len(res))
    return (res, whites)

# znajduje bounding boxy slow i indeksy slow (indeks == numer slowa w tekscie
# liczony od zera) ktore zawieraja tylko biale spacje
# zasada dzialania: symuluje dzialanie petli oznaczonej (%%%) w metodzie
# HOCRExporter.__exportNode
# parametr bboxes - bounding boxy znakow
def generateDivBboxes(divs, bboxes, children, hasFont, font):
    #return bboxes
    res = []
    whites = []
    white = True
    bbox = None
    divind = 0
    ind = 0
    inword = False
    for c in children:
        #print type(c)
        if isinstance(c, unicode):
            for chr in c:
                if ind in divs:
                    if white:
                        whites.append(divind)
                    res.append(bbox)
                    divind += 1
                    bbox = None
                    white = True
                if chr != " " and chr != "\n":
                    white = False
                bbox = combine(bbox, bboxes[ind])
                ind += 1
                if not ind in divs:
                    inword = True
                else:
                    inword = False
        else:
            if hasFont and font.getId() != c.getId() and inword:
                if white:
                    whites.append(divind)
                res.append(bbox)
                divind += 1
                bbox = None
                white = True
            hasFont = True
            font = c
    if ind in divs: # chyba zawsze
        if white:
            whites.append(divind)
        res.append(bbox)
    #print divs, len(res), len(divs), len(bboxes)
    #assert(len(divs) == len(res))
    return (res, whites)

# znajduje bounding boxy slow i indeksy slow (indeks == numer slowa w tekscie
# liczony od zera) ktore zawieraja tylko biale spacje
# zasada dzialania: symuluje dzialanie petli oznaczonej (***) w metodzie
# HOCRDirectConverter.receive_layout
def generateDivBboxesDirect(divs, items, hasFont, selffont, lib, page, enc):
    #return bboxes
    res = []
    whites = []
    white = True
    bbox = None
    divind = 0
    ind = 0
    inword = False
    for item in items:
        #print type(c)
        font = enc(item.fontname)
        size = item.size
        if (selffont == None or (selffont.fullName != font or selffont.size != size)) or not hasFont:
            if hasFont:
                if inword:
                    if white:
                        whites.append(divind)
                    res.append(bbox)
                    divind += 1
                    bbox = None
                    white = True
            selffont = lib.findFont(page, font).instantiate(size)
            hasFont = True
        if ind in divs:
            if white:
                whites.append(divind)
            res.append(bbox)
            divind += 1
            bbox = None
            white = True
        if item.text != " " and item.text != "\n":
            white = False
        bbox = combine(bbox, normalize(item.bbox))
        ind += 1
        if not ind in divs:
            inword = True
        else:
            inword = False
    if ind in divs: # chyba zawsze
        if white:
            whites.append(divind)
        res.append(bbox)
    #print divs, len(res), len(divs), len(bboxes)
    #assert(len(divs) == len(res))
    return (res, whites)

# zamienia bounding box na jego reprezentacje tekstowa
def bbox2str((x0,y0,x1,y1)):
    #return ""
    #print x0, y0, x1, y1
    #return '%.4f %.4f %.4f %.4f' % (x0, y0, x1, y1)
    return str(int(x0)) + " " + str(int(y0)) + " " + str(int(x1)) + " " + str(int(y1))

globalX = -1.0
globalY = -1.0

# przeskalowuje bounding box zgodnie z podanymi wspolrzednymi globalX, globalY
def scaleBbox(bbox):
    #print bbox
    if globalX != -1.0:
        yf = float(globalY) / bbox[3]
        xf = float(globalX) / bbox[2]
    else:
        yf = 1.0
        xf = 1.0
    return [bbox[0] * xf, bbox[1] * yf, bbox[2] * xf, bbox[3] * yf]

# zamienia wspolrzedne bounding boxa z (0,0) w lewym dolnym rogu (PDF) na (0,0) w
# lewym gornym rogu (hOCR)
# potem przeskalowuje bounding box zgodnie z podanymi wspolrzednymi globalX, globalY
# potrzebuje w tym celu bounding boxa strony
def changeCoords(pagebbox, bbox):
    #print bbox
    if bbox == None:
        return bbox
    if globalX != -1.0:
        yf = float(globalY) / pagebbox[3]
        xf = float(globalX) / pagebbox[2]
    else:
        yf = 1.0
        xf = 1.0 
    return [bbox[0] * xf, (pagebbox[3] - bbox[3]) * yf, bbox[2] * xf, (pagebbox[3] - bbox[1]) * yf] 

# patrz 3.8.3 Rectangles w PDF Reference 1.4
# pdfminer chyba tego nie robi, ale trzeba to dokladnie sprawdzic
def normalize((a, b, c, d)):
    e = min(a, c)
    f = min(b, d)
    g = max(a, c)
    h = max(b, d)
    return [e, f, g, h]
