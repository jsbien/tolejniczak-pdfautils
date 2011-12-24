"""
Copyright (c) 2010-2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>

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

import gc
import wx
import sys
import os
import uuid
import copy
from taglib import Font, Node, TagLib
from physbrowser import PhysList, ImagePanel
from hocrexport import HOCRExporter
from pdfminerparser import PDFMinerParser
from pdfminerconverter import PDFMinerNode, XMLLib
from dialogs import ModeDialog, SimpleModuleDialog
from columnize import Columnizer
import time
from threading import Timer
import wx.richtext as rt
import Image

# UWAGA, "TODO: I" oznaczaja miejsca na ktore nalezy zwrocic uwage

# TODO: D analyze (do poziomu lini + renderowanie popplerem)
# TODO: D wyswietlanie tekstu od razu po kliknieciu na span, bez dzieci
# TODO: D poprawic wyswietlanie obrazkow (efektywnosc po zoomie)

# przez tryb XML rozumiemy wyswietlanie ukladu strony zanalizowanego przez pdfminera
# a przez tryb PDF wyswietlanie struktury logicznej z PDF
# elementy struktury logicznej i ukladu strony bedziemy w skrocie nazywac elementami
# struktury a drzewo struktury logicznej i drzewo ukladu strony drzewami struktury

# w trybie PDF przez identyfikator strony (pageid) rozumiemy identyfikator pdfowego obiektu
# strony
# w trybie XML identyfikator strony (pageid) to indeks strony liczony od zera (bo jezeli
# drzewo struktury w trybie XML wczytalismy naprawde z XML to nie mamy informacji o
# identyfikatorach obiektow stron z PDF); tam gdzie w trybie XML wczytalismy drzewo
# z pliku PDF przetworzonego przez analizator ukladu strony pdfminera i potrzebny
# nam jest identyfikator obiektu strony PDF mozemy go uzyskac metoda
# PDFMinerNode.getRealPageId (patrz metody MainWindow.__onNext, MainWindow.__onPrev
# i MainWindow.__onEnter - tam jest nam potrzebne bo chcemy znalezc slownik zasobow
# strony w PTree, a tam strony sa identyfikowane przez identyfikator obiektu strony
# PDF)

# klasa rysuje strone w przegladarce graficznej
class Preview(wx.Panel):
#class Preview(wx.ScrolledWindow):
	# TODO: D poprawic wyswietlanie informacji o fontach pokazywanego tekstu
	
	def __init__(self, *args, **kwargs):
		#wx.ScrolledWindow.__init__(self, *args, **kwargs)
		wx.Panel.__init__(self, *args, **kwargs)
		self.__els = [] # lista elementow struktury do wyswietlenia (sa to te elementy
			# poddrzewa __page)
		self.__texts = [] # lista znakow do wyswietlenia (obiekty klasy PDFMinerNode
			# reprezentujace elementy "text" z ukladu strony zanalizowanego przez
			# pdfminera)
		self.__frame = None # obiekt klasy MainWindow (glowne okno aplikacji) w ktorym
			# jest dany obiekt klasy Preview
		self.__page = None # wezel poddrzewa struktury zwrocony przez
			# [XMLLib/TagLib].getStructureToDraw(ById) - zawiera wszystkie elementy
			# ktore mamy wyswietlic
		self.__pageid = None # identyfikator strony
		self.__text = False # czy wyswietlac tekst
		self.Bind(wx.EVT_PAINT, self.__onPaint)
		self.Bind(wx.EVT_MOUSEWHEEL, self.__onWheel)
		self.Bind(wx.EVT_MOTION, self.__onMotion)
		self.__scale = 1.25 # sklala obrazu - zwiekszajac ja pomniejszamy obraz,
			# a zmniejszajac powiekszamy
		self.__y = None # pozycja myszki przy ostatnim wywolaniu __onMotion bedacego
		self.__x = None # przeciaganiem myszy - pozwala nam obliczac przesuniecie myszki
		self.__startx = 0 # te dwie wartosci definiujam na przesuniecie - zwiekszajac
		self.__starty = 0 # __startx przesuwamy obrazek w prawo, a zwiekszajac __starty
			# przesuwamy go w dol
		self.__pagebbox = None # bounding box rysowanej strony
		self.SetBackgroundColour("#ffffff")
	
	# przygotowanie obiektu do wczytania nowego pliku
	def restart(self):
		self.__page = None
		self.__pageid = None
		self.__pagebbox = None
		self.__els = []
		self.__texts = []
	
	# zmienia wartosc flagi tekst po nacisnieciu na odpowiedni przycisk w glownym oknie
	# nastepnie wywoluje setPageToView by uwzglednic zmiane w strukturach __els i __texts 
	def onText(self):
		#print "ontext!!!"
		self.__text = not self.__text
		if self.__page != None:
			self.setPageToView(self.__page, self.__pageid)
	
	# oblicza o ile przesunela sie myszka od ostatniego wywolania zdarzenia bedacego
	# przeciaganiem myszy i na tej podstawie modyfikuje __startx i __starty
	# przemieszczajac obrazek
	# (daje to efekt przeciagania obrazu mysza)
	def __onMotion(self, event):
		# TODO: D sprawdzic czy nie da sie poprawic efektywnosc przez rozne bufory
		if self.__page == None:			
			return
		if event.Dragging():
			if self.__y == None or self.__x == None:
				self.__x = event.GetPosition()[0]
				self.__y = event.GetPosition()[1]
			else:
				dx = self.__x - event.GetPosition()[0]
				dy = self.__y - event.GetPosition()[1]
				self.__x = event.GetPosition()[0]
				self.__y = event.GetPosition()[1]
				self.__startx -= dx * self.__scale
				self.__starty -= dy * self.__scale
				self.redraw()
		else:
			self.__x = None
			self.__y = None
	
	# na podstawie ruchu kolka myszy oddala lub przybliza obrazek 
	def __onWheel(self, event):
		if self.__page == None:
			return
		if event.m_wheelRotation > 0:
			self.__scale /= 1.5
		else:
			self.__scale *= 1.5
		#self.AdjustScrollbars()
		#self.SetScrollbars(1, 1, self.__pagebbox[2] / self.__scale, self.__pagebbox[3] / self.__scale, 0, 0, True)
		self.redraw()
	
	# zdarzenie wx.EVT_PAIN
	def __onPaint(self, event):
		self.__draw(wx.PaintDC(self))
		#print "paint"

	# wlasciwa metoda rysujaca strone
	def __draw(self, dc):
		# TODO: E kolejnosc rysowania elementow
		tagmodel = self.__frame.getTagModel() # pobieramy model (elementy z jakimi
			# tagami getStandardText() chcemy rysowac i w jakim kolorze)
		if self.__pagebbox == None: # bo np nie zaladowalismy zadnego pliku?
			return
		#(self.__startx, self.__starty) = self.CalcScrolledPosition(0, 0)
		top = self.__pagebbox[3]
		bbox = copy.deepcopy(self.__pagebbox)
		bbox[1] = top - bbox[1] + self.__starty
		bbox[3] = top - bbox[3] + self.__starty
		bbox[2] += self.__startx
		bbox[0] += self.__startx
		dc.SetPen(wx.Pen("#000000"))
		#self.__scale = 1
		#dc.SetUserScale(self.__scale, self.__scale)
		# rysujemy strone:
		dc.DrawRectangle(bbox[0]/self.__scale, bbox[3]/self.__scale, (bbox[2] - bbox[0])/self.__scale, (bbox[1] - bbox[3])/self.__scale)
		for el in self.__els: # najpierw zaznaczamy element z wlaczana flaga (PDFMiner)Node.__selected 
			#if el[2].isSelected():
			if el.isSelected():
				#bbox = copy.deepcopy(el[1])
				bbox = copy.deepcopy(el.getBbox())
				bbox[1] = top - bbox[1] + self.__starty
				bbox[3] = top - bbox[3] + self.__starty
				bbox[2] += self.__startx
				bbox[0] += self.__startx
				dc.SetBrush(wx.Brush("#ffff00"))
				dc.SetPen(wx.Pen("#000000", style=wx.TRANSPARENT))
				dc.DrawRectangle(bbox[0]/self.__scale + 1, bbox[3]/self.__scale + 1, (bbox[2] - bbox[0])/self.__scale, (bbox[1] - bbox[3])/self.__scale)
		for el in self.__els: # potem elementy	
			#model = tagmodel.get(el[0])
			model  = tagmodel.get(el.getStandardText())
			if model != None and model[0]:
				dc.SetPen(wx.Pen(model[1], 1))
				#bbox = copy.deepcopy(el[1])
				bbox = copy.deepcopy(el.getBbox())
				#print el[2].getStandardText(), bbox
				#print el[1], bbox, el
				bbox[1] = top - bbox[1] + self.__starty
				bbox[3] = top - bbox[3] + self.__starty
				bbox[2] += self.__startx
				bbox[0] += self.__startx
				dc.DrawLine(bbox[0]/self.__scale, bbox[1]/self.__scale, bbox[2]/self.__scale, bbox[1]/self.__scale)
				dc.DrawLine(bbox[0]/self.__scale, bbox[1]/self.__scale, bbox[0]/self.__scale, bbox[3]/self.__scale)
				dc.DrawLine(bbox[2]/self.__scale, bbox[3]/self.__scale, bbox[0]/self.__scale, bbox[3]/self.__scale)
				dc.DrawLine(bbox[2]/self.__scale, bbox[3]/self.__scale, bbox[2]/self.__scale, bbox[1]/self.__scale)		
		if self.__text: # potem rysujemy tekst (to tylko dziala w trybie XML)
			# TODO: I to jest bardzo nieefektywne - uzyc popplera do normalnego
			# zrenderowania strony
			for c in self.__texts:
				(t, bbox) = c
				#print t,
				topp = (top - bbox[3] + self.__starty) / self.__scale
				left = (bbox[0] + self.__startx) / self.__scale
				#print t, top, left
				height = (bbox[3] - bbox[1]) / self.__scale
				# width = (bbox[2] - bbox[0]) / self.__scale
				dc.SetPen(wx.Pen("#000000", 1))
				font = dc.GetFont()
				#print width, height
				#font.SetPixelSize((width, height)) - pod Windows dzialalo, pod
					# gnome nie
				if height != 0:
					font.SetPixelSize((height, height))
				dc.SetFont(font)
				dc.DrawText(t, left, topp)
	
	# ustawia do wyswietlania przez ten obiekt strone o danym identyfikatorze
	# i wypelnia struktury __els i __texts majac dane jako parametr poddrzewo
	# struktury z elementami z tej strony
	def setPageToView(self, page, pageid):
		if page == None: # kiedy to moze sie zdarzyc?
			page = "DUMMY"
		self.__pageid = pageid
		self.__pagebbox = self.__frame.getLib().getPageBBox(pageid)
		#self.SetScrollbars(1, 1, self.__pagebbox[2], self.__pagebbox[3], 0, 0, True)
		#self.__frame.getLib().getNodeDict().clear()
		self.__els = []
		self.__texts = []
		self.__page = page
		if page != "DUMMY":
			self.__traverse(page) # tu wypelniamy __els i __texts
		#print self.__els, self.__texts	
		self.redraw()
	
	def getPageId(self):
		return self.__pageid
		
	def getPageToView(self):
		return self.__page
	
	# wypelnia pola __els i __texts przechodzac po poddrzewie struktury node
	def __traverse(self, node):
		if node.getBbox() == None:			
			return
		if node.getBbox() != None:
			#self.__els.append((node.getStandardText(), node.getBbox(), node))
			self.__els.append(node)
		#print node.isLeaf(), node.getStandardText(), self.__text
		if node.isLeaf() and node.getStandardText() == "text" and self.__text:
			for c in node.getChildren():
				if isinstance(c, unicode):
					self.__texts.append((c, node.getBbox()))
					break # TODO: NOTE wiecej nie powinno byc
		if not node.isLeaf():
			for c in node.getChildren():
				if isinstance(c, Node) or isinstance(c, PDFMinerNode):
					self.__traverse(c)
	
	# odwieza rysowana strone (lub rysuje nowa jesli sie zmienila)
	def redraw(self):
		self.ClearBackground()
		self.__draw(wx.MemoryDC())
		self.Refresh()

	def setFrame(self, frame):
		self.__frame = frame

# obiekt reprezentuje kontrolke pokazujaca drzewo struktury logicznej w formie drzewa
class LazyTree(wx.TreeCtrl):

	def __init__(self, *args, **kwargs):
		wx.TreeCtrl.__init__(self, *args, **kwargs)
		self.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.__onExpand)
		self.Bind(wx.EVT_TREE_ITEM_COLLAPSING, self.__onCollapse)
		self.Bind(wx.EVT_TREE_SEL_CHANGED, self.__onClick)
		self.__collapsing = False # potrzebne w __onCollapse 
		self.__dict = {} # slownik w ktorym elementy drzewa sa identyfikowane przez
			# jednoznaczne identyfikatory
			# te identyfikatory sa przechowywane w elementach drzewa kontrolki (items)
			# i po nich mozemy przejsc od elementu drzewa kontrolki do elementu drzewa
			# struktury ktoremu on odpowiada 
		self.__textCtrl = None # pole tekstowe w ktorym wyswietlamy zawartosc tekstowa
			# elementow drzewa struktury 
		self.__metaCtrl = None # pole tekstowe w ktorym wyswietlamy atrybuty elementu
			# struktury logicznej PDF i wartosci pod kluczami /ActualText, /Alt i
			# /Lang w tym elemencie
		self.__pageCtrl = None # kontrolka wyswietlajaca numer strony w glownym oknie
		self.__mode = "PDF" # tryb (patrz poczatek pliku)
		self.__lib = None # TagLib lub XMLLib z ktorego mozemy pobrac pewne informacje
			# o wczytanym pliku
		self.__nextFontId = 0 # identyfikator fontu w oknie __textCtrl (patrz __onClick)
		self.__fontIdMap = {} # mapowanie identyfikatorow na fonty w oknie __textCtrl (patrz __onClick)
		self.__fontMode = "LINKS" # tryb wyswietlania infomracji o fontach (patrz __onClick)
		self.__selected = None # element drzewa struktury ktory wybralismy w tej
			# kontrolce i ktory chcemy zaznaczyc w oknie rysowania strony,
			# ktorego zawartosc tekstowa chcemy pokazac w __textCtrl a rozne inne
			# informacje o nim w __metaCtrl 
		self.__preview = None # okno rysowania strony w glownym oknie
		self.__frame = None # glowne okno (obiekt klasy MainWindow)
	
	# przygotowanie obiektu do wczytania nowego pliku
	# drzewo jest czyszczone w setRoot i setXMLRoot przy wczytywaniu nowego
	# pliku
	def restart(self):
		self.__dict = {}
		self.__lib = None
		self.__fontIdMap = {}
	
	def setFrame(self, frame):
		self.__frame = frame
		
	def setPreview(self, preview):
		self.__preview = preview
	
	def setLib(self, lib):
		self.__lib = lib

	def setTextCtrl(self, textCtrl, metaCtrl):
		self.__textCtrl = textCtrl
		self.__metaCtrl = metaCtrl
	
	def setPageCtrl(self, pageCtrl):
		self.__pageCtrl = pageCtrl

	# dodaje do kontrolki drzewo struktury reprezentowane przez korzen pdfRoot i
	# ustawia tryb na PDF
	def setRoot(self, pdfRoot):
		self.__mode = "PDF"
		# TODO: I uuid w zasadzie nie miesci sie w incie - to trzeba zmienic
		# (jest obcinany, a wiec moga sie zdarzyc dwa takie same)
		uid = wx.TreeItemData(str(uuid.uuid1()))
		self.DeleteAllItems() # czyscimy wszystkie items (wezly drzewa w kontrolce)
		root = self.AddRoot('StructTreeRoot', data=uid) # dodajemy korzen (zostaje
			# utworzone item bedace korzeniem w kontrolce przechowujace klucz po
			# ktorym ze slownika __dict mozemy wyciagnac wlasciwy korzen
		self.__dict.setdefault(uid.GetData(), pdfRoot) # dodajemy do slownika
			# klucz po ktorym mozemy sie dostac do elementu przechowywanego w
			# item
		self.SetItemHasChildren(root) # zaznaczamy, ze korzen ma dzieci (bedzie go
			# mozna rozwinac)
	
	# j.w. ale tryb XML
	def setXMLRoot(self, xmlRoot):
		self.__mode = "XML"
		uid = wx.TreeItemData(str(uuid.uuid1()))
		self.DeleteAllItems()
		root = self.AddRoot('XML Root', data=uid)
		self.__dict.setdefault(uid.GetData(), xmlRoot)
		self.SetItemHasChildren(root)
	
	def getMode(self):
		return self.__mode
		
	# element bedacy korzeniem drzewa struktury
	def getRootNode(self):
		return self.__dict[self.GetItemData(self.GetRootItem()).GetData()]

	# rozwijamy wezel drzewa kontrolki, teoretycznie dopiero tu powinna byc wywolana
	# metoda __initialize na odpowiadajacym mu wezle drzewa struktury (jesli jest to
	# Node a nie PDFMinerNode), ale tak sie nie zawsze (lub nawet nigdy) dzieje
	# (patrz ostatnia uwaga w TagLib.uninitialize i por. uzycie metody Node.getPageIds
	# w __onClick)  
	def __onExpand(self, event):
		#print event.GetItem()
		#print self.__dict
		for (k, v) in self.__dict.iteritems():
			print k, v
		node = self.__dict[self.GetItemData(event.GetItem()).GetData()] # wezel
			# drzewa struktury odpowiadajacy rozwinietemy wezlowi drzewa kontrolki
		for l in node.getChildren():
			uid = wx.TreeItemData(str(uuid.uuid1()))
			#child = self.AppendItem(event.GetItem(), textOf(l), data=uid)
			text = l.getText() # tu rozrozniamy getText i getRole
			if self.__mode == "XML" and l.getStandardText() == "page":
				text += " " + str(l.getPageId() + 1) # jesli to strona w trybie XMl
					# to dopisujemy jej numer bo ulatwia to nawigacje; w trybie PDF
					# nie ma elementow reprezentujacych strony
			if l.getRole() != None:
				text += " (" + l.getRole() + ")"
			child = self.AppendItem(event.GetItem(), text, data=uid)
			self.__dict.setdefault(uid.GetData(), l)
			if not (l.isLeaf() or (self.__mode == "XML" and l.getStandardText() == "textline")):
				# nie wyswietlamy w kontrolce elementow typu "text" w trybie PDF (bo nie ma
				# robienie osobnych wezlow dla kazdego znaku) - dlatego traktujemy
				# ich rodzicow (elementy typu "textline") jak liscie 
				self.SetItemHasChildren(child, True) # por. setRoot
	
	# wyswietla zawartosc wybranego w kontrolce elementu w oknie rysowania strony,
	# w oknie __textCtrl i w oknie __metaCtrl; a takze zmienia pokazywana strone na
	# pierwsza ze strona na ktorej lezy element
	def __onClick(self, event):
		self.__textCtrl.Clear()
		item = event.GetItem()
		uid = self.GetItemData(event.GetItem()).GetData()
		#try:
		#	node = self.__dict[uid]		
		#except KeyError: # Empty
		#	return
		node = self.__dict[uid] # wezel drzewa struktury odpowiadajacy
			# rozwinietemu wezlowi drzewa kontrolki
		if isinstance(node, PDFMinerNode): # PDFMinerNode i Node maja rozne mechanizmy
				# zaznaczania, wynika to z tego ze XMLLib.getStructureToDrawById
				# zwraca elementy z tego samego drzewa co drzewo wyswietlane w tej
				# kontrolce, a TagLib.getStructureToDrawById zwraca nowo utworzone
				# elementy (tzn. w przypadku XMLLib ten sam element drzewa w drzewie
				# ktore wyswietla ta kontrolka i w poddrzewie zwroconym przez
				# getStructureToDrawById reprezentuje ten sam obiekt PDFMinerNode,
				# a w przypadku TagLib dwa ronze elementy Node)
			if self.__selected != None:
				self.__selected.unselect()
			self.__selected = node
			node.select()
			#print "selected", node.isSelected(), node.getStandardText(), node.getObjId()
		elif isinstance(node, Node):
			self.__metaCtrl.SetValue(node.getMetadata())
			self.__lib.select(node.getObjId()) # wybieramy obiekt do zaznaczenia -
				# - zeby zaznaczenie bylo widoczne musi byc wywolane getStructureToDrawById
				# poniej!
			self.__preview.redraw()
		if (isinstance(node, Node) or isinstance(node, PDFMinerNode)) and not node.isRoot(): # nie
				# ma sensu w przypadku korzenia, bo niejako z definicji lezy on na wielu stronach
				# (ale uwaga - w przypadku PDF jezeli dzieckiem korzenia bedzie np. element typu
				# "Document" to on tez jest na wielu stronach, ale nie jest traktowany jako korzen) 
			pageids = node.getPageIds() # tu bedzie zainicjalizowane cale poddrzewo
				# z korzeniem w node, co psuje caly mechanizm zarzadzania pamiecia
				# wspomniany przy __onExpand i Node.uninitialize) 
			if len(pageids) > 0:
			#pageids = [node.getPageId()]
			#if pageids != [None]:
				pageNo = self.__lib.getPageNoById(pageids[0]) # jak element lezy na
					# wiecej niz jednej stronie to po prostu pokazujemy jedna z nich
				self.__pageCtrl.SetValue(str(pageNo)) # zmieniamy strone na ta na
				self.__frame.setPageNo(pageNo)        # na ktorej lezy element
				self.__preview.setPageToView(self.__lib.getStructureToDrawById(pageids[0]), pageids[0])
					# przekazuje do okna rysowania strony poddrzewo do narysowania
			#self.__preview.SetPageToView(self.__lib.getNodesToDraw())
		if not self.ItemHasChildren(item): # and self.GetItemText(item) != "Empty":
			#print "=", self.__textCtrl.GetInsertionPoint()
			self.__textCtrl.SetInsertionPoint(0)
			self.__textCtrl.SetDefaultStyle(rt.TextAttrEx())
			#self.__textCtrl.SetDefaultStyleToCursorStyle()
			#print ":", self.__textCtrl.GetInsertionPoint()
			#self.__textCtrl.MoveCaret(0, True)
			#self.__textCtrl.EndAllStyles()
			#self.__textCtrl.EndURL()
			#self.__textCtrl.EndUnderline()
			#self.__textCtrl.EndTextColour()
			#self.__textCtrl.EndAllStyles()
			self.__textCtrl.Clear()
			self.__nextFontId = -1
			self.__textCtrl.resetURLMap()
			self.__fontIdMap = {}
			self.__metaCtrl.SetValue("Type: " + node.getContentType() + "\n" + node.getMetadata())
			if self.__mode == "XML" and node.getStandardText() == "textline":
				children = []
				for c in node.getChildren():
					for cc in c.getChildren():
						if isinstance (cc, unicode):
							children.append(cc)
			else: 
				children = node.getChildren()
			it = False
			bl = False
			sz = False			
			for c in children:
				if isinstance(c, Font):
					self.__nextFontId += 1 # kazdy font ma identyfikator, kolejnym napotkanym
						# fontom sa przydzielane identyfikatory bedace kolejnymi liczbami
						# naturalnymi
					self.__fontIdMap.setdefault(self.__nextFontId, c) # zapamietujemy
						# mapowanie z identyfikatora do fontu
					if self.__fontMode == "LINKS" or self.__fontMode == "WYSILINKS":
						self.__appendURL(self.__nextFontId) # umieszczamy w oknie __textCtrl
							# link do fontu o danym identyfikatorze (mozemy nadawac linkom
							# identyfikatory, dlatego po kliknieciu na link (metoda onURL)
							# i majac jego identyfikator (bedacy zarazem identyfikatorem fontu)
							# mozemy odnalezc font po identyfikatorze w __fontIdMap
					if self.__fontMode == "WYSIWYG" or self.__fontMode == "WYSILINKS":
						# tryby:
						# LINKS - tylko linki do fontow
						# WYSILINKS - linki do fontow i tekst wyswietlany w stylu fontu
						# WYSIWYG - tylko tekst wyswietlany w stylu fontu
						# w tej chwili na sztywno zaprogramowany jest styl LINKS i 
						# nie ma mozliwosci zmiany stylu w przegladarce
						# TODO: I trzeba doimplementowac mozliwosc zmiany trybu
						if it:
							self.__textCtrl.EndItalic()
							it = False
						if bl:
							self.__textCtrl.EndBold()
							bl = False
						if sz:
							self.__textCtrl.EndFont()
							self.__textCtrl.EndFontSize()
						if c.italic:
							self.__textCtrl.BeginItalic()
							it = True
						if c.bold:
							self.__textCtrl.BeginBold()
							bl = True
						#font = wx.Font(c.size, c.name, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
						self.__textCtrl.BeginFontSize(c.size)
						#self.__textCtrl.BeginFont(font) TODO: D dlaczego to nie dziala?
						sz = True		
				else:
					self.__textCtrl.WriteText(c)
			if it:
				self.__textCtrl.EndItalic()
			if bl:
				self.__textCtrl.EndBold()
			if sz:
				#self.__textCtrl.EndFont()
				self.__textCtrl.EndFontSize()
			#self.__textCtrl.AppendText(self.__dict[uid])
		pass

	# umieszczamy w oknie __textCtrl link do fontu o danym identyfikatorze
	def __appendURL(self, id):
		self.__textCtrl.BeginTextColour("#0000ff")
		self.__textCtrl.BeginBold()
		self.__textCtrl.BeginUnderline()
		self.__textCtrl.BeginURL(str(id)) # nadajemy linkowi identyfikator bedacy
			# jednoczesnie identyfikatorem fontu
		self.__textCtrl.WriteText("*") # w oknie __textCtrl link bedzie oznaczony
			# gwiazdka
		self.__textCtrl.addURL() # patrz opis przy tej metodzie
		self.__textCtrl.EndURL()
		self.__textCtrl.EndTextColour()
		self.__textCtrl.EndBold()
		self.__textCtrl.EndUnderline()
	
	def __onCollapse(self, event):
		#print self.__collapsing
		#print "oncollapse"
		if self.__collapsing:
			event.Veto()
		else:
			self.__collapsing = True
			item = event.GetItem()
			node = self.__dict[self.GetItemData(item).GetData()]
			if node.isSelected():
				node.unselect()
				self.__selected = None
				self.__preview.redraw()
			#print "unit", node.getText()
			if self.__mode == "PDF":
				node.uninitialize()
				# TODO: NOTE tu nie mozna uzyc unicjalizacji dla XML (z pdfa ladujemy sekwencyjnie tylko raz, nie ma tak jak przy prawdziwym pdfie ze mozemy sobie ponownie wczytywac ile chcemy)
			self.CollapseAndReset(item)
			self.SetItemHasChildren(item)
			self.__collapsing = False
	
	# kliknieto link do fontu w __textCtrl, sterowanie do tej metody jest przekazywane z
	# TagText.__onURL
	# klikniecie powoduje przelaczenie sie do trybu pokazywania slownika zasobow i
	# pokazanie w nim fontu
	def onURL(self, event):
		node = self.__fontIdMap.get(int(event.GetString())) # pobieramy ze slownika
			# obiekt klasy Font odpowiadajacy danemu identyfikatorowi
		self.__frame.switchTabs(node)
	
	# nazwa fontu do wyswietlenia po najechaniu na link (uzywane przez TagText) 
	def getFontName(self, id):
		font = self.__fontIdMap.get(id)
		return font.psname + ", " + str(font.size)

ID_OWN_TEXT = wx.ID_HIGHEST + 1

# modyfikacja klasy RichTextCtrl tak by po najechaniu mysza na link wyswietlila
# sie nazwa i rozmiar fontu
class TagText(rt.RichTextCtrl):
	
	# TODO: I to nie dziala do konca dobrze, nie zawsze po najechaniu mysza na link
	# pokazuje sie okienko z nazwa i rozmiarem fontu
	
	def __init__(self, *args, **kwargs):
		rt.RichTextCtrl.__init__(self, *args, **kwargs)
		self.__lastMotion = time.time()
		self.__timer = None
		self.__url2Pos = [] # lista pozycji w tekscie na ktorych zaczyna sie URL,
			# tekst miedzy dwoma URLami jest w foncie pierwszego URla
		#self.__tip = wx.ToolTip("")
		#self.__tip.SetDelay(0)
		#self.__tip.Enable(True)
		#self.SetToolTip(self.__tip)
		#self.__pos = (0, 0)
		#wx.ToolTip.Enable(True)
		#wx.ToolTip.SetDelay(0)
		#self.SetToolTipString("")
		#self.Bind(wx.EVT_MOTION, self.__onTextMotion, self)
		#self.Bind(wx.EVT_TEXT_URL, self.__onURL, self)
		self.__tree = None # obiekt LazyTree - pokazujemy zawartosc tekstowa jego
			# elementu i w razie klikniecia na link przekazujemy do niego (tzn.
			# do __tree) sterowanie
	
	# przygotowanie do wczytania nowego pliku
	def restart(self):
		self.__url2Pos = []

	# wylacza obsluge klikniecia na link i pokazywanie nazwy po
	# najechaniu nan mysza
	def disable(self):
		if self.__timer != None:
			self.__timer.cancel()
		self.SetToolTip(None)
		self.Unbind(wx.EVT_MOTION, self, self.__onTextMotion)
		self.Unbind(wx.EVT_TEXT_URL, self, self.__onURL)

	# wlacza obsluge klikniecia na link i pokazywanie nazwy po
	# najechaniu nan mysza
	# powinno byc wlaczane gdy otworzylismy plik PDF z uzyciem jego struktury logicznej
	# (nie z analizowaniem ukladu przez pdfminera)
	def enable(self):
		self.__tip = wx.ToolTip("")
		self.__tip.SetDelay(0)
		self.__tip.Enable(True)
		self.SetToolTip(self.__tip)
		self.Bind(wx.EVT_MOTION, self.__onTextMotion, self)
		self.Bind(wx.EVT_TEXT_URL, self.__onURL, self)
	
	def resetURLMap(self):
		self.__url2Pos = []
	
	# dodajemy do listy pozycji URLi aktualna pozycje karetki (czyli pozycje
	# dodawanego URLa w tekscie)
	def addURL(self):
		self.__url2Pos.append(self.GetCaretPosition())
	
	def setTree(self, tree):
		self.__tree = tree
	
	# kliknieto na link - przekazujemy sterowanie do obiektu LazyTree
	def __onURL(self, event):
		self.__tree.onURL(event)
	
	def __onTextMotion(self, e):
		(x, y) = e.GetPosition()
		(ok, pos) = self.HitTest((x, y))
		#print pos
		if ok == 0:
			self.__pos = pos
		else:
			self.__pos = -1
		#if b > 100.0:
		#	print "ok"
		#else:
		#	self.__tip.Enable(False)
		cur = time.time()
		diff = cur - self.__lastMotion
		self.__lastMotion = cur
		if diff < 0.1:
			if self.__timer != None:
				self.__timer.cancel()
				#print "timer"
				#wx.ToolTip.Enable(False)
				#wx.ToolTip.SetDelay(10000)
				#if self.__tip != None:
					#self.__tip.Enable(False)
				#self.SetToolTipString("")
				self.SetToolTip(None)
			self.__timer = Timer(0.1, self.__timeOut)
			self.__timer.start()
	
	def __timeOut(self):
		#print "TIMEOUT!!!"
		#self.__tip = wx.ToolTip("...")
		#self.__tip.Enable(True)
		#self.__tip.SetDelay(0)
		#self.SetToolTip(self.__tip)
		if self.__pos < 0:
			#print "zle"
			return
		i = -1
		j = len(self.__url2Pos) - 1
		# znajdujemy identyfikator URLa (czyli identyfikator fontu, patrz
		# LazyTree.__onClick) na podstawie jego pozycji w tekscie, korzystajac
		# z tego ze identyfiaktor URLa to jego numer przy liczeniu kolejnych
		# URLi od 0
		for pos in self.__url2Pos:
			i += 1
			if pos > self.__pos:
				j = i - 1
				break
		self.__tip = wx.ToolTip(self.__tree.getFontName(j)) # pobieramy nazwe i rozmiar
			# fontu na podstawie jego identyfikatora
		self.__tip.SetDelay(0)
		self.__tip.Enable(True)
		self.SetToolTip(self.__tip)
		#print "enabled"

# glowne okno przegladarki
class MainWindow(wx.Frame):

	def __init__(self, parent, title):
		wx.Frame.__init__(self, parent, title=title, size=(800, 600))
		self.CreateStatusBar()
		self.__fileLoaded = False # czy jest w tej chwili otwarty jakis plik
		filemenu = wx.Menu()
		menuOpen = filemenu.Append(wx.ID_ANY, "&Open", "Open a file")
		menuAnalize = filemenu.Append(wx.ID_ANY, "&Analize", "Open and analize file")
		menuExport = filemenu.Append(wx.ID_ANY, "&Export", "Export to hOCR format")
		menuExit = filemenu.Append(wx.ID_EXIT, "E&xit", "Terminate the program")
		menuBar = wx.MenuBar()
		menuBar.Append(filemenu, "&File")
		
		editmenu = wx.Menu()
		menuViewing = editmenu.Append(wx.ID_ANY, "&Viewing parameters", "Set viewing parameters")
		menuColumnize = editmenu.Append(wx.ID_ANY, "&Columnize", "Attempts to split page into given number of columns")
		menuColumnizeAll = editmenu.Append(wx.ID_ANY, "Columnize &all", "Attempts to split pages into given number of columns")
		menuExportImage = editmenu.Append(wx.ID_ANY, "&Export image", "Exports image")
		menuBar.Append(editmenu, "&Edit")
		
		self.__tabbed = wx.Notebook(self, -1)
		self.__page1 = wx.NotebookPage(self.__tabbed, -1)
		self.__page2 = wx.NotebookPage(self.__tabbed, -1)
		self.__tabbed.AddPage(self.__page1, "Logical structure")
		self.__tabbed.AddPage(self.__page2, "Physical structure")
		
		self.__splitter = wx.SplitterWindow(self.__page1, wx.ID_ANY)
		self.__subsplitter = wx.SplitterWindow(self.__splitter, wx.ID_ANY)
		self.__subsubsplitter = wx.SplitterWindow(self.__subsplitter, wx.ID_ANY)
		self.__control = LazyTree(self.__splitter, wx.ID_ANY) # kontrolka
			# wyswietlajaca drzewo struktury
		self.__splitter.SplitVertically(self.__control, self.__subsplitter, 200)
		self.__preview = Preview(self.__subsplitter) # kontrolka rysujaca strone
		#self.__preview.EnableScrolling(True, True)
		#self.__preview = wx.Panel(self.__subsplitter)
		self.__preview.setFrame(self)
		self.__control.setFrame(self)
		#self.preview.SetScrollbars(1, 1, self.preview.GetSize()[0], 1000, 0, 0, True)
		#self.preview.EnableScrolling(True, True)
		self.__text = TagText(self.__subsubsplitter, wx.ID_ANY, style=wx.TE_MULTILINE | wx.TE_AUTO_URL | wx.TE_READONLY)
			# kontrolka wyswietlajaca zawartosc tekstowa elementu struktury wraz z informacja o fontach
		self.__metaText = wx.TextCtrl(self.__subsubsplitter, wx.ID_ANY, style=wx.TE_MULTILINE | wx.TE_READONLY)
			# kontrolka wyswietlajaca atrybuty elementu struktury i inne dodatkowe informacje
			# (patrz Node.__contentType i Node.getMetadata())
		self.__subsubsplitter.SplitHorizontally(self.__text, self.__metaText, -200)
		self.__subsplitter.SplitVertically(self.__subsubsplitter, self.__preview, 200)
		#self.__subsplitter.Refresh()
		self.__control.setPreview(self.__preview)
		self.__text.setTree(self.__control)
		
		#self.Bind(wx.EVT_MOTION, self.__onTextMotion, self.__text)
		
		self.__splitter2 = wx.SplitterWindow(self.__page2, wx.ID_ANY)
		self.__splitter3 = wx.SplitterWindow(self.__splitter2, wx.ID_ANY)
		self.__tree2 = PhysList(self.__splitter2, wx.ID_ANY) # kontrolka wyswietlajaca
			# zawartosc slownika zasobow danej strony
		self.__text2 = rt.RichTextCtrl(self.__splitter3, wx.ID_ANY, style=wx.TE_MULTILINE | wx.TE_AUTO_URL | wx.TE_READONLY)
		self.__tree2.setFrame(self)
		#self.__image = wx.Panel(self.__splitter3, wx.ID_ANY)
		#self.__image = wx.StaticBitmap(self.__splitter3, wx.ID_ANY)
		self.__image = ImagePanel(self.__splitter3, wx.ID_ANY) # kontrolka wyswietlajaca
			# obrazek wybrany w kontrolce __tree2
		self.__image.EnableScrolling(True, True)
		self.__splitter2.SplitVertically(self.__tree2, self.__splitter3, 200)
		self.__splitter3.SplitHorizontally(self.__text2, self.__image, 200)
		self.__splitter3.Unsplit(self.__image)
		
		self.__tree2.setTextCtrl(self.__text2)
		self.__control.setTextCtrl(self.__text, self.__metaText)
		
		self.__toolbar = self.CreateToolBar()
		self.__toolbar.AddLabelTool(wx.ID_PREVIEW_PREVIOUS, "", wx.Bitmap("resources/prev.png"))
		#self.__toolbar.AddLabelTool(wx.ID_PREVIEW_PREVIOUS, "", wx.Bitmap("C:\\Users\\to\\workspace\\PDFAUtilities\\resources\\prev.png"))
		self.__pageNoCtrl = wx.TextCtrl(self.__toolbar, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
			# kontrolka wyswietlajaca numer aktualnie ogladanej strony
		self.__pageNoCtrl.SetSize((self.__pageNoCtrl.GetSize()[1] * 2.0, self.__pageNoCtrl.GetSize()[1]))
		self.__control.setPageCtrl(self.__pageNoCtrl)
		self.__pageNo = 0 # numer aktualnie ogladanej strony
		self.__maxPageNo = 0 # liczba stron w pliku
		self.__maxPageNoCtrl = wx.StaticText(self.__toolbar, wx.ID_ANY)
			# kontrolka wyswietlajaca liczbe stron w pliku - razem z __pageNoCtrl
			# tworzy w ten sposob zestaw: [2] of 10
		self.__maxPageNoCtrl.SetSize((self.__maxPageNoCtrl.GetSize()[1] * 3.0, self.__maxPageNoCtrl.GetSize()[1]))
		self.__maxPageNoCtrl.SetBackgroundStyle(wx.TRANSPARENT)
		self.__toolbar.AddControl(self.__pageNoCtrl)
		self.__toolbar.AddControl(self.__maxPageNoCtrl)
		self.__toolbar.AddLabelTool(wx.ID_PREVIEW_NEXT, "", wx.Bitmap("resources/next.png"))
		self.__toolbar.AddLabelTool(ID_OWN_TEXT, "", wx.Bitmap("resources/text.png"))
		#self.__toolbar.AddLabelTool(wx.ID_PREVIEW_NEXT, "", wx.Bitmap("C:\\Users\\to\\workspace\\PDFAUtilities\\resources\\next.png"))
		#self.__toolbar.AddLabelTool(ID_OWN_TEXT, "", wx.Bitmap("C:\\Users\\to\\workspace\\PDFAUtilities\\resources\\text.png"))
		self.__toolbar.Realize()
		
		self.SetMenuBar(menuBar)
		self.Bind(wx.EVT_MENU, self.__onExit, menuExit)
		self.Bind(wx.EVT_MENU, self.__onExport, menuExport)
		self.Bind(wx.EVT_MENU, self.__onOpen, menuOpen)
		self.Bind(wx.EVT_MENU, self.__onAnalize, menuAnalize)
		self.Bind(wx.EVT_MENU, self.__onViewing, menuViewing)
		self.Bind(wx.EVT_MENU, self.__onColumnize, menuColumnize)
		self.Bind(wx.EVT_MENU, self.__onColumnizeAll, menuColumnizeAll)
		self.Bind(wx.EVT_TOOL, self.__onNext, id=wx.ID_PREVIEW_NEXT)
		self.Bind(wx.EVT_TOOL, self.__onPrev, id=wx.ID_PREVIEW_PREVIOUS)
		self.Bind(wx.EVT_TOOL, self.__onText, id=ID_OWN_TEXT)
		self.Bind(wx.EVT_TEXT_ENTER, self.__onEnter, self.__pageNoCtrl)
		self.Bind(wx.EVT_MENU, self.__onExportImage, menuExportImage)
		self.Bind(wx.EVT_PAINT, self.__onPaint, self)
		self.Bind(wx.EVT_TEXT_URL, self.__onURL, self.__text2)
		#self.Bind(wx.EVT_PAINT, self.TOnPaint)
		
		self.__tags = [] # tagi (nazwy elementow struktury logicznej PDF lub elementow
			# ukladu strony zanalizowanego przez pdfminera) ktore sa uzywane w
			# strukturze wyswietlanej przez przegladarke;
		self.__tagmodel = {} # slownik okreslajacy, czy tagi z list __tags powinny
			# byc wyswietlane w oknie rysowania struktury strony (__preview)
		# dwie poprzednie struktury inicjalizowane w __onOpen i __onOpenXML
		# wartosciami domyslnymi
		# ustawienia __tagmodel mozna zmienic metoda __onViewing
		self.__root = None # korzen drzewa struktury pokazywanego pliku
		self.__lib = None # obiekt klasy TagLib udostepniajacy interfejs do obiektu
			# PDFDocument pdfminer a
		self.__physOnly = False # jezeli ma wartosc True to otworzylismy plik PDF
			# ktory nie zawiera struktury logicznej
		self.__columnizedPages = [] # lista numerow stron ktore zostaly podzielone na
			# kolumny (patrz __onColumnize)
	
	# przygotowanie obiektu i komponentow skladowych do wczytania nowego pliku
	# TODO: I powinno byc poddane kompleksowemu zarzadzaniu pamiecia
	def restart(self):
		self.__lib = None
		self.__root = None
		self.__tags = []
		self.__tagmodel = {}
		self.__control.restart()
		self.__tree2.restart()
		self.__text.restart()
		self.__preview.restart()
		self.__image.restart()
		gc.collect() # probujemy odzyskac troche pamieci

	# bez tego rozmiary okien rysuja sie nieprawidlowo
	# z jakiegos powodu pod Windows nie bylo to potrzebne
	def __onPaint(self, event):
		self.__splitter.SetSashPosition(200)
		self.__subsplitter.SetSashPosition(200)
		self.__splitter2.SetSashPosition(200)
		self.__splitter3.SetSashPosition(200)
		self.__subsubsplitter.SetSashPosition(-200)
		#self.Bind(event, handler, source, id, id2)
		self.Unbind(wx.EVT_PAINT, self, self.__onPaint)
		#self.Unbind(event, source, id, id2, handler)
	
	# pokazuje w kontrolce __image obrazek img (ktory jest bitmapa wxWidgets)
	# jezeli kontrolka byla schowana pokazuje ja
	def showImage(self, img):
		#self.__splitter3.SetSashPosition(200)
		#self.__image.Destroy()
		#self.__image = wx.StaticBitmap(self, wx.ID_ANY)
		#self.__image.SetBitmap(img)
		#self.__image.Refresh()
		if img != None:
			self.__image.setBMP(img)
			self.__image.SetScrollbars(20, 20, img.GetWidth() / 20.0, img.GetHeight() / 20.0, 0, 0, True)
			self.__image.setDimensions(img.GetWidth() / 20.0, img.GetHeight() / 20.0)
			self.__image.Refresh()
			self.__splitter3.SplitHorizontally(self.__text2, self.__image, 200)
		else: # tak sie zdarzy jak getWxImage nie uda sie znalezc?/rozkodowac? obrazka
			#print "refresh"
			self.__image.setBMP(None)
			self.__image.Refresh()
			self.__image.SetScrollbars(1, 1, 0, 0, 0, 0, True)
			self.__splitter3.SplitHorizontally(self.__text2, self.__image, 200)
	
	# chowa kontrolke __image
	def hideImage(self):
		self.__image.setBMP(None)
		self.__splitter3.Unsplit(self.__image)

	# kliknieto na link do kodowania lub przestrzeni kolorow (patrz metoda PhysList.onURL)
	# sterowanie zostaje przekazane do obiektu PhysList
	def __onURL(self, event):
		self.__tree2.onURL(event)

	def __onExit(self, e):
		#self.preview.Close()
		#print "onexit"
		if wx.MessageDialog(self, "Are you sure?", "Exit", wx.YES_NO).ShowModal() == wx.ID_YES:
			self.Close(True)
	
	# eksportuje obrazek widoczny w kontrolce __image i wybrany w przegladarce
	# slownika zasobow strona (__tree2) do pliku
	def __onExportImage(self, e):
		# TODO: F uzyc w konwerterze na hocr do wyciagania skanow tam gdzie sie da
		if self.__image.getBMP() != None: # czy jest wybrany jakis obrazek
			self.dirname = ""
			dlg = wx.FileDialog(self, "Specify file name", self.dirname, "", "*.*", wx.SAVE | wx.FD_OVERWRITE_PROMPT)
			if dlg.ShowModal() == wx.ID_OK:
				self.filename = dlg.GetFilename()
				self.dirname = dlg.GetDirectory()
				path = os.path.join(self.dirname, self.filename)
				img = wx.ImageFromBitmap(self.__image.getBMP())
				pil = Image.new('RGB', (img.GetWidth(), img.GetHeight()))
				pil.fromstring(img.GetData())
				pil.save(path)
			dlg.Destroy()

	# eksportuje otwarty plik do hOCR
	def __onExport(self, e):
		dirname = ""
		dlg = wx.FileDialog(self, "Specify file name", dirname, "", "*.html", wx.SAVE | wx.FD_OVERWRITE_PROMPT)
		if dlg.ShowModal() == wx.ID_OK:
			filename = dlg.GetFilename()
			dirname = dlg.GetDirectory()
			path = os.path.join(dirname, filename)
			dlg.Destroy()
			dlg = wx.MessageDialog(self, "Use special hOCR tags for fonts style?", "Export to hOCR", wx.YES_NO)
				# czy uzyc specjalnych elementow hOCR ocrx_italic i ocrx_bold do oznaczania fontow?
			if dlg.ShowModal() == wx.ID_YES:
				tags = True
			else:
				tags = False
			if self.__control.getMode() == "XML":
				hocr = HOCRExporter(self.__control.getRootNode(), path, self.__lib, xml=True, tags=tags)
			else:
				hocr = HOCRExporter(self.__control.getRootNode(), path, self.__lib, tags=tags)
			hocr.export()
			hocr.save()
		else:
			dlg.Destroy()

	# pozostalosc po niezaimplementowanym przechwytywaniu bledow MemoryError
	# TODO: X
	def open(self, file, mode):
		if mode == "PDFXML":
			self.__openXML(file, fromPDF=True, again=True)
		elif mode == "PDFXMLIGNORE":
			self.__openXML(file, fromPDF=True, ignoreGroups=True, again=True)
		elif mode == "PDF":
			self.__onOpen(None, path=file)
		elif mode == "XML":
			self.__openXML(file, again=True)
		elif mode == "XMLIGNORE":
			self.__openXML(file, ignoreGroups=True, again=True)
	
	# otwiera plik PDF ale zamiast wyciagac strukture logiczna z pliku analizuje
	# uklad strony pdfminerem i jego uzywa jako struktury
	# slowniki zasobow stron wyciaga z PDF
	def __onAnalize(self, e):
		self.dirname = ""
		dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
		if dlg.ShowModal() == wx.ID_OK:
			filename = dlg.GetFilename()
			dirname = dlg.GetDirectory()
			dlg.Destroy()
			dlg = wx.MessageDialog(self, "Ignore text groups?", "Analize layout", wx.YES_NO)
				# czy podczas analizy uklady strony igonrujemy elementy "textgroups"
				# (beda tylko elementy "textbox" bedace bezposrednimi dziecmi
				# elementow "page")
			if dlg.ShowModal() == wx.ID_YES:					
				self.__openXML(os.path.join(dirname, filename), fromPDF=True, ignoreGroups=True)
			else:
				self.__openXML(os.path.join(dirname, filename), fromPDF=True)
			dlg.Destroy()
		else:
			dlg.Destroy()

	# TODO: D tu i w konwerterze - sprawdzanie poprawnosci xml'a
	# otwiera plik PDF i wyciaga z niego strukture logiczna, jezeli okaze sie ze
	# plik PDF jej nie zawiera to pokazujemy tylko slowniki zasobow stron
	# jezeli okaze sie ze to nie jest PDF traktuje go jak XML pdfminera i probuje z
	# niego wyciagnac strukture logiczna
	# jezeli otwarty plik to PDF wyciaga tez z niego slowniki zasobow stron
	def __onOpen(self, e, path=None):
		# path to pozostalosc po niezaimplementowanym przechwytywaniu bledow
		# MemoryError, w normalnym funkcjonowaniu programu powinno byc None
		if path == None:
			dirname = ""
			dlg = wx.FileDialog(self, "Choose a file", dirname, "", "*.*", wx.OPEN)
		if path != None or dlg.ShowModal() == wx.ID_OK:
			try:
				if path == None:
					filename = dlg.GetFilename()
					dirname = dlg.GetDirectory()
				self.restart()
				self.__lib = TagLib(gui=True)
				if path == None:
					pdf = self.__lib.initialize(os.path.join(dirname, filename))
						# otwieramy plik PDF pdfminerem
				else:
					pdf = self.__lib.initialize(path)
				if not pdf: # to nie PDF, traktujemy go jak XML pdfminera
					#self.openXML(os.path.join(self.dirname, self.filename), dialog=dialog)
					dlg.Destroy()
					self.__physOnly = False
					dlg = wx.MessageDialog(self, "Ignore text groups?", "Analize layout", wx.YES_NO)
					if dlg.ShowModal() == wx.ID_YES:
						dlg.Destroy()
						self.__openXML(os.path.join(dirname, filename), ignoreGroups=True)
					else:
						dlg.Destroy()
						self.__openXML(os.path.join(dirname, filename))
					return
			except MemoryError:
				print "memory error"
				#if path != None:
				#	wx.MessageBox("Insuficient memory", "Error")
				#	exit()
				#os.system("pdfastructurebrowser " + os.path.join(dirname, filename) + " PDF")
				#exit()
				self.__app.ExitMainLoop()
				return
			self.__text.enable()
			if path == None:
				self.SetTitle(os.path.join(dirname, filename) + " - PDF structure browser")
			else:
				self.SetTitle(path + " - PDF structure browser")
			self.__fileLoaded = True
			self.__text.Clear() # czyscimy gui po porzednim pliku
			self.__text2.Clear() # j.w.
			self.__metaText.Clear() # j.w.
			self.hideImage() # j.w.
			if self.__lib.hasRoot(): # dokument zawiera drzewo struktury logicznej
				self.__physOnly = False
				self.__control.setRoot(self.__lib.getRoot()) # pokazujemy drzewo
					# struktury logicznej w kontrolce __control
				self.__control.setLib(self.__lib)
				self.__tree2.setRoot(self.__lib.getPhysicalTree()) # pokazujemy
					# slowniki zasobow stron w kontrolce __tree2 
				if path == None:
					self.__tree2.setPath(os.path.join(dirname, filename)) # przekazujemy
						# kontrolce PhysList sciezke do pliku (bedzie jej potrzebowac do
						# wywolania funkcji getWxImage)
				else:
					self.__tree2.setPath(path)
				if self.__lib.getPageNo() > 0:
					self.__tree2.show(self.__lib.getPageNos().get(1))
				# TODO: H stale
				# Copyright (C) 1985-2001 Adobe Systems Incorporated. All rights reserved
				self.__tags = ["Document", "Part", "Art", "Sect", "Div", "BlockQuote", "Caption",
							"TOC", "TOCI", "Index", "NonStruct", "Private", "P", "H", "H1", "H2", "H3", "H4", "H5", "H6", "L", "LI", "Lbl", "LBody",
							"Table", "TR", "TH", "TD", "THead", "TBody", "TFoot",
							"Span", "Quote", "Note", "Reference", "BibEntry", "Code",
							"Link", "Annot", "Ruby", "RB", "RT", "RP", "Warichu", "WT", "WP",
							"Figure", "Formula", "Form"] # domyslna wartosc __tags dla
								# struktury logicznej PDF
				for tag in self.__tags: # domyslna wartosc __tagmodel dla struktury
						# logicznej PDF 
					if tag == "Div":
						self.__tagmodel.setdefault(tag, (True, "#0000ff"))
					elif tag == "P":
						self.__tagmodel.setdefault(tag, (True, "#ff0000"))
					else:
						self.__tagmodel.setdefault(tag, (False, "#ffffff"))
				self.__pageNoCtrl.SetValue("1")
				self.__pageNo = 1 # ustawiamy numery aktualnie pokazywanej strony na 1
				self.__root = self.__lib.getRoot()
				#self.maxPageNo = self.__root.getPageNum()
				self.__maxPageNo = len(self.__lib.getPageNos().keys())
				self.__maxPageNoCtrl.SetLabel("of " + str(self.__maxPageNo))
				self.__preview.setPageToView(self.__lib.getStructureToDraw(1), self.__lib.getPageId(1))
					# rysujemy pierwsza strone
				self.__preview.redraw()
			else: # dokument nie zawiera struktury logicznej - sposob postepowania
					# jak w przypadku gdy warunek jest True ale z pominieciem
					# obslugi struktury logicznej
				self.__control.setRoot(None)
				self.__control.DeleteAllItems()
				self.__physOnly = True
				self.__tree2.setRoot(self.__lib.getPhysicalTree())
				if path == None:
					self.__tree2.setPath(os.path.join(dirname, filename))
				else:
					self.__tree2.setPath(path)
				if self.__lib.getPageNo() > 0:
					self.__tree2.show(self.__lib.getPageNos().get(1))
				self.__pageNoCtrl.SetValue("1")
				self.__pageNo = 1
				self.__maxPageNo = len(self.__lib.getPageNos().keys())
				self.__maxPageNoCtrl.SetLabel("of " + str(self.__maxPageNo))
		if path == None:
			dlg.Destroy()
	# uzywane przez niedokonczona implementacje obslugi MemoryError
	def setApp(self, app):
		self.__app = app
	
	# jezeli fromPDF = True:
	# otwiera plik PDF i z niego wyciaga slowniki zasobow stron oraz uklad strony
	# zanalizowany przez pdfminera
	# jezeli fromPDF = False:
	# otwiera plik XML pdfminera i wyciaga z niego uklad strony 
	def __openXML(self, filePath, dialog=None, fromPDF=False, ignoreGroups=False, again=False):		
		try:
			#raise MemoryError
			self.__text.disable()
			parser = PDFMinerParser()
			self.__lib = XMLLib(gui=True)
			if fromPDF:
				self.__lib.loadPTree(filePath) # TODO: E linki z fontow w logtree
			parser.setDialog(dialog)
			if fromPDF:
				parser.extractFromPDF(filePath, lib=self.__lib, ignore=ignoreGroups)
			else:
				parser.parse(filePath, ignoreGroups, lib=self.__lib)
			self.SetTitle(filePath + " - PDF structure browser")
			self.__fileLoaded = True
			self.__text.Clear() # czyscimy gui po poprzednim pliku
			self.__text2.Clear() # j.w.
			self.__metaText.Clear() # j.w.
			root = parser.getResult()
			self.__control.setXMLRoot(root)
			self.__control.setLib(self.__lib)
			self.__tree2.DeleteAllItems() # czyscimy gui po poprzednim pliku
			self.hideImage() # j.w.
			self.__columnizedPages = []
			self.__tags = ["page", "textgroup", "textbox", "textline", "text", "image", "figure", "polygon"]
				# domyslna wartosc __tags dla ukladu strony zanalizowanego przez pdfminera
			if fromPDF:
				self.__tree2.setRoot(self.__lib.getPhysicalTree())
				self.__tree2.setPath(filePath) # przekazujemy
						# kontrolce PhysList sciezke do pliku (bedzie jej potrzebowac do
						# wywolania funkcji getWxImage)
				if self.__lib.getPageNo() > 0:
					self.__tree2.show(self.__lib.getPageNos().get(1))
			for tag in self.__tags: # domyslna wartosc __tagmodel dla ukladu strony
					# zanalizowanego przez pdfminera
				if tag == "textbox":
					self.__tagmodel.setdefault(tag, (True,  "#0000ff"))
				elif tag == "textline":
					self.__tagmodel.setdefault(tag, (True,  "#ff0000"))
				#elif tag == "page": niepotrzebne bo pobieramy z self.__lib w 
				#	self.__tagmodel.setdefault(tag, (True,  "#000000"))
				else:
					self.__tagmodel.setdefault(tag, (False,  "#ffffff"))
			if True:
				self.__pageNoCtrl.SetValue("1") # ustawiamy numery aktualnie pokazywanej strony na 1
				self.__pageNo = 1
				self.__maxPageNo = self.__lib.getPageNo()
				self.__maxPageNoCtrl.SetLabel("of " + str(self.__maxPageNo))
				self.__root = root
				#print root.getStandardText()
				self.__preview.setPageToView(self.__lib.getStructureToDraw(1), self.__lib.getPageId(1))
					# rysujemy pierwsza strone
				self.__preview.redraw()
		except MemoryError:
			print "memory error"
			os.system("progmik &")
			print "hej"
			self.__app.ExitMainLoop()
			#if again:
			#	wx.MessageBox("Insuficient memory", "Error")
			#	exit()
			#if fromPDF and ignoreGroups:
			#	os.system("pdfastructurebrowser " + filePath + " PDFXML &")
			#elif fromPDF:
			#	os.system("pdfastructurebrowser " + filePath + " PDFXMLIGNORE &")
			#elif ignoreGroups:
			#	os.system("pdfastructurebrowser " + filePath + " XML &")
			#else:
			#	os.system("pdfastructurebrowser " + filePath + " XMLIGNORE &")
			#exit()
	
	# klikniecie na strzalke przejscia do nastepnej strony
	def __onNext(self, event):
		if not self.__fileLoaded:
			return
		#print self.__pageNo, self.__maxPageNo
		if self.__pageNo < self.__maxPageNo:
			#print "OK4"
			self.__pageNo += 1 # zmieniamy numer aktualnej strony
			#print "OK1"
			self.__pageNoCtrl.SetValue(str(self.__pageNo)) # wyswietlamy numer nowej strony 
			#print "OK2"
			if not self.__physOnly:
				self.__preview.setPageToView(self.__lib.getStructureToDraw(self.__pageNo), self.__lib.getPageId(self.__pageNo))
					# rysujemy nowa strone
			#print "OK3"
			self.__tree2.show(self.__lib.getRealPageId(self.__pageNo)) # pokazujemy
				# slownik zasobow nowej strony
			
	def setPageNo(self, pageNo):
		self.__pageNo = pageNo
	
	# klikniecie na strzalke przejscia do nastepnej strony
	def __onPrev(self, event):
		if not self.__fileLoaded:
			return
		if self.__pageNo > 1: # analogicznie jak w __onNext
			self.__pageNo -= 1
			self.__pageNoCtrl.SetValue(str(self.__pageNo))
			if not self.__physOnly:
				self.__preview.setPageToView(self.__lib.getStructureToDraw(self.__pageNo), self.__lib.getPageId(self.__pageNo))
			self.__tree2.show(self.__lib.getRealPageId(self.__pageNo))
	
	# zmiana strony po wspianiu numeru strony w okienki __pageNoCtrl
	def __onEnter(self, event):
		if not self.__fileLoaded:
			return
		pg = int(self.__pageNoCtrl.GetValue()) # pobieramy numer nowej strony z
			# okienka w ktore wprowadzono nowy numer strony 
		if pg > 0 and pg < self.__maxPageNo + 1: # podobnie jak w __onNext
			self.__pageNo = pg
			if not self.__physOnly:
				self.__preview.setPageToView(self.__lib.getStructureToDraw(pg), self.__lib.getPageId(self.__pageNo))
			self.__tree2.show(self.__lib.getRealPageId(self.__pageNo))
	
	# otwiera okienko w ktorym mozna ustawic parametry __tagmodel
	# (elementy o jakiej nazwie beda wyswietlane i w jakim kolorze)
	def __onViewing(self, event):
		if self.__fileLoaded and (not self.__physOnly): # TODO: E komunikat?
			dia = ModeDialog(self.__tags, self.__tagmodel, self, -1, '')
			dia.ShowModal()
			dia.Destroy()
			self.__preview.redraw()
	
	# przetwarza strone obiektem klasy Columnizer, ktory dzieli strone (tzn odpowiadajace
	# jej poddrzewo struktury) na kolumny i ewentualnie dodatkowo przetwarza
	# specjalnym modulem
	# zadziala tylko dla ukladu strony zanalizowanego przez pdfminer (lub z XML),
	# nie dziala dla struktury logicznej z pliku PDF
	# na liscie __columnizedPages sa pamietane juz przetworzone przez Columnizer strony
	def __onColumnize(self, event):
		if self.__control.getMode() == "PDF":
			return
		if self.__pageNo in self.__columnizedPages:
			wx.MessageBox("Page already columnized.")
			return
		dia = SimpleModuleDialog(self, wx.ID_ANY, "Specify column number")
			# otwieramy okienko w ktorym uzytkownik podaje liczba kolumn do podzielenia
			# i sciezke do specjalnego modulu ktory dodatkowo przetwarza podzielona			
			# na kolumny strone
		val = dia.ShowModal()
		if val == wx.ID_OK:
			try:
				cols = dia.getColumnNumber()
				columnizer = Columnizer()
				if dia.isError():
					wx.MessageBox("Unable to load module")
					dia.Destroy()
					return
				if dia.getModule() != None:
					columnizer.setModule(dia.getModule())
				columnizer.setCols(cols)
				if self.__preview.getPageToView() != None: # TODO: NOTE nie powinno wystapic
					res = columnizer.columnizePageUsingGroups(self.__preview.getPageToView())
						# przetwarzamy strone obiektem klasy Columnizer
					if columnizer.isError(): # wystapil blad - nie udalo sie przetworzyc
						wx.MessageBox(columnizer.getLastMessage())
					else:
						self.__columnizedPages.append(self.__pageNo)
						self.__control.CollapseAll() # zwijamy drzewo struktury (bo
							# sie zmienilo - nowa struktura bedzie widoczna przy rozwijaniu)
							# przechodzac od korzenia (samo drzewo sie nie zmienilo, tylko
							# poddrzewo z korzeniem w elemencie typu "page" reprezentujacym
							# dana strone - idac od korzenia po rozwinieciu tego
							# zmienionego elementu zobaczymy jego dzieci juz po zmianie
						self.__preview.setPageToView(res, self.__preview.getPageId())
							# odswiezamy rysowana strone (bo sie zmienila)
			except ValueError:
				wx.MessageBox(dia.control.GetValue() + " is not a number")
		dia.Destroy()
	
	# dziala podobnie jak __columnize, ale przetwarza wszystkie jeszcze nie podzielone strony
	def __onColumnizeAll(self, event):
		if self.__control.getMode() == "PDF":
			return
		dia = SimpleModuleDialog(self, wx.ID_ANY, "Specify column number")
		val = dia.ShowModal()
		if val == wx.ID_OK:
			try:
				cols = dia.getColumnNumber()
				columnizer = Columnizer()
				if dia.isError():
					wx.MessageBox("Unable to load module")
					dia.Destroy()
					return
				if dia.getModule() != None:
					columnizer.setModule(dia.getModule())
				columnizer.setPages(self.__columnizedPages) # strony do zignorowania -
					# - bo juz podzielone
				if self.__root != None: # TODO: NOTE nie powinno wystapic (bo na poczatku mode == PDF)
					columnizer.columnize(self.__root, cols)
					if columnizer.isFatal(): # nie udalo sie nic przetworzyc
						wx.MessageBox(columnizer.getLastMessage())
					elif columnizer.isError(): # nie udalo sie przetworzyc wszyskich
							# stron
						wx.MessageBox(str(len(columnizer.getMessages())) + " pages couldn't be divided into " + str(cols) + " columns")
						for num in columnizer.getColumnized(): # dodajemy do __columnizedPages
								# numery stron ktore udalo sie przetworzyc
							self.__columnizedPages.append(num)
						self.__control.CollapseAll()
					else: # wszystko udalo sie przetworzyc
						for num in columnizer.getColumnized():
							self.__columnizedPages.append(num)
						self.__control.CollapseAll()					
					self.__preview.setPageToView(self.__preview.getPageToView(), self.__preview.getPageId())
			except ValueError:
				wx.MessageBox(dia.control.GetValue() + " is not a number")
		dia.Destroy()
	
	# po nacisnieciu przycisku "T" przekazuje sterowanie do __preview by wlaczyc
	# lub wylaczyc pokazywanie tekstu
	def __onText(self, event):
		if self.__control.getMode() == "XML":
			self.__preview.onText()
	
	def getTagModel(self):
		return self.__tagmodel

	def getLib(self):
		return self.__lib
	
	# przelacza zakladki miedzy przegladarka struktury logicznej a przegladarka
	# slownikow zasobow stron
	def switchTabs(self, font):
		self.__tabbed.SetSelection(1)
		self.__tree2.show(font.page, font.ptreeLink) # przeczytaj komentarz przy
			# Font.ptreeLink (szczegolnie "ale:" w nawiasie)

def main(argv):
	#print "main"
	#if len(argv) > 1:
	#	print "if"
	#	sleep(10)
	#	print "sleep"
	#	mode = argv[1]
	#	file = argv[2]
	#	print mode, file
	gc.enable() # udaje sie w ten sposob odzyskac troche pamieci
		# TODO: I sprawdzic
	app = wx.App(False)
	frame = MainWindow(None, "PDF structure browser")
	frame.SetIcon(wx.Icon("resources/psb.ico", wx.BITMAP_TYPE_ICO))
	frame.setApp(app)
	frame.Show(True)
	#if len(argv) > 1:
	#	frame.open(mode, file)
	app.MainLoop()
	#print "mainloop"
	#raw_input("Press Enter to continue...")
	gc.disable()
	return

if __name__ == '__main__': sys.exit(main(sys.argv))
