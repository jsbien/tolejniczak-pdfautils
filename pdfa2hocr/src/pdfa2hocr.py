#!/usr/bin/python
# -*- coding: cp1250 -*-
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

from utils import MyException, loadModule#, globalX, globalY
import utils
from taglib import TagLib
from pdfminerparser import PDFMinerParser
from pdfminerconverter import XMLLib
from hocrexport import HOCRExporter
from optparse import OptionParser
from columnize import Columnizer
from fontmap import FontMap
import sys
import os

# TODO: I sprawdzanie, czy dokument ma strukture logiczna (co sie stanie jak nie ma?) 

# przetwarza opcje analizy ukladu strony
# zwraca obiekt analizujacy uklad strony i liczbe kolumn na ktore nalezy podzielic
# strony
def processModuleAndColumnsOptions(options):
    if options.columns != None:
        try:
            cols = int(options.columns)
        except ValueError:
            sys.stderr.write("Argument of --columns parameter should be a number\n")
            exit()
        if cols < 2:
            sys.stderr.write("Argument of --columns parameter should be at least 2\n")
            exit()
        pags = []
        if options.pages != "":
            pages = options.pages.split(",")
            for p in pages:
                if not str.isdigit(p):
                    sys.stderr.write("Argument of -g option malformed\n") 
                    exit()
                else:
                    pags.append(int(p))
        columnizer = Columnizer() # tworzy obiekt analizujacy uklad strony
        if pags != []:
            assert(pags != None)
            columnizer.setPages(pags) # przekazuje mu argument opcji -g (strony
                # ktorych uklad strony nie powinien byc analizowany) 
        if options.module != None:
            module = os.path.abspath(options.module)
            # TODO: D wszystkie przypadki
            if os.name == "nt":
                path = module.split("\\")
            else:
                path = module.split("/")
            module = path[len(path) - 1]
            pathString = ""
            for i in range(len(path) - 1):
                if os.name == "nt":
                    pathString += path[i] + "\\"
                else:	
                    pathString += path[i] + "/"
            module = loadModule(module, pathString)
            if module != None:
                columnizer.setModule(module) # przejazuje mu modul dowolnego
                    # przetwarzania
        return (columnizer, cols)
    return (None, None)

