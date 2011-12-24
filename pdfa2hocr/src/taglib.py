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

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import re
import uuid
from pdfminer.pdfparser import PDFDocument, PDFParser, PDFSyntaxError
from pdfminer.pdftypes import dict_value, stream_value, num_value, list_value
from pdfminermod import dict_value2, list_value2, num_value2, stream_value2, list_value_none
from pdfminermod import num_value_none, dict_value_none, str_value_none, stream_value_none, literal_name_none
from pdfminer.psparser import literal_name
from pdfminer.pdfinterp import PDFResourceManager, PDFTextExtractionNotAllowed
from pdfminer.layout import LAParams
from pdfminer.pdffont import PDFUnicodeNotDefined
from pdfreader import TagInterpreter, DummyConverter
from utils import combine, keyOf, uniToString, isSubsetName, normalize
from ttFontMod import TTFontMod

# Uwagi:
# przez identyfikator strony (czesto okreslany jako pageid) rozumiemy identyfikator
# obiektu PDF reprezentujacego strone
# dotyczy to tez innych obiektow - slowo identyfikator oznacza identyfikator obiektu
# PDF
# identyfikator jest tylko pierwsza czescis wlasciwego identyfikatora PDF, poniewaz
# pdfminer nie wspiera numerow generacji

# wszystkie numery stron dotycza:
# PDF Reference, Third Edition, Adobe Portable Document Format Version 1.4,
# Addison-Wesley, 2001

# TODO: I pole pageid w obiekcie PDFPage - trzeba sie upewnic, czy to jest zawsze
# ten identyfikator jak wspomniano powyzej ("empirycznie" jest)

# TODO: I warto kiedys sprawdzic, czy w programie nie trafiaja sie bledy typu:
# a = [jakas lista]
# b = a // myslimy ze to kopia, a to wskazniki
# zmieniamy(a)
# b sie nam zmienilo (a nie chcielismy tego)

