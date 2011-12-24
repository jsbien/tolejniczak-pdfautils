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

# klasa implementuje mapowanie z nazw postscriptowych fontu na rodzine fontu
# ladowane z pliku
# plik powinien miec postac:
# NAZWA_POSCTSCRIPTOWA<TAB>RODZINA_FONTU<NL>
# jezeli konwerter nie znajdzie rodziny fontu to wypisze komunikat informujacy
# o tym, dla jakiej nazwy posctiscriptowej brak rodziny i stad wiadomo jaka
# podac w pliku
class FontMap:

	def __init__(self, file):
		fp = open(file)
		self.__dict = {}
		for line in fp:
			line = line[:-1]
			if line == "":
				continue
			els = line.split("\t")
			self.__dict.setdefault(els[0], els[1])
		fp.close()
	
	def getName(self, psname):
		return self.__dict.get(psname)
