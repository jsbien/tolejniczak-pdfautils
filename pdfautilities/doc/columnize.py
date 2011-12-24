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
"""

from pdfminerparser import PDFMinerNode
from utils import combine

# jezeli przynajmniej BADNESS_THRESHOLD * 100 % linii nie ma za malo znakow zeby
# podzielic je na zadana liczbe kolumn, to program nie podzieli strony na kolumny
BADNESS_THRESHOLD = 0.1

# odstep miedzy dwoma znakami
class Break:

    def __init__(self, start, end, bbox):
        self.start = start # poczatek odstepu
        self.end = end # koniec odstepu
        self.matching = 0.0 # patrz metoda columnizePageUsingGroups
        self.bbox = bbox # bounding box linii w ktorej lezy odstep # TODO: I gdzie
            # to jest uzywane?

    def __str__(self):
        return "(" + str(self.start) + ", " + str(self.end) + ")"

# klasa implementuje dzielenie stron na kolumny
# znaczenie niektorych algorytmow dokladnie wyjasnione w zalaczonej pracy
class Columnizer:
    # TODO: D rozne algorytmy
    
    def __init__(self):
        self.__divNum = 1 # liczba odstepow miedzy kolumnami (o jeden mniejsza niz
            # liczba kolumn na ktore mamy podzielic strone)
        self.__module = None # modul dowolnego przetwarzania
        self.__pages = [] # lista numerow stron ktorych nie nalezy dzielic na kolumny
        #self.__mode = "SINGLE"
        self.__pageNo = 0 # numer dzielonej strony 
        self.__fatal = False # czy wystapil blad powodujacy przerwanie dzielenia dla
            # wszystkich stron
        self.__error = False # czy wystapil blad dla jednej strony
        self.__messages = [] # komunikaty o bledach
        self.__columnized = [] # lista numerow stron podzielonych na kolumny przez
            # obiekt, jest to wykorzystywane w MainWindow (por. metody __onColumnize
            # i __onColumnizeAll)
    
    def getColumnized(self):
        return self.__columnized
    
    def isFatal(self):
        return self.__fatal
    
    def isError(self):
        return self.__error
    
    def getMessages(self):
        return self.__messages
    
    def getLastMessage(self):
        return self.__messages[len(self.__messages) - 1]
    
    def setModule(self, module):
        self.__module = module
    
    #def setGroupMode(self):
    #    self.__mode = "GROUP"
    
    # ustawia liczbe kolumn na ktore mamy podzielic strony
    def setCols(self, cols):
        self.__divNum = cols - 1
    
    def setPages(self, pages):
        self.__pages = pages
    
    # dzielimy na strony caly dokument
    # tree - cale drzewo ukladu strony
    def columnize(self, tree, cols=2):
        self.__divNum = cols - 1
        self.__pages = None
        #print self.__cols
        pages = tree.getChildren()
        for p in pages:
            self.columnizePageUsingGroups(p) # dzielimy strone na kolumny
            if self.__fatal:
                return tree # bo wtedy wypisujemy komunikat i komus moze byc
                    # potrzebne stare drzewko
        return tree
    
    # czy odstepy na siebie nachodza (wystarczy, zeby sie zetknely krawedziami)
    def __matches(self, a, b):
        if a.start == a.end: # TODO: I sprawdzic czy to cos popsulo i czy moze sie tak
                # zdarzyc
            if not (b.start > a.end or b.end < a.start):
                return True
        if b.start == b.end: # j.w.
            if not (a.start > b.end or a.end < b.start):
                return True
        if a.start <= b.start and a.end >= b.end:
            # a=b b=a 
            return True
        if b.start <= a.start and b.end >= a.end:
            # b=a a=b
            return True
        if a.start <= b.start and a.end > b.start:
            # a=b a b
            return True
        if b.start <= a.start and b.end > a.start:
            # b=a b a
            return True
        if a.start < b.start and a.end >= b.start:
            # a b=a b
            return True
        if b.start < a.start and b.end >= a.start:
            # b a=b a
            return True
        return False
    
    # czesc wspolna dwoch odstepow = stosunek dlugosci ich czesci wspolnej do
    # dlugosci jednego z nich
    def __matchValue(self, a, b):
        if a.start <= b.start and a.end >= b.end:
                # a b b a
                #   xxx
                # yyyyyyy
                # x / y
            if a.start == a.end:
                return 0.0
            return (b.end - b.start) / (a.end - a.start)
        if b.start <= a.start and b.end >= a.end:
                # b a a b
                # xxxxxxx
                #   yyy
                # y / x
            if b.start == b.end:
                return 0.0
            return (a.end - a.start) / (b.end - b.start)
        if b.start <= a.start and b.end > a.start:
                # b a b a
                # xxxxx
                #   zzzyy
                # z / zy
            if a.start == a.end:            	
                return 0.0
            return (b.end - a.start) / (a.end - a.start)
        if a.start <= b.start and a.end > b.start:
                # a b a b
                #   xxxxx
                # yyzzz
                # z / yz
            if a.start == a.end:
                return 0.0
            return (a.end - b.start) / (a.end - a.start)
        return 0.0
    
    # laczymy dwie linie jesli jedna wystepuje bezposrednio po drugiej i jezeli
    # wysokosc jednej jest w calosci zawarta w drugiej lub jezeli czesc wspolna
    # ich wysokosci wynosi ponad 60\% wysokosci pierwszej linii
    # po polaczeniu dwoch linii tak polaczona linie moze byc laczona z kolejnymi
    # liniami jezeli spelnione sa powyzsze warunki
    # linie powinny byc posrtowane od gory do dolu wzgledem gornego kranca bounding
    # boxu przed wywolaniem tej metody
    def __joinLinesCopyWithMap(self, lines):
        map = {} # map nieuzywane
        def __compare(a, b):
            return cmp(a.getBbox()[0], b.getBbox()[0])
        newLines = []
        prev = lines[0].childrenCopy()
        map.setdefault(lines[0], prev)
        for i in range(len(lines) - 1): # TODO: NOTE zakladamy, ze linie w kolejnosci rosacej odleglosci od gory strony (sa sortowane, wiec chyba OK)
            l = lines[i + 1]
            if self.__sameLine(l.getBbox(), prev.getBbox()):
                prev.join(l)
                map.setdefault(l, prev)
            else:
                prev.sortChildren(__compare)
                newLines.append(prev)
                prev = l.childrenCopy()
                map.setdefault(l, prev)
        prev.sortChildren(__compare) # TODO: I gdzie to sie przyda?
        newLines.append(prev)
        return (newLines, map)

    # sklejamy linie
    # dwie linie sklejamy gdy jedna nastepuje bezposrednio po drugiej po
    # (linia powstala ze sklejenia dwoch innych moze byc potem sklejona z nastepna)
    # oraz spelniony jest jeden z warunkow:
    # * wysokosc jednej jest w calosci zawarta w wysokosci drugiej i czesc wspolna
    #   ich wysokosci wynosi ponad 90% wysokosci wyzszej linii
    # * czesc wspolna ich wysokosci wynosi ponad 90% wysokosci kazdej z linii
    # linie powinny byc posortowane od gory do dolu wzgledem gornego kranca bounding
    # boxu przed wywolaniem tej metody
    def __joinLinesCopy(self, lines, par):   
        def __compare(a, b):
            return cmp(a.getBbox()[0], b.getBbox()[0])
        newLines = []
        if len(lines) == 0:
            return lines
        prev = lines[0].childrenCopy()
        for i in range(len(lines) - 1): # TODO: NOTE zakladamy, ze linie w kolejnosci rosacej odleglosci od gory strony (sa sortowane, wiec chyba OK)
            l = lines[i + 1]
            #if l.getBbox() == None:
            #    print l.getStandardText()
            #    print l.getTextContent()
            #    print len(l.getChildren())
            if self.__sameLine(l.getBbox(), prev.getBbox(), par=par, special=True):
                prev.join(l)
            else:
                prev.sortChildren(__compare)
                newLines.append(prev)
                prev = l.childrenCopy()
        prev.sortChildren(__compare)
        newLines.append(prev)
        return newLines
    
    # dzieli linie na trzy grupy (pozwala to lepiej obsluzyc dokumenty gdzie
    # kolumny sa nieco pochyle), dzielac strone w poprzek na trzy rowne czesci:
    # +------------+
    # |            |
    # |  grupa 0   |
    # +------------+
    # |            |
    # |  grupa 1   |
    # +------------+
    # |            |
    # |  grupa 2   |
    # +------------+
    # zwraca: 
    # (wysokosci ciecia strony w poprzek, lista na ktorej znajduja sie listy linii
    # w poszczegolnych grupach)
    def __createGroups(self, lines):
        # TODO: D zmienna liczba grup
        max = 0.0
        min = Columnizer.INF
        for l in lines:
            if l.getBbox()[1] > max:
                max = l.getBbox()[1]
            if l.getBbox()[3] < min:
                min = l.getBbox()[3]
        diff = max - min
        gData1 = min + diff / 3.0
        gData2 = min + 2 * (diff / 3.0)
        gr0 = []
        gr1 = []
        gr2 = []
        for l in lines:
            if l.getBbox()[1] > gData2:
                gr2.append(l)
            elif l.getBbox()[1] > gData1:
                gr1.append(l)
            else:
                gr0.append(l)
        return ((gData1, gData2), [gr0, gr1, gr2])
    
    # wlasciwy algorytm dzielenia strony na kolumny
    def columnizePageUsingGroups(self, page):
        #def __checkLine(line):
        #    assert(line.getBbox() != None)
        self.__pageNo += 1 # numer aktualnie przetwarzanej strony
        if self.__pages != None and (self.__pageNo in self.__pages):
                # ta strone mamy zignorowac 
            return page
        oldChildren = page.getChildren() # zapamietujemy dzieci (przyda nam sie
            # jak wyskoczy blad i chcemy bedzieli przywrocic stan oryginalny)
        lines = page.findLines() # znajdujemy wszystkie elementy "textline"
            # (poniewaz to sa wyniki analizu ukladu strony pdfminera to to nie sa
            # zwykle pelne linie tylko ich kawalki) 
        if (len(lines) == 0):
            #return None
            return page # TODO: I no bo co innego mozemy zrobic?
        #else:
        #    def __check(node, level):
        #        if node.getBbox() == None:
        #            print node.getStandardText()
        #        assert (node.getBbox() != None)
        #    for l in lines:
        #        l.recursivelyProcess(__check)
        def __compare(a, b):
            return cmp(Columnizer.INF - a.getBbox()[3], Columnizer.INF - b.getBbox()[3])
        lines.sort(__compare) # sortowanie linii od gory strony w dol po gornym brzegu
            # bounding boxa
        linesOld = lines # oryginalne linie z pdfminera
        (lines, map) = self.__joinLinesCopyWithMap(lines) # laczymy linie z jednego
            # wiersza:
            # [aaaaaaa] [bbbbbbbb]  \   [aaaaaaa   bbbbbbb]
            # [ccccccc] [dddddddd]  /   [ccccccc   ddddddd]
            # jezeli w roznych kolumnach wiersze sa na roznych wysokosciach ale
            # ich wysokosci zachodza na siebie w wystarczajaco duzym stopniu to moga
            # nam sie skleic na przyklad w bloki po kilka linii:
            # | /\  /\ |                  |                        |
            # |/--\/--\|  | /\  /\ |   \  | /\  /\  /\  /\  /\  /\ |
            # | /\  /\ |  |/--\/--\|   /  |/--\/--\/--\/--\/--\/--\|
            # |/--\/--\|                  |                        |
            # map - nieuzywane
            # ta metoda sortuje tez znaki w obrebie linii po poczatku bounding boxa
        (groupData, lineGroups) = self.__createGroups(lines) # dzielimy linie na
            # trzy grupy (pozwala to lepiej obsluzyc dokumenty gdzie kolumny sa
            # nieco pochyle), dzielac strone w poprzek na trzy rowne czesci
            # groupData - wysokosci ciecia strony w poprzek
            # lineGroups - lista na ktorej znajduja sie listy linii w poszczegolnych
            # grupach 
        breakGroups = [] # lista list wszystkich odstepow miedzy znakami w
            # poszczegolnych grupach
        for _ in lineGroups:
            breakGroups.append([])
        #breakGroups.append([])
        total = 0 # liczba przetworzonych linii
        bad = 0 # liczba przetworzonych linii w ktorych jest za malo znakow zeby
            # podzielic je na zadana liczbe kolumn
        i = -1 # indeks aktualnie przetwarzanej grupy
        for lines in lineGroups: # dla kazdej grupy:
            i += 1
            for line in lines: # dla kazdej linii z grupy:
                total += 1
                right = -1.0 # prawy brzeg bounding boxa ostatnio przetwarzanego
                    # znaku
                maxes = [] # na ta zmienna zapisujemy znalezione __divNum
                    # najwiekszych odstepow
                #print "----------------"
                #print "----------------"                
                for text in line.getChildren(): # dla kazdego znaku w linii:
                    if text.getBbox()[0] >= text.getBbox()[2]:
                        # pisane od prawej do lewej?
                        # TODO: I czy jestesmy w stanie obsluzyc znaki gdy poczatek bounding boxu jest rowny koncowi?
                        self.__error = True
                        self.__messages.append("Page " + str(self.__pageNo) + " cannot be processed: non-positive character length")
                        return None
                    #if text.getBbox() == None:
                    # TODO: NOTE nie powinno wystapic
                    #    continue
                    assert(text.getText() == "text")
                    left = text.getBbox()[0] # lewy brzeg bounding boxa aktualnie
                        # przetwarzanego znaku
                    if right < 0.0: # pierwszy znak
                        diff = -1.0 # moze sie oczywiscie zdarzyc, ze znaki beda na
                            # siebie zachodzic i diff moze byc mniejszy od tego
                            # wartownika, ale nas interesuja tylko znaki miedzy
                            # ktorymi jest odstep (czyli diff > 0)
                    else:
                        diff = left - right # odstep miedzy aktualnie przetwarzanym
                            # znakiem a ostatnio przetwarzanym
                    #content = ""
                    #for t in text.getChildren():
                    #    if isinstance(t, unicode):
                    #        content += t.encode("utf-8")
                    #print t, left, right, diff
                    if len(maxes) < self.__divNum: # mamy mniej odstepow niz potrzeba
                            # do podzielenia na kolumny
                        if right < 0.0: # pierwszy znak, wstawiamy na liste odstep
                                # zaslepke mniejsza od wszystkich odstepow
                                # TODO: I to zadziala dobrze, jak wszystkie znaki
                                # sa w kolejnosci (mozna ewentualnie sortowac)
                            maxes.append(Break(0.0, -1.0, line.getBbox()))
                            #print 0.0, -1.0
                        else:
                            # dodajemy odstep do listy odstepow
                            maxes.append(Break(right, left, line.getBbox()))
                            #print "-", right, left
                    else: # mamy juz dobra ilosc odstepow, ale patrzymy, czy znaleziony
                            # przez naz nie jest od ktoregos z nich wiekszy
                        def __compare1(a, b):
                            return cmp(a.end - a.start, b.end - b.start)
                        maxes.sort(__compare1) # sortujemy odstepy rosnaco
                        minMax = maxes[0]
                        #print maxes.index(minMax)
                        #print t, right, left, diff, minMax
                        if diff > minMax.end - minMax.start: # jesli znaleziony odstep jest
                                # od niego wiekszy...
                            #print "ok"
                            #if right < 0.0:
                            #    #maxes[maxes.index(minMax)] = Break(0.0, -1.0, line.getBbox())
                            #    maxes = [Break(0.0, -1.0, line.getBbox())] + maxes[1:]
                            #else:
                            if True:
                                k = Break(right, left, line.getBbox())
                                #print ":", right, left
                                #print k
                                maxes = [k] + maxes[1:] # ... to podmieniamy je
                                #print "ok2"
                                #i = maxes.index(minMax)
                                #maxes[i] = Break(right, left, line.getBbox())
                                #print i, maxes[i], right, left
                                #for m in maxes:
                                #    print m
                    right = text.getBbox()[2] # uaktualniamy prawy brzeg ostatnio przetwarzanego
                        # znaku (bo teraz staje sie nim znak aktualny)
                if maxes[0].end == -1.0: # to znaczy, ze zaslepka zostala na liscie
                        # znalezionych odstepow - usuwamy ja (skracajac jednoczesnie
                        # liste odstepow)
                    maxes = maxes[1:]
                if len(maxes) < self.__divNum: # mamy za malo odstepow (bo bylo za
                        # malo znakow)
                    bad += 1 # zwiekszamy liczbe linii dla ktorych jest za malo
                        # odstepow
                for m in maxes:
                    if m.end - m.start < 0.0: # z jakiegos powodu na liscie wybranych odstepow
                            # pozostal odstep-zaslepka (czyli w zasadzie mamy za malo odstepow)
                        self.__error = True
                        self.__messages.append("Page " + str(self.__pageNo) + " cannot be processed: to few breaks")
                        return None
                breakGroups[i].append(maxes)
        #print bad, total
        #print bad / total
        if bad / total > BADNESS_THRESHOLD: # za duzo linii nie udalo sie przetworzyc,
                # niestety strony nie udalo sie podzielic
            self.__error = True
            self.__messages.append("Page " + str(self.__pageNo) + " cannot be divided into " + str(self.__divNum + 1) + " columns")
            return None
        i = -1
        for breaks in breakGroups: # dla kazdej grupy:
            for maxes in breaks: # dla kazdej linii maxes == breaks[i] w grupie:
                i += 1
                for max in maxes: # dla kazdego odstepu w linii maxes:
                    #print max
                    j = -1
                    for line in breaks: # dla kazdej linii line == breaks[j]
                        j += 1          # w grupie, takiej, ze i != j:
                        if i != j:      #
                            for lmax in line: # dla kazdego odstepu w linii line:
                                #print max, lmax
                                max.matching += self.__matchValue(max, lmax)
                                    # obliczamy wartosc ktora intuicyjnie mowi nam
                                    # jak bardzo ten odstep pasuje do odstepow w
                                    # innych liniach potencjalnie tworzac odstep
                                    # dzielacy strone na kolumny
        columnDivGroups = [] # lista list odstepow wybranych do dzielenia na kolumny
            # w poszczegolnych grupach
        for _ in lineGroups:
            columnDivGroups.append([])
        #columnDivGroups.append([])
        i = -1
        for columnDivs in columnDivGroups: # dla kazdej grupy:
            i += 1 # indeks grupy
            breaks = breakGroups[i] # linie dla grupy i
            while len(columnDivs) < self.__divNum: # dopoki mamy za malo odstepow
                    # by podzielic dana grupe na kolumny
                max = Break(0.0, 0.0, [0.0, 0.0, 0.0, 0.0]) # odstep maksymalny (ale patrz komentarz (***)
                max.matching = -1.0                         # ponizej, inicjalizowany na wartownika
                for line in breaks: # dla kazdej linii w grupie i:
                    for div in line: # dla kazdego odstepu w linii:
                        #print max, div
                        ok = True
                        for colDiv in columnDivs: # sprawdzamy czy odstep nie
                                # zachodzi na zaden z juz dodanych do columnDivs
                            if self.__matches(div, colDiv): # TODO: NOTE zapewnia,
                                    # ze nie bedzie dwoch takich samych divow (bo
                                    # one z definicji na siebie zachodza
                                #print "!", colDiv
                                ok = False
                                break
                        #print ok, div.matching, max.matching
                        if ok: # jezeli nie to patrzymy czy aktualnie rozpatrywany
                                # odstep jest wiekszy od dotychczas najwiekszego
                                # i w tej sytuacji ukatualniamy zmienna max 
                            if div.matching > max.matching:
                                #print "zmien!"
                                max = div
                                #print "max: ", max
                #print "--------------"
                columnDivs.append(max) # dodajemy znaleziony odstep maksymalny 
                #print len(columnDivs)
                #print "appended", max, len(columnDivs)
            # TODO: I caly ponizszy komentarz - sprawa jest do zbadania: jezeli to jest wlaczone
            # to nie dzieli na kolumny drugiej strony Probki2.pdf
            #for columnDivs in columnDivGroups:
            #    for div in columnDivs:
            #        if div.start == div.end and div.end == 0.0 and div.matching == -1.0 and div.bbox == [0.0, 0.0, 0.0, 0.0]:
            #                # to znaczy, ze do listy zostal dodany wartownik, czyli znalezlismy za
            #                # malo odstepow 
            #            self.__error = True
            #            self.__messages.append("Page " + str(self.__pageNo) + " cannot be processed: to few maximal breaks")
            #            return None
            def __compare2(a, b):
                return cmp(a.start, b.start)
            columnDivs.sort(__compare2) # sortujemy odstepy w kolejnosci od lewej
                # do prawej
        #print ":::"
        #for columnDivs in columnDivGroups:
        #    for div in columnDivs:
        #        print div
        page.setChildren([]) # usuwamy dzieci strony (potem dodamy nowe)
        def __previous(line): # nieuzywane
            fullLine = map.get(line)
            res = []
            for l in lines:
                if l == fullLine:
                    return res
                res.append(l)
            return res
        def __next(line): # nieuzywane
            fullLine = map.get(line)
            res = []
            ign = True
            for l in lines:
                if l == fullLine:
                    ign = False
                if not ign:
                    res.append(l)
            return res
        #print linesOld, groupData, columnDivGroups, page.getPageId()
        for l in linesOld:
            def __compareChars(a, b):
                return cmp(a.getBbox()[0], b.getBbox()[0])
            l.sortChildren(__compareChars)
        textgroups = self.__fillColumnsUsingGroupsAndLines(linesOld, groupData, columnDivGroups, page.getPageId(), __previous, __next)
            # dzielimy linie na kolumny
        for group in textgroups: # dla kazdej kolumny:
            #print ":", group.getTextContent(), ":"
            group.getChildren().sort(__compare) # sortujemy linie rosnaco z gory
                # na dol wzgledem gornych brzegow bounding boxow
            group.setChildren(self.__joinLinesCopy(group.getChildren(), 0.6))
                # sklejamy linie lezace w tym samym wierszu, ale w przeciwienstwie do
                # __joinLinesCopyWithMap nie laczymy linii w ten sposob:
                # | /\  /\ |                  |                        |
                # |/--\/--\|  | /\  /\ |   \  | /\  /\  /\  /\  /\  /\ |
                # | /\  /\ |  |/--\/--\|   /  |/--\/--\/--\/--\/--\/--\|
                # |/--\/--\|                  |                        |
                # ta metoda sortuje tez znaki w obrebie linii po poczatku bounding boxa
            page.add(group)
        i = -1
        #for columnDivs in columnDivGroups:
        #    i += 1
        #    for div in columnDivs: # TODO: D jako opcja, i zeby nie zapisywal do hocr
        #       divNode = PDFMinerNode("textbox")
        #       if i == 0:
        #            divNode.setBbox([div.start, 0.0, div.end, groupData[0]])
        #        elif i == 1:
        #            divNode.setBbox([div.start, groupData[0], div.end, groupData[1]])
        #        else:
        #            divNode.setBbox([div.start, groupData[1], div.end, 750.0])
        #        page.add(divNode)
        #for l in lines:
        #    page.add(l)
        #import pagina
        #pagina.customProcessing(page)
        self.__demultiplize(page) # poniewaz pdfminer powiela czasem linie (np.
            # sa 3 razy linie z tekstem "napis", w takim przypadku po wykonaniu
            # wczesniejszych operacji w tym momencie mamy jedna linie postaci:
            # "nnnaaapppiiisss") to ta operacja usuwa niektore z nich
        if self.__module != None:
            try:
                self.__module.customProcessing(page)
            except Exception, e:
                page.setChildren(oldChildren)
                self.__fatal = True
                self.__error = True
                self.__messages.append("Error in module: " + str(e))
                return None
        self.__columnized.append(self.__pageNo) # dodajemy numer strony do
            # listy stron podzielonych na kolumny
        #page.setChildren([])
        #for g in lineGroups:
        #    for l in g:
        #        page.add(l)
        return page
    
    # poniewaz pdfminer powiela czasem linie (np.
    # sa 3 razy linie z tekstem "napis", w takim przypadku po wykonaniu
    # wczesniejszych operacji w tym momencie mamy jedna linie postaci:
    # "nnnaaapppiiisss") to ta operacja usuwa niektore* z nich
    # * tylko niektore bo trzeba jeszcze:
    # TODO: D poprawic (dodac ignorowanie bialych znakow - linie "napis", "napis "
    # i "napis" ktore sie skleja w "nnnaaapppiiisss  " w tej chwili sie nie
    # poprawia, bo przy wywolaniu z mults = 3 spacje sa tylko dwie)
    # mults - zwielokrotnienie, jezeli metode wywolano z mults == 3 to metoda
    # poprawia tylko slowa postaci "nnnnaaapppiiisss", jesli z mults == 2 to
    # "nnaappiiss" itd.
    def __demultiplizeLine(self, line, mults):        
        #print line.textContent(), mults
        seqs = []
        for _ in range(mults):
            seqs.append([])
        i = -1
        for c in line.getChildren():
            i += 1
            assert(isinstance(c, PDFMinerNode))
            assert(c.getStandardText() == "text")
            #if not c.noBbox():
            ind = i % mults
            seqs[ind].append(c)
        prevLen = None
        for seq in seqs:
            if len(seq) != prevLen and prevLen != None:
                #print "LEN"
                return
            prevLen = len(seq)
        for i in range(prevLen):
            prevChar = None
            for seq in seqs:
                text = seq[i]
                for c in text.getChildren():
                    if isinstance(c, unicode):
                        if c != prevChar and prevChar != None:
                            #print "CHAR" + "[" + prevChar + "] [" + c + "]"
                            return
                        prevChar = c
                        break
        line.setChildren([])
        for text in seqs[0]:
            line.getChildren().append(text)
    
    # przechodzimy po wszystkich liniach by wykonac operacje __demultiplizeLine
    # dla roznych zwielokrotnien (od 21 do 2)
    def __demultiplize(self, node):
        # TODO: D dziala tylko dla idealnie zwielokrotnionych
        if isinstance(node, PDFMinerNode):
            if node.getStandardText() == "textline":
                for i in range(20):
                    #self.__demultiplizeLine(node, 4)
                    #self.__demultiplizeLine(node, 2)
                    self.__demultiplizeLine(node, 21 - i)
            else:
                for c in node.getChildren():
                    self.__demultiplize(c)
    
    # sprawdza czy linia line jest przed odstepem div
    # jesli zwracamy False to znaczy, ze linia jest za odstepem
    # jesli zwracamy None to znaczy, ze nie jestesmy w stanie ustalic czy linia jest
    # przed czy za odstepem (lezy na odstepie)
    # uwazamy ze linia jest przed odstepem jesli:
    # * zaczyna sie przed i konczy co najwyzej na koncu odstepu
    # uwazamy ze linia jest za odstepem jesli:
    # * zaczyna sie co najmniej na poczatku odstepu
    def __lineBefore(self, line, div):
        if line.getBbox()[0] >= div.start:
            return False
        elif line.getBbox()[2] <= div.end: # TODO: NOTE < zamiast <= ?
            return True
        else:
            return None
    
    # dzieli linie na kolumny
    def __fillColumnsUsingGroupsAndLines(self, lines, (gData1, gData2), columnDivGroups, pageid, prev, next):
        textgroups = [] # lista kolumn
        for _ in range(self.__divNum + 1): # tworzymy puste kolumny
            group = PDFMinerNode("textbox")
            group.setPageId(pageid)
            textgroups.append(group)
        j = 0
        for l in lines: # dla kazdej linii (oryginalnej z pdfminera):
            j += 1
            newLines = []
            if l.getBbox()[1] > gData2: # patrzymy do ktorej grupy nalezy linia
                columnDivs = columnDivGroups[2] # odstepy dla znalezionej grupy 
            elif l.getBbox()[1] > gData1:
                columnDivs = columnDivGroups[1] # j.w.
            else:
                columnDivs = columnDivGroups[0] # j.w.
            found = None
            for i in range(self.__divNum + 1): # dla kazdego odstepu patrzymy czy linia jest
                    # przed odstepem - jezeli tak to znalezlismy kolumne, jezeli nie jest przed
                    # zadnym odstepem tzn. ze jest w ostatniej kolumnie, jezei zaszla sytuacja
                    # (**) to nie jestesmy w stanie stwierdzic do ktorej kolumny nalezy
                    # linia i musimy ja podzielic znak po znaku
                try:
                    before = self.__lineBefore(l, columnDivs[i])
                except IndexError:
                    found = i # linia po i-1 odstepie, ktory jest ostatnim (i-ta kolumna)
                    break
                if before == None: # (**) nie jestesmy w stanie ustalic, czy linia jest
                        # przed czy po odstepie i musimy dzielic miedzy kolumny
                        # poszczegolne znaki
                    break
                if before: # linia przed i-tym odstepem (i-ta kolumna)
                    found = i
                    break
            if found != None: # ok, znalezlismy kolumne do ktorej nalezy linia,
                    # dodajemy ja do kolumny
                assert(l.getPageId() != None)
                textgroups[i].add(l)
                #print "TUTAJ:", l.getBbox(), textgroups[i].getBbox()
                textgroups[i].setBbox(combine(textgroups[i].getBbox(), l.getBbox()))
                continue
            # jezeli jestesmy tutaj to wystapila sytuacja (**) powyzej
            for _ in range(self.__divNum + 1):
                line = PDFMinerNode("textline") # tworzymy linie dla kazdej kolumny,
                    # bedziemy do nich przydzielac znaki
                line.setPageId(pageid)
                newLines.append(line)
            for text in l.getChildren(): # dla kazdego znaku:
                if text.getBbox() == None:#[0.0, 0.0, 0.0, 0.0]:
                    continue
                i = 0 # indeks kolumny
                for div in columnDivs:
                    if self.__before(text, div, l, prev, next): # jezeli znak jest
                            # przed i-tym odstepem to jest w i-tej kolumnie
                        break
                    i += 1
                #if j < 3:
                #    print i, text.getBbox(), div, text.__children[0]
                newLines[i].add(text) # dodajemy znak do utworzonej wczesniej linii
                    # dla i-tej kolumny 
                newLines[i].setBbox(combine(newLines[i].getBbox(), text.getBbox()))
            for i in range(self.__divNum + 1): # dodajemy do kolumn te z nowo utworzonych
                    # linii ktore nie sa puste (tzn. sa w nich jakies znaki)
                if newLines[i].getBbox() != None:#[0.0, 0.0, 0.0, 0.0]:
                    textgroups[i].add(newLines[i])
                    textgroups[i].setBbox(combine(textgroups[i].getBbox(), newLines[i].getBbox()))
        return textgroups
    
    # Sprawdza, czy znak jest przed odstepem.
    # Uwazamy, ze znak jest przed odstepem, jezeli:
    # * Znak konczy sie co najwyzej na poczatku odstepu.
    # * Znak zaczyna sie co najwyzej na poczatkku odstepu i konczy przed koncem
    #   odstepu.
    # * Jezeli znak zaczyna sie wewnatrz odstepu i konczy wewnatrz odstepu to zeby
    #   ustalic, czy znak jest przed odstepem stosujemy nastepujacy algorytm:
    #   * Obliczamy wartosc affinityBefore oznaczajaca najwiekszy odstep miedzy
    #     dwoma znakami w ciagu kolejnych znakow w ktorym ostatni to dany znak a
    #     pierwszy to pierwszy znak idac w lewo od danego znaku ktory zaczyna sie
    #     przed poczatkiem odstepu (oznaczmy go X).
    #   * Obliczamy wartosc affinityAfter oznaczajaca najwiekszy odstep miedzy dwoma
    #     znakami w ciagu kolejnych znakow w ktorym pierwszy to dany znak a ostatni
    #     to pierwszy znak idac w prawo od danego znaku ktory konczy sie po koncu
    #     odstepu (oznaczmy go Y).
    #   * Jezeli nie ma znaku Y to znaczy, ze znak jest przed odstepem.
    #   * W przeciwnym przypadku jezeli nie ma znaku $X$ to znaczy, ze znak nie jest
    #     przed odstepem.
    #   * W przeciwnym przypadku jezeli wartosc affinityBefore jest mniejsza niz
    #     0.1 to znaczy, ze znak jest przed odstepem.
    #   * Jezeli natomiast wartosc affinityAfter jest rozna od zera a stosunek
    #     affinityBefore do affinityAfter wynosi mniej niz 0.25 to takze znak jest
    #     przed odstepem.
    #   * Jezeli zaden z powyzszych warunkow nie zostal spelniony, to znaczy, ze
    #     znak jest za odstepem.
    #   * Znaki nastepne i poprzednie pobieramy tylko z oryginalnej linii w ktorej
    #     znajduje sie znak.
    def __before(self, text, div, line, prev, next): # TODO: D rozne tryby (ten AlignRight) tez patrz na sasiednie znaki
        start = text.getBbox()[0]
        end = text.getBbox()[2]
        if end <= div.start:
            return True
        if start <= div.start and end < div.end:
            return True
        else:
            #if self.__module != None:
            #    if start < div.end:
            #        after = self.__affinityAfter(text, div, line)
            #       before = self.__affinityBefore(text, div, line)
            #        #print text
            #        if after == 10000.00: # TODO: stala
            #            return True
            #        if before == 0.0:
            #            return False
            #        res = self.__module.before(text, div, line, after, before, self.__nearestBefore, self.__nearestAfter, prev, next)
            #        if res != None:
            #            return res
            #    else:
            #        return False
            if start < div.end and end < div.end: # TODO: NOTE zazebiajace sie z nastepna kolumna przechodza do niej automatycznie
                after = self.__affinityAfter(text, div, line)
                before = self.__affinityBefore(text, div, line)
                if after == Columnizer.EMPTY_AFFINITY:
                    return True
                if before == Columnizer.EMPTY_AFFINITY: #0:
                    return False
                #print after, before
                # TODO: I trzeba byc moze zmodyfikowac, bo jezeli zarowno after i
                # before sa ujemne, to wraz z maleniem after wspolczynnik before/after
                # maleje zamiast rosnac
                if (after != 0 and before / after < 0.25) or before < 0.1:
                    return True
            return False
    
    INF = 1000000.0
    EMPTY_AFFINITY = INF

    # wartosc oznaczajaca najwiekszy odstep miedzy dwoma znakami w ciagu kolejnych
    # znakow w ktorym pierwszy to dany znak a ostatni to pierwszy znak idac w prawo
    # od danego znaku ktory konczy sie po koncu odstepu
    # -->
    def __affinityAfter(self, text, div, line):
        near = text
        res = 0.0
        i = 0
        while True: # TODO: NOTE czy to sie zapetli? (chyba nie, bo bbox[0] rosnie)
            i += 1
            (aff, near) = self.__nearestAfter(near, line)
            if near == None:
                return Columnizer.EMPTY_AFFINITY
            res = max(aff, res)
            if near.getBbox()[2] > div.end:
                return res
            assert(i < 2000000)
   
    # najblizszy znak za text,
    # min - odleglosc (roznica miedzy kocem jednego a poczatkiem drugiego)
    # TODO: I tu tez zalozenie o dobrej kolejnosci znakow ...
    def __nearestAfter(self, text, line):
        min = Columnizer.INF
        minText = None
        for t in line.getChildren():
            if t.getBbox()[0] > text.getBbox()[0]:
                if t.getBbox() != text.getBbox():
                    diff = t.getBbox()[0] - text.getBbox()[2]
                    if diff < min:
                        min = diff
                        minText = t
        return (min, minText)
    
    # wartosc oznaczajaca najwiekszy odstrp miedzy dwoma znakami w ciagu kolejnych znakow
    # w ktorym ostatni to dany znak a pierwszy to pierwszy znak idac w lewo od
    # danego znaku ktory zaczyna sie przed poczatkiem odstepu
    # <--
    def __affinityBefore(self, text, div, line):
        near = text
        res = 0.0
        i = 0
        while True: # TODO: NOTE czy to sie zapietli? (chyba nie, bo bbox[2] caly
                # czas maleje)
            i += 1
            (aff, near) = self.__nearestBefore(near, line)
            if near == None:
                return Columnizer.EMPTY_AFFINITY 
            res = max(aff, res)
            if near.getBbox()[0] < div.start:
                return res
            assert(i < 2000000)
        return res
    
    # najblizszy znak przed text,
    # min - odleglosc (roznica miedzy kocem jednego a poczatkiem drugiego)
    # TODO: I tu tez zalozenie o dobrej kolejnosci znakow ...
    def __nearestBefore(self, text, line):
        min = Columnizer.INF
        minText = None
        for t in line.getChildren():
            if t.getBbox()[2] < text.getBbox()[2]:
                if t.getBbox() != text.getBbox():
                    diff = text.getBbox()[0] - t.getBbox()[2]
                    if diff < min:
                        min = diff
                        minText = t
        return (min, minText)
    
    # sprawdza, czy linie o podanych bounding boxach powinny byc sklejone przez
    # __joinLinesCopyWithMap i __joinLinesCopy
    # jezeli special == False:
    # zwracamy True jesli jeden z warunkow jest spelniony:
    # * wysokosc jednej z linii jest w calosci zawarta w drugiej
    # * czesc wspolna ich wysokosci wynosi ponad par * 100% wysokosci pierwszej linii
    # wpp zwracamy False
    # jezeli special == True:
    # zwracamy True jesli jeden z warunkow jest spelniony:
    # * wysokosc jednej z linii jest w calosci zawarta w wysokosci drugiej i czesc
    #   wspolna ich wysokosci wynosi ponad par * 100% wysokosci wyzszej linii
    # * czesc wspolna ich wysokosci wynosi ponad par * 100% wysokosci kazdej z linii
    # wpp zwracamy False
    # TODO: D par jako parametr (i par dla special tez jako parametr)
    def __sameLine(self, bbox1, bbox2, par=0.6, special=False):
        #atop = 2000.0 - bbox1[3]
        #btop = 2000.0 - bbox2[3]
        #adown = 2000.0 - bbox1[1]
        #bdown = 2000.0 - bbox2[1]
        atop = Columnizer.INF - bbox1[3]
        btop = Columnizer.INF - bbox2[3]
        adown = Columnizer.INF - bbox1[1]
        bdown = Columnizer.INF - bbox2[1]
        if atop <= btop and adown >= bdown:
            # a=b b=a
            #   xxx
            # yyyyyyy
            if not special:
                return True
            else:
                #return True
                # x / y > par 
                return (bdown - btop) / (adown - atop) > par 
        if btop <= atop and bdown >= adown:
            # b=a a=b
            #   yyy
            # xxxxxxx
            if not special:
                return True
            else:
                #return True
                # y / x > par
                return (adown - atop) / (bdown - btop) > par
        if btop <= atop and bdown > atop: # at least 60%
            # b=a b a
            #   zzzyy
            # xxxxx 
            ran = (bdown - atop) / (adown - atop)
            ran2 = (bdown - atop) / (bdown - btop)
            #print bbox1, bbox2, ran
            # z / zy > par
            # special: zy / x > par
            if ran > par and ((not special) or ran2 > par):
                return True
            else:
                return False
        if bdown >= adown and btop < adown: # at least 60 %
            # a b a=b
            # yyzzz
            #   xxxxx
            ran = (adown - btop) / (adown - atop)
            ran2 = (adown - btop) / (bdown - btop)
            #print bbox1, bbox2, ran
            #  z / yz > par
            # special: z / x > par
            if ran > par and ((not special) or ran2 > par):
                return True
            else:
                return False
        return False
