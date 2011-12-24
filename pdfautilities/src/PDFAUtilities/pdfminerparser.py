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

from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from pdfminer.layout import LAParams
from pdfminerconverter import PDFMinerConverter, PDFMinerNode
from pdfminer.pdfinterp import process_pdf, PDFResourceManager
from pdfminer.pdfparser import PDFSyntaxError
from hocrdirectconverter import HOCRDirectConverter
from pdfminermod import init_process_pdf, continue_process_pdf
from taglib import Font
from utils import HOCR_APP_NAME, HOCR_APP_VERSION

# TODO: E: tekst jako dziecko czegos innego niz textline 

# klasa laduje plik XML opisujacy uklad strony pliku PDF wygenerowany przez
# pdfminera (konkretnie przez pdf2txt.py)
# jest to w zasadzie funkcjonalnosc niepotrzebna, pozostalosc z czasow zanim
# napisalem pobieranie tej struktury bez posrednictwa pliku XML (pdfminerconverter.py)
# dlatego pomine szczegolowe komentarze
class PDFMinerHandler(ContentHandler):
    # TODO: G pasek postepu
    
    def __init__(self, root, ignore):
        self.__node = root
        self.__stack = [self.__node]
        self.__controlStack = ["root"]
        self.__isText = False
        self.__page = None
        self.__layout = None
        self.__num = -1
        self.__dialog = None
        self.__font = None
        self.__fontDict = {}
        self.__lib = None
        self.__wasLayout = False
        self.__badText = False
        self.__ignore = ignore
        self.__inGroup = False
    
    def setLib(self, lib):
        self.__lib = lib
    
    def setDialog(self, dialog):
        self.__dialog = dialog
        
    def startElement(self, name, attrs):
        self.__controlStack.append(name)
        if not name in ["text", "textgroup", "layout", "textbox", "textline", "text", "page", "pages"]:
            return
        if self.__ignore and name == "textgroup":
            return
        if self.__ignore and name == "layout":
            self.__inGroup = True
        if self.__ignore and name == "textbox" and self.__inGroup:
            return
        if name == "text":
            #assert(self.__node.getStandardText() == "textline")
            self.__isText = True
            try:
                attrs.getValue("bbox")
            except KeyError:
                self.__isText = False
                self.__badText = True
                return
            try:
                font = attrs.getValue("font")
                size = attrs.getValue("size")
                self.__font = self.__fontDict.setdefault(font + str(size), Font.xmlDummy(font, size))
            except KeyError:
                pass
        if name == "page":
            self.__wasLayout = False
            self.__num += 1
            #print "PAGE", self.__num
            #print self.__node.getStandardText(), self.__num
            self.__stack.append(self.__node)
            self.__page = PDFMinerNode("page")
            self.__page.setPageId(self.__num)
            self.__node = self.__page
            #assert(self.__node.bbox == None)
        elif name == "layout":
            self.__stack.append(self.__node)
            self.__layout = PDFMinerNode("layout")
            self.__node = self.__layout
            #assert(self.__node.bbox == None)
        else:
            #print "abc:", name
            self.__stack.append(self.__node)
            parent = self.__node
            if name == "textbox":
                id = attrs.getValue("id")
            else:
                id = None
            self.__node = PDFMinerNode(name, id)
            if name != "pages":
                #print name, self.__num
                self.__node.setPageId(self.__num)
            if name == "text":
                self.__node.setLeaf()
                #self.__node.setContentType("Text")
            parent.add(self.__node)
            #assert(self.__node.bbox == None)
        try:
            #print name, self.__isPageText
            #assert(self.__node.bbox == None)
            bboxString = attrs.getValue("bbox")
            bbox = []
            bbox.append(float(bboxString.split(",")[0]))
            bbox.append(float(bboxString.split(",")[1]))
            bbox.append(float(bboxString.split(",")[2]))
            bbox.append(float(bboxString.split(",")[3]))
            #assert(self.__node.bbox == None)
            #print name, self.__lib
            if name == "page" and self.__lib != None:
                self.__lib.addBbox(self.__node.getPageId(), bbox)
            self.__node.setBbox(bbox)
        except KeyError:
            pass
        
    def endElement(self, name):
        #print self.__controlStack, self.__stack
        self.__controlStack.pop()
        if not name in ["text", "textgroup", "layout", "textbox", "textline", "text", "page", "pages"]:
            return
        if self.__ignore and name == "textgroup":
            return
        if self.__ignore and name == "layout":
            self.__inGroup = False
        if self.__ignore and name == "textbox" and self.__inGroup:
            return
        if name == "text":
            if self.__badText:
                self.__badText = False
                return
            self.__isText = False
        if name == "layout":
            #print name
            self.__wasLayout = True
            self.__process()
        else:
            #print name#, self.__node.getStandardText()
            self.__node = self.__stack.pop()
            if name == "page" and not self.__wasLayout:
                self.__node.add(self.__page)
            #if name == "page":
            #    print name, self.__node.getStandardText()

    def characters(self, content):
        if self.__isText:
            if self.__font != None:
                #print ":" + self.__font.name
                self.__node.add(self.__font)
            self.__node.add(content)
            
    def __process(self):
        pageChildren = self.__page.getChildren()
        layoutChildren = self.__layout.getChildren()
        #print self.__layout.getStandardText()
        #print "####"
        if not self.__ignore:
            self.__processGroup(self.__layout, pageChildren)
            #for group in layoutChildren:
            #    #print group
            #    self.__processGroup(group, pageChildren)
            #print len(self.__layout.__children), len(self.__page.__children)
            self.__page.setChildren(layoutChildren)
        self.__node = self.__stack.pop() # zdejmujemy strone        
        #print self.__node.getStandardText()
        tmp = self.__stack.pop()
        tmp.add(self.__page)
        self.__stack.append(tmp)
        
    def __processGroup(self, group, pageChildren):
        for child in group.getChildren():
            #print child.getTextContent()
            if child.getText() == "textgroup":
                self.__processGroup(child, pageChildren)
            elif child.getText() == "textbox":
                for el in pageChildren:
                    #print el.getTextContent()
                    #print el.getId(), child.getId()
                    if isinstance(el, PDFMinerNode) and el.getText() == "textbox":
                        if el.getId() == child.getId():
                            child.replaceWith(el)

