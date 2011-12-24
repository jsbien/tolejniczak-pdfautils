# -*- coding: cp1250 -*-
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
from pdfminerconverter import PDFMinerNode
import copy

def odlegloscRedaktorska(a, b):
    d = []
    for i in range(len(a)):
        d.append([i])
    for j in range(len(b) - 1):
        d[0].append(j + 1)
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            if a[i + 1] == b[j + 1]:
                d[i + 1].append(d[i][j])
            else:
                d[i + 1].append(min(d[i][j + 1] + 1,
                                    d[i][j] + 1, d[i + 1][j] + 1))
    #print a.encode("utf-8"), b.encode("utf-8"), d[len(a) - 1][len(b) - 1]
    return d[len(a) - 1][len(b) - 1]

# przykladowy modul wlasnego przetwarzania
# znajduje pagine w slowniku Lindego
# zeby modul dzialal poprawnie musza byc dokladnie dwie kolumny
def customProcessing(page):
    if len(page.getChildren()) != 2:
        return
    paginaGorna = PDFMinerNode("textbox")
    paginaGorna.setPageId(page.getPageId())
    paginaDolna = PDFMinerNode("textbox")
    paginaDolna.setPageId(page.getPageId())
    jestDolna = False
    
    kolumna = page.getChildren()[0]
    if len(kolumna.getChildren()) < 2:
        return
    pagina = kolumna.getChildren()[0]
    kolumna.setChildren(kolumna.getChildren()[1:])
    paginaGorna.getChildren().append(pagina)
    
    #if page.getPageId() == 680:
    if False:
        cp = copy.copy(kolumna.getChildren())
        for el in kolumna.getChildren():
            if el.getBbox()[1] < 500.0:
                cp.remove(el)
        kolumna.setChildren(cp)
        kolumna.resetBbox()
        
        kolumna = page.getChildren()[1]
        if len(kolumna.getChildren()) < 2:
            return
        pagina = kolumna.getChildren()[0]
        kolumna.setChildren(kolumna.getChildren()[1:])
        paginaGorna.getChildren()[0].join(pagina)
        
        cp = copy.copy(kolumna.getChildren())
        for el in kolumna.getChildren():
            if el.getBbox()[1] < 500.0:
                cp.remove(el)
        kolumna.setChildren(cp)
        kolumna.resetBbox()
        kolumna.resetBbox()
    else:
        last = len(kolumna.getChildren()) - 1
        pagina = kolumna.getChildren()[last]
        ostatnia = pagina
        if odlegloscRedaktorska(pagina.getTextContent(),
                                u"Słownik Lindego wyd. 2. Tom I.") < 20:
            jestDolna = True
            paginaDolna.getChildren().append(pagina)
            kolumna.setChildren(kolumna.getChildren()[:-1])
        else:
            jestDolna = False
        kolumna.resetBbox()
    
        kolumna = page.getChildren()[1]
        if len(kolumna.getChildren()) < 2:
            return
        sredniaDlugosc = 0.0 
        pagina = kolumna.getChildren()[0]
        kolumna.setChildren(kolumna.getChildren()[1:])
        for linia in kolumna.getChildren():
            sredniaDlugosc += linia.getBbox()[2] - linia.getBbox()[0]
        sredniaDlugosc /= len(kolumna.getChildren())
        paginaGorna.getChildren()[0].join(pagina)
        last = len(kolumna.getChildren()) - 1
        pagina = kolumna.getChildren()[last]    
        if jestDolna:
            paginaDolna.getChildren()[0].join(pagina)
            kolumna.setChildren(kolumna.getChildren()[:-1])   
        else:
            #print (pagina.getBbox()[2] - pagina.getBbox()[0]) / sredniaDlugosc
            #pop = kolumna.__children[last - 1]
            #print pop.getBbox()[1] - pagina.getBbox()[3]    # 20.0
            #print pagina.getBbox()[0] - pop.getBbox()[0]    # 1.5
            #print
            if (pagina.getBbox()[2] - pagina.getBbox()[0]) / sredniaDlugosc < 0.1:
                paginaDolna.add(pagina)
                kolumna.setChildren(kolumna.getChildren()[:-1])
            elif ostatnia.getBbox()[1] > pagina.getBbox()[3]:
                paginaDolna.add(pagina)
                kolumna.setChildren(kolumna.getChildren()[:-1]) 
        kolumna.resetBbox()
    
    paginaGorna.resetBbox()
    page.getChildren().insert(0, paginaGorna)
    if len(paginaDolna.getChildren()) > 0:
        paginaDolna.resetBbox()
        page.add(paginaDolna)