# klasa udostepnia interfejs do pdfminera
# jeden obiekt tej klasy obsluguje jeden dokument PDF
class TagLib:
    
    def __init__(self, gui=False, map=None):
        self.__laparams = None # parametry analizatora struktury logicznej pdfminera (nieuzywane)
        self.__rsrcmgr = None # zarzadca zasobow pdfminera (PDFResourceManager) - umozliwia znalezienie pdfminerowego obiektu fontu
        self.__device = None # obiekt klasy DummyConverter znajdujacy bounding boxy znakow 
        self.__pagebboxes = {} # bounding boxy stron - kluczami sa identyfikatory stron
        self.__ptree = PTree() # obiekt zawierajacy slowniki zasobow stron dokumentow
        self.__roleMap = {} # /RoleMap ze slownika korzenia drzewa struktury logicznej (str. 590)
            # TODO: I z obluga /RoleMap jest w tej chwili taki ogolny problem:
            # Obecnie konwerter na hOCR nie wspiera mapowania na elementy hOCR
            # oryginalnych nazw elementow (pod kluczem /S), a powinien je wspierac,
            # poniewaz niektore aplikacje moga roznie traktowac rozne nazwy mimo ze
            # mapuja na ta sama nazwe standardowa tagowanego PDF. Pozwala tylko na mapowanie nazw
            # na ktore nazwy elementow mapuja z uzyciem obiektu pod kluczem /RoleMap
            # w drzewie struktury logicznej dokumentu. Poza tym mapowanie z /RoleMap
            # obliczane jest tylko raz (powinno byc obliczane ponownie dla obliczonej nazwy
            # az dojdziemy do nazwy standardowej tagowanego PDF)
        self.__classMap = {} # /ClassMap ze slownika korzenia drzewa struktury logicznej (str. 590)
        self.__mcrs = [] # tymczasowy obiekt na ktorym po wykonaniu metody getMcrs znajduja sie zawartosci oznaczone z danej strony
        self.__pageNo = 0 # liczba stron w dokumencie 
        self.__pageNos = {} # mapowanie z numerow stron na identyfikatory ich obiektow PDF
        self.__tagtree = None # korzen drzewa struktury logicznej
        self.__tagtreeId = 0 # identyfikator obiektu PDF bedacego korzeniem drzewa struktury (StructTreeRoot)
        self.__doc = None # pdfminerowy obiekt reprezentujacy dokument
        self.__ti = None # tymczasowy obiekt na ktorym w metodzie getMcrs znajduje sie obiekt TagInterpreter dla danej strony
        self.__tmpNodeDict = {} # tymczasowy slownik dokumentow uzywany w getStructureToDrawById
        self.__selected = None # identyfikator elementu struktury logicznej ktory ma byc zaznaczony w oknie rysowania strony przegladarki graficznej
        self.__gui = gui # flaga informujaca czy klasa jest wykorzystywana przez program w graficzny (nie sa wtedy wypisywane komunikaty o fontach)
        self.__map = map # mapowanie postscriptowych nazw fontow na nazwe rodziny fontu, podawane jako parametr w konwerterze na hOCR
    
    # laduje dokument o sciezce filen za pomoca pdfminera
    def initialize(self, filen, dialog=None):
        self.__tagtree = None
        self.__tagtreeId = 0
        self.__pageNos = {}
        self.__doc = PDFDocument()
        fp = file(filen, 'rb')
        parser = PDFParser(fp)
        parser.set_document(self.__doc)
        try:
            self.__doc.set_parser(parser)
        except PDFSyntaxError:
            return False # nie udalo sie wczytac dokumentu
        self.__doc.initialize('')
        if not self.__doc.is_extractable:
            raise PDFTextExtractionNotAllowed("Extraction is not allowed")
        self.__mcrs = []
        self.__laparams = LAParams()
        self.__rsrcmgr = PDFResourceManager()
        self.__device = DummyConverter(self.__rsrcmgr, laparams=self.__laparams)
        self.__ptree = PTree()
        self.__initializePTree(self.__doc)
        #print "PTree __initialized"
        counter = 0
        #length = sum(1 for p in doc.get_pages())
        self.__pageNo = num_value(dict_value(self.__doc.catalog.get("Pages")).get("Count"))
        for p in self.__doc.get_pages():
            self.__pagebboxes.setdefault(p.pageid, normalize(p.mediabox))
            counter += 1
            self.__pageNos.setdefault(counter, p.pageid)
        #print "pages"
        if self.__doc.catalog.get("StructTreeRoot") != None:
            self.__tagtree = dict_value(self.__doc.catalog.get('StructTreeRoot'))
            self.__tagtreeId = self.__doc.catalog.get('StructTreeRoot').objid
        if self.__tagtree != None:
            self.__roleMap = dict_value(self.__tagtree.get("RoleMap"))
            self.__classMap = dict_value(self.__tagtree.get("ClassMap"))
        #print "catalog"
        #for mc in mcrs:
        #    print mc[0]
        #print "TagLib ready"
        return True
    
    # czy dokument zawiera drzewo struktury logicznej
    def hasRoot(self):
        return self.__tagtree != None

    # zwraca obiekt inicjalizowany w __initializePTree    
    def getPhysicalTree(self):
        return self.__ptree

    # tworzy obiekt w ktorym pamietane sa fonty i obrazki zawarte w slownikach zasobow
    # poszczegolnych stron
    def __initializePTree(self, doc):
        self.__ptree.label = "Document"
        i = 1
        for p in doc.get_pages():
            child = PTree()
            child.label = "Page " + str(i)
            i += 1
            child.data = p.pageid
            self.__ptree.children.append(child)
            child.parent = self.__ptree
            fonts = dict_value(p.resources.get("Font"))
            images = dict_value(p.resources.get("XObject"))
            #print images
            for (fontid, spec) in fonts.iteritems():
                # TODO: I to opiera sie na tym, ze w tym miejscu zawsze wystapi
                # referencja - poniewaz nie zawsze musi tak byc program moze sie
                # wywalic - w ostatecznosci trzeba znalezc jakies obejscie
                objid = spec.objid
                spec = dict_value(spec)
                child2 = PTree()
                child2.label = "Font " + str(fontid)
                child2.data = Font.new(spec, self.__rsrcmgr.get_font(objid, spec), p.pageid, child2, gui=self.__gui, map=self.__map)
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
                # TODO: I to opiera sie na tym, ze w tym miejscu zawsze wystapi
                # referencja - poniewaz nie zawsze musi tak byc program moze sie
                # wywalic - w ostatecznosci trzeba znalezc jakies obejscie
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
    
    # znajduje font o danym kluczu w slowniku zasobow na danej stronie przy pomocy
    # obiektu tworzonego w __initializePTree  
    def findFont(self, page, font):
        for p in self.__ptree.children:
            if p.data == page.pageid:
                for c in p.children:
                    if c.label[0:4] == "Font":
                        if literal_name(font) == c.label[5:]:
                            return c.data
    
    def getRoleMap(self):
        return self.__roleMap
    
    def getClassMap(self):
        return self.__classMap

    def getPageBBox(self, pageid):
        #print pageid, self.__pagebboxes.keys()
        return self.__pagebboxes.get(pageid)
    
    def getPageNos(self):
        return self.__pageNos
    
    # obie ponizsze metody daja ten sam wynik, bo w TagLibie jest tylko jedno
    # znaczenie identyfikatora strony
    # w XMLLibie jest inaczej i powstala potrzeba rozroznienia tych dwoch
    # identyfikatorow - dlatego sa dwie metody (bo obie klasy maja ten sam interfejs)
    # (por. XMLLib.getRealPageId) 
    def getPageId(self, pageNo):
        return self.__pageNos.get(pageNo)
    
    def getRealPageId(self, pageNo):
        return self.__pageNos.get(pageNo)
    
    # zamienia identyfikator strony na numer strony
    def getPageNoById(self, pageId):
        return keyOf(self.__pageNos, pageId)

    # liczba stron
    def getPageNo(self):
        return self.__pageNo

    # zwraca obiekt Node reprezentujacy korzen drzewa struktury logicznej
    def getRoot(self):
        rootNode = Node(self.__tagtree, self.__tagtreeId, self)
        #rootNode = tagtree
        rootNode.setRoot()
        return rootNode
    
    # znajduje wszystkie zawartosci oznaczone z danej strony
    def getMcrs(self, pageid):
        # TODO: NOTE czy p.pageid jest zawsze idem pdfowym? (pageid jest bo wyciagamy
        # go ze slownika StructElem)
        if self.__ti == None or self.__ti.getPageId() != pageid:
            self.__ti = TagInterpreter(self.__rsrcmgr, self.__device)
            self.__ti.setPageId(pageid)
            for p in self.__doc.get_pages():
                #print stream_value(p.contents[0])
                #print stream_value(p.contents[1])
                #print stream_value(p.contents[2])
                #print "PAGE"
                if p.pageid == pageid:
                    #self.__ti.resetPage()
                    self.__ti.process_page(p)
                    break
        self.__mcrs = self.__ti.getMcrs()
        return self.__mcrs

    # dekoduje tekst przy uzyciu pdfminerowego obiektu fontu i zamienia na unicode
    def textof(self, text, font):
        if font == None:
            return text.encode("utf-8")
        x = u""
        for obj in text:
            for cid in font.decode(obj):
                try:
                    x += font.to_unichr(cid)
                except PDFUnicodeNotDefined:
                    x += u'?'
        return x
    
    # znajduje w drzewie ParentTree (PDF Reference Third Edition str. 600)
    # obiekt pod kluczem num
    def __getNum(self, tree, num):
        li = list_value2(tree.get("Nums"))
        if li == None:
            for k in list_value2(tree.get("Kids")):
                k = dict_value(k)
                if k.get("Limits")[0] <= num and k.get("Limits")[1] >= num:
                    return self.__getNum(k, num)
        else:
            for i in range(len(li) / 2):
                #print i, i *2, i * 2 + 1, num
                if i == num:
                    return li[i * 2 + 1]
        return None
    
    # znajduje wspolnego przodka wezlow nodes w drzewie struktury logicznej
    # ogolna zasada dzialania: z kazdego wezla w nodes idziemy do jego ojca, w
    # nastepnym kroku z ojcow do dziadkow itd., jak po drodze gdzies natrafimy
    # na odwiedzony wezel to zapamietujemy go jako miejsce polaczenia
    # potem, jak zostanie nam tylko jeden wezel, cofamy sie od niego w dol do
    # pierwszego miejsca polaczenia
    def __lastCommonAncestor(self, nodes):
        parents = []
        parents.extend(nodes)
        joins = []
        visited = []
        for n in nodes:
            visited.append(n.getObjId())
        if len(nodes) == 1:
            #print ":::::::::::::::::::::::::::::::::::::::::::::", nodes[0].getStandardText()
            #print nodes[0].getTextContent()
            #print nodes[0].isLeaf()
            #print len(nodes[0].getChildren())
            #print nodes[0].getBbox()
            return nodes[0]
        while len(nodes) > 1:
            #for n in nodes:
            #    assert(n.getObject().get("P") != None)
            nodesCopy = []
            nodesCopy.extend(nodes)
            nodes = []
            #for n in nodesCopy:
            #    print n.getStandardText(),
            #print "-"
            #for p in parents:
            #    print p.getStandardText(),
            #print "-"
            #for j in joins:
            #    print j.getStandardText(),
            #print "----"
            for n in nodesCopy:
                #print "  PROC:", n.getStandardText()
                # TODO: I roota sprawdzac spojnie z determinePageParents - tam jest
                # jeszcze dodatkowo sprawdzane, czy Document jest jedynym dzieckiem
                # StructTreeRoota 
                if n.getStandardText() == "StructTreeRoot" or n.getStandardText() == "Document":
                    #print "    root!"
                    if not n in nodes:
                        #assert(n.getObject().get("P") != None)
                        nodes.append(n)
                    continue
                #print n.getStandardText()
                parent = self.__getNode(dict_value(n.getObject().get("P")), n.getObject().get("P").objid)
                if not parent.getObjId() in visited:
                    visited.append(parent.getObjId())
                #print parent, parent.getText()
                #parent = Node(dict_value(n.getObject().get("P")), n.getObject().get("P").objid, self)
                if parent in parents: # juz bylismy w parencie
                    #print "  JOIN:", parent.getStandardText()
                    if not parent in joins:
                        #assert(isinstance(parent, Node))
                        joins.append(parent)
                else:
                    #print "  NODE:", parent.getStandardText()
                    if not parent in parents:
                        parents.append(parent)
                    if not parent in nodes:
                        nodes.append(parent)
            #if len(nodes) == 0:
            #    print parents
            #    print joins
            #if len(nodes) == 0:
        #print "AFTER"
        #for n in nodesCopy:
        #    print n.getStandardText(),
        #print "-"
        #for p in parents:
        #    print p.getStandardText(),
        #print "-"
        #for j in joins:
        #    print j.getStandardText(),
        #print "----"
        #for j in joins:
        #    print ":", j.getObjId(), j.getStandardText()
        lca = nodes[0]
        #print "=>", lca.getStandardText()
        pars = [lca]
        if lca in joins:
            #print lca.getStandardText()
            return lca
        #for (k, v) in self.__nodeDict.iteritems():
        #    print k, v.getStandardText(), v.getObjId()
        #print "tu"
        while True:
            newPars = []
            for par in pars:
                #print par.getStandardText()
                if not isinstance(par, Node):
                    continue
                for c in par.getChildrenFromDict(self.__getNode, visited):
                    #if not c.getObjId() in visited:
                    #    continue
                    #if isinstance(c, Node) and c.getText() == "Document":
                    #    for j in joins:
                    #        print ":", j.getObjId(), j.getStandardText()
                    #        if isinstance(c, Node):
                    #            print c.getObjId(), c.getStandardText()
                    #            print j == c, j, c
                    if c in joins:
                        #print c.getStandardText()
                        return c
                    newPars.append(c)
            pars = newPars
        #print "tam"
        assert(False)                    
    
    # znajduje w slowniku __tmpNodeDict obiekt Node o danym identyfikatorze, a jak
    # nie ma to dodaje go do tego slownika
    # metoda wykorzystywana tylko w getStructureToSrawById
    def __getNode(self, obj, objid):
        #print objid
        if self.__tmpNodeDict.get(objid) == None:
            node = Node(obj, objid, self, preview=True)
            self.__tmpNodeDict.setdefault(objid, node)
            #print "niema"
            return node
        else:
            #print "jest"
            return self.__tmpNodeDict.get(objid)
    
    # znajduje elementy struktury logicznej ktore znajduja sie na stronie o
    # identyfikatorze pageid
    # sa one przekazywane jako wezel w drzewie struktury logicznej bedacy wspolnym
    # przodkiem wszystkich tych elementow obcietym tylko do elementow z danej strony
    # znalezione elementy beda pokazane w oknie rysowania strony przegladarki graficznej 
    # metoda wykorzystuje drzewo pod kluczem /ParentTree w korzeniu drzewa struktury logicznej
    # TODO: I uwaga - obiekty zwracane przez ta metode istnieja niezaleznie od obiektow
    # powstalych przez rozwiniecie przez __initialize drzewa z korzeniem w obiekcie
    # zwroconym przez getRoot do przegladarki drzewa struktury; mialo to na celu uproszczenie
    # zarzadzania pamiecia
    def getStructureToDrawById(self, pageid):
        # TODO: F referencje z obiektow (ale potem, bo narazie i tak nie obslugujemy obiektow)
        #print pageid
        self.__tmpNodeDict = {}
        pparent = dict_value(dict_value(self.__doc.catalog.get("StructTreeRoot")).get("ParentTree"))
        nodes = []
        for p in self.__doc.get_pages():
            if p.pageid == pageid:
                id = num_value_none(p.attrs.get("StructParents"))
                if id == None:
                    return None
                val = self.__getNum(pparent, id)
                #print id, val, pageid
                if list_value2(val) == None:
                    obj = dict_value(val)
                    objid = val.objid
                    node = self.__getNode(obj, objid)
                    #node = Node(obj, objid, self)
                    if not node in nodes:
                        assert(obj.get("P") != None)
                        nodes.append(node)
                else:
                    for objref in list_value2(val):
                        obj = dict_value(objref)
                        #print obj
                        objid = objref.objid
                        node = self.__getNode(obj, objid)
                        #node = Node(obj, objid, self)
                        assert(obj.get("P") != None)
                        if not node in nodes:
                            nodes.append(node)
                for n in nodes:
                    assert(n.getObject().get("P") != None)
                #print "tu"
                #print nodes
                lca = self.__lastCommonAncestor(nodes)
                #print "tam"
                #if len(lca.getChildren() > 2 * len(nodes)):
                # TODO: D ID0 zrobic: oraz efektywny lastCommonAncestor, przy czym jest to heureza i dobrze by bylo znalezc lepsza
                # TAK:
                # a) Document i StructTreeRoot
                # b) multipage wiecej niz 20 stron
                # c) pageid == None
                # tutaj
                #print lca.getStandardText()
                if lca.multipage():
                    #print "&$#*($#($^#&*$^*&#$^*@#$^(@*#(@#&)(@#*&(*$^#*&$^#*(&$^@*(#$&(@#*&@(*#$"
                    lca.split(True)
                    #print str.getCopies().get(pageid)
                    res = lca.getCopies().get(pageid)
                    self.__select(res)
                    return res
                self.__select(lca)
                return lca
        return None
    
    # zapala w obiekcie Node flage __selected ktora oznacza ze element struktury logicznej
    # reprezentowany przez ten obiekt powinien byc widoczny w oknie rysowania strony przegladarki graficznej
    def __select(self, node):
        #print self.__selected, node.getObjId()
        if self.__selected == node.getObjId():
            node.select()
        for c in node.getChildren():
            if isinstance(c, Node):
                self.__select(c)

    # wybiera do zaznaczenia w oknie rysowania strony przegladarki graficznej element struktury o identyfikatorze objid
    # informacja ta jest potem wykorzystywana w metodzie getStructureToDrawById do zapalenia w
    # odpowiednim obiekcie klasy Node flagi __selected  
    def select(self, objid):
        self.__selected = objid

    # znajduje elementy struktury logicznej ktore znajduja sie na stronie o danym numerze
    # patrz opis metody getStructureToDrawById
    def getStructureToDraw(self, pageNo):
        pageid = self.__pageNos.get(pageNo)
        str = self.getStructureToDrawById(pageid)
        #print "#############################", str.getStandardText()
        #print str.multipage()
        return str

