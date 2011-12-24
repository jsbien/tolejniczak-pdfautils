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

# TODO: D klasy nowego typu i super (poczytac)
# TODO: D bboxy znakow w hocr
# TODO: D wyciaganie obrazkow i linki do skanow w hocr

from utils import HOCR_APP_NAME, HOCR_APP_VERSION, repeat, MyException, divideIntoWords
from utils import generateDivBboxes, bbox2str, generateDivBboxesTextline, changeCoords
from utils import scaleBbox
from taglib import Font
import sys
import re

# drzewo struktury - w tym pliku drzewo struktury logicznej PDF lub drzewo zanalizowanego
# przez pdfminera ukladu strony

# reprezentuje tag HTML z dodatkowymi informacjami hOCR
class HOCRElement:
    
    def __init__(self, tag="", clazz="", title=""):
        self.__tag = tag # tag HTML
        self.__class = clazz # atrybut class (nazwa elementu hOCR)
        self.__title = title # atrybut title (wlasciwosci elementu hOCR) - zdaje sie
            # ze nie jest nigdzie uzywane
        self.__ignored = False # czy ignorujemy (obiekt tej klasy z ta flaga ustawiona
            # na True oznacza, ze element drzewa struktury ktoremu on odpowiada nie
            # powinien byc eksportowany, natomiast eksportujemy jego dzieci)
            # tzn.:
            # P -> odpowiada mu HOCRElement z __ignored False, __tag = p i __class = ocr_par
            #   Span -> odpowiada mu HOCRElement z __ignored True
            #       [zawartosc tekstowa]
            # da:
            # <p class="ocr_par">
            #   [zawartosc tekstowa]
            # </p>
        self.__bbox = False # czy w atrybucie title ma byc informacja o bounding boxach?
        #self.__pageParent = False
        #self.__pageAncestor = False
    
    def getClass(self):
        return self.__class
    
    def ignore(self):
        self.__ignored = True
        return self
    
    def isIgnored(self):
        return self.__ignored
    
    def useBbox(self):
        self.__bbox = True
        return self
    
    #def ancestorOfPage(self):
    #    self.__pageAncestor = True
    #    return self
    
    #def parentOfPage(self):
    #    self.__pageParent = True
    #    self.__pageAncestor = True
    #    return self
    
    #def isPageParent(self):
    #    return self.__pageParent
    
    #def isPageAncestor(self):
    #    return self.__pageAncestor
    
    # wypisuje poczatek tagu HTML
    def start(self, groupid=None, bbox=None):
        #if self.tag != "div" and self.tag != "body":
        #    return ""
        title = self.__title
        if self.__bbox and bbox != None:
            # TODO: E czy to jest na pewno user space (Reference 4.2.1) - chyba tak bo biezemy to z LTChar.bbox jak w pdf2txt.py
            (a, b, c, d) = bbox
            if self.__title == "":
                title = "bbox " + str(int(a)) + " " + str(int(b)) + " " + str(int(c)) + " " + str(int(d))
            else:
                title += self.__title + "; bbox " + str(int(a)) + " " + str(int(b)) + " " + str(int(c)) + " " + str(int(d))
        if self.__class != "":
            style = " class=\"" + self.__class + "\""
        else:
            style = ""
        if title == "" and groupid != None: # dopisujemy groupid do wlasciwosci
            title = "groupid " + str(groupid)
        elif groupid != None:
            title = "groupid " + str(groupid) + "; " + title
        if title != "":
            title = " title=\"" + title + "\""
        if self.__ignored:
            return ""
        elif self.__tag == "table":
            return "<" + self.__tag + style + title + " border=\"1\">" # zeby ja bylo
                # widac
        return "<" + self.__tag + style + title + ">"
    
    # wypisuje koniec tagu HTML
    def stop(self):
        #if self.tag != "div" and self.tag != "body":
        #    return ""
        if self.__ignored:
            return ""
        return "</" + self.__tag + ">"

    def hasBbox(self):
        return self.__bbox