# klasa pierwotnie pelnila funkcje parsera SAX dla plikow XML generowanych przez
# pdfminera, potem dodalem do niej trzy metody ktore pozwalaja na pobranie ukladu
# strony analizowanego przez pdfminera bezposrednio przez odwolanie sie do jego
# obiektow i tylko one sa tutaj istotne (extractFromPDF, extractHOCRFromPDF,
# extractHOCRFromPDFDirect)
class PDFMinerParser:
    
    def __init__(self):
        self.__result = None # drzewo zanalizowanego przez pdfminera ukladu strony
        self.__dialog = None
        self.__noFakeRoot = False
        
    def setDialog(self, dialog):
        self.__dialog = dialog
    
    # metoda otwiera plik PDF z uzyciem pdfminera
    # obiekt klasy PDFMinerConverter tworzy drzewo zanalizowanego przez pdfminera
    # ukladu strony
    # inicjalizuje pola __root, __bboxes i __pageno w zaslepce XMLLib
    def extractFromPDF(self, pdfFile, lib=None, ignore=False):
        rsrcmgr = PDFResourceManager()
        device = PDFMinerConverter(rsrcmgr, ignore, lib=lib, laparams=LAParams())
        fp = open(pdfFile, 'rb')
        process_pdf(rsrcmgr, device, fp)
        self.__result = device.getResult()
        if lib != None:
            lib.setRoot(self.__result)
            lib.setPageNo(len(self.__result.getChildren()))
        self.__noFakeRoot = True # jesli True to zachowanie PDFMinerParser.getResult()
            # jest intuicyjne - zwraca self.__result,
            # zachowanie przy False jest uzywane tylko przy wczytywaniu XML
    
    # metoda otwiera plik PDF z uzyciem pdfminera i od razu eksportuje go do hOCR
    # z uzyciem eksportera hocr
    # obiekt klasy PDFMinerConverter tworzy drzewo zanalizowanego przez pdfminera
    # ukladu strony logicznej, bedzie on uzyty zamiast wbudowanej w plik struktury
    # do eksportu, jezeli podano jako argument columnizer to on zanalizuje uklad strony
    # uzywajac tego z pdfminera i to on zostanie uzyta do eksportu
    # inicjalizuje pola __bboxes i __pageno w zaslepce XMLLib
    # zwraca False jesli podany plik nie jest plikiem PDF, True wpp
    def extractHOCRFromPDF(self, pdfFile, lib, hocr, columnizer, ignore):
        rsrcmgr = PDFResourceManager()
        fp = open(pdfFile, 'rb')
        try:
            (doc, pageNo) = init_process_pdf(fp)
        except PDFSyntaxError:
            fp.close()
            return False
        lib.setPageNo(pageNo)
        hocr.beginExportByPages()
        device = PDFMinerConverter(rsrcmgr, ignore, laparams=LAParams(), lib=lib, hocr=hocr, columnizer=columnizer)
        continue_process_pdf(doc, rsrcmgr, device)
        hocr.endExportByPages()
        return True
    
    # metoda otwiera plik PDF z uzyciem pdfminera i od razu eksportuje go do hOCR
    # do pliku outfp
    # obiekt klasy HOCRDirectConverter wypisuje zanalizowany przez pdfminera
    # uklad strony do pliku outfp
    # zwraca False jesli podany plik nie jest plikiem PDF, True wpp
    def extractHOCRFromPDFDirect(self, pdfFile, lib, outfp, ignore, verbose, fontMap, icu, tags):
        fp = open(pdfFile, "rb")
        try:
            (doc, pageNo) = init_process_pdf(fp)
        except PDFSyntaxError:
            fp.close()
            return False
        outfp = open(outfp, "w")
        outfp.write("<html>")
        outfp.write("<head>")
        #outfp.write("<link rel=\"stylesheet\" href=\"styl.css\" type=\"text/css\"/>")
        outfp.write("<meta http-equiv=\"content-type\" content=\"text/html; charset=utf-8\"/>")
        outfp.write("<meta name=\"ocr-system\" content=\"" + HOCR_APP_NAME + " " + HOCR_APP_VERSION + "\"/>")
        if tags:
            if icu != None:
                outfp.write("<meta name=\"ocr-capabilities\" content=\"ocrp_font ocr_carea ocr_lines ocrx_word ocrx_italic ocrx_bold\"/>")
            else:
                outfp.write("<meta name=\"ocr-capabilities\" content=\"ocrp_font ocr_carea ocr_lines ocrx_italic ocrx_bold\"/>")
        else:
            if icu != None:
                outfp.write("<meta name=\"ocr-capabilities\" content=\"ocrp_font ocr_carea ocr_lines ocrx_word\"/>")
            else:
                outfp.write("<meta name=\"ocr-capabilities\" content=\"ocrp_font ocr_carea ocr_lines\"/>")
        outfp.write("<meta name=\"ocr-number-of-pages\" content=\"" + str(pageNo) + "\"/>")
        outfp.write("</head>")
        outfp.write("<body class=\"ocr_document\">")
        rsrcmgr = PDFResourceManager()
        device = HOCRDirectConverter(rsrcmgr, outfp, ignore, lib, fontMap, icu, tags, laparams=LAParams())
        continue_process_pdf(doc, rsrcmgr, device, verbose=verbose)
        fp.close()
        outfp.write("</body>")
        outfp.write("</html>")
        outfp.close()
        return True
        
    def parse(self, file, ignore, lib=None):
        self.__result = PDFMinerNode("Document")
        handler = PDFMinerHandler(self.__result, ignore)
        handler.setDialog(self.__dialog)
        handler.setLib(lib)
        saxparser = make_parser()
        saxparser.setContentHandler(handler)
        fp = open(file, 'r')
        saxparser.parse(fp)
        if lib != None:
            lib.setRoot(self.getResult())
            lib.setPageNo(len(self.getResult().getChildren()))
        
    # zwraca drzewo struktury zanalizowane przez extractFromPDF
    def getResult(self):
        if not self.__noFakeRoot:
            res = self.__result.getChildren()[0] # <pages>
            #print res.getChildren()
        else:
            res = self.__result
        res.setRoot()
        #print res.isRoot()
        #print res.getStandardText()
        return res