# obiekt w ktorym jest zapamietywana zawartosc slownika zasobow strony
# powinien on w zasadzie byc zaimplementowany inaczej, forma drzewa jest
# pozostaloscia z dawnej implementacji graficznego interfejsu
# dziecmi korzenia sa strony, a ich dzieci to fonty i obrazki
class PTree:
    
    def __init__(self):
        self.data = None # (patrz __initializePTree) dla fontow: obiekt klasy Font,
            # dla obrazkow: (pdfowy slownik obrazka, nr strony, identyfikator pdfowego
            # slownika obrazka (uwaga: dla maski jest to identyfikator maskowanego obrazka a
            # nie wlasciwej maski, oczywiscie jezeli maska maskuje wiecej niz jeden obrazek
            # program moze sie wywalic, numer generacji slownika obrazka - zawsze zero (bo
            # pdfminer nie wspiera))
            # TODO: I program moze sie wywalic (patrz komentarz wyzej) 
        self.label = "" # etykieta fontu lub obrazka widoczna w przegladarce graficznej,
            # zawiera klucz fontu lub obrazka ze slownika zasobow strony
            # etykieta Fontu zaczyna sie od Font a obrazka od Image, dzieki temu mozna
            # sie dowiedziec jakiego typu obiekt reprezentuje ten wezel PTree
        self.children = [] # dzieci wezla
        self.parent = None # ojciec wezla

