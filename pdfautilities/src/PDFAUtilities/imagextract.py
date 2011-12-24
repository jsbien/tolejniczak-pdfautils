#!/usr/bin/python
# coding: utf-8
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
import pdfaimg
import wx
from utils import pbm2bmp

# proba implementacji konwertera PBM na RGB  - strasznie nieefektywna
# zamiast tego jest uzywany PIL (patrz pbm2bmp w utils.py)
def pbm2rgb(img, width, height, parent):
	res = ""
	j = 0
	#print len(img)
	padwidth = (len(img) * 8)/ height
	#print padwidth, width
	dialog = wx.ProgressDialog("Loading image", "Loading image, please wait...", 100, parent, wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
	ind = -1
	for c in img:
		ind += 1
		dialog.Update((float(ind) / float(len(img))) * 100, "Loading image, please wait...")
		c = ord(c)
		for i in range(8):
			if j % padwidth < width:
				if (c >> (7 - i)) & 1 == 0:
					res += chr(255)
					res += chr(255)
					res += chr(255)
				else:
					res += chr(0)
					res += chr(0)
					res += chr(0)
			#else:
				#print j % padwidth
			j += 1
			#if j > leng:
			#	return res
	dialog.Destroy()
	#assert(i == len)
	#print j, leng, 2398 * 3207
	return res

# wyciaga obrazek z pliku
# znaczenie parametrow - patrz PDFAUtilitiesCpp, metoda getImage
def getWxImage(path, page, num, gen, mask, parent):
	#print type(path), type(page), type(num), type(gen), type(mask), type(page)
	img = pdfaimg.getImage(str(path.encode("utf-8")), num, gen, mask, page)
	#if len(img) == 0:
	#	print "getwx"
	width = (ord(img[0]) << 8) | ord(img[1])
	height = (ord(img[2]) << 8) | ord(img[3])
	jpeg = ord(img[4])
	pbm = ord(img[5])
	#print width, height, jpeg, pbm
	img = img[6:]
	if len(img) == 0:
		return (None, 0, 0)
	#	print "none"
	sio = StringIO(img)
	if jpeg:
		imag = wx.ImageFromStream(sio).ConvertToBitmap()
	elif pbm:
		#nsio = StringIO(pbm2bmp("P4\n" + str(width) + " " + str(height) + "\n" + img).tostring())
		#imag = wx.ImageFromStream(nsio).ConvertToBitmap()
		imag = wx.ImageFromData(width, height, pbm2bmp("P4\n" + str(width) + " " + str(height) + "\n" + img).convert("RGB").tostring()).ConvertToBitmap()
			# zanim przekazemy do konwertera musimy dopisac przed danymi o pikselach
			# troche informacji zeby to udawalo plik PBM
	#elif pbm:
	#	imag = wx.ImageFromData(width, height, pbm2rgb(img, width, height, parent)).ConvertToBitmap()
	else:
		imag = wx.ImageFromData(width, height, img).ConvertToBitmap()
	sio.close()
	return (imag, width, height) # width height nie wykorzystywane, wydawalo mi sie
		# ze te wymiary sa inne niz podane w slowniku obrazka w PDF, wiec chcialem
		# wyswietlac i te i te, ale okazalo sie ze sa takie same wiec z tego
		# zrezygnowalem 