# obiekt eksportuje plik do hOCR
# ma dwa tryby dzialania - cale drzewo i strona po stronie
class HOCRExporter:
    
    def __init__(self, root, file, lib, mapping=None, xml=False, verbose=False, fontMap=None, icu=None, tags=False):
        self.__root = root # korzen drzewa do eksportowania
        self.__fontMap = fontMap # mapowanie nazw fontow (patrz Font.new)
        self.__icu = icu # jezeli == None to nie dzielimy na slowa, wpp dzielimy i
            # ma wartosc lokalizacji uzywanej do podzialu
        self.__specialTags = tags # czy uzywamy specjalnych tagow ocrx_bold i ocrx_italic
        self.__lib = lib # TagLib lub XMLLibs
        self.__file = open(file, "w") # plik wynikowy
        if xml: # uklad strony
            self.__mapping = HOCRPDFMinerXMLMapping(mapping) # mapowanie elementow
                # ukladu strony na tagi HTML i elementy hOCR
            self.__xml = True
        else: # struktura logiczna PDF
            self.__mapping = HOCRStandardMapping(mapping) # mapowanie elementow
                # struktury logicznej na tagi HTML i elementy hOCR
            self.__xml = False
        self.__sectionNesting = 0 # zagniezdzenie elementu struktury o nazwie /Sect (przechodzimy
            # po drzewie podczas eksportu)
        self.__headerNesting = 0 # j.w. dla elementu o nazwie /H
        self.__page = None # PDF'owy identyfikator obiektu strony (w przypadku
            # eksportu drzewa ukladu strony jego znaczenie jest troche inne, patrz
            # implementacja PDFMinerNode) elementy z ktorej aktualnie wypisujemy
        self.__pageNum = 0 # numer strony liczony od 0
        self.__font = None # ostatnio uzyty font (obiekt klasy Font)
        self.__tagHasFont = False # czy aktualnie przetwarzany element ma font, tzn. czy podczas
            # przetwarzania jego zawartosci natrafilismy na font
            # jezeli ma wartosc True to znaczy ze jest otwarty tag <span style=""> ze
            # stylem fontu
        self.__pageAncestors = [] # lista nazw (tagow) elementow ktore nie powinny byc
            # dzielone miedzy strony (chodzi glownie o "Document", "StructTreeRoot"
            # (korzen drzewa struktury w pliku PDF nie jest w zasadzie elementem i nie ma nazwy,
            # ale w naszych strukturach danych ma nazwe "StructTreeRoot") w przypadku
            # struktury logicznej i "pages" w przypadku ukladu strony
            # patrz determine __pageParents
        self.__pageParents = [] # j. w., ale chodzi tylko o nazwy elementow, ktore
            # po eksporcie do hOCR beda bezposrednimi przodkami strony, tzn.:
            # pages w przypadku self.__xml = True i StructTreeRoot lub Document wpp
        self.__firstPage = True # jezeli ma wartosc True, tzn ze jestesmy w obrebie tagu
            # HTML ktory ma byc bezposrednim przodkiem strony (odpowiada on jakiemus elementowi
            # o nazwie z listy __pageParents) i nie wypisalismy jeszcze tagu oznaczajacego
            # poczatek strony (zob. metody __processNode i __exportNode)
        self.__processingIgnoredTagFont = False
            # wyobrazmy sobie taka sytuacje:            
            # /Element
            #   /Podelement
            #     Font A
            #     tekst
            #   /Podelement
            #     Font A
            #     inny tekst
            #   /Podelement
            #     Font A
            #     jeszcze tekst
            # normalnie przy eksporcie daje to:
            # <tag class="ocr_element">
            # <tag class="ocr_podelement">
            # <span style="font-family: Font A">tekst</span>
            # </tag>
            # <tag class="ocr_podelement">
            # <span style="font-family: Font A">inny tekst</span>
            # </tag>
            # <tag class="ocr_podelement">
            # <span style="font-family: Font A">jeszcze tekst</span>
            # </tag>
            # </tag>
            # jezeli teraz przy eksporcie zignorujemy element o nazwie Podelement
            # to dostaniemy:
            # <tag class="ocr_element">
            # <span style="font-family: Font A">tekst</span>
            # <span style="font-family: Font A">inny tekst</span>			
            # <span style="font-family: Font A">jeszcze tekst</span>
            # </tag>
            # podczas gdy chcielibysmy: (**)
            # <tag class="ocr_element">
            # <span style="font-family: Font A">tekstinny tekstjeszcze tekst</span>            
            # </tag>
            # normalnie wychodzac z eksportu liscia w __exportNode wypisujemy tag
            # zakonczenia fontu (</span>)
            # a) zeby osiagnac zachowanie (**) to jezeli lisc jest ignorowany wychodzac
            # z niego nie zamykamy fontu, ale ustawiamy __processingIgnoredTagFont
            # na True
            # jesli jest on True to:
            # b) wchodzac do nastepnego zignorowanego elementu nie wypisujemy
            # poczatku fontu tylko korzystamy z otwrtego juz tagu fontu
            # c) chyba ze sie zmienil font, wtedy zmieniamy go tak jak normalnie
            # d) jezeli dochodzimy do konca elementu zawierajacego zignorowane
            # elementy (tutaj - /Element) to musimy wypisac zakonczenie fontu
            # (__processingIgnoredTagFont ustawiamy wtedy z powrotem na False)
            # e) jezeli napotkamy na niezignorowany element bedacy rodzenstwem
            # ignorowanego elementu (w naszym przypadku gdyby oprocz /Podelement
            # /Element mial tez dzieci /BratPodelementuNieignorowany, to 
            # przed eksportem elemtnu /BratPodelementuNieignorowany trzeba by takze
            # zamknac zakonczenie fontu - wtedy ustawiamy __processingIgnoredTagFont
            # na False, bo nastepny zignorowany element nie bedzie w obrebie fontu
            # i bedzie musial otworzyc nowy tag span dla fontu
            #
            # powinno to tez zadzialac dla tagow pietrowo ignorowanych (ze zarowno
            # ojciec jak i syn sa ignorowani)
        #self.__lastFontStyle = None
        #self.__lvl = 0
        self.__verbose = verbose # czy wypisujemy numery aktualnie przetwarzanych stron
        self.__divs = None      # znaczenie
        self.__ind = 0          # tych
        self.__divbboxes = None # zmiennych
        self.__whites = None    # wyjasnione
        self.__wordInd = 0      # wraz z ich
        self.__inWord = False   # uzyciem w
        #self.__stop = False
        self.__useICU = False   # metodzie __exportNode
        
    def beginExportByPages(self): # poczatek eksportu strona po stronie
        self.__file.write("<html>")
        self.__writeHead()
        self.__file.write("<body class=\"ocr_document\">")
    
    def endExportByPages(self): # koniec eksportu strona po stronie
        self.__file.write("</body>")
        self.__file.write("</html>")
        self.save()
    
    # eksportujemy pojedyncza strone w trybie eksportu strona po stronie
    # strona jest w tym wypadku elementem drzewa ukladu strony zanalizowanego przez
    # pdfminera (element o nazwie "page"), poniewaz tego trybu uzywamy tylko dla
    # pdfminera 
    def exportPage(self, page):
        bbox = page.getBbox()
        if self.__verbose:
            print "Processing page " + str(page.getPageId() + 1)
        self.__file.write("<div class=\"ocr_page\" title=\"pageno " +
                        str(page.getPageId()) + "; bbox " + bbox2str(scaleBbox(bbox)) +
                        "\">")
        for c in page.getChildren():
            element = self.__getElement(c) # tag HTML z elementem hOCR dla danego
                # elementu drzewa struktury
            if element != None: # jezeli nie podano tagu dla elementu drzewa o
                    # danej nazwie to powinien byc zignorowany lacznie z dziecmi
                    # (w przeciwienstwie do sytuacji gdy jest podany, ale ma
                    # zapalona flage __ignored)
                self.__exportNode(c, element, pagesInTree=True)
        self.__file.write("</div>")
    
    # eksportujemy caly plik w trybie eksportu calego drzewa
    def export(self):
        #print "TU jestem"
        self.__determinePageParents(self.__root)
        #if self.__pageParents == []: # kazdy element ma jedno dziecko
        #    self.__pageAncestors = []
        #    self.__pageParents.append(self.__root)
        #    self.__pageAncestors.append(self.__root)
        #print ">>>>>>>:", self.__pageParents
        #print self.__root.getStandardText()
        #print self.__root.isRoot()
        self.__processNode(self.__root)
    
    # konczymy eksport calego drzewa
    def save(self):
        self.__file.close()
    
    # ustala elementy ktore nie powinny byc dzielony miedzy strony (__pageAncestors)
    # oraz __pageParents (podzbior __pageAncestors), kazdy tag z __pageParents
    # (w zasadzie powinien tam byc tylko jeden) spelnia nastepujaca wlasciwosc:
    # odpowiadajacy mu tag HTML zawiera tagi odpowiadajace stronom (ocr_page);
    # jest to pozostalosc po bardziej skomplikowanym algorytmie ktory byl tutaj
    # wczesniej, dopoki nie uswiadomilem sobie, ze w zasadzie wystarczy wziac korzen
    def __determinePageParents(self, node):
        if self.__xml:
            self.__pageParents.append("pages") # wynika wprost ze struktury drzewa
                # ukladu strony pdfminera
            self.__pageAncestors.append("pages")
            return
        else:
            if len(node.getChildren()) == 1 and node.getChildren()[0].getStandardText() == "Document":
                self.__pageParents.append("Document") # jedynym dzieckiem korzenia jest
                    # element o nazwie /Document 
                    # TODO: I PDF/A, /Art, itp., czy moze byc wiele?
                self.__pageAncestors.append("Document")
                self.__pageAncestors.append("StructTreeRoot")
            else:
                self.__pageParent.append("StructTreeRoot") # wpp tylko korzen
                self.__pageAncestors.append("StructTreeRoot")
    
    # eksportujemy pojedynczy element
    # (uwaga: najpierw przeczytaj komentarz do __processNode)
    # znaczenie parametru pagesInTree:
    # False - tryb eksportu calego drzewa - metoda musi podczas eksportu sama sprawdzac,
    # czy zmienila sie strona, wypisywac je, musi tez wywolywac dla dzieci
    # __processNode, zeby sprawdzila ona czy element jest na wielu stronach i
    # ewentualnie ja podzielic
    # True - tryb eksportu strona po stronie - wszelkimi sprawami zwiazanymi ze
    # stronami zajmuje sie exportPage, ta metoda nie musi nic robic i dla dzieci
    # moze wywolywac __exportNode 
    def __exportNode(self, node, element, pagesInTree=False):
        # wypisujemy poczatego tagu HTML
        pagebbox = self.__lib.getPageBBox(node.getPageIds()[0])
        if element.hasBbox(): # czy w atrybucie title mamy wypisac bounding box box?
            self.__file.write(element.start(groupid=node.getGroupId(),
										bbox=changeCoords(pagebbox, node.getBbox())))
        else:
            self.__file.write(element.start(groupid=node.getGroupId()))
        #self.__file.write("\nSTART " + node.textOf() + ": " + str(self.tagHasFont) + ", " + str(self.processingIgnoredTagFont) + "\n")
        if not pagesInTree:
            if self.__pageParent(node): # tag HTML odpowiadajacy naszemu wezlowi
                    # bedzie bezpostednim przodkiem tagu HTML odpowiadajacemu stronie
                    # (element hOCR ocr_page)
                self.__firstPage = True # zaznaczamy, ze nie wypisano jeszcze tagu
                    # otwierajacego jakas strone - w metodzie __processNode dla
                    # dziecka bedzie to sprawdzone i wypisany zostanie poczatek
                    # strony
        if node.isLeaf(): # lisc
            useICU = self.__icu != None and ((not self.__xml) or node.getStandardText() != "text")
                # czy mamy dzielic zawartosc elementu na wyrazy? uwaga - jezeli eksportujemy
                # strukture ukladu strony to nie dzielimy slow w obrebie lisci (elementow o
                # nazwie text), tylko w obrebie elementow textline
                # TODO: I (*****) w chwili obecnej spowoduje to wyprodukowanie nieprawidlowego pliku XML jezeli
                # tagi text nie beda ignorowane (beda sie zazebiac, o tak:
                #     <span* class="ocr_text"><span class="ocrx_word"></span*>...
                # )
            #print self.__icu, useICU, self.__icu != None
            if useICU:
                text = node.getTextContent() # zawartosc tekstowa
                self.__divs = divideIntoWords(text, self.__icu) # znajdujemy punkty podzialu
                    # na slowa
                #print text, self.__divs
                #res = u""
                #for c in node.getCharbboxes():
                #    res += c
                #print text, len(text), len(node.getCharbboxes()), res#, node.getCharbboxes()
                assert(len(text) == len(node.getCharbboxes()))
                (self.__divbboxes, self.__whites) = generateDivBboxes(self.__divs, node.getCharbboxes(), node.getChildren(), self.__tagHasFont, self.__font)
                    # znajduje bounding boxy slow i indeksy slow (indeks == numer slowa w tekscie
                    # text liczony od zera) ktore zawieraja tylko biale spacje
                self.__divs = [0] + self.__divs # dzieki temu kazde slowo jest ograniczone z dwoch
                    # stron
                #print len(text), self.__divs[-1], len(self.__divs), len(self.__divbboxes)
                self.__ind = 0 # indeks aktualnie przetwarzanego znaku w tekscie, zawsze oznacz
                    # indeks pierwszego znaku nastepnego slowa
                self.__wordInd = 0 # indeks slowa (numer w tekscie), zawsze oznacza indeks
                    # nastepnego slowa
                self.__inWord = False # czy jestesmy wewnatrz tagu <span class="ocrx_word">?
            if useICU:
                self.__useICU = True # self__useICU decyduje czy mamy eksportowac informacje o
                    # podziale na slowa - poza obliczaniem warunku useICU = ... powyzej,
                    # self.__useICU moze byc tez True jezeli eksportujemy uklad strony i zostal
                    # podzielony ojciec aktualnego elementu o nazwie textline (patrz (***) sporo ponizej
                    # w tej metodzie)
            for c in node.getChildren(): # (%%%)
                if isinstance(c, Font):
                    #self.__file.write("\n<LEAF CHILDREN=\"FONT\"/>\n")
                    willChange = self.__fontWillChange(c) # __fontWillChange ma wartosc True
                        # jezeli w __changeFont zostanie zmieniony font (spowoduje to zamkniecie
                        # tagu z definicja fontu, a poniewaz zawiera on tagi z ocrx_word, to
                        # musimy zamknac tag dla slowa; powoduje to rozciecie slow przez zmiany
                        # fontow w ich obrebie) 
                        # TODO: I polaczyc rozciete zmiana fontu kawalki slowa za pomoca
                        # groupid
                    if self.__useICU and self.__inWord and willChange:
                        if not (self.__wordInd - 1) in self.__whites:
                            self.__file.write("</span>")
                    self.__changeFont(c) # sprawdzamy czy zmienil sie font i jesli tak to informacje
                        # o tym wypisujemy do hOCR (zamykamy tag span i wypisujemy poczatek dla nowego
                        # fontu, jezeli nie bylo wczesniej zadnego fontu w elemencie to wypisujemy
                        # tylko, ze zaczal sie nowy font (tag otwierajacy span)
                    if self.__useICU and self.__inWord and willChange:
                        if not self.__wordInd in self.__whites:
                            self.__file.write("<span class=\"ocrx_word\" title=\"bbox " + bbox2str(changeCoords(pagebbox, self.__divbboxes[self.__wordInd])) + "\">")
                                # nie powinno byc bbox == None (patrz TagInterpreter.do_w), bo \n to bialy znak
                                # tak samo w podobnych sytuacjach ponizej
                        self.__wordInd += 1
                    self.__tagHasFont = True # w elemencie jest font (otworzylismy tag span dla fontu)
                    #print c.name, c.italic
                else: # TODO: I tu byla taka notatka: "tu wydarzy sie katastrofa - jak obecny tag bedzie ignored i nie bedzie mial na poczatku
                    # fontu (a moze sie tak zdarzyc w PDF, a kto wie czy i nie w XML)" - ale nie moge sobie przypomniec o co chodzilo
                    if not self.__tagHasFont: # w elemencie nie ma fontu, wykrzystujemy ostatni
                        #if self.__font == None:
                        #    print node.getStandardText(), node.getTextContent()
                        self.__writeFont(self.__font) # wypisujemy poczatek fontu
                        self.__tagHasFont = True # w elemencie teraz jest juz font (wypisalismy poczatek
                            # fontu (tag otwierajacy <span...>))
                    #self.__file.write("\n<LEAF CHILDREN =\"" + c.replace("\"", "'").replace("<", "&lt;").replace("&", "").encode("utf-8") + ": " + str(self.__tagHasFont) + ", " + str(self.__processingIgnoredTagFont) + "\"/>\n")
                    #print divs
                    if self.__useICU: # uzywamy dzielenia na slowa
                        #print self.__ind in self.__divs
                        if self.__ind in self.__divs: # poczatek nastepnego slowa
                            if not self.__wordInd in self.__whites: # patrzymy czy slowo nie jest spacja
                                self.__file.write("<span class=\"ocrx_word\" title=\"bbox " + bbox2str(changeCoords(pagebbox, self.__divbboxes[self.__wordInd])) + "\">")
                                    # (****) jesli nie jest wypisujemy poczatek*
                                    # * fragmenty bedace spacjami sa wypisywane na zewnatrz elementow ocrx_word
                            self.__wordInd += 1
                            self.__inWord = True                        
                        words = self.__getWords(c, self.__ind, self.__divs) # dzielimy fragment tekstu c na kawalki
                            # nalezace do roznych slow
                        #print c, words, self.__divs, self.__ind                        
                        if len(words) > 0:
                            # wypisujemy pierwszy kawalek
                            self.__file.write(words[0].replace("<", "&lt;").replace("&", "&amp;").encode("utf-8"))
                        for w in words[1:]: # wypisujemy kolejne kawalki zmieniajac slowa
                            #print self.__wordInd, len(self.__divs), len(self.__divbboxes)#, self.__divbboxes[self.__wordInd]
                            if not (self.__wordInd - 1) in self.__whites: # patrz (****) powyzej
                                self.__file.write("</span>")
                            if not self.__wordInd in self.__whites: # patrz (****) powyzej
                                self.__file.write("<span class=\"ocrx_word\" title=\"bbox " + bbox2str(changeCoords(pagebbox, self.__divbboxes[self.__wordInd])) + "\">")
                            self.__file.write(w.replace("<", "&lt;").replace("&", "&amp;").encode("utf-8"))
                            self.__wordInd += 1
                            self.__inWord = True
                        self.__ind += len(c)
                        if self.__ind in self.__divs: # koniec slowa
                            if not (self.__wordInd - 1) in self.__whites: # patrz (****) powyzej
                                self.__file.write("</span>") # wypisujemy koniec slowa 
                            self.__inWord = False
                    else: # nie dzielimy na slowa - wypisujemy calosc tesktu
                        self.__file.write(c.replace("<", "&lt;").replace("&", "&amp;").encode("utf-8"))
            if useICU: # jezeli useICU bylo False a self.__useICU True, to nie powinnismy ustawiac
                    # self.__useICU na False, bo oznacza to ze dzielimy na slowa caly element
                    # textline i nastepne elementy text tez powinny widziec self.__useICU
                self.__useICU = False
        else: # nie lisc (***)
            self.__useICU = node.getStandardText() == "textline" and self.__xml and self.__icu != None
                # eksportujemy uklad strony
                # dzielimy na slowa cala zawartosc elementu textline
                # jezeli elementy o nazwie text nie beda zignorowane to zadziala to niepoprawnie
                # (patrz (*****) na poczatku metody)
                # self.__useICU ustawione na True bedzie widoczne w dzieciach i
                # to w nich bedzie sie odbywal wlasciwy eksport (patrz kod powyzej)
            if self.__useICU:
                # dzialanie analogiczne do podobnego fragmentu powyzej
                # roznice w dzialaniu metod generateDivBboxesTextline i generateDivBboxes
                # wyjasnione w komentarzach przy ich implementacji
                text = node.getTextContent()
                self.__divs = divideIntoWords(text, self.__icu)
                (self.__divbboxes, self.__whites) = generateDivBboxesTextline(self.__divs, node.getCharbboxes(), node.getChildren(), self.__tagHasFont, self.__font)
                self.__divs = [0] + self.__divs
                #print text, self.__divs
                self.__ind = 0
                self.__wordInd = 0
                self.__inWord = False
            for c in node.getChildren(): # (%%%%)
                #print c.textOf()
                if self.__getElement(c) == None: # ignorujemy element razem z jego dziecmi
                    continue
                if not self.__getElement(c).isIgnored() and self.__processingIgnoredTagFont:
                    # patrz przypadek e) komnentarza do zmiennej __processingIgnoredTagFont 
                    # nie trzeba tego uwzgledniac w dzieleniu na wyrazy, bo przypadek e) nie
                    # trafi sie przy eksporcie ukladu strony (bo jedynym dzieckiem textline
                    # jest text a on na razie nie moze byc nieignorowany (wspominany powyzej
                    # problem przy dzieleniu wyrazow)
                    #self.__file.write("\nCHILD ELEMENT " + c.textOf() + ": " + str(self.tagHasFont) + ", " + str(self.processingIgnoredTagFont) + "\n")
                    self.__tagHasFont = False # bo zamykamy tag fontu ponizej ...
                    self.__processingIgnoredTagFont = False
                    self.__endSpecialTags(self.__font)
                    self.__file.write("</span>") # ... o tutaj
                if pagesInTree: # patrz komentarz na poczatku metody - eksportujemy
                        # strona po stronie i nie musimy wywolywac __processNode
                        # zarzadzajacym stronami, bo robi to za nas metoda exportPage,
                        # wiec od razu wywolujemy __exportNode
                    el = self.__getElement(c)
                    if el != None: # jesli None to ignorujemy element razem z dziecmi
                        self.__exportNode(c, el, pagesInTree=True)
                else:
                    self.__processNode(c)
                    #if self.__stop:
                    #    self.__file.write(element.stop())
                    #    return
            self.__useICU = False # jesli to koniec elementu textline to oczywiscie
                # wychodzimy z trybu dzielenie slow
        if node.isLeaf() and not element.isIgnored():
            #self.__file.write("\nCASE 1 " + node.textOf() + ": " + str(self.tagHasFont) + ", " + str(self.processingIgnoredTagFont) + "\n")
            if self.__tagHasFont: # koniec liscia, lisc nie ignorowany, i jest
                    # otwarty tag z fontem, trzeba go oczywiscie zamknac
                self.__tagHasFont = False
                self.__endSpecialTags(self.__font)
                self.__file.write("</span>") # TODO: NOTE bo po ostatnim nie ma change font
        elif node.isLeaf() and self.__tagHasFont: # koniec liscia ignorowanego
                # (przypadek a) w komentarzu do __processingIgnoredTagFont)
            #self.__file.write("\nCASE 2 " + node.textOf() + ": " + str(self.tagHasFont) + ", " + str(self.processingIgnoredTagFont) + "\n")
            self.__processingIgnoredTagFont = True
        elif self.__processingIgnoredTagFont: # koniec elementu zawierajacego element
                # ignorowany, jest otwarty tag z fontem i trzeba go zamknac (przypadek d)
                # z komentarza do __processingIgnoredTagFont
            #self.__file.write("\nCASE 3 " + node.textOf() + ": " + str(self.tagHasFont) + ", " + str(self.processingIgnoredTagFont) + "\n")
            self.__tagHasFont = False
            self.__processingIgnoredTagFont = False
            self.__endSpecialTags(self.__font)
            self.__file.write("</span>")
        #if element.__pageParent:
        #if node.pageid == None and (not node.__isLeaf) and node.textOf() == self.__pageParent:
        if not pagesInTree: # tryb eksportu calego drzewa - jezeli element w ktorym
                # jestesmy ma odpowiadajacy mu tag HTML ktory jest bezposrednim
                # przodkiem tagu ze strona (class="ocr_page") to trzeba zamknac
                # tag ze strona
                # TODO: I czy moze sie zdarzyc ze ten tag bedzie pusty i nie bedzie
                # zawieral strony?
            #if self._pageParent(node): # TODO: NOTE bo po ostatniej stronie nie bedzie page changed
            #print node.getStandardText()
            if self.__pageParent(node):
                self.__file.write("</div>")
        #self.__file.write("\nELEMENT STOP " + node.textOf() + ": " + str(self.tagHasFont) + ", " + str(self.processingIgnoredTagFont) + "\n")
        self.__file.write(element.stop()) # wypisujemy koniec tagu HTML

    # ekportujemy element w trybie eksportu calego drzewa
    # ta metoda zawiera rozne operacje pomocnicze, w celu wlasciwego eksportu wywoluje
    # __exportNode
    def __processNode(self, node, initialized=False, uninitialize=True):#, ignoreRoot=False):
        #if node.isRoot() and (not ignoreRoot): # TODO: X ignoreRoot - sprawdzic czy
            # bez tego eksport z XML tez dziala 
        if node.isRoot():
            self.__initializeRoot(node) # wezel jest korzeniem calego drzewa -
                # - odnosnie zachowania programu patrz komentarz do metody __initializeRoot
        #elif node.__isLeaf:
            #for c in node.children:
                #self.__file.write(c.encode("utf-8"))
        #if False:
        #    pass
        else: # nie-korzen
            #print node.textOf()
            element = self.__getElement(node) # tag HTML i element hOCR odpowiadajacy
                # danemu elementowi
            if element == None: # element ignorowany razem z dziecmi
                #print "NONE"                
                return
            #print self.__pageAncestor(node), node.getStandardText(), self.__pageChanged(node)
            if not self.__pageAncestor(node): # mozna podzielic element miedzy strony
                    # w praktyce jedyny przypadek gdy __pageAncestor(node) == True
                    # ma miejsce gdy eksportujemy strukture logiczna PDF i
                    # node.getStandardText() == "Document" i node jest jedynym
                    # dzieckiem korzenia
                if node.multipage(): # element jest na wielu stronach
                    #print repeat("  ", self.__lvl) + "MULTIPAGE:", node.text
                    node.split() # dzielimy element
                    #assert(node.getCopies() != None)
                    #assert(not node.multipage())
                    self.__processNode(node, True, uninitialize=False) # wywolujemy
                        # jeszcze raz dla elementu obcietego do jednej strony (i podajemy
                        # parametr opcjonalny, ktory zabrania uzywania metody
                        # uninitialize (bo uzywamy jej pare liniii kodu nizej)) 
                    #assert(node.getCopies() != None)
                    #print "OK"
                    for (_, v) in node.getCopies().iteritems(): # wywolujemy dla
                            # czesci elementu z innych stron
                        self.__processNode(v, True)
                    node.uninitialize() # teoretycznie powinno to zwalniac pamiec
                        # zajeta przez __initialize, ale patrz komentarz o zarzadzaniu
                        # pamiecia
                    return
                elif self.__pageChanged(node): # element lezy na jednej stronie i
                        # jest to inna strona niz ta na ktorej lezal ostatni element (a)
                        # lub nie wypisalismy jeszcze tagu otwierajacego strone (b)
                    self.__changePage(node) # wypisujemy tag konczacy aktualna strone
                        # (jezeli taka istnieje) (a), i wypisujemy tag otwierajacy
                        # strone na ktorej lezy element (a i b) 
                    #if self.__stop:
                    #    return
                #print "CHANGED", self.page
            ###if self.page == None or self.page != node.pageid:
            ###   self._newPage()
            #print node.getText(), "- OK"
            self.__exportNode(node, element) # wlasciwy eksport wezla
            if uninitialize: # patrz wywolanie self.__processNode(node, True, uninitialize=False)
                    # pare linijek powyzej
                node.uninitialize() # to mialo teoretycznie zwalniac pamiec zajeta
                    # przez __initialize

    # por. uzycie w metodzie __exportNode
    # text - fragment tekstu podzielonego na wyrazy
    # index - indeks pierwszego znaku we fragmencie wzgledem calego podzielonego tekstu
    # breaks - miejsca podzialow na slowa
    # zwraca fragment text podzielony na slowa
    def __getWords(self, text, index, breaks):
        #print text, index#, breaks,
        tmp = u""
        res = []
        for c in text:
            if index in breaks and tmp != u"":
                #print "jest", tmp
                res.append(tmp)
                tmp = u""
            tmp += c
            index += 1        
        res.append(tmp)
        #print res
        return res

    # czy wywolana za chwile metoda __changeFont zmieni font?
    def __fontWillChange(self, font):
        return not (self.__tagHasFont and font.getId() == self.__font.getId())
            
    # jesli jest otwarty tag span fontu i jest on inny niz font font, to zmienia
    # font, jezeli to ten sam font to nic nie robi, jezeli nie bylo otwartego tagu
    # fontu to wypisuje tylko poczatek nowego
    def __changeFont(self, font):
        if self.__tagHasFont: # tag byl otwarty
            #print font.getId(), self.__font.getId()
            if font.getId() == self.__font.getId(): # font sie nie zmienil
            #if self.__font != None and font.getId() == self.__font.getId():
            # TODO: NOTE tu chyba nigdy bedzie self.__font == None
                return
            # font sie zmienil - zamykamy tag
            self.__endSpecialTags(self.__font)
            self.__file.write("</span>")
        # otwieramy tag nowego fontu
        self.__font = font
        self.__writeFont(font)
    
    # wypisuje tag otwierajacy font
    def __writeFont(self, font):
        def __style(font):
            if font.italic:
                return "; font-style: italic"
            else:
                return ""
        def __weight(font):
            if font.bold:
                return "; font-weight: bold"
            else:
                return ""
        name = None
        if self.__fontMap != None:
            name = self.__fontMap.getName(font.name)
            #print font.name, name
        if name == None:
            name = font.name
        self.__file.write("<span style=\"font-family: " + name + "; font-size: " + str(font.size) + "pt" + __style(font) + __weight(font) + "\">")
        self.__startSpecialTags(font)
    
    # wypisuje tagi specjalne ocrx_bold i ocrx_italic (uzywane wszedzie tam gdzie wypisuje
    # poczatek tagu fontu)
    def __startSpecialTags(self, font):
        if self.__specialTags:
            if font.italic and font.bold:
                self.__file.write("<span class=\"ocrx_bold\"><span class=\"ocrx_italic\">")
            elif font.italic:
                self.__file.write("<span class=\"ocrx_italic\">")
            elif font.bold:
                self.__file.write("<span class=\"ocrx_bold\">")
    
    # zamyka tagi specjalne ocrx_bold i ocrx_italic (uzywane wszedzie tam gdzie zamyka tag
    # fontu)
    def __endSpecialTags(self, font):
        if self.__specialTags:
            if font.italic and font.bold:
                self.__file.write("</span></span>")
            elif font.italic:
                self.__file.write("</span>")
            elif font.bold:
                self.__file.write("</span>")

    # pobiera obiekt opisujacy tag HTML i element hOCR odpowiadajacy danemu elementowi
    # drzewa struktury
    def __getElement(self, node):
        tag = node.getStandardText()
        if tag == "L": # element bedacy lista (element struktury PDF)
            (ordered, unordered) = self.__checkListOrder(node) # czy lista jest
                # uporzadkowana (to nie dziala do konca - patrz komentarz do
                # __checkListOrder)
            if ordered and not unordered:
                # lista uporzadkowana
                element = self.__mapping.hOCRElement("L.Ordered", [])
            else:
                element = self.__mapping.hOCRElement("L.Unordered", [])
        elif tag == "H": # element bedacy naglowkiem (element struktury PDF)
            self.__headerNesting += 1
            element = self.__mapping.hOCRElement("H", [self.__headerNesting])
                # przekazujemy zagniezdzenie jako argument, bo mapowanie moze
                # zamieniac np. na h1....h6
        elif tag == "Sect": # element bedacy rozdzialem (element struktury PDF)
            self.__sectionNesting += 1
            element = self.__mapping.hOCRElement("Sect", [self.__sectionNesting])
                # przekazujemy zagniezdzenie jako argument, bo mapowanie moze
                # zamieniac np. na (sub)*section
        else:
            element = self.__mapping.hOCRElement(tag, [])
            #print tag, element
        return element
    
    # wypisujemy naglowek pliku HTML
    def __writeHead(self):
        #self.__file.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>")
        self.__file.write("<head>")
        #self.__file.write("<link rel=\"stylesheet\" href=\"styl.css\" type=\"text/css\"/>")
        self.__file.write("<meta http-equiv=\"content-type\" content=\"text/html; charset=utf-8\"/>")
        self.__file.write("<meta name=\"ocr-system\" content=\"" + HOCR_APP_NAME + " " + HOCR_APP_VERSION + "\"/>")
        self.__file.write("<meta name=\"ocr-capabilities\" content=\"ocrp_font")
        if self.__specialTags:
            self.__file.write(" ocrx_italic ocrx_bold")
        if self.__icu != None:
            self.__file.write(" ocrx_word")
        for capability in self.__mapping.mappingCapabilities():
            self.__file.write(" ")
            self.__file.write(capability)
        self.__file.write("\"/>")
        #
        self.__file.write("<meta name=\"ocr-number-of-pages\" content=\"" + str(self.__lib.getPageNo()) + "\"/>") 
        self.__file.write("</head>")
    
    # wypisujemy naglowek HTML i tag otwierajacy <body>, nastepnie
    # przechodzimy do eksportu dzieci, ktore zostana wypisane wewnatrz
    # <body>
    def __initializeRoot(self, node):
        self.__file.write("<html>")
        self.__writeHead()
        self.__file.write("<body class=\"ocr_document\">")
        #if self.__xml:
        #    self.__processNode(node, ignoreRoot=True)
        #else:
        #   for c in node.getChildren():
        #       self.__processNode(c)
        if self.__pageParent(node): # tag HTML odpowiadajacy naszemu wezlowi
                # bedzie bezpostednim przodkiem tagu HTML odpowiadajacemu stronie
                # (element hOCR ocr_page)
            self.__firstPage = True # zaznaczamy, ze nie wypisano jeszcze tagu
                # otwierajacego jakas strone - w metodzie __processNode dla
                # dziecka bedzie to sprawdzone i wypisany zostanie poczatek
                # strony
        for c in node.getChildren():
            self.__processNode(c)
        if self.__pageParent(node): # jezeli element w ktorym
                # jestesmy ma odpowiadajacy mu tag HTML ktory jest bezposrednim
                # przodkiem tagu ze strona (class="ocr_page") to trzeba zamknac
                # tag ze strona
                # TODO: I czy moze sie zdarzyc ze ten tag bedzie pusty i nie bedzie
                # zawieral strony?
            self.__file.write("</div>")
        self.__file.write("</body>")
        self.__file.write("</html>")

    # sprawdzamy, czy lista jest uporzadkowana (lista jest uporzadkowana jezeli
    # kazdy z jej elementow ma etykiete ktora mapowanie uzna za etykiete listy
    # uporzadkowanej)
    def __checkListOrder(self, node):
        ordered = False
        unordered = False
        # TODO: NOTE to zaklada, ze lista jest poprawnie sformatowana (tzn. w elemencie
        # o nazwie Lbl naprawde sa numery lub punkty listy)
        # jest to nieprawdo np. w przypadku listy w plikach PDF/A generowanych przez
        # OpenOffice
        # TODO: I sa rozne atrybuty elementow struktury logicznej (patrz Tagged PDF)
        # ktore informuja o tym czy lista jest ordered czy nie, trzeba by je tez
        # jakos wykorzystac
        for c in node.getChildren():
            for cc in c.getChildren():
                #print cc.textOf()
                if cc.getStandardText() == "Lbl":
                    if not self.__mapping.ordered(cc.getTextContent()):
                        #print res, self.__mapping.ordered(res)
                        unordered = True
                    else:
                        ordered = True
        return (ordered, unordered)
        
    def __pageParent(self, node):
        return node.getStandardText() in self.__pageParents
    
    def __pageAncestor(self, node):
        return node.getStandardText() in self.__pageAncestors

    # czy zmienila sie strona (tzn. czy strona na ktorej lezy element jest inna
    # niz aktualna strona?)
    def __pageChanged(self, node):
        if self.__page == None: # jeszcze nie bylo strony - musimy wypisac poczatek
            return True
        else:
            if node.getPageIds()[0] != self.__page: # TODO: X
            #if node.getPageId() != self.__page: #and node.pageid != None:
                return True
            else:
                return False

    # zmienia strone
    def __changePage(self, node):
        if self.__page != None:
            if self.__firstPage: # (*) nie ma jeszcze wypisanej zadnej strony w tagu HTML
                    # w ktorym maja byc zawarte strony (w tagu odpowiadajacym 
                    # elementom o nazwach z __pageParents)
                self.__firstPage = False
            else: # jest juz strona - musimy wypisac jej tag zamykajacy
                self.__file.write("</div>")
            self.__pageNum += 1
            #if self.__pageNum == 3:
            #    self.__stop = True
            #    return
        elif self.__firstPage: # jak (*) powyzej
            self.__firstPage = False
        # pobieramy identyfikator strony:
        if self.__xml: # TODO: NOTE w zasadzie niepotrzebne bo dla PDFMinerNode
                # getPageId() == getPageIds()[0]
            self.__page = node.getPageId()
        else:
            #print node.getText()
            # TODO: D tu moze jakos inaczej? bo to sie opiera o zalozenie, ze wszystkie
            # eksportowane elementy sa niepuste albo maja self.__pageid (ale np. w pustak2.pdf puste tez maja strone)
            if len(node.getPageIds()) == 0:
                print "PDF/A Utilities can't process this PDF file."
                self.__file.close()
                exit()
            self.__page = node.getPageIds()[0]
        bbox = self.__lib.getPageBBox(self.__page)
        if self.__verbose:
            print "Processing page " + str(self.__pageNum + 1)
        self.__file.write("<div class=\"ocr_page\" title=\"pageno " +
                        str(self.__pageNum) + "; bbox " + bbox2str(scaleBbox(bbox)) +
                        "\">") # wypisujemy tag otwierajacy
 
