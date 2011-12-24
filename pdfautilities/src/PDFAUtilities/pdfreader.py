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

from pdfminer.pdfinterp import PDFPageInterpreter, PDFInterpreterError
from pdfminer.pdftypes import dict_value
from pdfminer.psparser import STRICT, literal_name
from pdfminer.converter import PDFLayoutAnalyzer
from pdfminer.layout import LTChar
from pdfminer.utils import mult_matrix, translate_matrix
from pdfminer.pdffont import PDFUnicodeNotDefined
from utils import combine, tuple2list, normalize

# TODO: G wyrazenia regularne na poleceniach (np z jakichs dziwnych polecen
# tworzymy brakujacy znak i chcemy go czyms zastapic przy eksporcie do hOCR)

# Klasa reprezentuje zawartosc oznaczona w pliku PDF (miedzy BDC/BMC a EMC).
class MarkedContent(object):

    def __init__(self, mcid, tag, page, pagination, artifact, firstFont):
    #def __init__(self, mcid, tag, page, pagination, artifact, pageNo, firstFont):
        self.page = page # strona na ktorej jest zawartosc (pdfminerowy obiekt PDFPage)
        self.pagination = pagination # czy zawartosc jest pagina
        self.artifact = artifact # czy zawartosc jest artefaktem
        self.bbox = None # bounding box zawartosci (suma bounding boxow znakow)
        self.charbboxes = [] # lista bounding boxow znakow
        #self.control = []
        self.mcid = mcid # identyfikator zawartosci w obrebie strony (MCID)
        self.tag = tag # argument polecenia BMC lub BDC opisujacy znaczenie zawartosci
        #self.pageNo = pageNo
        self.els = [firstFont] # napisy i fonty stanowiace zawartosc oznaczona (faktycznie
            # sa to argumentu napotkanych przez TagInterpreter polecen tekstowych)
            # na poczatku jest dodawany ostanio okreslony font (bo moze sie zdarzyc, ze w
            # zawartosci nie ma definicji fontu, bo byl on okreslony wczesniej
        self.initialized = False # TODO: X patrz TODO w taglibie "sprawdzic stare mcidy"