# obiekt reprezentuje czcionke
# moze reprezentowac zarowno pdfowy slownik fontu umieszczony w zasobach strony,
# lub font w zawartosci tekstowej (dzieci obiektu Node z ustawiona flaga __isLeaf),
# ktory oznacza ze wszytskie wystepujace po nim znaki  w danym momencie nalezy
# wypisywac w tym foncie (zawiera wtedy tez informacje o rozmiarze czcionki)
class Font(object):

    def __init__(self):
        self.name = None # rodzina fontu, jesli sie nie da to w przyblizeniu
        self.psname = None # self.fullName obciete do nazwy postscriptowej (jezeli jest to podzbior fontu
            # to fullName zawiera na poczatku [A-Z][A-Z][A-Z][A-Z][A-Z][A-Z]+, ktore jest obcinane w psname
        self.size = None # rozmiar fontu
        self.dict = None # pdfowy slownik fontu
        self.fullName = None # nazwa fontu jak w /BaseName lub w /FontName w deskryptorze fontu
        self.ptreeLink = None # wezel w drzewie PTree zawierajacy font w polu data
            # umozliwia znalezienie wezla do ktorego nalezy font (lub do ktorego nalezal
            # font z ktorego ten zostal skopiowany metoda instantiate) w metodzie
            # MainWindow.switchTabs - dzieki temu wiemy ktory wezel pokazac w
            # PhysList (ale: w zasadzie do pokazania wezla wystarczy nam sam obiekt
            # klasy Font, to jest pozostalosc z czasow gdy PhysList bylo drzewem
            # i trzeba bylo je rozwinac zeby w kontrolce PhysList (ktora wtedy byla
            # nie lista, a drzewem) rozwinac odpowiedni wezel); powinno sie natomiast
            # dodac jakies zaznaczanie odpowiedniego item wxWidgets (por. komentarz do
            # metody PhysList.show) w kontrolce PhysList - pytanie, czy do tego przyda
            # sie ptreeLink?)
        self.page = None # identyfikator strony do ktorej slownika zasobow font nalezy
        self.pdfminerFont = None # pdfminerowy obiekt fontu odpowiadajacy danemu fontowi
        self.italic = False
        self.bold = False
    
    @staticmethod
    # tworzy font-zaslepke uzywany przy wczytywaniu plikow XML pdfminera (bo wtedy nie mamy
    # dostepu do fontow z pdfa)
    def xmlDummy(name, size):
        res = Font()        
        res.fullName = name
        res.size = size
        res.psname = Font.removeSubset(res.fullName) # w plikach XML sa nazwy fullName
        res.name = res.psname
        if re.search("bold", res.psname) != None or re.search("Bold", res.psname) != None:
            res.bold = True
        if re.search("italic", res.psname) != None or re.search("Italic", res.psname) != None:
            res.italic = True
        if re.search("oblique", res.psname) != None or re.search("Oblique", res.psname) != None:
            res.italic = True
        return res
    
    @staticmethod
    # tworzy nowy obiekt Font
    # probuje znalezc rodzine fontu (jesli sie to nie uda wypisuje komunikat - chyba,
    # ze parametr gui ma wartosc True)
    # map - mapowanie z nazwy postscriptowej na rodzine fontow (przydatne jesli
    # rodziny sie nie da znalezc, parametr pdfa2hocr)
    def new(dict, pdfminerFont, page, ptree, gui=False, map=None):
        res = Font()
        type = literal_name_none(dict.get("Subtype"))
        if type == "Type3":
            res.name = str(uuid.uuid1()) # potrzebna zaslepka, bo eksporter do hocr
                # poznaje po nazwie czy font sie zmienil
                # TODO: I (chociaz w zasadzie to i tak nie ma wtedy sensu, bo jako
                # nazwe fontu w hOCR wypiszemy ta zaslepke)
            res.psname = res.name
            res.fullName = res.name
            res.ptreeLink = ptree
            res.page = page
            res.pdfminerFont = pdfminerFont
            return res
        descr = dict_value_none(dict.get("FontDescriptor"))
        nsfamily = None
        if descr != None:
            nsfamily = str_value_none(descr.get("FontFamily")) # nie jest w PDF 3rd edition (wiec tez nie ma w PDF/A), ale finereader mimo wszystko wypelnia 
            res.fullName = descr.get("FontName")
            if res.fullName != None:
                res.fullName = literal_name(res.fullName)
            else:
                res.fullName = literal_name(dict.get("BaseFont"))
        else:
            res.fullName = literal_name(dict.get("BaseFont"))
        # /BaseFont i /FontName z deskryptora powinny byc niby takie same, ale finereader tworzu rozne
        res.dict = dict
        res.psname = Font.removeSubset(res.fullName)
        #print self.psname, self.fullName
        res.size = None
        res.ptreeLink = ptree
        res.page = page
        res.italic = False
        res.bold = False
        res.pdfminerFont = pdfminerFont
        # probujemy sie czegos dowiedziec z nazwy (moze w deskryptorze i pliku beda
        # lepsze informacje, ale jak nie to i tak bedziemy cos wiedziec):
        if re.search("bold", res.psname) != None or re.search("Bold", res.psname) != None:
            res.bold = True
        if re.search("italic", res.psname) != None or re.search("Italic", res.psname) != None:
            res.italic = True
        if re.search("oblique", res.psname) != None or re.search("Oblique", res.psname) != None:
            res.italic = True
        #print dict.get("Subtype"), type
        if type == "TrueType":
            # dla fontow TrueType wyciagamy szczegolwe informacje z deskryptora i pliku
            # fontu:
            # TODO: D analiza z deskryptora nie tylko dla TrueType
            (family, italic, bold) = res.__extractNameAndStyle(dict, gui, map == None or map.getName(res.psname) == None)
            if family != None:
                res.name = family
            else:
                res.name = res.psname
            if italic:
                res.italic = True
            if bold:
                res.bold = True
        elif nsfamily == None:
            res.name = res.psname
            if not gui and map != None and map.getName(res.name) == None:
                print "Warning: couldn't find name of font " + res.name + ". Resulting hOCR",
                print "file won't display fonts properly in browser. You can retry",
                print "conversion process with substitution of " + res.name + " by font",
                print "name by using -f option."
        else:
            res.name = nsfamily
        return res
    
    # jednoznaczny identyfikator fontu, dzieki niemu konwerter na hOCR rozroznia fonty
    def getId(self):
        return self.psname + str(self.size)
    
    # na podstawie obiektu na ktorym zostala wywolana ta metoda (foncie ze slownika
    # zasobow strony) tworzy jego kopie z dodatkowa informacja o rozmiarze czionki
    # (tak utworzony obiekt jest umieszczany w lisciach drzewa struktury logicznej
    # (obiekt Node) przemieszany ze znakami i oznacza, ze wszystkie nastepujace po nim
    # znaki sa w tym foncie)
    def instantiate(self, size):
        new = Font()
        new.dict = self.dict
        new.pdfminerFont = self.pdfminerFont
        new.page = self.page
        new.ptreeLink = self.ptreeLink
        new.name = self.name
        new.psname = self.psname
        new.fullName = self.fullName
        new.bold = self.bold
        new.italic = self.italic
        new.size = size
        return new
    
    # probuje poznac rodzine i styl fontu TrueType z deskryptora i z
    # pliku fontu
    def __extractNameAndStyle(self, dict, gui, noInMap):
        type = literal_name(dict.get("Subtype"))
        if type != "TrueType" and (not gui):
            print "Warning: non TrueType font handling not implemented"
            return (None, False, False)
        descr = dict_value_none(dict.get("FontDescriptor"))
        name = literal_name(dict.get("BaseFont"))
        bold = False
        family = None
        italic = False
        if descr != None:
            # font jest bold jezeli informacja o tym jest w deksryptorze lub pliku
            # font jest itailc jezeli informacja o tym jest w deksryptorze lub pliku
            # odnosnie rodziny deskryptor ma pierwszenstwo przed plikiem
            family = str_value_none(descr.get("FontFamily"))
            weight = num_value_none(descr.get("FontWeight"))
            file = stream_value_none(descr.get("FontFile2"))
            if file != None:
                sio = StringIO(file.get_data())
                fontFile = TTFontMod(sio)
                (family, italic, bold) = self.__getFamilyAndStyle(fontFile['name'].names, name, gui, family, noInMap)
                sio.close()
            if weight >= 700:
                bold = True
            flags = num_value_none(descr.get("Flags"))
            if flags == None:
                flags = 0
            if flags & 0x40:
                italic = True
        #print family, name
        if family == None and (not gui) and noInMap:
            print "Warning: Could'nt find name of font " + Font.removeSubset(name) + ". Resulting hOCR",
            print "file won't display fonts properly in browser. You can retry",
            print "conversion process with substitution of " + Font.removeSubset(name) + " by font",
            print "name by using -f option."
        return (family, italic, bold)
    
    # probujemy poznac rodzine i styl fontu z pliku TrueType
    # family - rodzina z deskryptora fontu
    def __getFamilyAndStyle(self, names, name, gui, family, noInMap):
        winFamily = None
        style = None
        winStyle = None
        newFamily = None
        for n in names:
            if (n.platformID == 0 or (n.platformID == 1 and n.platEncID == 0 and n.langID == 0x0)
		        or (n.platformID == 2 and n.platEncID == 1 and n.langID == 0x0409)):
                if (n.platformID == 1):
                    data = n.string.decode("latin-1")
                else:
                    data = uniToString(n.string)
                if len(n.string) == 0:
                    continue
                if n.nameID == 1:
                    newFamily = data
                elif n.nameID == 2:
                    style = data
                elif n.nameID == 16:
                    winFamily = data
                elif n.nameID == 17:
                    winStyle = data
        if winFamily != None:
            newFamily = winFamily
        if winStyle != None:
            style = winStyle
        bold = False
        italic = False
        if style != None:
            if re.search("bold", style) != None or re.search("Bold", style) != None:
                bold = True
            if re.search("italic", style) != None or re.search("Italic", style) != None:
                italic = True
            if re.search("oblique", style) != None or re.search("Oblique", style) != None:
                italic = True
        if family == None:
            if newFamily == None:
                return (None, italic, bold)
            family = newFamily
        if isSubsetName(family) and (not gui) and noInMap:
            family = Font.removeSubset(family)
            # z niewiadomych powodow finereader zapisuje w pliku TrueType nazwe
            # postscriptowa z rozszerzeniem podzbioru fontu ([A-Z][A-Z][A-Z][A-Z][A-Z][A-Z]+)
            # dlatego musimy sprawdzic, czy taka sytuacja sie nie zdarza i poinformowac
            # o tym; z drugiej strony finerader umieszcza informacje o rodzinie w
            # deskryptorze, wiec nie uzyjemy rodziny z pliku ale z deskryptora i
            # zmienna family oznacza wtedy rodzine z deskryptora (wiec isSubsetName(family)
            # bedzie wtedy False)
            print "Warning: font name of " + Font.removeSubset(name) + " font incorrect. Resulting hOCR",
            print "file won't display fonts properly in browser. You can retry",
            print "conversion process with substitution of " + Font.removeSubset(name) + " by font",
            print "name by using -f option."
        return (family, italic, bold)
 
    #def setItalic(self, italic):
    #    if italic:
    #        self.italic = True
    
    #def setBold(self, bold):
    #    if bold:
    #        self.bold = True
    
    #def setFamily(self, family):
    #    if family != None:
    #        self.name = family
    
    @staticmethod
    # usuwa rozszerzenie [A-Z][A-Z][A-Z][A-Z][A-Z][A-Z]+ uzywane przy podzbiorach
    # fontow z nazwy postscriptowej
    def removeSubset(name):
        blocks = name.split('+')
        return blocks[len(blocks) - 1]