def main(argv):
    #global globalX, globalY
    usage = "%prog [OPTIONS] INPUT_FILE OUTPUT_FILE"
    parser = OptionParser(usage = usage, version = "pdfa2hocr 0.2")
    parser.add_option("-m", "--mapping", help="mapping from PDF/A tags to hOCR elements", dest="mapping", default=None)
    parser.add_option("-c", "--columns", help="divide text into columns", dest="columns", default=None)
    parser.add_option("-p", "--pdfminer", action="store_true", help="analyze layout using pdfminer", dest="pdfminer", default=False)
    parser.add_option("-l", "--module", help="custom layout analyzing module", dest="module", default=None)    
    parser.add_option("-v", "--verbose", action="store_true", help="write information about progress", dest="verbose", default=False)
    parser.add_option("-i", "--ignore-text-groups", action="store_true", help="ignore textgroups from pdfminer (textboxes only - simpler layout)", dest="ignore", default=False)
    parser.add_option("-g", "--ignore-pages", help="pages which should not be divided into columns", dest="pages", default="")
    parser.add_option("-f", "--font-mapping", help="mapping of PostScript font names into html style", dest="fontMap", default=None)
    parser.add_option("-u", "--icu", help="use ICU word segmentation algorithm", dest="icu", default=None)
    parser.add_option("-t", "--special-font-tags", action="store_true", help="use special font style hOCR tags", dest="tags", default=False)
    parser.add_option("-r", "--resolution", help="resolution of page in pixels", dest="resolution", default=None)
    (options, args) = parser.parse_args(argv)
    if len(args) != 3:
        #print args
        parser.print_help()
        exit()
    #print args
    #print "a", options.columns, options.ignore, options.module
    #fin = "C:\\Users\\to\\Documents\\Próbka2.pdf"
    #fin = "C:\\Users\\to\\Desktop\\linde\\Linde2edK_1_0133-0222.pdf"
    #fin = "C:\\Users\\to\\Desktop\\pliki\\FRiLindeJSBkor1-50.pdf"
    #fin = "C:\\Users\\to\\Desktop\\linde\\wyn.xml"
    #fout = "C:\\Users\\to\\Documents\\a.html"
    fin = args[1]
    fout = args[2]
    if not os.path.exists(fin):
        sys.stderr.write("File " + fin + " does not exist\n")
        exit()
    # TODO: E sprawdzic, czy sciezka do fout jest prawidlowa
    map = None
    if options.fontMap != None:
        if not os.path.exists(options.fontMap):
            sys.stderr.write("File " + options.fontMap + " does not exist\n")	
            exit()
        map = FontMap(options.fontMap) # ladujemy z pliku mapowanie postscriptowych
            # nazw fontow na rodziny
    if options.module != None:
        if not os.path.exists(options.module):
            sys.stderr.write("File " + options.module + " does not exist\n")
            exit()
        if options.module[-3:] != ".py":
            sys.stderr.write("File " + options.module + " should have .py " +
                             "extension\n")
            exit()
    if options.mapping != None:
        if not os.path.exists(options.mapping):
            sys.stderr.write("File " + options.mapping + " does not exist\n")
            exit()
    if options.resolution != None:
        dims = options.resolution.split("x")
        utils.globalX = int(dims[0])        
        utils.globalY = int(dims[1])
        if (not str.isdigit(dims[0])) or int(dims[0]) == 0 or (not str.isdigit(dims[1])) or int(dims[1]) == 0:
            sys.stderr.write("Invalid parameters of -r/--resolution option")
            exit()
    if options.pdfminer: # wczytujemy PDF i analizujemy uklad strony PDFMinerem
        lib = XMLLib(map=map) # tworzymy obiekt udajacy TagLib (patrz TagLib i
            # XMLLib)
        lib.loadPTree(fin) # ladujemy slowniki zasobow stron
        parser = PDFMinerParser()
        (columnizer, cols) = processModuleAndColumnsOptions(options)
        print options.columns
        if columnizer != None:
            columnizer.setCols(cols) # ustawiamy liczbe kolumn do podzielenia
        if options.mapping == None and columnizer == None: # eksportujemy bez
                # dodatkowej analizy ukladu strony
            if not parser.extractHOCRFromPDFDirect(fin, lib, fout, options.ignore, options.verbose, map, options.icu, options.tags):
                    # patrz opis metody extractHOCRFromPDFDirect 
                sys.stderr.write("File " + fin + " is not a PDF file.\n")
            exit()
        else:
            hocr = HOCRExporter(None, fout, lib, mapping=options.mapping, xml=True, verbose=options.verbose, fontMap=map, icu=options.icu, tags=options.tags)
                # tworzymy obiekt eksportujacy do hOCR
            if not parser.extractHOCRFromPDF(fin, lib, hocr, columnizer, options.ignore):
                    # patrz opis metody extractHOCRFromPDF
                sys.stderr.write("File " + fin + " is not a PDF file.\n")
            exit()
    else:
        try:
            lib = TagLib(map=map) # tworzymy obiekt bedacy interfejsem do pdfminera
                # dla kokretnego pliku
            if not lib.initialize(fin): # otwieramy plik PDF pdfminerem
                # okazalo sie, ze to jednak plik XML:
                # TODO: F od razu page z SAXA do hOCR
                if options.fontMap == None:
                    sys.stderr.write("Warning: pdfmimer results conversion to hOCR without font map specified. In resulting hOCR fonts won't display properly in browser.\n")
                parser = PDFMinerParser()
                lib = XMLLib(map=map) # tworzymy obiekt udajacy TagLib (patrz TagLib i
                    # XMLLib)
                parser.parse(fin, options.ignore, lib=lib) # wczytujemy plik XML
                root = parser.getResult() # pobieramy korzen drzewa struktury
                (columnizer, cols) = processModuleAndColumnsOptions(options)
                if columnizer != None:
                    columnizer.columnize(root, cols) # analizujemy uklad strony
                    if columnizer.isFatal(): # blad w columnizerze - nie udalo sie
                            # nic podzielic
                        sys.stderr.write(columnizer.getLastMessage())
                        sys.exit()
                    elif columnizer.isError(): # nie udalo sie podzielic niektorych stron
                        for m in columnizer.getMessages():
                            sys.stderr.write("Warning: " + m + "\n")
                hocr = HOCRExporter(root, fout, lib, mapping=options.mapping, xml=True, verbose=options.verbose, fontMap=map, icu=options.icu, tags=options.tags)
                    # tworzymy obiekt konwertujacy do hOCR 
            else: # to faktycznie plik PDF
                if options.columns != None:
                    sys.stderr.write("Warning: --columns option specified for" +
                                     " export using PDF structural tags. Option" +
                                     " ignored.\n")
                if options.module != None:
                    sys.stderr.write("Warning: --module option specified for" +
                                     " export using PDF structural tags. Option" +
                                     " ignored.\n")
                if options.ignore:
                    sys.stderr.write("Warning: --ignore option specified for" +
                                     " export using PDF structural tags. Option" +
                                     " ignored.\n")
                if options.pages != "":
                    sys.stderr.write("Warning: --ignore-pages option specified for" +
                                     " export using PDF structural tags. Option" +
                                     " ignored.\n")
                if not lib.hasRoot(): # nie ma StructTreeRoot
                    sys.stderr.write("PDF file does not contain logical strucutre.\n")
                    exit()
                root = lib.getRoot()          
                hocr = HOCRExporter(root, fout, lib, mapping=options.mapping, verbose=options.verbose, fontMap=map, icu=options.icu, tags=options.tags)
                    # tworzymy obiekt eksportujacy plik PDF
        except MyException:
            exit()
    hocr.export() # eksportujemy plik PDF
    hocr.save()

if __name__ == '__main__': sys.exit(main(sys.argv))
