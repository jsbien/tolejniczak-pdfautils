"""
Copyright (c) 2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>

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

The PDFAUtilities software was created solely by Tomasz Olejniczak
and Yusuke Shinyama is not in any way connected with its development.
However, because some parts of this file are heavily based on PDFMiner software
the copyright notice from PDFMiner is included:

Copyright (c) 2004-2010 Yusuke Shinyama <yusuke at cs dot nyu dot edu>

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

from pdfminer.converter import PDFLayoutAnalyzer
from pdfminer.layout import LTPage, LTText, LTLine, LTRect, LTCurve
from pdfminer.layout import LTFigure, LTImage, LTChar, LTTextLine, LTTextBox
from pdfminer.layout import LTTextGroup
from pdfminer.utils import enc
from utils import divideIntoWords, bbox2str, generateDivBboxesDirect, changeCoords
from utils import scaleBbox, normalize

# rozszerzenie klasy PDFLayoutAnalyzer ktore w locie konwertuje zanalizowana strukture
# na hOCR i od razu zapisuje do pliku 
class HOCRDirectConverter(PDFLayoutAnalyzer):

    #def __init__(self, rsrcmgr, outfp, codec='utf-8', laparams=None):
    def __init__(self, rsrcmgr, outfp, ignore, lib, fontMap, icu, tags, laparams=None):
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, laparams=laparams)
        #self.__codec = codec
        self.__outfp = outfp # plik do ktorego eksportujemy hOCR
        self.__lib = lib # 
        self.__num = -1 # numer strony (liczony od 0)
        self.__fontMap = fontMap # mapowanie postscriptowych nazw fontow na rodziny
        self.__icu = icu # lokalizacja ktora ma byc uzyta przez ICU do podzialu
            # na slowa; jezeli jest rowna None to znaczy, ze mamy nie dzielic na
            # slowa
        self.__specialTags = tags # czy uzywamy specjalnych tagow ocrx_bold i
            # ocrx_italic?
        #self.__fontDict = {}
        #self.__font = None
        self.__font = None # ostatnio wypisany font
        #self.__page = None
        self.__hasFont = False # czy jestesmy wewnatrz tagu <span> z definicja fontu
        #self.__isLine = False 
        self.__ignore = ignore # czy ignorujemy elementy "textgroup"
        self.__page = None # aktualnie przetwarzana strona (obiekt PDFPage)
        self.__pagebbox = None # bounding box aktualnie przetwarzanej strony
        self.__chars = [] # tu zapamietujemy znaki podczas przetwarzania elementow
            # "textline" - dzieki temu potem mamy cala zawartosc tekstowa "textline"
            # i mozemy ja wykorzystac do dzielenia na slowa
        self.__divs = [] # por. HOCRExporter
        self.__ind = 0
        self.__inWord = False
        self.__wordInd = 0
        self.__divbboxes = None
        self.__whites = None
        return
    
    # poczatek przetwarzania strony - zapamietujemy aktualnie przetwarzana strone
    # i przechodzimy do nadklasy
    def begin_page(self, page, ctm):
        self.__page = page
        PDFLayoutAnalyzer.begin_page(self, page, ctm)

    # konwertuje strukture logiczna pdfminera przekazana w parametrze ltpage na
    # hOCR i zapisuje do pliku
    def receive_layout(self, ltpage):
        def render(item):
            if isinstance(item, LTPage):
                self.__num += 1
                self.__outfp.write("<div class=\"ocr_page\"")
                self.__outfp.write(" title=\"")
                self.__outfp.write("pageno " + str(self.__num) + ";")
                self.__outfp.write(" bbox " + bbox2str(scaleBbox(normalize(ltpage.bbox))))
                self.__outfp.write("\">")
                for child in item:
                    #print child
                    render(child)
                self.__outfp.write("</div>") 
            elif isinstance(item, LTLine):
                pass
            elif isinstance(item, LTRect):
                pass
            elif isinstance(item, LTCurve):
                pass
            elif isinstance(item, LTFigure):
                pass
            elif isinstance(item, LTTextLine):
                self.__outfp.write("<span class=\"ocr_line\"")
                self.__outfp.write(" title=\"bbox " +
                             bbox2str(changeCoords(self.__pagebbox, normalize(item.bbox))) + "\"")
                self.__outfp.write(">")
                #self.__isLine = True
                self.__hasFont = False
                self.__chars = []
                for child in item:
                    render(child)
                text = u""
                for c in self.__chars:
                    text += c.get_text()
                if self.__icu != None:
                    # zob. metode HOCRExporter.__exportNode 
                    self.__divs = divideIntoWords(text, self.__icu)
                    (self.__divbboxes, self.__whites) = generateDivBboxesDirect(self.__divs, self.__chars, self.__hasFont, self.__font, self.__lib, self.__page, enc)
                    self.__divs = [0] + self.__divs
                    self.__ind = 0
                    self.__wordInd = 0
                    self.__inWord = False
                for c in self.__chars: # (***)
                    self.__renderChar(c)
                if self.__hasFont:
                    self.__endSpecialTags(self.__font)
                    self.__outfp.write("</span>")
                #self.__isLine = False
                self.__outfp.write("</span>")
            elif isinstance(item, LTTextBox):
                self.__outfp.write("<div class=\"ocr_carea\"")
                self.__outfp.write(" title=\"bbox " +
                             bbox2str(changeCoords(self.__pagebbox, normalize(item.bbox))) + "\"")
                self.__outfp.write(">")
                for child in item:
                    render(child)
                self.__outfp.write("</div>")
            elif isinstance(item, LTChar):
                self.__chars.append(item)
            elif isinstance(item, LTText):
                pass
                # TODO: NOTE ignorujemy tekst pusty (tu byly same spacje)
                #self.outfp.write('<text>%s</text>\n' % item.get_text())
            elif isinstance(item, LTImage):
                pass
            elif isinstance(item, LTTextGroup):
                self.__outfp.write("<div class=\"ocr_carea\"")
                self.__outfp.write(" title=\"bbox " + bbox2str(changeCoords(self.__pagebbox, normalize(item.bbox))) + "\"")
                self.__outfp.write(">")
                for child in item:
                    render(child)
                self.__outfp.write("</div>")
            else:
                assert 0, item
            return
        # ltpage to strona ktorej dziecmi sa elementy typu "textbox",
        # w ltpage.layout jest struktura z uzyciem elementow "textgroup" (ktora
        # zawiera jako potomkow takze elementy "textbox" bedace dziecmi strony)
        self.__pagebbox = normalize(ltpage.bbox)
        if ltpage.groups and not self.__ignore: # nie ignorujemy "textgroup" i
                # "textgroup" sa w zanalizowanej strukturze 
            #print "ignore"
            self.__num += 1
            self.__outfp.write("<div class=\"ocr_page\"")
            self.__outfp.write(" title=\"")
            self.__outfp.write("pageno " + str(self.__num) + ";")
            self.__outfp.write("bbox " + bbox2str(scaleBbox(normalize(ltpage.bbox))))
            self.__outfp.write("\">")
            for lay in ltpage.groups:
              render(lay)
            self.__outfp.write("</div>")
        else: # ignorujemy "textgroup" lub ich nie ma 
            # TODO: I sprawdzic: jezeli brak ltpage.layout to chyba rownoznaczne ze strona bez tekstu?
            render(ltpage)
        return

    # eksportuje znak, jednoczesne zmieniajac w razie potrzeby font lub slowo (por.
    # metoda HOCRExport.__exportNode) 
    def __renderChar(self, item):
        #if not self.__isLine:
        #    return
        #font = enc(item.font.basefont)
        font = enc(item.fontname)
        #size = item.get_size()
        size = item.size
        fontChanged = False
        if (self.__font == None or (self.__font.fullName != font
            or self.__font.size != size)) or not self.__hasFont:
                # zmienil sie font lub nie jestesmy w obrebie tagu <span> dla fontu 
            #if self.__font == None:
            #    print "None",
            #else:
            #    print self.__font.psname,
            if self.__hasFont:
                if self.__icu != None and self.__inWord:
                    if not (self.__wordInd - 1) in self.__whites:
                        self.__outfp.write("</span>")
                    fontChanged = True
                self.__endSpecialTags(self.__font)
                self.__outfp.write("</span>")
            self.__font = self.__lib.findFont(self.__page, font).instantiate(size)
            #print self.__font.psname
            self.__outfp.write("<span style=\"")
            name = None
            if self.__fontMap != None:
                name = self.__fontMap.get(self.__font.name)
            if name == None:
                name = self.__font.name
            self.__outfp.write("font-family: " + self.__font.name)
            if self.__font.bold:
                self.__outfp.write("; font-weight: bold")
            if self.__font.italic:
                self.__outfp.write("; font-style: italic")
            #self.__outfp.write("; ps-name: " + font)
            self.__outfp.write("; font-size: " + str(self.__font.size))
            self.__outfp.write("\">")
            self.__startSpecialTags(self.__font)
            self.__hasFont = True            
        if self.__icu != None:
            if self.__ind in self.__divs or fontChanged: # TODO: I jezeli hasFont bylo False przy wywolaniu renderChar
                    # i wypisalismy nowy font to wtedy nie moze byc srodek slowa (wiec __ind bedzie w self.__divs bo to 0)
                if not self.__wordInd in self.__whites:
                    self.__outfp.write("<span class=\"ocrx_word\" title=\"bbox " + bbox2str(changeCoords(self.__pagebbox, self.__divbboxes[self.__wordInd])) + "\">")
                self.__wordInd += 1
                self.__inWord = True
        self.__outfp.write(item.get_text().replace("<", "&lt;").replace("&", "&amp;").encode("utf-8"))
        if self.__icu != None:
            self.__ind += 1
            if self.__ind in self.__divs:
                if not (self.__wordInd - 1) in self.__whites:
                    self.__outfp.write("</span>")
                self.__inWord = False
    
    # wypisuje tagi specjalne ocrx_bold i ocrx_italic (uzywane wszedzie tam gdzie wypisuje
    # poczatek tagu fontu)
    def __startSpecialTags(self, font):
        if self.__specialTags:
            if font.italic and font.bold:
                self.__outfp.write("<span class=\"ocrx_bold\"><span class=\"ocrx_italic\">")
            elif font.italic:
                self.__outfp.write("<span class=\"ocrx_italic\">")
            elif font.bold:
                self.__outfp.write("<span class=\"ocrx_bold\">")

    # zamyka tagi specjalne ocrx_bold i ocrx_italic (uzywane wszedzie tam gdzie zamyka tag
    # fontu)
    def __endSpecialTags(self, font):
        if self.__specialTags:
            if font.italic and font.bold:
                self.__outfp.write("</span></span>")
            elif font.italic:
                self.__outfp.write("</span>")
            elif font.bold:
                self.__outfp.write("</span>")
