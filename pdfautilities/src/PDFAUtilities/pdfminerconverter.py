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
from pdfminer.layout import LTFigure, LTImage, LTChar, LTTextLine, LTTextBox, LTTextGroup
from pdfminer.utils import enc, bbox2str
from pdfminer.pdfparser import PDFDocument, PDFSyntaxError, PDFParser
from pdfminer.pdfinterp import PDFTextExtractionNotAllowed
from pdfminer.pdftypes import dict_value, num_value, stream_value
from pdfminer.psparser import literal_name
from pdfminermod import stream_value2
from taglib import Font, PTree
from pdfreader import combine
from utils import normalize
import sys

# TODO: H nadklasa XMLLiba i TagLiba

# jezeli bierzemy strukture logiczna z pliku PDF to wtedy ladujemy go po prostu z
# uzyciem TagLiba
# ale jezeli bierzemy uklad strony z pdfminera za pomoca jednej z trzech istotnych metod
# PDFMinerParsera, to tego TagLiba nie mamy
# ta klasa powstala wiec jako zaslepka w takim wypadku - zalozenie jest ze niezaleznie
# od tego skad biezemy strukture dokumentu interfejs jest ten sam i niczym nie musimy
# sie przejmowac (w paru miejscach tak nie jest - sprawdzamy czy korzystamy ze
# struktury logicznej z pliku czy ukladu strony z pdfminera)
# poniewaz znaczenie metod i pol jest w wiekszosci przypadkach takie samo komentarze
# sa tylko tam gdzie cos jest inaczej, z tym ze z powodu tego ze to jest zaslepka
# nie ma tu initialize tylko rozne metody do ustawiania pol z zewnatrz
class XMLLib():
    
    def __init__(self, gui=False, map=None):
        self.__bboxes = {} # znaczenie to samo jak __pagebboxes w TagLibie, ale
            # musza byc przekazane do klasy przez metode addBbox
        self.__pageNo = 0
        self.__root = None
        self.__ptree = None 
        self.__pagenos = {} # prawdziwe numery stron (patrz getRealPageId)
        self.__gui = gui
        self.__map = map
    
    # laduje __ptree (jak w TagLibie intialize, tylko okrojone na potrzeby
    # samego tworzenia __ptree)
    def loadPTree(self, filen):
        doc = PDFDocument()
        fp = file(filen, 'rb')
        parser = PDFParser(fp)
        parser.set_document(doc)
        try:
            doc.set_parser(parser)
        except PDFSyntaxError:
            return False
        doc.initialize('')
        if not doc.is_extractable:
            raise PDFTextExtractionNotAllowed("Extraction is not allowed")
        self.__ptree = PTree()
        self.__initializePTree(doc)
        return True

    def getPhysicalTree(self):
        return self.__ptree
    
    def getPageNos(self):
        return self.__pagenos

    def __initializePTree(self, doc):
        self.__ptree.label = "Document"
        i = 1
        for p in doc.get_pages():
            child = PTree()
            child.label = "Page " + str(i)
            self.__pagenos.setdefault(i, p.pageid)
            i += 1
            child.data = p.pageid
            self.__ptree.children.append(child)
            child.parent = self.__ptree
            fonts = dict_value(p.resources.get("Font"))
            images = dict_value(p.resources.get("XObject"))
            #print images
            for (fontid, spec) in fonts.iteritems():
                # TODO: I czy tu zawsze bedzie referencja?
                objid = spec.objid
                spec = dict_value(spec)
                child2 = PTree()
                child2.label = "Font " + str(fontid)
                child2.data = Font.new(spec, None, p.pageid, child2, gui=self.__gui, map=self.__map)
                #print spec
                assert(child2.data.name != None)
                child.children.append(child2)
                child2.parent = child
            maskMap = {}
            masks = []
            def __isMask(spec):
                spec = stream_value(spec)
                if spec.get("ImageMask") == None:
                    return False
                else:
                    #print "else", num_value(spec.get("Mask")) 
                    return num_value(spec.get("ImageMask")) == 1 
            def __hasMask(spec):
                if stream_value(spec).get("Mask") == None:
                    #print "false"
                    return False
                elif stream_value2(stream_value(spec).get("Mask")) != None:
                    #print "true"
                    # TODO: NOTE pdfminer nie obsluguje genno                    
                    maskMap.setdefault(stream_value(spec).get("Mask").objid, spec.objid)
                    #print stream_value(spec).get("Mask").objid, spec.objid
                else:
                    #print "else"
                    return False
            for (objname, spec) in images.iteritems():
                #print spec
                # TODO: I czy tu zawsze bedzie referencja?
                objid = spec.objid
                isMask = False
                if __isMask(spec):
                    isMask = True
                spec = stream_value(spec)
                __hasMask(spec)
                if literal_name(spec.get("Subtype")) == "Image":
                    #print objid
                    child2 = PTree()
                    child2.label = "Image " + str(objname)
                    child2.data = (spec, i - 1, objid, 0)
                    child.children.append(child2) # TODO: NOTE pdfminer nie wspiera genno
                    child2.parent = child
                    if isMask:
                        masks.append(child2)
            for mask in masks:
                (a, b, c, d) = mask.data
                objid = maskMap.get(c)
                if objid != None:
                    #print c, objid
                    mask.data = (a, b, objid, d)
    
    # znajduje font o daenj nazwie w slowniku zasobow na danej stronie przy pomocy
    # obiektu tworzonego w __initializePTree  
    def findFont(self, page, font):
        #print page.pageid, font
        for p in self.__ptree.children:
            if p.data == page.pageid:
                for c in p.children:
                    #print c.data.fullName 
                    if font == c.data.fullName:
                        #print ":", font
                        #print c.data.bold 
                        return c.data
    
    def addBbox(self, pageid, bbox):
        self.__bboxes.setdefault(pageid, bbox)
    
    def getPageBBox(self, pageid):
        #print pageid, self.__bboxes
        return self.__bboxes.get(pageid)
    
    def getPageNo(self):
        return self.__pageNo
    
    def setRoot(self, root):
        self.__root = root
    
    def setPageNo(self, no):
        self.__pageNo = no
    
    # wynika wprost z wlasnosci ukladu strony zanalizowanego przez pdfminera
    # (dziecmi korzenia sa poszczegolne strony)
    # poniewaz jak widac poddrzewo zwracane przez ta metode bierzemy z tego samego
    # drzewa co zwrocone przez getRoot (co bierze sie z tego ze PDFMinerNode w
    # przeciwienstwie do Node nie jest poddane zwalnianiu pamieci) to nie ma
    # tu zaznaczania elementow do zaznaczenia w oknie rysowania strony przegladrki
    # graficznej jak w TagLib - odpowiedni wezel jest zaznaczany od razu w metodzie
    # LazyTree.__onClick - jest to jeden z przykladow gdzie interfejsy sie roznia
    # i trzeba explicite sprawdzac ktorego rodzaju struktury uzywamy
    def getStructureToDraw(self, pageNo):
        #print self.__root.getText(), pageNo, self.__root.getChildren()
        return self.__root.getChildren()[pageNo - 1]
    
    # j.w.
    def getStructureToDrawById(self, pageId):
        return self.__root.getChildren()[pageId]

    def getPageId(self, pageNo):        
        return pageNo - 1
    
    # jak widac w metodzie powyzej identyfikatory stron w ukladzie strony z
    # pdfminera to nie identyfikatory ich obiektow PDF tylko po prostu indeksy w
    # pliku liczone od 0
    # przyczyna tego jest to, ze poczatkowo uklad strony pdfminera ladowano
    # tylko parserem saxowym z pdfminerparser.py - a tam nie bylo identyfikatorow
    # pdfowych wiec przyjeto indeksowanie od 0
    # potem ta metoda zostala przyjeta dla ukladu strony pdfminera ladowanego
    # bezposrednio ze struktur danych pdfminera, ale okazalo sie ze w niektorych
    # przypadkach* potrzebny nam jest prawdziwy pdfowy identyfikator strony, wiec
    # dodano tako metode
    # zmienna self.__pagenos jest inicjalizowana w initializePTree
    # * patrz komentarz odnosnie identyfikatorow stron przed poczatkiem klasy
    # Preview w pdfastructurebrowser.py
    def getRealPageId(self, pageNo):
        #print pageNo, self.__pagenos.get(pageNo)
        return self.__pagenos.get(pageNo)
    
    def getPageNoById(self, pageId):
        return pageId + 1
    
    #def getNodeDict(self):
    #    return {}

