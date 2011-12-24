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
import os
import sys
from pdfminer.pdfparser import PDFDocument, PDFParser, PDFSyntaxError
from pdfminer.pdfparser import literal_name
from pdfminer.pdfinterp import PDFResourceManager, PDFTextExtractionNotAllowed
from pdfminer.pdftypes import dict_value, num_value, str_value, list_value
from pdfminer.layout import LAParams
from pdfminermod import dict_value_none, dict_value2
from pdfreader import DummyConverter
from pdfareader import PDFAPageInterpreter
from utils import isSubsetName

# Copyright (C) 1985-2001 Adobe Systems Incorporated. All rights reserved.
SYMBOLS = ["/Alpha", "/Beta", "/Chi", "/Delta", "/Epsilon", "/Eta",
		"/Euro", "/Gamma", "/Ifraktur", "/Iota", "/Kappa", "/Lambda",
		"/Mu", "/Nu", "/Omega", "/Omicron", "/Phi", "/Pi", "/Psi",
		"/Rfraktur", "/Rho", "/Sigma", "/Tau", "/Theta", "/Upsilon",
		"/Upsilon1", "/Xi", "/Zeta", "/aleph", "/alpha", "/ampersand",
		"/angle", "/angleleft", "/angleright", "/approxequal",
		"/arrowboth", "/arrowdblboth", "/arrowdbldown", "/arrowdblleft",
		"/arrowdblright", "/arrowdblup", "/arrowdown", "/arrowhorizex",
		"/arrowleft", "/arrowright", "/arrowup", "/arrowvertex", "/asteriskmath",
		"/bar", "/beta", "/braceleft", "/braceright", "/bracelefttp",
		"/braceleftmid", "/braceleftbt", "/bracerighttp", "/bracerightmid",
		"/bracerightbt", "/braceex", "/bracketleft", "/bracketright",
		"/bracelefttp", "/braceleftex", "/braceleftbt", "/bracerighttp",
		"/bracerightex", "/bracerightbt", "/bullet", "/carriagereturn",
		"/chi", "/circlemultiply", "/circleplus", "/club", "/colon",
		"/comma", "/congruent", "/copyrightsans", "/copyrightserif",
		"/degree", "/delta", "/diamond", "/divide", "/dotmath", "/eight",
		"/element", "/ellispis", "/emptyset", "/epsilon", "/equal",
		"/equivalence", "/eta", "/exclam", "/existential", "/five",
		"/florin", "/four", "/fraction", "/gamma", "/gradient", "/greater",
		"/greaterequal", "/heart", "/infinity", "/integral", "/integraltp",
		"/integralex", "/integralbt", "/intersection", "/iota", "/kappa",
		"/lambda", "/less", "/lessequal", "/logicaland", "/logicalnot",
		"/logicalor", "/lozenge", "/minus", "/minute", "/mu", "/multiply",
		"/nine", "/notelement", "/notequal", "/notsubset", "/nu", "/numbersign",
		"/omega", "/omega1", "/omicron", "/one", "/parenleft", "/parenright",
		"/parenlefttp", "/parenleftex", "/parenleftbt", "/parenrighttp",
		"/parenrightex", "/parenrightbt", "/partialdiff", "/percent", "/period",
		"/perpendicular", "/phi", "/phi1", "/pi", "/plus", "/plusminus",
		"/product", "/propersubset", "/propersuperset", "/proportional", "/psi",
		"/question", "/radical", "/radicalex", "/reflexsubset",
		"/reflexsuperset", "/registerserif", "/rho", "/second", "/semicolon",
		"/seven", "/sigma", "/sigma1", "/similar", "six", "/slash", "/space",
		"/spade", "/suchthat", "/summation", "/tau", "/therefore", "/theta",
		"/theta1", "/three", "/trademarksans", "/trademarkserif", "/two",
		"/underscore", "/union", "/universal", "/weierstrass", "/xi", "/zero",
		"/zeta"
    ]