# Klasa znajduje i zapamietuje zawartosci oznaczone. Tworzona dla jednej strony.
# Dziala w ten sposob, ze przetwarza kolejne polecenia PDF (wiekszosc ignoruje,
# zwraca uwage tylko na te dotyczace tekstu i zawartosci oznaczonych).
class TagInterpreter(PDFPageInterpreter):
    
    def __init__(self, *args, **kwargs):
        super(TagInterpreter, self).__init__(*args, **kwargs)
        self.__pageid = None # identyfikator strony (numer obiektu strony w PDF)
        self.__page = None # pdfminerowy obiekt PDFPage, przetwarzana strona
        self.__mcrs = [] # lista zawartosci oznaczonych na przetwarzanej stronie
        #self.__fontmap = {}
        self.__bdcs = [] # UWAGA: por. komentarz ponizej konstruktora
            # stos elementow typu MarkedContent oznaczajacych aktualnie
            # przetwarzane zawartosci oznaczone (moga sie zagniezdzac) - uwaga, na ten
            # stos sa kladzone tylko zawartosci zawierajace MCID
        self.__mc = False # czy jestesmy w zawartosci oznaczonej
        self.__aktfont = None # ostatni font (ustawiony poleceniem Tf)
        self.__aktfontsize = 0 # rozmiar ostatniego fontu
        #self.__ind = 0
        self.__pagination = False # jesli > 0, to jestesmy w paginie (por. implementacja
            # do_BDC, do_BMC, do_EMC
        self.__artifact = False # jesli > 0, to jestesmy w artefakcie (por. implementacja
            # do_BDC, do_BMC, do_EMC
            # teoretycznie wedlug specyfikacji Tagged PDF artefakt lub pagina nie moze byc w strukturze logicznej,
            # ale niekoniecznie dokument musi byc Tagged PDF, poza tym FineReader mimo
            # wszystko umieszcza pagine w strukturze logicznej PDF/A
        self.__bbox = None # bounding box zawartosci oznaczonej (poniewaz zawartosci
            # moga sie zagniezdzac dotyczy on zawsze tylko zawartosci posiadajacej
            # MCID (a zatem takiej ktora jest zawartoscia jakiegos elementu struktury)
        self.__stack = [] # stos napisow ktore okreslaja typ zawartosci oznaczonej
            # umozliwia on nam dowiedzenie sie jaki typ ma zawartosc oznaczona zamykana
            # przez dane polecenie EMC w metodzie do_EMC
            # (MCID - zawartosc zawierajaca identyfikator MCID, Pagination - zawartosc
            # bedaca pagina, Artifact - zawartosc bedaca artefaktem)
        
    # TODO: I tu cos jest nie tak z self.__bdcs i self.__bbox, self.__mc
    # jezeli zawartosci z MCIDami moga sie zagniezdzac, to wtedy self.__bbox i self.__mc beda
    # niepoprawne (bo moga one dotyczyc tylko jednej zawartosci)
    # jezeli zas zawartosci z MCIDami nie moga sie zagniezdzac, to po co stos
    # self.__bdcs?
    
    def setPageId(self, pageid):
        self.__pageid = pageid
        
    def getPageId(self):
        return self.__pageid
        
    def getMcrs(self):
        return self.__mcrs
    
    # zwraca wlasciwosc key zawartosci oznaczonej (szczegoly implementacji patrz str. 585)
    def getValue(self, props, key):
        try:
            return props.get(key) # slownik w contencie
        except AttributeError: # slownik w resource'ach
            dict = self.resources.get("Properties").get(literal_name(props))
            return dict_value(dict).get(key)
    
    # przetwarza polecenie BDC
    def do_BDC(self, tag, props):
        #print "BDC"
        super(TagInterpreter, self).do_BDC(tag, props)
        if self.getValue(props, "MCID") != None:
            # zawartosc oznaczona zawierajaca MCID 
            #print "BDC, MCID =", self.getValue(props, "MCID")
            bdc = MarkedContent(props.get("MCID"), tag, self.__page, self.__pagination > 0 or literal_name(self.getValue(props, "Type")) == "Pagination",
							#literal_name(tag) == "Artifact", self.__ind, [self.__aktfont, self.__aktfontsize])
							#literal_name(tag) == "Artifact", [self.__aktfont, self.__aktfontsize])
							self.__artifact > 0 or literal_name(tag) == "Artifact", [self.__aktfont, self.__aktfontsize])
            # od razu na poczatku dodalismy do zawartosci ostatni font (bo zawartosc moze nie
            # miec na poczatku fontu tylko od razu tekst (korzysta wtedy z fontu zdefiniowanego
            # przed zawartoscia (czyli wlasnie tego ostatniego ktory do niej dodalismy)) 
            self.__mc = True
            bdc.initialized = True
            self.__bdcs.append(bdc)
            self.__stack.append("MCID")
        elif literal_name(tag) == "Artifact" and literal_name(self.getValue(props, "Type")) == "Pagination" and not self.__pagination:
            # dana zawartosc oznaczona jest pagina (poniewaz zawartosci moga byc zagniezdzone
            # to w niej moze byc np. zawartosc z MCIDem) i wtedy ona bedzie traktowana jako
            # pagina (bo znajduje sie we wiekszej zawartosci bedacej pagina, co poznamy po
            # polu self.__pagination))
            self.__pagination += 1
            self.__stack.append("Pagination")
        elif literal_name(tag) == "Artifact":
            # j.w. z tym ze zawartosc jest artefaktem nie pagina
            self.__artifact += 1
            self.__stack.append("Artifact")
        else:
            # inna zawartosc oznaczona
            self.__stack.append("BDC")
        #print ":", self.stack, self.bdcs
        return
    
    # przetwarza polecenie BMC
    def do_BMC(self, tag):
        super(TagInterpreter, self).do_BMC(tag)
        if literal_name(tag) == "Artifact":
            self.__stack.append("BMCArtifact")
            self.__artifact += 1
        else:
            self.__stack.append("BMC")
        #print "::", self.stack, self.bdcs
        return

    # przetwarza polecenie EMC
    def do_EMC(self):
        #print "EMC"
        super(TagInterpreter, self).do_EMC()
        #print self.stack, self.bdcs
        opening = self.__stack.pop()
        if opening == "MCID":
            #print "OK", self.bdc[0]
            bdc = self.__bdcs.pop()
            self.__mcrs.append(bdc)
            bdc.bbox = tuple2list(self.__bbox)
            #print self.bdc
            self.__mc = False
            self.__bbox = None
            #sum0 = ""
            #sum1 = ""
            #for e in bdc.els:
            #    if not isinstance(e, list):
            #        sum0 += e
            #for e in bdc.control:
            #    for el in e:
            #        sum1 += el
            #assert(sum0 == sum1)
        elif opening == "Pagination":
            self.__pagination -= 1
        elif opening == "Artifact":
            self.__artifact -= 1
        elif opening == "BMCArtifact":
            self.__artifact -= 1
        return
    
    # TODO: H jakos ladniej niz [font, size] i odroznianie znakow od fontow po typie w
    # Node.__initialize (a nie ze font jest lista)
    # przetwarza polecenie Tf, zapamietuje ostatni font
    # jezeli jestesmy w zawartosci oznaczonej z MCIDem to dodaje do niej ten font
    # jezeli jest juz w niej tylko jeden font to zastepuje go (bo jest to font
    # dodawany zawsze na wszelki wypadek w do_BDC, skoro jest jedynym elementem
    # zawartosci to znaczy ze nie wystapil jeszcze tekst i nie jest on potrzebny
    # (bo aktualnie przetwarzany font wystepuje przed tekstem))
    def do_Tf(self, fontid, fontsize):
        super(TagInterpreter, self).do_Tf(fontid, fontsize)
        self.__aktfont = fontid
        self.__aktfontsize = fontsize
        if self.__mc:
            for bdc in self.__bdcs:
                if len(bdc.els) == 1 and isinstance(bdc.els[0], list):
                    bdc.els = [[self.__aktfont, self.__aktfontsize]]
                else:
                    bdc.els.append([self.__aktfont, self.__aktfontsize])
        return
   
    #@staticmethod
    #def toUni(font, seq):
    #    res = u""
    #    for obj in seq:
    #        for cid in font.decode(obj):
    #            res += font.to_unichr(cid)
    #    return res
    
    # przetwarza polecenie TJ, poza tym metody przetwarzajace inne polecenia
    # tekstowe przekazuja tu sterowanie
    def do_TJ(self, seq):
        if self.textstate.font is None:
            if STRICT:
                raise PDFInterpreterError('No font specified!')
            return
        #print "[-" + str(seq) + "-]"
        self.device.resetCharbboxes()
        self.device.render_string(self.textstate, seq) # ta metoda obliczy nam bounding boxy znakow i calego tekstu seq
        #fontik = self.textstate.font
        #print type(fontik)
        #exit()
        #textik = TagInterpreter.toUni(self.textstate.font, seq)
        self.__bbox = combine(self.__bbox, self.__bboxof(self.device)) # pobieramy bounding box calego tekstu
        self.__resetbbox(self.device)
        #print "TJ", self.bbox
        #print "[" + str(seq) + "]"
        if self.__mc:
            #lena = 0
            #lenb = 0
            for el in seq:
                assert(not isinstance(el, unicode))
                # dodajemy tekst do aktualnie przetwarzanej zawartosci oznaczonej z MCIDem
                if isinstance(el, str):
                    #print "[" + el + "]"
                    for bdc in self.__bdcs:
                        bdc.els.append(el)
                        #lena += len(el)
            for bdc in self.__bdcs:
                # pobieramy bouding boxy znakow
                for c in self.device.getCharbboxes():
                    bdc.charbboxes.append(c)
                    #lenb += 1
            #bdc.control.append(fontik)
            #bdc.control.append(seq)
            #for c in textik:
            #    #bdc.charbboxes.append(c)
            #    bdc.control.append(c)
            #    #lenb += 1
            #lena = len(textik)
            #if lena > 1000:
            #    print lena, lenb, len(seq), seq, self.device.getCharbboxes()
            #assert(lena == lenb)
        return
    
    # zwraca bounding box napisu przetworzonego przez Dummy Converter
    def __bboxof(self, device):
        if isinstance(device, DummyConverter):
            return device.getBbox()
        return None # nie powinno wystapic

    # resetuje bounding box zapamietany w Dummy Converter 
    def __resetbbox(self, device):
        if isinstance(device, DummyConverter):
            device.setBbox(None)
        return None # nie powinno wystapic

    # ponizej pozostale polecenia tesktowe:
    # TODO: I trzeba sie zastanowic co zrobic z poleceniami przenisienia do
    # nastepnego wiersza - czy na pewno wstawiac tam znak nowej linii? (co wtedy w hOCR (chodzi o rozne hardbreaki itp.))
    # poza tym w tej chwili ten dodawany znak \n nie ma odpowiadajacego mu charbboxa,
    # co spowoduje wywalenie sie programu 
    
    def do_Tj(self, s):
        self.do_TJ([s])
        return

    def do__q(self, s):
        self.do_T_a()
        if self.__mc:
            for bdc in self.__bdcs:
                #print "newline"
                #exit()
                bdc.els.append("\n")
                bdc.charbboxes.append(None)
        self.do_TJ([s])
        return
    
    def do__w(self, aw, ac, s):
        self.do_Tw(aw)
        self.do_Tc(ac)
        if self.__mc:
            for bdc in self.__bdcs:
                #print "newline"
                #exit()
                bdc.els.append("\n")
                bdc.charbboxes.append(None)
        self.do_TJ([s])
        return
    
    # TODO: F obsluga XForm (polecenie Do)
    
    # przetworz strone page (wywoluje nadklase pfdminerowa, ktora sie wszystkim
    # zajmie, przekazuje tylko sterowanie do metod tej klasy gdy dzieje sie cos
    # ciekawego)
    def process_page(self, page):
        #print "processPage"
        #print stream_value(page.contents[0])
        #print stream_value(page.contents[1])
        #print stream_value(page.contents[2])
        #print page
        #print page.contents
        #print page.contents[0]
        #print page.contents[1]
        #print page.contents[2]
        self.__page = page
        super(TagInterpreter, self).process_page(page)
        #print "STRONA: ", self.page
        return

