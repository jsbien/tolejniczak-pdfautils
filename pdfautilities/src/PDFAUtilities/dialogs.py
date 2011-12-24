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

import wx
import sys
import wx.richtext as rt
from pdfminermod import list_value2, dict_value2
from pdfminer.pdftypes import list_value, stream_value, dict_value
from utils import hexdump, loadModule, isHTMLColor
from pdfminer.pdfparser import literal_name

#def convert(pilImage):
#    # http://jehiah.cz/a/pil-to-wxbitmap
#    wxImage = wx.EmptyImage(pilImage.size[0], pilImage.size[1])
#    wxImage.SetData(pilImage.convert("RGB").tostring())
#    #wxImage.SetAlphaData(pilImage.convert("RGBA").tostring()[3::4])
#    return wxImage

# pokazuje kodowanie lub przestrzen kolorow
# patrz PhysList.onURL
class ColourSpaceDialog(wx.Dialog):

    def __init__(self, parent, id, title):
        wx.Dialog.__init__(self, parent, id, title)
        self.__sizer = wx.BoxSizer(wx.VERTICAL)
        self.__bsizer = self.CreateButtonSizer(wx.OK)
        self.__control = rt.RichTextCtrl(self, wx.ID_ANY, style=wx.TE_READONLY)
        #self.__control.SetSize((300, 250))
        self.__sizer.Add(self.__control, 1, wx.ALIGN_CENTER | wx.EXPAND)
        self.__sizer.Add(self.__bsizer, 0, wx.ALIGN_CENTER)
        self.SetSizer(self.__sizer)
        self.SetSize((350, 300))
        #self.__object = None
        self.__childObject = None
        self.__mode = "Image"
        self.Bind(wx.EVT_TEXT_URL, self.__onURL, self.__control)
    
    def __onURL(self, event):
        if self.__mode == "Encoding":
            dia = ColourSpaceDialog(self, wx.ID_ANY, "Encoding")
            dia.setEncoding(self.__childObject)
            dia.ShowModal()
            dia.Destroy()
        else:
            if self.__colorSpace != None:
                dia = ColourSpaceDialog(self, wx.ID_ANY, "Color space")
                dia.setColourSpace(self.__childObject)
                dia.ShowModal()
                dia.Destroy()
    
    def setEncoding(self, enc):
        #self.__control.SetInsertionPoint(0)
        #self.__control.Clear()
        self.__mode = "Encoding"
        #self.__object = enc
        dEncoding = dict_value2(enc.get("Encoding"))
        differences = list_value(enc.get("Differences"))
        if dEncoding == None:
            nEncoding = literal_name(enc.get("Encoding"))
        if dEncoding == None:
            self.__control.WriteText("Base encoding: " + nEncoding + "\n")
        else:
            self.__colorSpace = dEncoding
            self.__control.BeginTextColour("#0000ff")
            self.__control.BeginUnderline()
            self.__control.BeginURL("0")
            self.__control.WriteText("Encoding")
            self.__control.EndURL()
            self.__control.EndUnderline()
            self.__control.EndTextColour()
        self.__control.WriteText("Differences:\n")
        code = 0
        for el in differences:
            if isinstance(el, int):
                code = el
            else:
                self.__control.WriteText("\t" + str(code) + ": " + literal_name(el) + "\n")
                code += 1
        self.__control.ShowPosition(0)

    def setColourSpace(self, cs):
        #self.__control.SetInsertionPoint(0)
        #self.__control.Clear()
        #self.__object = cs
        if list_value2(cs) != None:
            colourSpace = literal_name(list_value(cs)[0])
            self.__control.WriteText("Type: " + colourSpace + "\n")
            if colourSpace == "ICCBased":
                param = stream_value(list_value(cs)[1])
                tmpDict = {}
                if param.get("N") != None:
                    tmpDict.setdefault("N", param.get("N"))
                if param.get("Range") != None:
                    tmpDict.setdefault("Range", param.get("Range"))
                self.__control.WriteText(str(tmpDict) + "\n")
                if list_value2(param.get("Alternate")) == None:
                    if param.get("Alternate") != None:
                        self.__control.WriteText("Alternate color space: " + literal_name(param.get("Alternate")) + "\n")
                if param.get("Alternate") != None:
                    self.__control.BeginURL("0")
                    self.__control.BeginTextColour("#0000ff")
                    self.__control.BeginUnderline()
                    self.__control.WriteText("Alternate color space\n")
                    self.__control.EndURL()
                    self.__control.EndUnderline()
                    self.__control.EndTextColour()
                    self.__childObject = param.get("Alternate")
                self.__control.WriteText("ICC profile: " + hexdump(param.get_data()) + "\n")
            elif colourSpace in ["CalGray", "CalRGB", "Lab"]:
                self.__control.WriteText(str(dict_value(list_value(cs)[1])) + "\n")
            elif colourSpace == "Indexed":
                self.__control.WriteText(colourSpace + "\n")
                self.__control.WriteText("Hival: " + str(list_value(cs)[2]) + "\n")
                self.__control.WriteText("Lookup: " + str(list_value(cs)[3]) + "\n")
                if list_value2(list_value(cs)[3]) == None:
                    self.__control.WriteText("Base color space: " + literal_name(list_value(cs)[3]) + "n")
                else:
                    self.__control.BeginURL("0")
                    self.__control.BeginTextColour("#0000ff")
                    self.__control.BeginUnderline()
                    self.__control.Writetext("Base color space\n")
                    self.__control.EndURL()
                    self.__control.EndUnderline()
                    self.__control.EndTextColour()
                    self.__childObject = list_value(cs)[3]
            elif colourSpace in ["Separation", "DeviceN"]:
                # TODO: E implementacja przestrzeni kolorantow w atrybutach DeviceN
                self.__control.WriteText(colourSpace + "\n")
                self.__control.WriteText("Names: " + str(list_value(cs)[1]) + "\n")
                self.__control.WriteText("Tint transform : " + str(list_value(cs)[3]) + "\n")
                if list_value2(list_value(cs)[2]) == None:
                    self.__control.WriteText("Alternate color space: " + literal_name(list_value(cs)[2]) + "\n")
                else:
                    self.__control.BeginURL("0")
                    self.__control.BeginTextColour("#0000ff")
                    self.__control.BeginUnderline()
                    self.__control.Writetext("Alternate color space\n")
                    self.__control.EndURL()
                    self.__control.EndUnderline()
                    self.__control.EndTextColour()
                    self.__childObject = list_value(cs)[2]
            self.__control.ShowPosition(0)

