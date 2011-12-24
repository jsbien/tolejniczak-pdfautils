"""
This file contains modified code from pdfminer software licensed under Expat (MIT)
License:

For modification:
Copyright (c) 2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>
For original pdfminer code:
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

from pdfminer.pdfinterp import PDFTextExtractionNotAllowed, PDFPageInterpreter
from pdfminer.pdfparser import PDFDocument, PDFParser
from pdfminer.pdftypes import num_value, dict_value, resolve1, PDFTypeError, PDFStream
from pdfminer.pdftypes import STRICT
from pdfminer.psparser import literal_name

def init_process_pdf(fp, password=''):
# Create a PDF parser object associated with the file object.
    parser = PDFParser(fp)
    # Create a PDF document object that stores the document structure.
    doc = PDFDocument()
    # Connect the parser and document objects.
    parser.set_document(doc)
    doc.set_parser(parser)
    # Supply the document password for initialization.
    # (If no password is set, give an empty string.)
    doc.initialize(password)
    # Check if the document allows text extraction. If not, abort.
    if not doc.is_extractable:
        raise PDFTextExtractionNotAllowed('Extraction is not allowed: %r' % fp)
    return (doc, num_value(dict_value(doc.catalog.get("Pages")).get("Count")))

def continue_process_pdf(doc, rsrcmgr, device, pagenos=None, maxpages=0, password='', verbose=False):
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    # Process each page contained in the document.
    for (pageno,page) in enumerate(doc.get_pages()):
        if pagenos and (pageno not in pagenos): continue
        if verbose:
            print "Processing page", pageno + 1
        interpreter.process_page(page)
        if maxpages and maxpages <= pageno+1: break
    return

def num_value2(x):
    x = resolve1(x)
    if not (isinstance(x, int) or isinstance(x, float)):
        return None
    return x

def num_value_none(x):
    if x == None:
        return None
    x = resolve1(x)
    if not (isinstance(x, int) or isinstance(x, float)):
        if STRICT:
            raise PDFTypeError('Int or Float required: %r' % x)
        return 0
    return x
   
def str_value_none(x):
    if x == None:
        return None
    x = resolve1(x)
    if not isinstance(x, str):
        if STRICT:
            raise PDFTypeError('String required: %r' % x)
        return ''
    return x

def list_value2(x):
    x = resolve1(x)
    if not (isinstance(x, list) or isinstance(x, tuple)):
        if STRICT:
            raise PDFTypeError('List required: %r' % x)
        return None
    return x

def list_value_none(x):
    if x == None:
        return None
    x = resolve1(x)
    if not (isinstance(x, list) or isinstance(x, tuple)):
        if STRICT:
            raise PDFTypeError('List required: %r' % x)
        return []
    return x

def dict_value2(x):
    x = resolve1(x)
    if not isinstance(x, dict):
        if STRICT:
            raise PDFTypeError('Dict required: %r' % x)
        return None
    return x

def dict_value_none(x):
    if x == None:
        return None
    x = resolve1(x)
    if not isinstance(x, dict):
        if STRICT:
            raise PDFTypeError('Dict required: %r' % x)
        return ''
    return x

def stream_value2(x):
    x = resolve1(x)
    if not isinstance(x, PDFStream):
        if STRICT:
            raise PDFTypeError('PDFStream required: %r' % x)
        return None
    return x

def stream_value_none(x):
    if x == None:
        return None
    x = resolve1(x)
    if not isinstance(x, PDFStream):
        if STRICT:
            raise PDFTypeError('PDFStream required: %r' % x)
        return None
    return x

def literal_name_none(x):
    if x == None:
        return x
    else:
        return literal_name(x)