#class HOCRMapping:
#    
#    def __init__(self):
#        #print "init"
#        self.__dict = None
 
# mapowanie z elementow struktury logicznej PDF na tagi HTML i elementy hOCR
class HOCRStandardMapping:#(HOCRMapping):
    
    def __init__(self, mapping=None):
        #print "initstandard"
        self._dict = {} # slownik zawierajacy mapowanie (por. __useDefaultMapping)
        if mapping != None:
            self._useMappingFromFile(mapping)
        else:
            self.__useDefaultMapping()
    
    # laduje mapowanie z pliku
    # format pliku:
    # nazwa_elementu<NL>
    # nazwa_elementu<TAB>tag_HTML<NL>
    # nazwa_elementu<TAB>tag_HTML<TAB>element_HOCR<NL>
    # nazwa_elementu<TAB>tag_HTML<TAB>element_HOCR<TAB>bbox<NL>
    # ktore odpowiadaja nastepujacym operacja na slowniku (por. __useDefaultMapping):
    # self._dict.setdefault("nazwa_elementu", HOCRElement().ignore())
    # self._dict.setdefault("nazwa_elementu", HOCRElement("tag_HTML"))
    # self._dict.setdefault("nazwa_elementu", HOCRElement("tag_HTML", "element_HOCR"))
    # self._dict.setdefault("nazwa_elementu", HOCRElement("tag_HTML", "element_HOCR").useBbox())
    def _useMappingFromFile(self, mappingFile, xml=False):
        # TODO: NOTE sprawdzanie czy tagi sa wlasciwymi tagami PDF? - ale moga byc podane dowolne tagi bez role map
        file = open(mappingFile, "r")
        i = 0
        ok = True
        for line in file:
            line = line[:-1]
            i += 1
            elements = line.split("\t")
            if len(elements) == 1:
                self._dict.setdefault(elements[0], HOCRElement().ignore())
            elif len(elements) == 2:
                #if elements[1] == "PARENT":
                #    self._dict.setdefault(elements[0], HOCRElement().ignore().parentOfPage())
                #elif elements[1] == "ANCESTOR":
                #    self._dict.setdefault(elements[0], HOCRElement().ignore().ancestorOfPage())
                #else:
                self._dict.setdefault(elements[0], HOCRElement(elements[1]))
            elif len(elements) == 3:
                #if elements[2] == "PARENT":
                #    self._dict.setdefault(elements[0], HOCRElement(elements[1]).parentOfPage())
                #elif elements[2] == "ANCESTOR":
                #    self._dict.setdefault(elements[0], HOCRElement(elements[1]).ancestorOfPage())
                #else:
                self._dict.setdefault(elements[0], HOCRElement(elements[1], elements[2]))
            elif len(elements) == 4:
                #if elements[3] == "PARENT":
                #    self._dict.setdefault(elements[0], HOCRElement(elements[1], elements[2]).parentOfPage())
                #elif elements[3] == "ANCESTOR":
                #    self._dict.setdefault(elements[0], HOCRElement(elements[1], elements[2]).ancestorOfPage())
                #elif elements[3] == "bbox":
                if elements[3] == "bbox":
                    self._dict.setdefault(elements[0], HOCRElement(elements[1], elements[2]).useBbox())
                else:
                    sys.stderr.write("Mapping __file malformed in line " + str(i) + ": " + elements[3] + "\n")
                    ok = False
            else:
                sys.stderr.write("Mapping __file malformed in line " + str(i) + ": " + len(elements) + "\n")
                ok = False
        if xml and not self._dict.get("text").isIgnored():
            sys.stderr.write("Export of \"text\" tags not supported, mark \"text\" tags as ignored in mapping file\n")
            ok = False
        file.close()
        if not ok:
            raise MyException("File malformed")
    
    # domyslne mapowanie dla struktury logicznej PDF
    # zasada dzialania opisana na przykladach ponizej:
    def __useDefaultMapping(self):
        #self._dict.setdefault("StructTreeRoot", HOCRElement("body", "ocr_document")) wykomentowane
            # bo zarowno body jak i StructTreeRoot sa przetwarzane w inny sposob niz pozostale
            # elementy
        # self.__dict.setdefault("StructTreeRoot", HOCRElement().ignore())
        self._dict.setdefault("Table", HOCRElement("table")) # Table zamieniane na tag <table>
        self._dict.setdefault("Table Contents", HOCRElement("p", "ocr_par").useBbox()) 
        #self._dict.setdefault("Text body", HOCRElement("p", "ocr_par").useBbox())
        self._dict.setdefault("TH", HOCRElement("th"))
        self._dict.setdefault("TR", HOCRElement("tr"))
        self._dict.setdefault("TD", HOCRElement("td"))
        self._dict.setdefault("L.Ordered", HOCRElement("ol")) # L bedace lista uporzadkowana
        self._dict.setdefault("L.Unordered", HOCRElement("ul")) # L bedace lista nieuporzadkowana
        self._dict.setdefault("LI", HOCRElement("li"))
        self._dict.setdefault("LBody", HOCRElement().ignore()) # Lbody ignorowane ale eskportowane jego dzieci
            # jezeli natomiast HOCRElement dla LBody nie zostalby dodany do slownika, to zignorowane bylyby takze
            # jego dzieci
        self._dict.setdefault("P", HOCRElement("p", "ocr_par").useBbox()) # P zamieniane na tag <p class="ocr_par" title="bbox ...">
        self._dict.setdefault("H", HOCRElement("h$", "ocr_par").useBbox()) # $ jest zamnieniane na liczbe oznaczajaca poziom zagniezdzenia
        self._dict.setdefault("H1", HOCRElement("h1", "ocr_par").useBbox())
        self._dict.setdefault("H2", HOCRElement("h2", "ocr_par").useBbox())
        self._dict.setdefault("H3", HOCRElement("h3", "ocr_par").useBbox())
        self._dict.setdefault("H4", HOCRElement("h4", "ocr_par").useBbox())
        self._dict.setdefault("H5", HOCRElement("h5", "ocr_par").useBbox())
        self._dict.setdefault("H6", HOCRElement("h6", "ocr_par").useBbox())
        self._dict.setdefault("Document", HOCRElement().ignore())
        self._dict.setdefault("Part", HOCRElement("div", "ocr_part")) # Part zamieniane na tag <div class="ocr_part">
        self._dict.setdefault("Art", HOCRElement("div", "ocr_chapter").useBbox())
        self._dict.setdefault("Sect", HOCRElement("div", "ocr_*section")) # * jest zamieniana na "", "sub", "subsub" itd. w zaleznosci
            # od poziomu zagniezdzenia
        self._dict.setdefault("Div", HOCRElement("div", "ocr_carea").useBbox())
        self._dict.setdefault("BlockQuote", HOCRElement("blockquote", "ocr_blockquote").useBbox())
        self._dict.setdefault("Code", HOCRElement("code", "ocr_blockquote").useBbox())
        self._dict.setdefault("Span", HOCRElement().ignore()) # TODO: NOTE bbox? czy moze byc bbox jak nie ma ocr...?        

    # do ilu zagniezdzen tagow z $ (patrz metoda powyzej) wypisujemy w capabilities
    NUM_DEPTH = 6
    # j.w. dla *
    SUB_DEPTH = 3

    # zwraca liste mozliwosci (capabilities) do wyswietlenia w naglowku pliku hOCR
    def mappingCapabilities(self):
        capabilities = []
        for (_, v) in self._dict.iteritems():
            capability = v.getClass()
            if v.getClass() == "":
                continue
            # TODO: E dowolne $ i *, definicja zagniezdzen w mapowaniu, mozliwe co innego niz sub
            #print capability, re.search("\*", capability), capability.replace("*", repeat("sub", 1))
            if re.search("\$", capability) != None:
                for i in range(HOCRStandardMapping.NUM_DEPTH):
                    cap = capability.replace("$", str(i + 1))
                    if not cap in capabilities:
                        capabilities.append(cap)
            elif re.search("\*", capability) != None:
                for i in range(HOCRStandardMapping.SUB_DEPTH):
                    cap = capability.replace("*", repeat("sub", i))
                    if not cap in capabilities:
                        capabilities.append(cap)
            else:
                if not capability in capabilities:
                    capabilities.append(capability)
        #print capabilities
        return capabilities

    # zwraca obiekt opisujacy tag HTML i element hOCR odpowiadajacy danemu
    # elementowi drzewa struktury
    # arguments - poziom zagniezdzenia elementow H lub Sect
    def hOCRElement(self, tag, arguments):
        #print "hocrelement: ", self._dict
        try:
            if tag == "H" or tag == "Sect": # uwzgledniamy informacje o zagniezdzeniu
                hocrel = self._dict[tag]
                hocrel.replace("$", str(arguments[0]))
                hocrel.replace("*", repeat("sub", arguments[0] - 1))
                #if hocrel.tag == "h$":
                #    hocrel.tag = "h" + str(arguments[0])
                #elif hocrel.tag == "ocr_$section":
                #    hocrel.tag = "ocr_" + repeat("sub", arguments[0] - 1) + "section"
                return hocrel            
            #elif self._dict[tag] == "implemented":
            #    return self._implementation(tag, arguments)
            else:
                return self._dict[tag]
        except KeyError:
            return None

    #def __onSect(self, arguments):
    #    if arguments[0] == 0:
    #        return HOCRElement("div", "ocr_section")
    #   else:
    #        return HOCRElement("div", "ocr_" + repeat("sub", arguments[0]) + "section")
    
    #def __onH(self, arguments):
    #    return HOCRElement("h" + str(arguments[0]), "ocr_par")
    
    #def _implementation(self, tag, arguments):
    #    if tag == "Sect":
    #        return self.__onSect(arguments)
    #    elif tag == "H":
    #        return self.__onH(arguments)
    
    # metoda sluzy do sprawdzania, czy dana etykieta listy jest etykieta listy
    # uporzadkowanej (jest jesli etykieta ma postac 1., 2., 3. itd.)
    def ordered(self, label):
        if label[0:len(label) - 2].isdigit() and label[-1] == u'.':
            return True
        return False

# modyfikacja klasy HOCRStandardMapping ktora mapuje elementy ukladu stony na
# tagi HTML i elementy hOCR 
class HOCRPDFMinerXMLMapping(HOCRStandardMapping):
    
    def __init__(self, mappingFile):
        self._dict = {}
        if mappingFile != None:
            self._useMappingFromFile(mappingFile, xml=True)
        else: # domyslne mapowanie dla ukladu strony
            #self._dict.setdefault("pages", HOCRElement().ignore()) wykomentowane
                # bo pages jest przetwarzane w inny sposob niz pozostale elementy
            self._dict.setdefault("page", HOCRElement().ignore())
            self._dict.setdefault("textgroup", HOCRElement("div", "ocr_carea").useBbox())
            self._dict.setdefault("textbox", HOCRElement("div", "ocr_carea").useBbox())
            self._dict.setdefault("textline", HOCRElement("span", "ocr_line").useBbox())
            self._dict.setdefault("text", HOCRElement().ignore())