class PDFAValidator():
    
    def __init__(self, levelb=False):
        self.__doc = None
        self.__levelb = levelb
        self.__interp = None
        self.__ok = True
    
    def isOK(self):
        return self.__ok
    
    def validate(self, fileName):
        self.__loadDocument(fileName)
        self.__write("GLOBAL:")
        self.__validateDocumentCatalog(self.__doc.catalog)
        j = 0
        for p in self.__doc.get_pages():
            j += 1
            self.__write("PAGE " + str(j) + ":", error=False)
            images = dict_value(p.resources.get("XObject"))
            for (k, v) in images.iteritems():
                self.__validateXObjectDictionary(dict_value(v), literal_name(k))
            gstates = dict_value(p.resources.get("ExtGState"))
            for (k, v) in gstates.iteritems():
                self.__validateGraphicsStateParameterDictionary(dict_value(v), literal_name(k))
            # TODO: V czy w ten sposob sprawdzimy wszystkie wzorce o typie 2?
            patterns = dict_value(p.resources.get("Pattern"))
            for (k, v) in patterns.iteritems():
                self.__validatePattern(dict_value(v), literal_name(k))
            i = -1
            for a in list_value(p.annots):
                i += 1
                self.__validateAnnotationDictionary(dict_value(a), str(i) + " on page " + p.pageid)
            # TODO: V powinno byc sprawdzane, czy font jest uzywany (p. 6.3.4)
            fonts = dict_value(p.resources.get("Font"))
            for (k, v) in fonts.iteritems():
                self.__validateFont(dict_value(v), literal_name(k))
            self.__interp.process_page(p)
        
    def __loadDocument(self, fileName):
        self.__doc = PDFDocument()
        fp = file(fileName, 'rb')
        parser = PDFParser(fp)
        parser.set_document(self.__doc)
        self.__doc.set_parser(parser)
        self.__doc.initialize('')
        if not self.__doc.is_extractable:
            raise PDFTextExtractionNotAllowed('Text extraction is not allowed: %r' % fp)
        rsrcmgr = PDFResourceManager()
        self.__interp = PDFAPageInterpreter(rsrcmgr, DummyConverter(rsrcmgr, laparams=LAParams()))
        self.__interp.setValidator(self)
    
    def __validateOutline(self, outl, id):
        if outl.get("Next") != None:
            self.__validateOutline(dict_value(outl.get("Next")), outl.get("Next").objid)
        if outl.get("First") != None:
            self.__validateOutline(dict_value(outl.get("First")), outl.get("First").objid)
        if outl.get("A") != None:
            self.__validateAction(dict_value(outl.get("A")), "in outline " + str(id))
        
    def validateRenderingIntent(self, ri, msg):
        # 6.2.9
        if not ri in ["AbsoluteColorimetric", "RelativeColorimetric",
                      "Saturation", "Perceptual"]:
            self.__write(msg + " Permitted values are: /AbsoluteColorimetric" +
                         ", /RelativeColorimetric, /Saturation and" +
                         " /Perceptual")

    def __validatePattern(self, dict, id):
        if num_value(dict.get("PatternType")) == 2:
            self.__validateGraphicsStateParameterDictionary(dict_value(dict.get("ExtGState")),
														"in " + str(id) + " pattern")

    def __validateGraphicsStateParameterDictionary(self, dict, id):
        # 6.2.8
        if dict.get("TR") != None:
            self.__write("Graphics state parameter dictionary " + str(id) +
                         " contains TR entry")
        if dict.get("TR2") != None:
            if literal_name(dict.get("TR2")) != "Default":
                # TODO: X wypisac wartosc i wogole zrobic jakies funkcje
                # sprawdzajace typ obiektu PDFowego
                self.__write("Graphics state parameter dictionary " + str(id) +
                         " contains TR2 entry with value other than /Default")
        if dict.get("RI") != None:
            self.__validateRenderingIntent(literal_name(dict.get("Intent")),
                                           "Graphics state parameter " +
                                           "dictionary " + str(id) + " contains RI" +
                                           " entry with value " +
                                           literal_name(dict.get("Intent"))
                                           + ".")
        if dict.get("SMask") != None:
            # 6.4
            if literal_name(dict.get("SMask")) != "None":
                self.__write("Image dictionary " + str(id) + " contains SMask " +
                             "entry which value isn't /None")
        if dict.get("BM") != None:
            # 6.4
            if not literal_name(dict.get("BM")) in ["Normal", "Compatible"]:
                self.__write("Image dictionary " + str(id) + " contains BM " +
                             "entry which value isn't /Normal or /Compatible")
        if dict.get("CA") != None:
            # 6.4
            if num_value(dict.get("CA")) != 1.0:
                self.__write("Image dictionary " + str(id) + " contains CA " +
                             "entry which value isn't 1.0")      
        if dict.get("ca") != None:
            # 6.4
            if num_value(dict.get("ca")) != 1.0:
                self.__write("Image dictionary " + str(id) + " contains ca " +
                             "entry which value isn't 1.0")
    
    # TODO: X fonty /MMType1 powinny spelniac wszystkie warunki co /Type1

    def __validateXObjectDictionary(self, dict, id):
        if literal_name(dict.get("Subtype")) == "Form":
            # 6.2.5
            if dict.get("Ref") != None:
                # 6.2.6
                self.__write("XObject dictionary " + str(id) +
                             " is a reference XObject")
            if dict.get("OPI") != None:
                self.__write("Form XObject dictionary " + str(id) +
                             " contains OPI entry")
            # TODO: NOTE ale w reference 3 nie ma nic o Subtype2 i PS
            if dict.get("Subtype2") != None:
                if literal_name(dict.get("Subtype2")) == "PS":
                    self.__write("Form XObject dictionary " + str(id) + " contains" +
                                 "Subtype2 entry with PS value")
            if dict.get("PS") != None:
                self.__write("Form XObject dictionary " + str(id) +
                             " contains PS entry")
            if dict.get("Group") != None:
                # 6.4
                groupDict = dict_value(dict.get("Group"))
                if literal_name(groupDict.get("S")) == "Transparency":
                    self.__write("Form XObject dictionary " + str(id) +
                                 "contains Group entry which S attribute value"
                                 + " id /Transparency")
        elif literal_name(dict.get("Subtype")) == "PS":
            # 6.2.7
            self.__write("Document contains PostScript XObject " + str(id))
        elif literal_name(dict.get("Subtype")) == "Image":
            self.__validateImageDictionary(dict, str(id))
    
    def __validateImageDiciotnary(self, dict, id):
        # 6.2.4
        if dict.get("Alternates") != None:
            self.__write("Image dictionary " + str(id) +
                         " contains Alternates entry")
        if dict.get("OPI") != None:
            self.__write("Image dictionary " + str(id) + " contains OPI entry")
        if dict.get("Interpolation") != None:
            if bool(dict.get("Interpolation")) == True:
                self.__write("Image dictionary " + str(id) +
                             " contains Interpolate entry with value true")
        if dict.get("Intent") != None:
            self.__validateRenderingIntent(literal_name(dict.get("Intent")),
                                           "Image dictionary " + str(id) +
                                           " contains Intent entry with value "
                                           + literal_name(dict.get("Intent"))
                                           + ".")
        if dict.get("SMask") != None:
            # 6.4 TODO: NOTE ale w Image XObject nie moze byc name 
            if literal_name(dict.get("SMask")) != "None":
                self.__write("Image dictionary " + str(id) + " contains SMask " +
                             "entry which value isn't /None")
    
    def __validateAnnotationDictionary(self, dict, id):
        # 6.5
        if not literal_name(dict.get("Subtype")) in ["Text", "Link", "FreeText",
                                                     "Line", "Square", "Circle",
                                                     "Highlight", "Underline",
                                                     "Squiggly", "StrikeOut",
                                                     "Stamp", "Ink", "Popup",
                                                     "Widget", "PrinterMark",
                                                     "TrapNet"]:
            self.__write("Annotation dictionary " + str(id) + "contains invalid" +
                         " Subtype entry")
        if dict.get("CA") != None:
            if num_value(dict.get("CA")) != 1.0:
                self.__write("Annotation dictionary " + str(id) + " contains CA " +
                             "entry which value isn't 1.0")
        if dict.get("F") != None:
            self.__write("Annotation dictionary " + str(id) + " contains F entry")
        if literal_name(dict.get("Subtype")) == "Widget":
            self.__validateWidgetAnnotation(dict, id)
        else:
            if dict.get("A") != None:
                self.__validateAction(dict_value(dict.get("A")), "in annotation " + str(id))
            # TODO: V co jak bedzie AA? wedlug specyfikacji nie powinno sie pojawic
            # poza widgetAnnotation, ale co jak bedzie w pozniejszej wersji?

    def __validateFont(self, font, id):
        # 6.3
        if literal_name(font.get("Subtype")) == "Type0":
            self.__warning("Handling of Type0 fonts unimplemented")
        # 6.3.4 TODO: V sprawdzic czy font jest uzywany (patrz NOTE1 na nastepnej stronie)
        desc = dict_value_none(font.get("FontDescriptor"))
        if desc == None and literal_name(font.get("Subtype")) in ["TrueType",
																"Type1", "MMType1"]:
            self.__write("Font " + str(id) + " does not have FontDescriptor")
        if literal_name(font.get("Subtype")) == "TrueType":
            if desc != None and desc.get("FontFile2") == None:
                self.__write("Font " + str(id) + " does not have embedded file")
        if literal_name(font.get("Subtype")) in ["Type1", "MMType1"]:
            if desc != None and desc.get("FontFile1") == None:
                if desc != None and desc.get("FontFile3") == None:
                    self.__write("Font " + str(id) + " does not have embedded file")
        # 6.3.5
        if literal_name(font.get("Subtype")) == "Type1": # TODO: MMType1 tez?
            if isSubsetName(literal_name(font.get("BaseFont"))):
                if desc != None and desc.get("CharSet") == None:
                    self.__write("Font " + str(id) +
								" is Type1 font subset and does not contain CharSet")
        # 6.3.7
        if literal_name(font.get("Subtype")) == "TrueType":
            if desc != None and desc.get("Flags") & 0x20 != 0: # non-symbolic
                if not literal_name(font.get("Encoding")) in ["MacRomanEncoding",
															"WinAnsiEncoding"]:
                    self.__write("TrueType font " + str(id) + " is non-symbolic and its" +
								" encoding is different than MacRomanEncoding or " +
								"WinAnsiEncoding")
            elif desc != None and desc.get("Flags") & 0x4 != 0: # symbolic
                if font.get("Encoding") != None:
                    self.__write("TrueType font " + str(id) + " is symbolic and it" +
								" have Encoding entry in font dictionary")
        # 6.3.8
        if not self.__levelb:
            if not literal_name(font.get("Encoding")) in ["WinAnsiEncoding",
													"MacRomanEncoding",
													"MacExpertEncoding"]:
                check = False
                if literal_name(font.get("Subtype")) in ["Type1", "MMType1"]:
                    if desc == None:
                        check = True
                    else:
                        set = str_value(desc.get("CharSet")).split(" ")
                        ok = True
                        for s in set:
                            if not s in SYMBOLS: # TODO: informacja o tym (bugcheck)
                                ok = False
                        if not ok:
                            check = True
                else:
                    check = True
                if check and font.get("ToUnicode") == None:
                    self.__write("Font " + str(id) + " should have ToUnicode CMap," +
								" but have not")

    def __validateAction(self, action, id):
        # 6.6
        # 6.6.1
        if literal_name(action.get("S")) in ["Launch", "Sound", "Movie", "ResetForm",
											"ImportData", "JavaScript", "set-state",
											"no-op"]:
            self.__write("Action " + str(id) + " has type " + literal_name(action.get("S"))
						+ ", which is not permitted")
        if literal_name(action.get("S")) == "Named" and not literal_name(
            action.get("N")) in ["NextPage", "PrevPage", "LastPage", "FirstPage"]:
            self.__write("Named action " + str(id) + " has name " +
						literal_name(action.get("N")) + ", which is not permitted")

    def __validateWidgetAnnotation(self, widget, id):
        # 6.6.2, 6.9
        if widget.get("AA") != None:
            self.__write("Widget annotation " + str(id) + " contains AA entry")
        # 6.9
        if widget.get("A") != None:
            self.__write("Widget annotation " + str(id) + " contains A entry")
    
    def __validateField(self, field, id):
        # 6.6.1, 6.6.2, 6.9
        if field.get("AA") != None:
            self.__write("Field dictionary " + str(id) + " contains AA entry")
        for f in list_value(field.get("Kids")):
            self.__validateField(dict_value(f), f.objid)
    
    def __validateDocumentCatalog(self, doc):
        # 6.6.2
        if doc.get("AA") != None:
            self.__write("Document catalog contains AA entry")
        # 6.8.2.2
        if doc.get("MarkInfo") == None:
            self.__write("Document catalog does not contain MarkInfo entry")
        else:
            if not dict_value(doc.get("MarkInfo")).get("Marked"):
                self.__write("Marked flag in mark information dictionary is not set")
        # 6.8.4
        if doc.get("Lang") == None:
            self.__write("Document catalog does not specify language")
        # 6.1.11
        if doc.get("Names") != None:
            if dict_value(doc.get("Names")).get("EmbeddedFiles") != None:
                self.__write("Document name dictionary contains EmbeddedFiles key")
        # 6.1.13
        if doc.get("OCProperties") != None:
            self.__write("Document catalog contains OCProperties key")
        if doc.get("AcroForm") != None:
            i = -1
            for f in list_value(dict_value(doc.get("AcroForm")).get("Fields")):
                i += 1
                self.__validateField(dict_value(f), str(i) + " in AcroForm")
        if doc.get("Outlines") != None:
            self.__validateOutline(dict_value(dict_value(doc.get("Outlines")).get("First")),
								dict_value(doc.get("Outlines")).get("First").objid)
        if dict_value2(doc.get("OpenAction")) != None:
            self.__validateAction(dict_value(doc.get("OpenAction")),
								"OpenAction from document catalog")

    # TODO: V wymaga modyfikacji pdfminera
    #def __validateStream(self, stream, id):
    #    # 6.1.10
    #    if stream.get("Filter") != None:
    #        if list_value2(stream.get("Filter")) != None:
    #            for f in list_value2(stream.get("Filter")):
    #                if literal_name(f) == "LZWDecode":
    #                    self.__write("Stream " + id + " uses LZWDecode filter")
    #        else:
    #            if literal_name(stream.get("Filter")) == "LZWDecode":
    #                self.__write("Stream " + id + " uses LZWDecode filter")
    
    # TODO: V problem zeby znalezc wszystkie
    #def __validateFileSpecificationDictionary(self, dict, id):
    #    # 6.1.11
    #    if dict.get("EF") != None:
    #        self.__write("File specification dictionary " + id + " contains EF key")
    
    #def __validateColorSpace(self, space, id):
    #    pass

    def __warning(self, text):
        print "WARNING: " + text

    def __write(self, text, error=True):
        if error:
            self.__ok = False
            print "ERROR: " + text
        else:
            print text

def main(argv):
    if len(argv) != 2:
        print "Usage: pdfavalidate file.pdf"
        exit()
    fin = argv[1]
    if not os.path.exists(fin):
        print "Usage: pdfavalidate file.pdf"
        exit()
    validator = PDFAValidator()
    try:
        validator.validate(fin)
        if validator.isOK():
            print "File OK"
    except PDFSyntaxError:
        print argv[1] + " is not PDF!"
        exit()

if __name__ == '__main__': sys.exit(main(sys.argv))