# pozwala na podanie wartosci tekstowej przez uzytkownika
class SimpleDialog(wx.Dialog):
    
    def __init__(self, parent, id, title):
        wx.Dialog.__init__(self, parent, id, title)
        self.__sizer = wx.BoxSizer(wx.VERTICAL)
        self.__bsizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.__control = wx.TextCtrl(self)
        self.__sizer.Add(self.__control, 0, wx.ALIGN_CENTER)
        self.__sizer.Add(self.__bsizer, 0, wx.ALIGN_CENTER)
        self.SetSizer(self.__sizer)
        self.SetSize((self.GetSize()[0], 80))
    
    def setText(self, text):
        self.__control.SetValue(text)
    
    def getText(self):
        return self.__control.GetValue()

# pozwala zaladowanie dowolnego modulu
class SimpleModuleDialog(wx.Dialog):
    
    def __init__(self, parent, id, title):
        wx.Dialog.__init__(self, parent, id, title)
        self.__sizer = wx.BoxSizer(wx.VERTICAL)
        self.__bsizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.__control = wx.TextCtrl(self)
        self.__module = wx.StaticText(self)
        self.__button = wx.Button(self, wx.ID_ANY, "&Use module")
        self.__sizer.Add(self.__control, 0, wx.ALIGN_CENTER)
        self.__sizer.Add(self.__module, 0, wx.ALIGN_CENTER)
        self.__sizer.Add(self.__button, 0, wx.ALIGN_CENTER)
        self.__sizer.Add(self.__bsizer, 0, wx.ALIGN_CENTER)
        self.SetSizer(self.__sizer)
        self.SetSize((self.GetSize()[0], 120))
        self.Bind(wx.EVT_BUTTON, self.__onClick, self.__button)
        self.__module = None
        self.__error = False
        self.__control.SetValue("2")
    
    def getColumnNumber(self):
        return int(self.__control.GetValue())
        
    def __onClick(self, event):
        dlg = wx.FileDialog(self, "Choose module file", "", "", "*.py", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            file = dlg.GetFilename()
            path = dlg.GetDirectory()
            self.__module = loadModule(file, path)
            if self.__module == None:
                self.__error = True
        dlg.Destroy()
    
    def isError(self):
        return self.__error
    
    def getModule(self):
        return self.__module

# tag = nazwa elementu (po zamapowaniu z uzyciem /RoleMap) = (PDFMiner)Node.getStandardText()
# umozliwia zmiane ustawien rysowania strony (MainWindow.__tagmodel)
class ModeDialog(wx.Dialog):

    def __init__(self, items, model, parent, id, title):
        
        wx.Dialog.__init__(self, parent, id, title)
        
        self.SetTitle("Set viewing preferences")
        self.SetSize((self.GetSize()[0], 300))
        
        self.__sizer0 = wx.BoxSizer(wx.VERTICAL)
        #self.list = wx.ListCtrl(self)
        self.__list = wx.ListBox(self, style=wx.LB_SINGLE)
        #self.list.SetSize((self.list.GetSize()[0], 100))
        
        self.__items = items
        self.__model = model # __tagmodel ktory edytujemy
        for i in self.__items:
            self.__model.setdefault(i, (False, "#ffffff"))
        self.__list.Set(self.__items)
        self.__current = self.__items[0]
        self.__veto = False
        
        self.__sizer4 = wx.BoxSizer(wx.HORIZONTAL)
        self.__sizer1 = wx.GridSizer(3, 2)
        self.__box = wx.CheckBox(self)
        self.__label0 = wx.StaticText(self)
        self.__label1 = wx.StaticText(self)
        self.__label0.SetLabel("Show")
        self.__label1.SetLabel("Set color")
        self.__text = wx.TextCtrl(self)
        self.__addBtn = wx.Button(self, wx.ID_ANY, "Add")
        self.__sizer1.Add(self.__label0)
        self.__sizer1.Add(self.__box)
        self.__sizer1.Add(self.__label1)
        self.__sizer1.Add(self.__text)
        self.__sizer1.Add(self.__addBtn)
        
        self.__sizer4.Add(self.__list, 1, wx.ALIGN_TOP)
        self.__sizer4.Add(self.__sizer1, 1, wx.ALIGN_TOP)
        
        #self.sizer = wx.BoxSizer(wx.VERTICAL)
        #self.button1 = wx.RadioButton(self)
        #self.button2 = wx.RadioButton(self)
        #self.button3 = wx.RadioButton(self)
        #self.sizer.Add(self.button1, wx.ALIGN_CENTER)
        #self.sizer.Add(self.button2, wx.ALIGN_CENTER)
        #self.sizer.Add(self.button3, wx.ALIGN_CENTER)
        self.__bsizer = self.CreateButtonSizer(wx.OK)
        #for c in self.GetChildren():
        #    print c.GetId(), wx.OK
        self.__ok = self.__bsizer.GetAffirmativeButton()
        #self.sizer.Add(self.bsizer, wx.ALIGN_CENTER)
        
        self.__sizer0.Add(self.__sizer4, 1, wx.ALIGN_CENTER)
        #self.sizer0.Add(self.sizer, wx.ALIGN_CENTER)
        self.__sizer0.Add(self.__bsizer, 0, wx.ALIGN_CENTER)
        self.SetSizer(self.__sizer0)
        self.Centre()
        self.Bind(wx.EVT_LISTBOX, self.__onSelect, self.__list)
        self.Bind(wx.EVT_CHECKBOX, self.__onBox, self.__box)
        self.Bind(wx.EVT_TEXT, self.__onType, self.__text)
        self.Bind(wx.EVT_BUTTON, self.__onAdd, self.__addBtn)
        self.Bind(wx.EVT_BUTTON, self.__onOK, self.__ok)        
    
    # walidujemy dane przy kliknieciu OK
    def __onOK(self, event):
        #print "[" + self.__box.GetValue() + "]"     
        if self.__list.GetSelection() == None:
            event.Skip() 
        if self.__box.GetValue() and not isHTMLColor(self.__text.GetValue()):
            wx.MessageBox("Invalid color string (use HTML colors)")
        else:
            event.Skip()
    
    # dodajemy nowy tag do slownika
    # TODO: I czy moga wystapic tagi niemapowane na standardowe?
    # w tagowanym chyba nie, ale w zwyklym?
    def __onAdd(self, event):
        dia = SimpleDialog(self, wx.ID_ANY, "Add element type")
        val = dia.ShowModal()
        if val == wx.ID_OK:
            if not dia.getText() in self.__items:
                self.__items.append(dia.getText())
                self.__model.setdefault(dia.getText(), (True, "#000000"))
                self.__list.Set(self.__items)
        dia.Destroy()
    
    # zmieniamy flage decydujaca, czy element drzewa struktury o zaznaczonym tagu bedzie
    # pokazywany
    def __onBox(self, event):
        if self.__veto:
            return
        (_, color) = self.__model.get(self.__current)
        self.__model.__delitem__(self.__current)
        self.__model.setdefault(self.__current, (self.__box.GetValue(), color))
    
    # zaznaczono nowy tag z listy - walidujemy dane poprzednio zaznaczonego tagu i
    # zmieniamy wyswietlane informacje
    def __onSelect(self, event):
        if self.__list.GetSelection() != None and self.__box.GetValue():
            if not isHTMLColor(self.__text.GetValue()):
                wx.MessageBox("Invalid color string (use HTML colors)")
                return
        i = self.__list.GetSelection()
        item = self.__list.GetItems()[i]
        self.__veto = True
        self.__text.SetValue(self.__model.get(item)[1])
        self.__box.SetValue(self.__model.get(item)[0])
        self.__veto = False
        self.__current = item
    
    # pisanie w oknie definiujacym kolor w jakim bedzie wyswietlany element o zaznaczonym
    # tagu - zapisujemy zmiany
    def __onType(self, event):
        if self.__veto:
            return
        (show, _) = self.__model.get(self.__current)
        self.__model.__delitem__(self.__current)
        self.__model.setdefault(self.__current, (show, self.__text.GetValue()))