# klasa poza tym ze sluzy jako zaslepka dla metod pdmfinerowych oblicza bouding boxy
# znakow i calych napisow na potrzeby TagInterpretera
class DummyConverter(PDFLayoutAnalyzer):
    
    def __init__(self, rsrcmgr, pageno=1, laparams=None):
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.__bbox = None # bounding box przetwarzanego napisu
        self.__itembbox = None # bounding box aktualnie przetwarzanego znaku
        self.__charbboxes = [] # bounding boxy znakow przetwarzanego napisu
        return
    
    def getBbox(self):
        return self.__bbox
    
    def getCharbboxes(self):
        return self.__charbboxes
    
    # resetuje bounding boxy znakow przed przetworzeniem nastepnego napisu
    def resetCharbboxes(self):
        self.__charbboxes = []

    def setBbox(self, bbox):
        self.__bbox = bbox

    # zaslepka
    def write(self, text):
        return

    # zaslepka
    def receive_layout(self, ltpage):
        return
    
    # metoda ktora w pdfminerze zajmuje sie czym innym, ale my wykorzystujemy
    # ja do obliczania bounding boxow napisu seq i jego znakow
    def render_string(self, textstate, seq):
        matrix = mult_matrix(textstate.matrix, self.ctm)
        font = textstate.font
        fontsize = textstate.fontsize
        scaling = textstate.scaling * .01
        charspace = textstate.charspace * scaling
        wordspace = textstate.wordspace * scaling
        rise = textstate.rise
        if font.is_multibyte():
            wordspace = 0
        dxscale = .001 * fontsize * scaling
        if font.is_vertical():
            textstate.linematrix = self.render_string_vertical(
                seq, matrix, textstate.linematrix, font, fontsize,
                scaling, charspace, wordspace, rise, dxscale)
        else:
            textstate.linematrix = self.render_string_horizontal(
                seq, matrix, textstate.linematrix, font, fontsize,
                scaling, charspace, wordspace, rise, dxscale)
        return
    
    # metoda ktora w pdfminerze zajmuje sie czym innym, ale my wykorzystujemy
    # ja do obliczania bounding boxow napisu seq i jego znakow
    def render_string_horizontal(self, seq, matrix, (x,y), 
                                 font, fontsize, scaling, charspace, wordspace, rise, dxscale):
        needcharspace = False
        #print len(self.__charbboxes)
        #print "render: " + str(seq)
        for obj in seq:
            #print "<" + obj + ">"
            if isinstance(obj, int) or isinstance(obj, float):
                x -= obj*dxscale
                needcharspace = True
            else:
                for cid in font.decode(obj):
                    if needcharspace:
                        x += charspace
                    x += self.render_char(translate_matrix(matrix, (x,y)),
                                          font, fontsize, scaling, rise, cid)
                    self.__bbox = combine(self.__bbox, self.__itembbox) # dodajemy bounding box
                        # przetworzonego znaku do sumy bounding boxow juz przetworzonych znakow
                    if cid == 32 and wordspace:
                        x += wordspace
                    needcharspace = True
        #print len(self.__charbboxes)
        return (x, y)

    #def render_string_vertical(self, seq, matrix, (x,y), 
    #                           font, fontsize, scaling, charspace, wordspace, rise, dxscale):
    # TODO: NOTE not implemented
    
    # metoda ktora w pdfminerze zajmuje sie czym innym, ale my wykorzystujemy
    # ja do obliczania bounding boxu znaku
    def render_char(self, matrix, font, fontsize, scaling, rise, cid):
        #super(PDFLayoutAnalyzer, self).render_char(matrix, font, fontsize, scaling, rise, cid)
        #item = LTChar(matrix, font, fontsize, scaling, rise, cid)
        try:
            text = font.to_unichr(cid)
        except PDFUnicodeNotDefined:
            text = '?'
        item = LTChar(matrix, font, fontsize, scaling, rise, text, font.char_width(cid), font.char_disp(cid))
        self.__itembbox = normalize(item.bbox)
        #self.__charbboxes.append(text)
        self.__charbboxes.append(self.__itembbox)
        self.cur_item.add(item)
        return item.adv
