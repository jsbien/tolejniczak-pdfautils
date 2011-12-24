#Copyright 2011
#by Tomasz Olejniczak
#
#                        All Rights Reserved
#
#Permission to use, copy, modify, and distribute this software and 
#its documentation for any purpose and without fee is hereby granted,
#provided that the above copyright notice appear in all copies and 
#that both that copyright notice and this permission notice appear 
#in supporting documentation, and that the name of Tomasz Olejniczak 
#not be used in advertising or publicity pertaining to
#distribution of the software without specific, written prior
#permission.
#
#TOMASZ OLEJNICZAK DISCLAIM ALL WARRANTIES WITH
#REGARD TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF
#MERCHANTABILITY AND FITNESS, IN NO EVENT SHALL TOMASZ OLEJNICZAK
#BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL
#DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
#PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
#TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
#PERFORMANCE OF THIS SOFTWARE.
#
# This file contains code copied from part of FontTools software and modified for
# PDF/AUtilities (TTFontMod class). Also the fontToolsUniToString function is based
# on code from FontTools software.
# The creator of FontTools, Just van Rossum, is not in any way connected with
# the creation of PDFAutilities software which was created solely by Tomasz
# Olejniczak. The following copyright notice is included because the
# ttFontMod.py file contains code based on FontTools:
#
#Copyright 1999-2004
#by Just van Rossum, Letterror, The Netherlands.
#
#                        All Rights Reserved
#
#Permission to use, copy, modify, and distribute this software and 
#its documentation for any purpose and without fee is hereby granted,
#provided that the above copyright notice appear in all copies and 
#that both that copyright notice and this permission notice appear 
#in supporting documentation, and that the names of Just van Rossum 
#or Letterror not be used in advertising or publicity pertaining to
#distribution of the software without specific, written prior
#permission.
#
#JUST VAN ROSSUM AND LETTERROR DISCLAIM ALL WARRANTIES WITH
#REGARD TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF
#MERCHANTABILITY AND FITNESS, IN NO EVENT SHALL JUST VAN ROSSUM OR 
#LETTERROR BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL
#DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
#PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
#TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
#PERFORMANCE OF THIS SOFTWARE.
#
#just@letterror.com

import array
import struct
import string
from fontTools import ttLib

# modyfikacja klasy ttLib.TTFont tak by mozna bylo podac StringIO jako plik do czytania
# zamiast nazwy pliku
class TTFontMod(ttLib.TTFont):
    
    def __init__(self, file=None, res_name_or_index=None,
            sfntVersion="\000\001\000\000", checkChecksums=0,
            verbose=0, recalcBBoxes=1, allowVID=0, ignoreDecompileErrors=False,
            fontNumber=-1):

        from fontTools.ttLib import sfnt
        self.verbose = verbose
        self.recalcBBoxes = recalcBBoxes
        self.tables = {}
        self.reader = None

        # Permit the user to reference glyphs that are not int the font.
        self.last_vid = 0xFFFE # Can't make it be 0xFFFF, as the world is full unsigned short integer counters that get incremented after the last seen GID value.
        self.reverseVIDDict = {}
        self.VIDDict = {}
        self.allowVID = allowVID
        self.ignoreDecompileErrors = ignoreDecompileErrors

        self.reader = sfnt.SFNTReader(file, checkChecksums, fontNumber=fontNumber)
        self.sfntVersion = self.reader.sfntVersion

needswap = struct.pack("h", 1) == "\001\000"

def fontToolsUniToString(uni):
    a = array.array("H")
    a.fromstring(uni)
    if needswap:
        a.byteswap()
        def __process(n):
            return chr(n)
        res = string.join(map(__process, a), "")
        return res