# wezel drzewa ukladu strony zanalizowanego przez pdfminera
# poniewaz przyjeto zalozenie ze niezaleznie od tego skad biezemy strukture dokumentu
# interfejs jest ten sam i niczym nie musimy sie przejmowac (w paru miejscach tak nie
# jest - sprawdzamy czy korzystamy ze struktury logicznej z pliku czy ukladu strony z pdfminera)
# wiec klasa ma ten sam interfejs co Node i trzeba bylo powprowadzac zaslepki
# tak jak dla XMLLiba komentarze podane tylko tam gdzie roznice wzgledem Node 
class PDFMinerNode:

    def __init__(self, text, id=None):
        self.__text = text # nazwa elementu ukladu strony zanalizowanego przez pdfminera:
            # page, textgroup, textbox, textline lub text
        self.__id = id # uzywane tylko w SAXie
        self.__children = [] # dzieci, jak w Node
            # TODO: I jezeli chodzi o fonty, to obecnie do kazdego liscia
            # (elementu text reprezentujacego jeden znak) dodawany jest jeden font na
            # poczatku listy __children bedacy fontem tego znaku - jest to zaczerpniete z XML pdfminera,
            # ale w zasadzie mozna by tak to zrobic, ze font wstawiamy tylko do pierwszego
            # znaku w danym foncie, a nastepny dopiero jak font sie zmieni
        self.__bbox = None
        self.__contentType = "Text" # zawsze tekst (bo przetwarzany przez nas uklad
            # strony pdfminera zawiera tylko tekst)
        self.__isRoot = False
        self.__isLeaf = False
        self.__pageid = None
        self.__selected = False
    
    # w zasadzie niepotrzebne
    #def getObjId(self):
    #    return self.__pageid
        
    def isSelected(self):
        return self.__selected
    
    def select(self):
        self.__selected = True
    
    def unselect(self):
        self.__selected = False
    
    # puste - bo PDFMinerNode nie jest poddany zarzadzaniu pamiecia
    def uninitialize(self):
        self.__children = []
        pass
    
    # uzywane w Columnizerze - poniewaz drzewa z Node nigdy nie trafiaja
    # do Columnizera to w Node tej metody nie ma
    # jest tez uzywane w jednym miejscu w parserze SAX
    def setChildren(self, children):
        self.__children = children
    
    def getChildren(self):
        return self.__children

    # bo PDFMinerNode nigdy nie jest dzielony
    def getGroupId(self):
        return None

    def setPageId(self, pageid):
        self.__pageid = pageid
    
    # w przeciwienstwie do getPageId w Node ta metoda fatycznie sie przydaje,
    # bo mozna za jej pomoca uzyskac numer strony w module dowolnego przetwarzania
    def getPageId(self):
        return self.__pageid
       
    def getPageIds(self):
        return [self.__pageid]
    
    def isLeaf(self):
        return self.__isLeaf
    
    # bo tu nie ma tagow z pdfa wiec slownik /RoleMap nie ma sensu
    def getStandardText(self):
        return self.__text
    
    # wynika ze struktury drzewa - jedynym elementem polozonym na wiecej niz jednej
    # stronie jest korzen a implementacja konwertera gwarantuje ze na nim nigdy ani
    # ta metoda ani split nie bedzie wywolany
    def multipage(self):
        return False
    
    # j.w.
    def split(self):
        pass
    
    def getBbox(self):
        #if self.__bbox == None:
        #    print self.getText()
        # TODO: NOTE bo zawsze bbox ustawiany przy parsowaniu, ale moze byc czasowo None
        # w obiektach tworzonych w columnizerze; w module dowolnego przetwarzania
        # musi byc zainicjalizowany metoda resetBbox
        #assert(self.__bbox != None)
        return self.__bbox

    # wynika z wlasnosci ukladu strony zanalizowanego przez pdfminera - lisciami
    # sa pojedyncze znaki
    def getCharbboxes(self):
        if self.getText() == "text":
            return [self.__bbox]
        else:
            res = []
            for c in self.__children:
                res += c.getCharbboxes()
            return res
    
    def isRoot(self):
        return self.__isRoot
    
    def setRoot(self):
        self.__isRoot = True
    
    def add(self, child):
        self.__children.append(child)

    def setBbox(self, bbox):
        self.__bbox = bbox
    
    def isPage(self):
        return self.__text == "page"
    
    # nazwa elementu
    def getText(self):
        return self.__text
    
    # bo tu nie ma tagow z pdfa wiec slownik /RoleMap nie ma sensu
    def getRole(self):
        return None

    def getId(self):
        return self.__id

    # podmienia aktualny element na textBox - uzywane w Columnizerze
    def replaceWith(self, textBox):
        self.__children = textBox.__children
        self.__bbox = textBox.getBbox()

    # uzywane bylo do debugowania
    def write(self, level=0):
        for _ in range(level):
            print "  ",
        #if self.__isLeaf: nie wystapi bo przeskajujemy przez text z textline
        if self.__text == "textline":
            res = ""
            for c in self.__children:
                if c.getText() == "text":
                    for d in c.__children:
                        if isinstance(d, unicode):
                            res += d.encode("utf-8")
                        elif isinstance(d, str):
                            res += d
            print res
        else:
            print self.__text
            for child in self.__children:
                if isinstance(child, PDFMinerNode):
                    child.write(level + 1)
    
    # moze sie przydac (np. w module dowolnego przetwarzania)
    # uzyc np. jesli zmenily sie dzieci (a w takim module tak wlasnie sie dzieje)
    # Columnizer zdaje sie recznie ustawia bounding boxy wiec nie uzywa tej metody
    def resetBbox(self):
        if not self.__isLeaf:
            for c in self.__children:
                c.resetBbox()
            self.__bbox = None
            for c in self.__children:
                self.__bbox = combine(self.__bbox, c.getBbox())
    
    # kopiuje element na potrzeby Columnizera
    # w przeciwienistwie do Node.__partialCopy dzieci tez sa kopiowane,
    # ale jako referencje (tzn. oryginalny element i kopia maja na liscie
    # __children te same obiekty) 
    def childrenCopy(self):
        # TODO: NOTE kopiuje referencje do dzieci i bboxa
        copy = PDFMinerNode(self.__text)
        copy.__children = []
        copy.__isLeaf = self.__isLeaf
        copy.__isRoot = self.__isRoot
        copy.__contentType = self.__contentType
        copy.__bbox = self.__bbox
        copy.__text = self.__text
        copy.__pageid = self.__pageid        
        for c in self.__children:
            copy.__children.append(c)
        return copy
    
    # skleja dwa elementy w jeden
    def join(self, joinedNode):
        for c in joinedNode.__children:
            self.__children.append(c)
        self.setBbox(combine(self.getBbox(), joinedNode.getBbox()))
    
    # TODO: H uzyc gdzie sie da zamiast recznego sklejania z <text>
    def getTextContent(self):
        def __traverse(node, res=u""):
            if node.__text == "text":
                for c in node.__children:
                    if isinstance(c, unicode):
                        res += c
            else:
                for c in node.__children:
                    res += __traverse(c)
            return res
        res = __traverse(self)
        assert(isinstance(res, unicode))
        return res
    
    def getContentType(self):
        return self.__contentType
    
    def setLeaf(self):
        self.__isLeaf = True
    
    # znajduje wszystkich potomkow bedacych liniami (uzywane w Columnizerze)
    def findLines(self, lines=None):
        if lines == None:
            lines = []
        for c in self.__children:
            if isinstance(c, PDFMinerNode):
                if c.__text == "textline":
                    lines.append(c)
                else:
                    lines = c.findLines(lines=lines)
        return lines
    
    # zsortuje dzieci za pomoca funkcji cmp (uzywane w Columnizerze)
    def sortChildren(self, cmp):
        self.__children.sort(cmp)
    
    # rekurencyjnie wywoluje na wszystkich wezlach poddrzewa z korzeniem w self
    # funkcje fun (uzywane w Columnizerze)
    def recursivelyProcess(self, fun, level=0):
        fun(self, level)
        for c in self.__children:
            if isinstance(c, PDFMinerNode):
                c.recursivelyProcess(fun, level=level + 1)

    # metadane maja sens tylko dla Node
    def getMetadata(self):
        return ""

