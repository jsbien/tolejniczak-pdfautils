"""
Copyright (c) 2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>

    This file is part of PDFAUtilites.

    PDFAUtilites are free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PDFAUtilities are distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PDFAUtilities.  If not, see <http://www.gnu.org/licenses/>.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from pdfminer.pdftypes import num_value, dict_value, list_value
from pdfminer.pdfparser import literal_name
from pdfminer.cmapdb import CMapParser, FileUnicodeMap
from fontTools import ttLib
#from fontTools import xmlWriter
from ttFontMod import TTFontMod
from imagextract import getWxImage
from exif import extractExif
from pdfminermod import list_value2, str_value_none, dict_value_none, num_value_none, stream_value_none, dict_value2, literal_name_none
from utils import uniToString
from dialogs import ColourSpaceDialog
from taglib import Font
import wx
import ImageFile

# klasa implementuje kontrolke pokazujaca obrazek
class ImagePanel(wx.ScrolledWindow):

    SCALE_FACTOR = 2.0

    def __init__(self, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, *args, **kwargs)
        self.__bmp = None # pokazywany obrazek
        self.__scale = 1 # skala obrazka (ile razy powiekszamy obrazek)
        self.__w = 0 # rozmiary obrazka
        self.__h = 0
        self.Bind(wx.EVT_PAINT, self.__onPaint)
        self.Bind(wx.EVT_MOUSEWHEEL, self.__onWheel)
    
    def setDimensions(self, width, height):
        self.__w = width
        self.__h = height
    
    # przygotowanie do wczytania nowego pliku
    def restart(self):
        self.__bmp = None
    
    # ustawienie obrazka ktory bedzie pokazywany
    def setBMP(self, bmp):
        self.__bmp = bmp
        self.__scale = 1
    
    def getBMP(self):
        return self.__bmp

    # wlasciwe rysowanie obrazka
    def __onPaint(self, event):
        #print "draw"
        (x, y) = self.CalcScrolledPosition(0, 0) # gdzie jest teraz (0, 0) - obrazek
            # jest scrollowany wiec moze sie zmieniac
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.SetUserScale(self.__scale, self.__scale) # skalujemy obrazek
        x /= self.__scale # skalujemy (0, 0)
        y /= self.__scale
        if self.__bmp != None:
            dc.DrawBitmap(self.__bmp, x, y, True) # rysujemy obrazek w punkcie (0, 0)
    
    # zmniejszamy lub powiekszamy obrazek
    def __onWheel(self, event):
        if self.__bmp == None:
            return
        #print self.GetScrollRange(wx.VERTICAL), self.GetScrollRange(wx.HORIZONTAL)
        if event.m_wheelRotation > 0:
            if self.__scale <= 4.0: 
                self.__scale *= ImagePanel.SCALE_FACTOR            
                #self.SetScrollbars(20, 20, self.GetScrollRange(wx.HORIZONTAL) * 1.5, self.GetScrollRange(wx.VERTICAL) * 1.5, 0, 0, True)
                self.SetScrollbars(20, 20, self.__w * ImagePanel.SCALE_FACTOR, self.__h * ImagePanel.SCALE_FACTOR, 0, 0, True)
                self.__w *= ImagePanel.SCALE_FACTOR
                self.__h *= ImagePanel.SCALE_FACTOR
                self.__onPaint(None)
        else:
            if self.__scale >= 0.25:
                self.__scale /= ImagePanel.SCALE_FACTOR
                #self.SetScrollbars(20, 20, self.GetScrollRange(wx.HORIZONTAL) / 1.5, self.GetScrollRange(wx.VERTICAL) / 1.5, 0, 0, True)
                self.SetScrollbars(20, 20, self.__w / ImagePanel.SCALE_FACTOR, self.__h / ImagePanel.SCALE_FACTOR, 0, 0, True)
                self.__w /= ImagePanel.SCALE_FACTOR
                self.__h /= ImagePanel.SCALE_FACTOR
                self.__onPaint(None)

# klasa implementuje kontrolke pokazujaca zawartosc slownika zasobow strony 
class PhysList(wx.ListCtrl):
    
    def __init__(self, *args, **kwargs):
        wx.ListCtrl.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.__onClick)
        self.__textCtrl = None # kontrolka w ktorej wyswietlamy tekst z informacjami
            # o pokazywanym obrazku lub foncie
        self.__root = None # obiekt PTree ze slownikami zasobow stron (patrz TagLib i
            # XMLLib) - nazwa jest pozostaloscia z czasow gdy ta kontrolka byla drzewem
        self.__frame = None # glowne okno aplikacji (MainWindow) 
        self.__path = None # sciezka do wczytanego pliku PDF, potrzebna do wyciagniecia
            # obrazka z pliku
        self.__colorSpace = None # przestrzen kolorow ktora chcemy pokazac w osobnym
            # oknie dialogowym (patrz onURL, slownik przestrzeni koloru)
        self.__encoding = None # kodowanie znakow ktore chcemy pokazac w osobnym
            # oknie dialogowym (patrz onURL, slownik kodowania PDF)
        self.__urlMode = "Image" # jezeli ma wartosc Image to znaczy, ze w oknie
            # __textCtrl pokazujemy informacje o obrazku i link w nim prowadzi do
            # przestrzeni kolorow, wpp pokazujemy informacje o foncie i link
            # prowadzi do kodowania
        self.__nodes = [] # lista wezlow obiektu PTree z fontami i obrazkami, indeks
            # na tej liscie jest jednoczesnie informacja przechowywana w itemach
            # wxWidgets bedacych elementami tej kontrolki (patrz metoda show)
    
    # przygotowujemy sie do wczytania nowego pliku
    def restart(self):
        self.__root = None
        self.__path = None
        self.__colorSpace = None

    def setPath(self, path):
        self.__path = path
      
    def setFrame(self, frame):
        self.__frame = frame

    def setTextCtrl(self, textCtrl):
        self.__textCtrl = textCtrl
    
    # kliknieto na link
    # (poniewaz informacje o kodowaniu fontu i przestrzeni kolorow sa zlozone, sa
    # wyswietlane oknie dialogowym otwieranym po kliknieciu w odpowiedni link w
    # __textCtrl)
    def onURL(self, event):
        if self.__urlMode == "Image": # w __textCtrl pokazujemy informacje o obrazku,
                # a zatem link prowadzi do przestrzeni kolorow
            if self.__colorSpace != None:
                dia = ColourSpaceDialog(self, wx.ID_ANY, "Color space")
                dia.setColourSpace(self.__colorSpace)
                dia.ShowModal() # pokazujemy przestrzen kolorow
                dia.Destroy()
        else: # wpp pokazujemy informacje o foncie, a zatem link prowadzi do kodowania
            if self.__encoding != None:
                dia = ColourSpaceDialog(self, wx.ID_ANY, "Encoding")
                dia.setEncoding(self.__encoding)
                dia.ShowModal() # pokazujemy kodowanie
                dia.Destroy()
        #self.__textCtrl.EndAllStyles()
        #self.__textCtrl.EndUnderline()
        #self.__textCtrl.EndTextColour()
        #self.__textCtrl.EndURL()

    def setRoot(self, tree):
        self.__root = tree

    # pokazuje slownik zasobow strony o danym identyfikatorze page
    # jezeli seekedNodde != None to chcemy pokazac konkretny font (w zasadzie
    # (por. komentarze do MainWindow.switchTabs i Font.ptreeLink) moznaby od razu
    # wywolywac w MainWindow.switchTabs __showFont, a obecna implementacja to
    # pozostalosc gdy PhysList bylo drzewem i trzeba bylo je odpowiednio rozwijac;
    # powinno sie natomiast dodac jakies zaznaczanie odpowiedniego item wxWidgets
    # w kontrolce PhysList)
    def show(self, page, seekedNode=None):
        if self.__root == None: # wczytany plik jest plikiem XML i nie ma slownikow
                # zasobow stron
            return
        self.ClearAll() # czyscimy kontrolke
        self.__nodes = [] # j.w.
        id = 0
        for c in self.__root.children: # dzieci korzenia PTree to strony
            #print c.data, page
            if c.data == page: # mamy strone ktorej szukamy 
                for cc in c.children: # dzieci strony to fonty i obrazki (elementy
                        # jej slownika zasobow)
                    #item = wx.ListItem()
                    #item.SetText(cc.label)
                    #self.Append([cc.label])
                    self.InsertStringItem(id, cc.label) # dodajemy item wxWidgets do
                        # listy
                    #self.SetStringItem(id, 0, cc.label, id)
                    self.SetItemData(id, id) # wkladamy do niego indeks na liscie
                        # __node - dzieki temu mozemy sie z itema dostac do fontu
                        # lub obrazka ktoremu od odpowiada 
                    id += 1
                    self.__nodes.append(cc) # dodajemy font lub obrazek do listy __nodes
                    if seekedNode == cc: # tego parametru uzywamy, jezeli metode wywolano
                            # z metody MainWindow.switchTabs, zeby pokazac font po
                            # nacisnieciu na link w MainWindow.__textCtrl
                        self.__showFont(cc) # pokazujemy font
        self.Refresh()
    
    # pokazuje dany font w __textCtrl
    # data - obiekt PTree reprezentujacy font
    def __showFont(self, data):
        #self.__textCtrl.EndAllStyles()
        self.__textCtrl.SetInsertionPoint(0) # potrzebne, wpp caly tekst po kliknieciu
        self.__textCtrl.Clear()              # na link robi sie niebieski
        (result, enc, result2) = self.__processFont(data.data) # zwraca tekst
            # z informacja o foncie, ktory ma byc wyswietlony, na podstawie
            # obiektu klasy Font (data.data) 
        self.__textCtrl.WriteText(result)
        if enc != None:
            self.__textCtrl.BeginTextColour("#0000ff")
            self.__textCtrl.BeginUnderline()
            self.__textCtrl.BeginURL("0")
            self.__urlMode = "Font" # patrz onURL
            self.__encoding = enc # zapisuje na __encoding slownik kodowania fontu
                # ktory bedzie widoczny w metodzie onURL
            self.__textCtrl.WriteText("Encoding\n")
            self.__textCtrl.EndURL()
            self.__textCtrl.EndUnderline()
            self.__textCtrl.EndTextColour()
        self.__textCtrl.WriteText(result2)
        self.__textCtrl.ShowPosition(0)
    
    # kliknieto na jeden z itemow listy
    # pobiera na jego podstawie obiekt PTree odpowiadajacy fontowi lub obrazkowi z
    # listy __nodes i wyswietla w polu __textCtrl
    def __onClick(self, event):
        #print "ON CLICK", event.GetItem(), self.GetItemText(event.GetItem())
        item = event.GetItem()
        #print item.GetData()
        data = self.__nodes[item.GetData()]
        #print ":" + str(item) + ":" + item.GetText()
        if item.GetText()[0:4] == "Imag": # obrazek, odnosnie warunku patrz pole PTree.label
            #self.__textCtrl.MoveCaret(0, True)
            self.__textCtrl.SetInsertionPoint(0) # potrzebne, wpp po kliknieciu na link
            #self.__textCtrl.EndAllStyles()
            #self.__textCtrl.EndURL()
            #self.__textCtrl.EndUnderline()
            #self.__textCtrl.EndTextColour()
            self.__textCtrl.Clear()              # caly tekst robi sie niebieski
            (text, url, text2, img) = self.__processImage(data.data)
            #self.__textCtrl.AppendText(text)
            #self.__textCtrl.SetInsertionPoint(0)
            #self.__textCtrl.SetStyle(rt.RichTextRange(0.0, 10000.0), rt.TextAttrEx())            
            self.__textCtrl.WriteText(text)
            if url != None:
                self.__textCtrl.BeginTextColour("#0000ff")
                self.__textCtrl.BeginUnderline()
                self.__textCtrl.BeginURL("0")
                #print "begin"
                self.__urlMode = "Image" # patrz onURL,
                    # self.__colorSpace ustawiane powyzej w metodzie __processImage
                self.__textCtrl.WriteText(url)
                #print url
                self.__textCtrl.EndURL()
                #print "end"
                self.__textCtrl.EndUnderline()
                self.__textCtrl.EndTextColour()
            #self.__textCtrl.BeginBold()
            self.__textCtrl.WriteText(text2)
            #self.__textCtrl.EndBold()
            #self.__textCtrl.EndAllStyles()
            self.__textCtrl.ShowPosition(0)
            self.__frame.showImage(img)
        elif item.GetText()[0:4] == "Font": # font, przekazanie sterowania do metody
                # __showFont ktora zajmie sie fontem, odnosnie warunku patrz pole PTree.label
            #self.__textCtrl.SetInsertionPoint(0)
            #self.__textCtrl.Clear()
            self.__showFont(data)
            self.__frame.hideImage() # chowamy obrazek (bo moze byc po potrzednim
                # obiekcie)
    
    # wyciaga informacje ze slownika fontu (ktory z kolei wyciaga z obiektu klasy Font)
    # zwraca krotke (tekst do wyswietlenia przed linkiem do kodowania fontu, slownik kodowania fontu,
    # tekst do wyswietlenia po linku do kodowania fontu) jezeli kodowanie fontu jest w
    # postaci slownika lub (tekst do wyswietlenia przed nazwa kodowania fontu z nazwa
    # wlacznie, None, tekst do wyswietlenia po nazwie kodowania fontu) jezeli kodowanie fontu jest
    # w postaci nazwy
    def __processFont(self, font):
        dict = font.dict
        result = u""
        type = literal_name(dict.get("Subtype"))
        name = literal_name_none(dict.get("BaseFont"))
        if name != None:
            fullName = Font.removeSubset(name)
        descr = dict_value_none(dict.get("FontDescriptor"))
        family = None
        stretch = None
        weight = None
        file = None
        type1File = False
        file3 = False
        desName = None
        monospace = False
        serif = False
        symbolic = False
        script = False
        nonsymbolic = False
        italic = False
        allCap = False
        smallCap = False
        if descr != None:
            family = str_value_none(descr.get("FontFamily"))
            stretch = literal_name_none(descr.get("FontStretch"))
            weight = num_value_none(descr.get("FontWeight"))
            file = stream_value_none(descr.get("FontFile2"))
            type1File = descr.get("FontFile1") != None
            file3 = descr.get("FontFile3") != None
            desName = literal_name(descr.get("FontName"))
            if weight >= 700:
                strWeight = "bold"
            else:
                strWeight = "normal"
            flags = num_value(descr.get("Flags"))
            if flags == None:
                flags = 0
            monospace = flags & 0x1
            serif = flags & 0x2
            symbolic = flags & 0x4
            script = flags & 0x8
            nonsymbolic = flags & 0x20
            italic = flags & 0x40
            allCap = flags & 0x10000
            smallCap = flags & 0x20000
        encoding = dict.get("Encoding") != None
        if type == "Type0":
            encoding = False
        enc = None
        if encoding:
            dEncoding = dict_value2(dict.get("Encoding"))
            if dEncoding != None:
                enc = dEncoding
            else:
                nEncoding = literal_name(dict.get("Encoding"))
        cmap = stream_value_none(dict.get("ToUnicode"))
        if name != None:
            result += "PostScript name: " + fullName + "\n"
            result += "Full name: " + name + "\n"
        if descr != None:
            result += "Descriptor: yes\n"
        elif type == "TrueType" or type == "Type1":
            result += "Descriptor: no\n"
        if desName != None:
            result += "Full name in descriptor : " + desName + "\n"
        if family != None:
            result += "Family: " + family + "\n"
        result += "Type: " + type + "\n"
        if stretch != None:
            result += "Stretch: " + stretch + "\n"
        if weight != None:
            result += "Weight: " + str(weight) + " (" + strWeight + ")\n"
        if descr != None:
            result += "Flags set: "
            useComma = False
            if monospace != 0:
                result += "monspace"
                useComma = True
            if serif != 0:
                if useComma:
                    result += ", "
                result += "serif"
                useComma = True
            if symbolic != 0:
                if useComma:
                    result += ", "
                result += "symbolic"
                useComma = True
            if italic != 0:
                if useComma:
                    result += ", "
                result += "italic"
                useComma = True
            if nonsymbolic != 0:
                if useComma:
                    result += ", "
                result += "nonsymbolic"
                useComma = True
            if script != 0:
                if useComma:
                    result += ", "
                result += "script"
                useComma = True
            if allCap != 0:
                if useComma:
                    result += ", "
                result += "allCap"
                useComma = True
            if smallCap != 0:
                if useComma:
                    result += ", "
                result += "smallCap"
            result += "\n"
        if encoding:
            if enc == None:
                result += "Encoding: " + nEncoding + "\n"
        result2 = ""
        if file3:
            result2 += "Embedded file: non standard (FontFile3)\n"
        if type == "TrueType":
            if file != None:
                result2 += "Embedded file: yes\n"
            else:
                result2 += "Embedded file: no\n"
            if file != None:
                sio = StringIO(file.get_data())
                fontFile = TTFontMod(sio)
                #print fontFile.getTableData("name")
                result2 += self.__processNamesTable(fontFile['name'].names)
                sio.close()
        elif type == "Type1":
            if type1File:
                result2 += "Embedded file: yes\n"
            else:
                result2 += "Embedded file: no\n"
        if cmap != None:
            result2 += "Mapping to unicode:\n"
            unicodeMap = FileUnicodeMap()
            sio = StringIO(cmap.get_data())
            CMapParser(unicodeMap, sio).run()
            sio.close()
            i = 0
            for (k, v) in unicodeMap.cid2unichr.iteritems():
                i += 1
                if unicode(v) == "\n":
                    result2 += str(k) + ":\tLF\t" + hex(ord(unicode(v)))
                elif unicode(v) == "\r":
                    result2 += str(k) + ":\tCR\t" + hex(ord(unicode(v)))
                elif unicode(v) == "\t":
                    result2 += str(k) + ":\tTAB\t" + hex(ord(unicode(v)))
                else:
                    code = ""
                    j = 0
                    for c in unicode(v):
                        j += 1
                        code += hex(ord(c)) + " "
                    if j == 1 and i % 3 != 0:
                        code += "\t"
                    result2 += str(k) + ":\t" + unicode(v) + "\t" + code
                if i % 3 == 0:
                    result2 += "\n"
                else:
                    result2 += "\t\t"
        return (result, enc, result2)
    
    # wyciaga informacje z tabeli nazw fontu TrueType
    def __processNamesTable(self, names):
        copyright = None
        license = None
        family = None
        style = None
        completeName = None
        psName = None
        tm = None
        licenseURL = None
        winFamily = None
        winStyle = None
        macFamily = None
        res = u""
        for n in names:
            #print n.platformID, n.platEncID, n.langID
            if (n.platformID == 0 or (n.platformID == 1 and n.platEncID == 0 and n.langID == 0x0)
		        or (n.platformID == 2 and n.platEncID == 1 and n.langID == 0x0409)):
                if (n.platformID == 1):
                    #sys.stderr.write("[" + n.string + "]")
                    #sys.stderr.write("[" + n.string.decode("latin-1") + "]")
                    data = n.string.decode("latin-1")
                else:
                    data = uniToString(n.string)
                if len(n.string) == 0:
                    continue
                if n.nameID == 0:
                    copyright = data
                elif n.nameID == 1:
                    family = data
                elif n.nameID == 13:
                    license = data
                elif n.nameID == 2:
                    style = data
                elif n.nameID == 4:
                    completeName = data
                elif n.nameID == 6:
                    psName = data
                elif n.nameID == 7:
                    tm = data
                elif n.nameID == 14:
                    licenseURL = data
                elif n.nameID == 16:
                    winFamily = data
                elif n.nameID == 17:
                    winStyle = data
                elif n.nameID == 18:
                    macFamily = data
        res += u"Font embedded information:\n"
        if copyright != None:
            res += u"\tCopyright notice: " + copyright + u"\n"
        if license != None:
            res += "\tLicense:\n" + license + "\n"
        if licenseURL != None:
            res += "\tLicense URL: " + licenseURL + "\n"
        if tm != None:
            res += "\tTrademark: " + tm + "\n"
        if family != None:
            res += "\tFamily name: " + family + "\n"
        if style != None:
            res += "\tStyle: " + style + "\n"
        if completeName != None:
            res += "\tComplete name: " + completeName + "\n"
        if psName != None:
            res += "\tPostScript name: " + psName + "\n"
        if winFamily != None:
            res += "\tWindows family name: " + winFamily + "\n"
        if winStyle != None:
            res += "\tWindows style: " + winStyle + "\n"
        if macFamily != None:
            res += "\tMac family name: " + macFamily + "\n"
        return res

    # wyciaga informacje o obrazku ze slownika obrazka
    # znaczenie parametrow - patrz komentarz do pola PTree.data
    # zwraca krotke (tekst do wyswietlenia przed linkiem do przestrzeni kolorow,
    # tekst linka do przestrzeni kolorow, tekst do wyswietlenia po linku do przestrzeni
    # kolorow, obrazek do narysowania przez ImagePanel (obiekt klasy wx.Image)) - jezeli
    # przestrzen kolorow jest skomplikowana i trzeba ja przedstawic w osobnym oknie -
    # - lub krotke (tekst do wyswietlenia przed przestrzenia kolorow i przestrzen kolorow,
    # None, tekst do wyswietlenia po przestrzeni kolorow) - jezeli przestrzen kolorow
    # mozna przedstawic w postaci prostego napisu
    def __processImage(self, (img, page, num, genno)):
        result = ""
        length = num_value(img.get("Length"))
        name = literal_name_none(img.get("Name"))
        filters = None
        filter = None
        if list_value2(img.get("Filter")) != None:
            filters = []
            for f in list_value(img.get("Filter")):
                filters.append(literal_name(f))
        else:
            filter = literal_name_none(img.get("Filter"))
        file = img.get("F")
        width = num_value(img.get("Width"))
        height = num_value(img.get("Height"))
        url = None
        if list_value2(img.get("ColorSpace")) != None:
            colourSpace = literal_name(list_value(img.get("ColorSpace"))[0])
            if colourSpace in ["ICCBased", "Separation", "DeviceN", "Indexed"]:
                url = colourSpace + "\n"
                self.__colorSpace = img.get("ColorSpace") # zapamietujemy przestrzen
                    # kolorow zeby byla widoczna w metodzie onURL
            elif colourSpace in ["CalGray", "CalRGB", "Lab"]:
                colourSpace += ", " + str(dict_value(list_value(img.get("ColorSpace"))[1]))  
        else:
            colourSpace = literal_name_none(img.get("ColorSpace"))
        bpp = num_value_none(img.get("BitsPerComponent"))
        mask = num_value_none(img.get("ImageMask"))
        intent = literal_name_none(img.get("Intent"))
        if mask != 0 and mask != None:
            result += "Mask\n"
        dict = None
        mode = None
        isMask = mask != 0 and mask != None
        #print page, num, genno, isMask
        if file == None:
            # TODO: D czy pdfimages poradzi sobie z wielokrotnymi filtrami         	
            (imag, _, _) = getWxImage(self.__path, page, num, genno, isMask, self.__frame)
                # wyciagamy obrazek z pliku (patrz imagextract.py i PDFAUtilitiesCpp)
        else:
            imag = None
        exif = ""
        if filter == "DCTDecode" and file == None: # JPEG
            parser = ImageFile.Parser()
            parser.feed(img.rawdata)
            image = parser.close()
            dict = image.info
            mode = image.mode
            sio = StringIO(img.rawdata)
            exif = extractExif(sio) # wyciagamy metadane EXIF z obrazka JPEG
            sio.close()
        hasMetadata = img.get("Metadata") != None
        if name != None:
            result += "Name: " + name + "\n"
        result += "Length: " + str(length) + "\n"
        if filters != None and len(filters) > 0:
            result += "Filters: "
            result += filters[0]
            for f in filters[1:]:
                result += ", " + filters[1]
            result += "\n"
        if filter != None:
            result += "Filter: " + filter + "\n"
        else:
            result += "No filter used\n"
        result += "Dimensions: " + str(width) + "x" + str(height) + "\n"
        if url == None and colourSpace != None:
            result += "Colour space: " + str(colourSpace) + "\n"
        result2 = ""
        if bpp != None:
            result2 += "BPP: " + str(bpp) + "\n"
        if intent != None:
            result2 += "Intent: " + intent + "\n"       
        if hasMetadata:
            result2 += "Metadata: yes\n"
        else:
            result2 += "Metadata: no\n"
        if dict != None or mode != None or exif != "":
            result2 += "File embedded information:\n"
        if dict != None:
            dict = self.__formatJfif(dict)
            for (k, v) in dict.iteritems():
                result2 += "\t" + str(k) + ": " + str(v) + "\n"
        if exif != "":
            result2 += exif
        if mode != None:
            result2 += "\t" + "Mode: " + str(mode) + "\n"
        if imag == None:
            if file != None:
                result2 += "Image in external file\n"
            else:
                result2 += "Image not from this page!\n" # moze sie zdarzyc, ze
                    # slowniki zasobow sa dzielone miedzy wiele stron;
                    # wtedy metoda getWxImage zwroci obrazek tylko wtedy, jezeli
                    # aktualnie pokazujemy slownik zasobow dla strony na ktorej
                    # jest ten obrazek;
                    # dla innych stron, mimo ze maja ten sam slownik zasobow,
                    # zostanie pokazany ten komunikat 
        return (result, url, result2, imag)
    
    # formatujemy metadane obrazka JPEG zwrocone przez biblioteke PIL w bardziej
    # przystepny sposob, czesc z nich pomijamy (ale exif jest obslugiwany osobno pakieten
    # exif.py)
    def __formatJfif(self, dict):
        res = {}
        for (k, v) in dict.iteritems():
            # TODO: NOTE flashpix niezaimplementowany
            # TODO: NOTE PIL niepoprawnie odczytuje metadane adobe
            if k == "jfif" or k == "exif" or k == "flashpix" or k == "adobe" or k == "adobe_transform":
                continue
            elif k == "dpi":
                res.setdefault("DPI", v)
            elif k == "jfif_version":
                res.setdefault("JFIF Version", v)
            elif k == "jfif_density":
                res.setdefault("JFIF Density (X, Y)", v)
            elif k == "jfif_unit":
                if v == 0:
                    res.setdefault("JFIF Density Units", "Aspect ratio")
                elif v == 1:
                    res.setdefault("JFIF Density Units", "Pixels per inch")
                elif v == 2:
                    res.setdefault("JFIF Density Units", "Pixels per centimeter")
            else:
                res.setdefault(k, v)     	
        return res