# reprezentuje wezel drzewa struktury logicznej dokumentu (element struktury logicznej)
# lub korzen drzewa struktury logicznej
class Node:
    
    __ids = {}
    
    @staticmethod
    # generator groupidow na potrzeby metody split
    def __getId(tag):
        if Node.__ids.get(tag) != None:
            new = Node.__ids.get(tag) + 1
            del Node.__ids[tag]
            Node.__ids.setdefault(tag, new)
            return new
        return Node.__ids.setdefault(tag, 0)
    
    def __init__(self, object, id, lib, preview=False):
        #lib.getNodeDict().setdefault(id, self)
        self.__isCopy = False # czy obiekt jest kopia (kawalkiem elementu powstalym po podziale, patrz opis metody split)
        self.__preview = preview
        self.__groupid = None # hocrowa wlasciwosc groupid ktora pozwala zidentyfikowac
            # elementy hOCR podzielone na czesci bo sa polozone na kilku stronach
            # obiekty Node o takiej samej wartosci __groupid i takich samych tagach
            # (__text) sa czesciami jednego obiektu
        self.__lib = lib # obiekt klasy TagLib obslugujacy dokument PDF do ktorego nalezy dany wezel
        self.__object = object # obiekt PDF bedacy wezlem w drzewie struktury logicznej ktory reprezentuje dany obiekt Node
        #assert(self.__object.get("P") != None)
        self.__objid = id # identyfikator obiektu PDF self.__object
        self.__children = None # TODO: NOTE inicjalizacja na None jako sprawdzanie bledow
            # dzieci wezla - inne wezly Node lub zawartosc tekstowa (zawiera
            # znaki i fonty)
            # TODO: I obecnie program nie wspiera zawartosci bedacej np. obrazkiem
        self.__isLeaf = False # czy obiekt jest lisciem (nie ma dzieci bedacych
            # obiektami Node (natomiast moze byc dzieci bedace zawartoscia tekstowa))
            # TODO: I obecnie program nie wpsiera zawartosci mieszanej (dzieci bedace
            # obiektami Node i wlasciwa zawartoscia (tekst lub np. obrazek) w jednym
            # wezle) 
        self.__isRoot = False # czy obiekt jest korzeniem drzewa struktury
        self.__contentType = None # typ zawartosci liscia (moze byc tekst, pagina albo artefakt - patrz TagInterpreter)
            # jezeli wezel jest lisciem pustym, to ma typ Empty
        self.__bbox = None # bounding box wezla (suma bouding boxow znakow wszystkich
            # potomkow)
        self.__initialized = False # czy obiekt jest zainicjalizowany (czy wywolano
            # na nim __initialize)
        self.__splitted = False # czy obiekt zostal podzielony przez metode split lub jest kopia
            # powstala w wyniku wywolania tej metody - w obu przypadkach metoda
            # split zignoruje obiekt (bo zostal juz raz podzielony)
        self.__childrenByPage = {} # dzieci wezla z podzialem na strony na ktorych
            # wystepuja (dotyczy tylko lisci)
        self.__bboxByPage = {} # sumy bounding boxow znakow stanowiacych zawartosc
            # liscia i znajdujacych sie na jednej stronie indeksowane po stronach
            # (dotyczy tylko lisci) 
        self.__charbboxes = [] # bounding boxy znakow bedacych zawartoscia liscia
            # w takiej samej kolejnosci jak znaki (dotyczy tylko lisci)
        self.__charbboxesByPage = {} # j.w. ale z podzialem na strony
        self.__selected = False # czy wezel powinien byc podswietlony w oknie rysowania
            # strony przegladarki graficznej
        self.__copies = None # kopie wezla dla poszczegolnych stron (czesci powstale
            # po podziale wezla w metodzie split, patrz opis metody split)
            # TODO: NOTE inicjalizacja na None jako sprawdzanie bledow
        try:
            self.__pageid = object.get("Pg").objid # identyfikator strony obecny pod kluczem /Pg w obiekcie self.__object
                # (strona na ktorej "lezy" dany element - ale element moze byc na wiecej niz jednej stronie, poza tym
                # element /Pg jest opcjonalny - dlatego jak chcemy sie dowiedziec na jakiej stronie lezy element
                # lepiej uzyc getPageIds)
        except AttributeError:
            self.__pageid = None
        self.__text = literal_name(self.__object.get('S')) # tag oznaczajacy typ elementu (np. tabelka, lista, akapit)
            # lub StructTreeRoot dla korzenia (nazwa elementu)
        if self.__object.get('S') == None:
            self.__text = "StructTreeRoot" # TODO: I jezeli korzen drzewa ma zawsze tylko jedno dziecki
                # to teoretycznie mozna zamiast niego dac odrazu to dziecki (ale czy zawsze tak jest?)
        #print "utworz", self.__objid, self.__text
    
    # tworzy kopie elementu (czesc powstala w wyniku podzialu elementu) na potrzeby
    # metody split i inicjalizuje niektore informacje (reszte split)
    # jednoczesnie przydziela elementowi (jezeli jeszcze nie ma) i kopii identyfikator
    # groupid, ktory zostanie wykorzystany w hOCR do zidentyfikowania powstalych
    # kopii jako czesci jednego elementu
    def __partialCopy(self):
        copy = Node(self.__object, self.__objid, self.__lib)
        assert(copy.__object.get("P") != None)
        if self.__groupid == None:
            self.__groupid = Node.__getId(self.getStandardText())
        copy.__groupid = self.__groupid
        copy.__isCopy = True
        copy.__children = []
        copy.__isLeaf = self.__isLeaf
        copy.__isRoot = self.__isRoot
        copy.__contentType = self.__contentType
        #copy.__bbox = None # ustawiane w splicie
        copy.__text = self.__text
        copy.__initialized = True # zostanie zainicjalizowana przez metode split, nie przez __initialize
        copy.__splitted = True # bo kopie sa kawalkami powstalymi po podziale elementu i nie powinny juz byc dzielone
        copy.__pageid = None # ustawiany w splicie
        return copy
    
    def isSelected(self):
        #print self.__selected
        return self.__selected
    
    def select(self):
        self.__selected = True
        #print self.__selected
    
    def unselect(self):
        self.__selected = False
    
    def getGroupId(self):
        return self.__groupid
    
    # generalnie uzywac getPageIds
    # self.__pageid uzywane tylko w jednym miejscu w __initialize
    # (jak jest gdzie indziej to znaczy ze cos tam chyba jest nie tak)
    def getPageId(self):
        return self.__pageid
    
    def getCopies(self):
        #assert(self.__copies != None)
        self.__initialize()
        return self.__copies
    
    # metoda zwraca dzieci danego elementu, ale w przeciwienstwie do metody
    # getChildren zamiast zwracac wszystkie dzieci jako nowo utworzone
    # niezainicjalizowane wezly, zwraca ona tylko dzieci o identyfikatorach z listy
    # visited pobierajac je ze slownika do ktorego interfejs zapewnia funkcja dict
    # patrz metoda __lastCommonAncestor (dzieki temu nie trzeba sprawdzac pozostalych
    # dzieci)
    def getChildrenFromDict(self, dict, visited):
        self.__initialize(dict=dict, visited=visited)
        return self.__children
    
    def getChildren(self):
        self.__initialize()
        return self.__children
    
    def getObject(self):
        #assert(self.__object.get("P") != None)
        return self.__object
    
    def getObjId(self):
        return self.__objid
    
    def getContentType(self):
        self.__initialize()
        return self.__contentType

    def getCharbboxes(self):
        return self.__charbboxes
        #if self.__isLeaf:
        #    return self.__charbboxes
        #else:
        #    res = []
        #    for c in self.__children:
        #        for cr in c.__charbboxes:
        #            res.append(cr)
        #   return res
    
    def isLeaf(self):
        self.__initialize()
        return self.__isLeaf
    
    def isRoot(self):
        #self.__initialize() # TODO: NOTE chyba niepotrzebne
        return self.__isRoot
    
    def setRoot(self):
        self.__isRoot = True
    
    # zwraca atrybuty danego elementu w postaci napisu ktory zostanie wyswietlony
    # w oknie przegladarki graficznej, wykorzystuje slownik /ClassMap udostepniany
    # przez obiekt self.__lib
    def __getAttrs(self):
        attrs = []
        #print self.__object.get("A")
        li = list_value_none(self.__object.get("A"))
        isList = list_value2(self.__object.get("A"))
        #print li, isList
        if li != None and isList != None:
            if len(li) == 2 and num_value(li[1]) != None:
                    attrs.append((dict_value(li[0]), num_value(li[1])))
            else:
                for el in li:
                    if list_value2(el) != None:
                        lst = list_value2(el)
                        attrs.append((dict_value(lst[0]), num_value(lst[1])))
                    else:
                        attrs.append((dict_value(lst), 0))
        elif li != None:
            attrs.append((dict_value(self.__object.get("A")), 0))
        cl = list_value_none(self.__object.get("C"))
        isList = list_value2(self.__object.get("C"))
        classes = []
        if cl != None and isList != None:
            if len(cl) == 2 and num_value2(cl[1]) != None:
                classes.append(literal_name(cl[0]), num_value(cl[1]))
            else:
                for el in cl:
                    if list_value2(el) != None:
                        lst = list_value(el)
                        classes.append((literal_name(lst[0]), num_value(lst[1])))
                    else:
                        classes.append((literal_name(el), 0))
        elif cl != None:
            classes.append(literal_name(self.__object.get("C")), 0)
        for (c, rev) in classes:
            els = self.__lib.getClassMap().get(literal_name(c))
            if list_value2(els) != None:
                for attr in list_value(els):
                    attrs.append((dict_value(attr), rev))
            else:
                attrs.append((dict_value(els), rev))
        return attrs

    # zwraca "metadane" danego elementu (atrybuty i inne pola z dodatkowymi danymi
    # na temat elementu) jako napis ktory zostanie wyswietlony w oknie przegladarki
    # graficznej
    def getMetadata(self):
        lang = str_value_none(self.__object.get("Lang"))
        title = str_value_none(self.__object.get("Title"))
        altDesc = str_value_none(self.__object.get("Alt"))
        substText = str_value_none(self.__object.get("ActualText"))
        res = ""
        if title != None:
            res += "Title: " + title + "\n"
        if lang != None:
            res += "Language: " + lang + "\n"
        if altDesc != None:
            res += "Alternative description: " + altDesc + "\n"
        if substText != None:
            res += "Substitute text: " + substText + "\n"
        attrs = self.__getAttrs()
        for (attr, rev) in attrs:
            for (k, v) in attr.iteritems():
                res += str(k) + " (" + str(rev) + "): " + str(v) + "\n"
        return res
    
    # zwraca identyfikatory wszystkich stron na ktorych umieszczona jest zawartosc tekstowa
    # lisci, jezeli nie ma zadnej zawartosci w lisciach zwraca identyfikatory stron
    # w polach self__pageid potomkow
    # intuicja: strony na ktorych "lezy" dany element
    # w obiektach Node przetworzonych przez metode split lista ma zawsze dlugosc najwyzej 1
    def getPageIds(self):
        # TODO: D nie przeliczac dynamicznie - tzn. dodac self.__pageids resetowane przez split()
        self.__initialize()
        if self.__isLeaf:
            if self.__childrenByPage.keys() == []:
                if self.getPageId() == None:
                    return []
                else:
                    return [self.getPageId()]
            return self.__childrenByPage.keys()
        res = []
        if self.__children == None:
            if self.getPageId() == None:
                return []
            else:
                return [self.getPageId()]
        #    print self.text
        #    print self.object
        for c in self.__children:
            #if isinstance(c, Font):
            #    print self.text
            #    print self.__children
            for id in c.getPageIds():
                if not id in res:
                    res.append(id)
        return res
            
    # zwraca bounding box elementu - jezeli jest to lisc jest to suma bounding boxow
    # zawartych w nim znakow, wpp suma bouding boxow dzieci
    # jezeli jest to lisc pusty (bez zawartosci tekstowej) - to jego bounding box jest
    # rowny None (nie ma bounding boxa)
    # uwaga: bounding box jest obliczany raz, potem jego wartosc jest na self.__bbox,
    # zmieniana jest tylko w splicie jezeli element staje sie jedna z czesci (patrz
    # opis metody split, tryb zwykly)
    def getBbox(self):
        self.__initialize()
        if self.__bbox != None:
            assert(isinstance(self.__bbox, list))
            return self.__bbox
        else:
            # TODO: NOTE pusty element (np. NonStruct, Figure)
            if self.__isLeaf:
                return None
            bbox = None
            for c in self.__children:
                c.__initialize()
                bbox = combine(bbox, c.getBbox())
            self.__bbox = bbox
            assert(isinstance(bbox, list) or bbox == None)
            return bbox

    # TODO: I zwalnianie pamieci:
    # Poczatkowo drzewo zwrocone przez metode getRoot w TagLib zawiera tylko pojedynczy
    # wezel. W miare potrzeby kolejni potomkowie sa inicjalizowanie przez metode
    # __initialize (np. przy rozwijaniu wezlow drzewa w przegladarce graficznej lub
    # jego eksporcie przez konwerter). Po zwinieciu wezla (lub wyeksportowaniu go do
    # hOCR) teoretycznie moze on byc "odinicjalizowany" (generalnie chodzi o to, ze
    # traci on wszystkich potomkow ktorych uzyskal w wyniku wywolania na nim i potem na
    # jego potomkach __initialize).
    # Tym wlasnie zajmuje sie ta metoda. Niestety odzyskiwanie pamieci nie jest 100% -
    # - jest to temat do solidnej przerobki calego pakietu PDFAUtilities. Pierwotne
    # zalozenie - ze najwazniejsze jest zwalnianie pamieci przy zwijaniu wezlow - okazalo
    # sie bledne (bo oprocz drzewa obiektow Node jest jeszcze caly dokument zaladowany
    # prze pdfminera), ale zostalo pozostawione w implementacji (bo i tak jest potrzebna
    # kompleksowa przerobka zarzadania pamiecia). Bardziej istotne okazalo sie
    # zwalnianie pamieci zajetej przez obsluge dotychczasowego pliku przy otwarciu
    # nowego pliku.
    # UWAGA:
    # Zeby zwalnianie pamieci przy zwijaniu wezlow w przegladarce graficznej bylo
    # niezalezne od elementow wyswietlanych w oknie rysowania strony przegladarki graficznej
    # sa one tworzone w metodzie getStructureToDrawById zamiast brania ich z drzewa
    # tworzonego z korzenia getRoot.
    # UWAGA:
    # Ponadto, poniewaz rozne metody klasy Node same wywoluja metode __initialize,
    # przedstawione powyzej zachowanie: konwerter/przegladarka eksportuje/rozwija wezel
    # przez __initialize a potem go odinicjalizowuje (np. przy zwijaniu w przegladarce)
    # moze mijac sie z prawda, bo ktoras z metod moze np. spowodowac zainicjalizowanie
    # jakiegos obiektu Node niezaleznie od konwertera/przegladarki (jak tak sie stanie
    # po uninitialize, to oczywiscie ten obiekt moze nie byc potem odinicjalizowany).
    # Szczegolnie psuja nam to zachowanie metody getPageIds i multipage.
    def uninitialize(self):
        if not self.__initialized:
            return
        for c in self.__children: # czy trzeba? czy wystarczy self.__children = None
            if isinstance(c, Node):
                # TODO: NOTE kopie sa wykorzystywane tylko (na razie) w konwerterze
                # TODO: I czy kopie tez powinnismy zwolnic? w zasadzie c.__isCopy w
                # ponizszym warunku nie powinno wystapic, ale czy powinnismy tez
                # przejrzec self.__copies?
                if c.__initialized and not c.__isCopy:
                    #print "bye", c.getText()
                    c.uninitialize()
                #else:
                    #print "uninit"
        #if (not self.__isCopy) and delDict:
        #    #if self.__objid == 6:
        #    #    print "usun", self.__objid, self.__text
        #    del self.__lib.getNodeDict()[self.__objid]
        self.__children = None
        self.__isLeaf = False
        self.__isRoot = False
        self.__contentType = None
        self.__bbox = None
        self.__initialized = False
        #self.__uninitialized = True
        self.__splitted = False
        self.__childrenByPage = {}
        self.__bboxByPage = {}
        self.__copies = None      
        #del self.__nodeDict[self.__object.objid]
        # TODO: NOTE pageid i text sie nie zmienia?
    
    # czy dany obiekt jest slownikiem odnosnika do zawartosci oznaczonej (str. 594)
    def __isMCRDict(self, obj):
        dic = dict_value2(obj)
        if dic == None:
            return False
        else:
            if literal_name(dic.get("Type")) == "MCR":
                return True
            return False
    
    #def __getValue(self, page, name, key):
    #    try:
    #        return name.get(key) # slownik w contencie
    #    except AttributeError: # slownik w resource'ach
    #        dict = page.resources.get("Properties").get(literal_name(name))
    #        return dict_value(dict).get(key)

    # inicjalizuje obiekt (pobiera z obiektu self.__object informacje o dzieciach,
    # dodaje dzieci do self.__children i wypelnia rozne inne pola na podstawie
    # informacji o dzieciach)
    # wywolujac metode getMcrs posrednio zbiera informacje o zawartosciach oznaczonych
    # za pomoca klasy TagInterpreter
    # zachowanie w razie podania parametrow dict i visited patrz metoda getChildrenFromDict
    def __initialize(self, dict=None, visited=None):
        #print self.__text
        if self.__initialized:
            #for c in self.__children:
            #    assert((not isinstance(c, Font)) or self.__isLeaf)
            return
        self.__initialized = True
        obj = self.__object
        #print obj.get("K")        
        if obj.get('K') == None: # brak dzieci
            #return ([], True, "Empty", None)
            self.__children = []
            self.__isLeaf = True
            self.__contentType = "Empty"
            #for c in self.__children:
            #    assert((not isinstance(c, Font)) or self.__isLeaf)
            return
        # TODO: D zaimplementowac obsluge marked content we wszystkich wezlach drzewa (nie
        # tylko w lisciach); bedzie to wymagalo zmian w przegladarce i konwerterze
        # TODO: I nie obslugujemy mieszanych StructElem i MCIDow (patrz TODO wyzej)
        # TODO: H jakos ta cala metode zrobic ladniej        
        kid = dict_value2(obj.get('K'))
        #if kid == None:
        if kid == None or (not self.__isStructElem(kid)):
            kids = list_value2(obj.get('K'))
            if kids == None or (len(kids) > 0 and (num_value2(kids[0]) != None or self.__isMCRDict(kids[0]))):
                # TODO: I /K jest lista zawierajaca identyfikatory zawartosci oznaczonych - 
                # - poniewaz nie obslugujemy zawartosci tekstowej nie w lisciach
                # i zawartosci nie bedacej tekstowa (np. obrazki) zakladamy, ze
                # w takim przypadku wszytstkie elementy na liscie to identyfikatory
                # zawartosci oznaczonych
                # to zalozenie jest w zasadzie bledne
                res = [] # tu pamietamy zawartosc tekstowa
                rbbox = None # tu sumujemy bouding boxy znakow
                pagination = None # jezeli jest lista wielu zawartosci oznaczonych to
                    # zeby element byl pagina lub artefaktem wszystkie zawartosci
                    # musza byc pagina lub artefaktami
                artifact = None
                mcids = list_value2(obj.get("K"))
                if mcids == None:
                    if self.__isStructElem(obj.get("K")):
                        mcids = [dict_value(obj.get("K"))]
                    elif self.__isInteger(obj.get("K")):
                        mcids = [num_value(obj.get("K"))]
                    else:
                        mcids = []
                for mcid in mcids:
                    pageid = self.__pageid # tu akurat zawsze przez referencje
                    # pageid = obj.get("Pg").objid
                    dic = dict_value2(mcid)
                    if dic != None and self.__isMCRDict(mcid):
                        if mcid.get("Pg").objid != None:
                            pageid = mcid.get("Pg").objid
                        mcid = mcid.get("MCID")
                    elif not self.__isInteger(mcid):
                        continue
                    # TODO: I uwaga: pageid moze byc dziedziczony, trzeba to
                    # zaimplementowac
                    for mc in self.__lib.getMcrs(pageid):
                        assert(mc.initialized)
                        #if len(mc) == 0: TODO: X przywrocic stare mcry i sprawdzic czy to sie kiedys trafialo
                        #   continue
                        #print mc[2].page
                        if mc.mcid == mcid:
                            pagination = mc.pagination and (pagination == None or pagination)
                            artifact = mc.artifact and (artifact == None or artifact)
                            rbbox = combine(rbbox, mc.bbox)
                            #print rbbox
                            #assert(isinstance(rbbox, list) or rbbox == None)
                            for c in mc.charbboxes:
                                self.__charbboxes.append(c)
                                self.__charbboxesByPage.setdefault(pageid, []).append(c)
                            #resg = u""
                            #for c in mc.charbboxes:
                            #    resg += c
                            #print "[" + resg + "]"
                            #resg = u""
                            #f = None
                            #textik = u""
                            #for c in mc.control:
                            #    #print c
                            #    if isinstance(c, list):
                            #        textik += TagInterpreter.toUni(f, c)
                            #    else:
                            #        if f == None:
                            #            f = c
                            #print "{" + textik + "}"
                            #resg = u""
                            for el in mc.els:
                                if isinstance(el, list):
                                    aktfont = el[0]
                                    aktfontsize = el[1]
                                    #print ":::::::::::::::", aktfont, aktfontsize
                                    if aktfont != None:
                                        font = self.__lib.findFont(mc.page, aktfont).instantiate(aktfontsize)
                                        assert(font != None)
                                        res.append(font) # TODO: I trzeba dodac sprawdzanie, czy ostatnim elementem
                                            # na liscie res nie jest font, i wtedy go usunac przed dodaniem
                                            # nowego
                                        self.__childrenByPage.setdefault(pageid, []).append(font)
                                else:
                                    #resg += TagInterpreter.toUni(f, el)
                                    pdfminerfont = self.__lib.findFont(mc.page, aktfont).pdfminerFont
                                    text = self.__lib.textof(el, pdfminerfont)
                                    res.append(text)
                                    self.__childrenByPage.setdefault(pageid, []).append(text)
                                    #print "::", text, self.__childrenByPage.get(__pageid)
                                    try:
                                        bbox = self.__bboxByPage[pageid]
                                    except KeyError:
                                        bbox = None
                                    try:
                                        self.__bboxByPage.__delitem__(pageid)
                                    except KeyError:
                                        pass
                                    self.__bboxByPage.setdefault(pageid, combine(bbox, mc.bbox))
                            #rest = u""
                            #for c in res:
                            #    if isinstance(c, unicode):
                            #        rest += c
                            #    else:
                            #        assert(isinstance(c, Font))
                            #print "<" + resg + ">"
                                    #print fontof(mc[2].page, aktfont)
                text = "Text"
                if pagination == True:
                    text = "Pagination"
                elif artifact == True:
                    text = "Artifact" 
                self.__children = res
                self.__isLeaf = True
                #res = u""
                #for c in self.__charbboxes:
                #    res += c
                #print self.getTextContent(), res
                #print len(self.__charbboxes), len(self.getTextContent())
                assert(len(self.__charbboxes) == len(self.getTextContent()))
                self.__contentType = text
                assert(isinstance(rbbox, list) or rbbox == None)
                self.__bbox = rbbox
                ok = False
                for c in self.__children:
                    if not isinstance(c, Font):
                        ok = True
                # if len(self.__children) == 1:
                if not ok: # TODO: NOTE same fonty (z poprzednich
                        # elementow, ten jest pusty)
                    self.__children = []
                #if self.bbox == None:
                #    print self.__children
                #    assert(self.bbox != None)
                #print res
                #print self.__childrenByPage
                #for c in self.__children:
                #    assert((not isinstance(c, Font)) or self.bbox != None)
                return
            else: # /K to lista, mamy wiele dzieci
                # TODO: I obslugujemy jedynie przypadek gdy wszystkie elementy listy
                # to elementy struktury logicznej
                res = []
                for kid in kids:
                    if visited != None and not kid.objid in visited:
                        continue
                    if dict != None:
                        res.append(dict(dict_value(kid), kid.objid))
                    else:
                        #print self.__text, self.__objid
                        res.append(Node(dict_value(kid), kid.objid, self.__lib))
                self.__children = res
                #for c in self.__children:
                #    assert((not isinstance(c, Font)) or self.__isLeaf)
                return
        #else: # jedno dziecko
        elif self.__isStructElem(obj.get("K")): # /K to slownik, sprawdzamy czy slownik bedacy elementem struktury logicznej - jesli tak - jedno dziecko Node
            #return ([Node(kid)], False, "", None)
            kidId = obj.get("K").objid
            if visited != None and not kidId in visited:
                self.__children = []
                return
            if dict != None:
                self.__children = [dict(kid, kidId)]
            else:
                self.__children = [Node(kid, kidId, self.__lib)]
            #for c in self.__children:
            #    assert((not isinstance(c, Font)) or self.__isLeaf)
            return

    # czy dany obiekt PDF zwrocony przez pdfminera jest liczba
    def __isInteger(self, obj):
        return num_value2(obj) != None

    #TODO: D jakos lepiej?
    def __isStructElem(self, obj):
        dic = dict_value2(obj)
        if dic == None:
            return False
        else:
            if dic.get("S") != None and dic.get("P") != None:
                return True
            # TODO: NOTE PDF/A nakazuje uzycie:
            #if literal_name(dic.get("Type")) == "StructElem":
            #    return True
            # ale my chcemy obsluzyc tez nie-PDF/A ze struktura logiczna 
            return False

    # tag (self.__text) zamapowany na jeden ze standardowych tagow (str. 626)
    def getRole(self):
        map = self.__lib.getRoleMap()
        if map != None:
            for (tag, role) in map.iteritems():
                if tag == self.__text:
                    return literal_name(role)
        return None
    
    # jezeli tag (nazwe) elementu (self.__text) mozna zamapowac na standardowy zwraca standardowy,
    # wpp zwraca self.__text
    def getStandardText(self):
        role = self.getRole()
        if role != None:
            return role 
        return self.__text
    
    # zwraca tag elementu (nazwe elementu)
    def getText(self):
        return self.__text
    
    # zawartosc tekstowa elementu
    def getTextContent(self):
        self.__initialize()
        res = u""
        if self.__isLeaf:
            for c in self.__children:
                if isinstance(c, unicode):
                    res += c
        else:
            for c in self.__children:
                res += c.getTextContent()
        return res
    
    # sprawdza, czy element znajduje sie na wielu stronach (zawartosc lisci jest na
    # wielu stronach)
    def multipage(self):
        # TODO: D po efektywnym zaimplementowaniu pageids mozna sie zastanowic, czy tego nie wykorzystac
        # (wystarczy: return len(self.getPageIds()) > 1?)
        def __multipage(node):
            node.__initialize()
            if node.__isLeaf:
                return (node.__childrenByPage.keys(), len(node.__childrenByPage.keys()) > 1)
            res = []
            for c in node.__children:
                (ids, multi) = __multipage(c)
                #print c.getStandardText(), multi
                if multi:                    
                    return (ids, True) # jezeli multi jest True to wartosc ids jest dowolna
                for id in ids:
                    if not id in res:
                        res.append(id)
                        if len(res) > 1:
                            return (res, True) # j.w.
            return (res, False)
        (_, ok) = __multipage(self)
        return ok

    # dzieli element na czesci z ktorych kazda jest tylko na jednej stronie
    # (jezeli jacys potomkowie tez sa na kilku stronach to sa dzieleni i ich
    # czesci trafiaja do odpowiednich czesci elementu)
    # sa dwa tryby dzielenia:
    # w trybie copyAll element nie ulega zmianie, natomiat powstale czesci (kopie) sa
    # zapisywane w self.__copies (ten tryb jest uzywany do ograniczenia wyniku
    # metody getStructureToDrawById do jednej strony) - uwaga, jezeli element znajduje sie
    # tylko na jednej stronie i tak jest dzielony na jeden kawalek zapisywany w self.__copies
    # w trybie zwyklym element staje sie czescia dla jednej strony, natomiast
    # w self__copies sa zapisywane czesci dla pozostalych stron (ten tryb jest uzywany
    # w eksporcie na hOCR)
    # powstale kopie i element maja pole self.__groupid o tej samej wartosci
    # co jest wykorzystywane przy eksporcie do hOCR (patrz __partialCopy) 
    def split(self, copyAll=False):
        if self.__splitted:
            assert(self.__copies != None)
            return
        self.__splitted = True
        #print self.__text, self.multipage()
        if self.multipage() and self.__isLeaf:
            # lisc - zawartosc tekstowa jest dzielona pomiedzy poszczegolne czesci
            #print self.__text
            newChildren = []
            newChildrenByPage = {}
            self.__copies = {}
            #print "SPLIT"
            #print self
            #print self.__children
            #print self.__childrenByPage
            pageid = self.getPageIds()[0]
            for (k, vl) in self.__childrenByPage.iteritems():
                #if k == self.__pageid and not copyAll:
                if k == pageid and not copyAll: # TODO: X
                    for v in vl:
                        newChildren.append(v)
                        #print "appending:", k
                        newChildrenByPage.setdefault(k, []).append(v)
                        #print newChildrenByPage
                else:
                    # TODO: H wybrac ktore jest poprawne (KeyError vs None):
                    try:
                        copy = self.__copies.get(k)
                        if copy == None:
                            copy = self.__partialCopy()
                            copy.__pageid = k # TODO: D tego chyba nie powinno tu byc (bo to powinno byc /Pg ze slownika elementu) 
                            self.__copies.setdefault(k, copy)
                    except KeyError:
                        copy = self.__partialCopy()
                        copy.__pageid = k
                        self.__copies.setdefault(k, copy)
                    copy.__children = vl + copy.__children #[v] + copy.__children
                    tmp = copy.__childrenByPage.setdefault(k, [])
                    #tmp = copy.__childrenByPage.get(k)
                    tmp = vl + tmp #[v] + tmp
                    # TODO: H bez delitem
                    copy.__childrenByPage.__delitem__(k)
                    copy.__childrenByPage.setdefault(k, tmp)
            if not copyAll:
                self.__bbox = None
            for (k, v) in self.__bboxByPage.iteritems():
                #print k, self.__copies
                # TODO: H mozna zrezygnowac, bo getBbox() i tak to policzy
                #if k != self.__pageid or copyAll:
                if k != pageid or copyAll: # TODO: X
                    self.__copies.get(k).__bbox = combine(self.__copies.get(k).__bbox, v)
                else:
                    self.__bbox = combine(self.__bbox, v)
            charbsbp = self.__charbboxesByPage
            if not copyAll:
                self.__charbboxes = []
                self.__charbboxesByPage = {}
            for (k, v) in charbsbp.iteritems():
                #if k != self.__pageid or copyAll:
                if k != pageid or copyAll: # TODO: X
                    for c in v:
                        self.__copies.get(k).__charbboxes.append(c)
                        #self.__copies.get(k).__charbboxesByPage.setdefault(k, []).append(c)
                else:
                    for c in v:
                        self.__charbboxes.append(c)
                        #self.__charbboxesByPage.setdefault(k, []).append(c)
            if not copyAll:
                #print "zmiana dzieci"
                self.__children = newChildren
                self.__childrenByPage = newChildrenByPage
            #print "ABC: ", self.newChildrenByPage
            #print self.childrenByPage.keys()
            #assert(not self.multipage())
            #print self.__bbox
        elif self.multipage():
            # najpierw dzielimy dzieci i wszystkie ich czesci staja sie dziecmi
            # elementu - potem rozdzielimy je miedzy kopie:
            pageid = self.getPageIds()[0]
            newChildren = []
            for c in self.__children:
                #print "C:", c.getPageId(), c.getText() # TODO: I dlaczego ostatni nie inicjalizowany? (ale teraz juz chyba nie wystepuje ten problem)
                if c.multipage():
                    #print c.text
                    c.split(copyAll)
                    #print c.__copies
            for c in self.__children:
                # TODO: I druga czesc warunku trzeba chyba bylo wykomentowac, bo z powodu
                # warunku elif copyAll pod koniec tej metody ten c bedzie miec swoja
                # kopie w przypadku (copyAll and not c.multipage()) i sie nam by
                # wtedy podwojnie wkleil
                # TODO: I okazuje sie ze jednak nie, bo przeciez powyzej split sie
                # odbywa tylko w przypadku multipage
                if (not copyAll) or (not c.multipage()):
                    newChildren.append(c)
                if c.__copies == None:
                    continue
                for cc in c.__copies.values():
                    #print "ABCDE:", cc, cc.__children
                    newChildren.append(cc)
            if copyAll:
                myChildren = self.__children
                myChildrenByPage = self.__childrenByPage
            self.__children = newChildren
            #print self.__children
            for c in self.__children:
                # TODO: NOTE: czy moze byc, ze c.__pageid == None?
                #self.__childrenByPage.setdefault(c.__pageid, []).append(c)
                self.__childrenByPage.setdefault(c.getPageIds()[0], []).append(c) # TODO: X
                #print c.text, c.getPageId()
                #print self.__childrenByPage
            self.__copies = {}
            newChildren = []
            #for (k, vl) in self.__childrenByPage.iteritems():
                #print "KEY", k
                #for v in vl:
                    #print "VALUE", v.__children
            for (k, vl) in self.__childrenByPage.iteritems():
                #if k == self.object.get("Pg").objid and not copyAll:
                #if k == self.__pageid and not copyAll:
                if k == pageid and not copyAll: # TODO: X
                    for v in vl:
                        newChildren.append(v)
                else:
                    copy = self.__copies.get(k)
                    if copy == None:
                        copy = self.__partialCopy()
                        copy.__pageid = k
                        self.__copies.setdefault(k, copy)
                    copy.__children = vl + copy.__children
                    for el in vl:
                        copy.__bbox = combine(copy.getBbox(), el.getBbox())
                    #print "XXXXXXXX", copy.children
                    #print k, v.children
            #print "KOPIE:", self.copies
            #print "DZIECI:",
            #for (k, v) in self.copies.iteritems():
            #    for c in v.children:
            #        print c.children, c.object
            #print newChildren
            if not copyAll:
                self.__children = newChildren
                self.setBbox(None) # bedzie obliczony automatycznie przy wywolaniu getBbox()
            else:
                self.__children = myChildren
                self.__childrenByPage = myChildrenByPage
        elif copyAll:
            self.__copies = {}
            copy = self.__partialCopy()
            #copy.__pageid = self.__pageid
            copy.__pageid = self.getPageId()[0] # TODO: X
            for c in self.__children:
                copy.__children.append(c)
                copy.__childrenByPage.setdefault(copy.__pageid, []).append(c)
            # nie kopiujemy charbboxow, bo to sie trafia tylko w getStructureToDrawById gdzie one nie sa uzywane
            copy.__bbox = self.__bbox
            self.__copies.setdefault(copy.__pageid, copy)
        if not copyAll:
            #print self.getPageIds()
            assert(not self.multipage())
        assert(self.__copies != None)