# rozszerzenie klasy PDFLayoutAnalyzer ktore na podstawie zanalizowanego ukladu strony
# tworzy drzewo struktury z elementow PDFMinerNode
# jezeli podano jako argument eksporter do hOCR to wygenerowany uklad strony jest od
# razu eksportowana, byc moze po przetworzeniu Columnizerem
class PDFMinerConverter(PDFLayoutAnalyzer):

    def __init__(self, rsrcmgr, ignore, codec='utf-8', pageno=1, laparams=None, outdir=None, lib=None, hocr=None, columnizer=None):
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        #self.__codec = codec
        self.__ignore = ignore # patrz parametry pdfa2hocr.py
        #self.__outdir = outdir
        if hocr == None: # nie eksportujemy do hOCR
            #self.__root.__isRoot = True # ustawiane w PDFMinerParserze.getResult()
            self.__node = PDFMinerNode("pages") # korzen drzewa struktury, jezeli
                # eksportujemy do hOCR niepotrzebny, bo eksportujemy strona po stronie 
            self.__root = self.__node # korzen generowanego drzewa struktury
        else: # eksportujemy
            self.__node = None # aktualnie przetwarzany wezel
        self.__hocr = hocr # eksporter do hOCR
        self.__columnizer = columnizer # obiekt przeprowadzajacy dodatkowa analize
            # uklady strony
        self.__fontDict = {} # slownik fontow (zeby nie fontom o tej samej
            # nazwie i rozmiarze odpowiadal jeden obiekt klasy Font)
        self.__page = None # aktualnie przetwarzana strona (obiekt PDFMinerNode)
        self.__num = -1 # numer strony liczony od 0 (PDFMinerNode.__pageid)
        self.__font = None # ostatnio przetwarzany font
        self.__stack = [] # stos na ktorym sa przodkowie aktualnie przetwarzanego elementu
        self.__lib = lib # zaslepka XMLLib w ktorej musimy zainicjalizowac bounding boxy stron
            # i ktora zawiera obiekt __ptree z ktorego pobierzemy fonty
        self.__pdfminerpage = None # aktualnie przetwarzana strona (obiekt pdfminera)
        return
    
    # korzen wygenerowanego drzewa struktury
    def getResult(self):
        return self.__root
       
    def begin_page(self, page, ctm):
        self.__pdfminerpage = page
        PDFLayoutAnalyzer.begin_page(self, page, ctm)
    
    def __setBbox(self, node, bboxString):
        # TODO: od razu z item.bbox
        bbox = []
        bbox.append(float(bboxString.split(",")[0]))
        bbox.append(float(bboxString.split(",")[1]))
        bbox.append(float(bboxString.split(",")[2]))
        bbox.append(float(bboxString.split(",")[3]))
        #assert(node.__bbox == None)
        node.setBbox(bbox)

    # przetwarza uklad strony pdfminera przekazana w parametrze ltpage
    def receive_layout(self, ltpage):
        def render(item):
            self.__stack.append(self.__node)
            parent = self.__node
            if isinstance(item, LTPage):
                self.__num += 1                
                self.__page = PDFMinerNode("page")
                self.__page.setPageId(self.__num)
                self.__setBbox(self.__page, bbox2str(normalize(item.bbox)))
                if self.__lib != None:
                    self.__lib.addBbox(self.__page.getPageId(), self.__page.getBbox())
                self.__node = self.__page
                for child in item:
                    render(child) 
            elif isinstance(item, LTLine):
                pass
            elif isinstance(item, LTRect):
                pass
            elif isinstance(item, LTCurve):
                pass
            elif isinstance(item, LTFigure):
                pass
            elif isinstance(item, LTTextLine):
                #print "textline"
                self.__node = PDFMinerNode("textline")
                self.__node.setPageId(self.__num)
                parent.add(self.__node)
                self.__setBbox(self.__node, bbox2str(normalize(item.bbox)))                
                for child in item:
                    render(child)
            elif isinstance(item, LTTextBox):
                self.__node = PDFMinerNode("textbox", item.index)
                self.__node.setPageId(self.__num)
                parent.add(self.__node)
                self.__setBbox(self.__node, bbox2str(normalize(item.bbox)))
                for child in item:
                    render(child)
            elif isinstance(item, LTChar):
                #font = enc(item.font.fontname)
                font = enc(item.fontname)
                #size = item.get_size()
                size = item.size
                self.__font = self.__fontDict.get(font + str(size))
                if self.__font == None:
                    self.__font = self.__fontDict.setdefault(font + str(size), self.__lib.findFont(self.__pdfminerpage, font).instantiate(size))
                self.__node = PDFMinerNode("text")
                self.__node.setPageId(self.__num)
                self.__node.setLeaf()
                #self.__node.setContentType("Text")
                parent.add(self.__node)
                #print parent.textOf()
                #assert(parent.textOf() == "textline")
                self.__setBbox(self.__node, bbox2str(normalize(item.bbox)))
                if self.__font != None:
                    self.__node.add(self.__font)
                    #assert(self.__node.textOf() == "text")
                self.__node.add(item.get_text())    
            elif isinstance(item, LTText):
                pass
                # TODO: NOTE ignorujemy tekst pusty (tu byly same spacje)
                #self.outfp.write('<text>%s</text>\n' % item.get_text())
            elif isinstance(item, LTImage):
                pass
            elif isinstance(item, LTTextGroup):
                self.__node = PDFMinerNode("textgroup")
                self.__node.setPageId(self.__num)
                parent.add(self.__node)
                self.__setBbox(self.__node, bbox2str(normalize(item.bbox)))
                for child in item:
                    render(child)
            else:
                assert 0, item
            self.__node = self.__stack.pop()
            return
        # ltpage to strona ktorej dziecmi sa elementy typu "textbox",
        # w ltpage.layout jest uklad z uzyciem elementow "textgroup" (ktora
        # zawiera jako potomkow takze elementy "textbox" bedace dziecmi strony)
        if ltpage.groups and not self.__ignore: # nie ignorujemy "textgroup" i
                # "textgroup" sa w zanalizowanym ukladzie 
            self.__num += 1
            self.__stack.append(self.__node)
            self.__page = PDFMinerNode("page") # recznie eksportujemy strone
            self.__page.setPageId(self.__num)
            self.__setBbox(self.__page, bbox2str(normalize(ltpage.bbox)))
            if self.__lib != None:
                self.__lib.addBbox(self.__page.getPageId(), self.__page.getBbox())
            self.__node = self.__page
            for lay in ltpage.groups:
              render(lay) # eksportujemy "textgroup" i potem rekurencyjnie
                # potomkow
            self.__node = self.__stack.pop()
            if self.__hocr == None:
                self.__node.add(self.__page) # dodajemy strone do korzenia drzewa
            else:
                if self.__columnizer != None:
                    self.__columnizer.columnizePageUsingGroups(self.__page)
                    if self.__columnizer.isFatal():
                        sys.stderr.write(self.__columnizer.getLastMessage())
                        sys.exit()
                    elif self.__columnizer.isError():
                        sys.stderr.write("Warning: " + self.__columnizer.getLastMessage() + "\n")
                self.__hocr.exportPage(self.__page)
        else: # ignorujemy "textgroup" lub ich nie ma 
            # TODO: I sprawdzic: jezeli brak ltpage.layout to chyba rownoznaczne ze strona bez tekstu?
            render(ltpage) # eksportujemy strone i potem rekurencyjnie potomkow
            if self.__hocr == None:
                self.__node.add(self.__page) # dodajemy strone do korzenia drzewa
            else:
                if self.__columnizer != None:
                    self.__columnizer.columnizePageUsingGroups(self.__page)
                    if self.__columnizer.isFatal():
                        sys.stderr.write(self.__columnizer.getLastMessage())
                        sys.exit()
                    elif self.__columnizer.isError():
                        sys.stderr.write("Warning: " + self.__columnizer.getLastMessage() + "\n")
                self.__hocr.exportPage(self.__page)
        return

    #def close(self):
    #    pass
