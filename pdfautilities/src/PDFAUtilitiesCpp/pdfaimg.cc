//========================================================================
//
// pdfimages.cc
//
// Copyright 1998-2003 Glyph & Cog, LLC
//
// Modified for Debian by Hamish Moffatt, 22 May 2002.
//
//========================================================================

//========================================================================
//
// Modified under the Poppler project - http://poppler.freedesktop.org
//
// All changes made under the Poppler project to this file are licensed
// under GPL version 2 or later
//
// Copyright (C) 2007-2008 Albert Astals Cid <aacid@kde.org>
//
// Modified for PDFA/Utilities:
// Copyright (C) 2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>
//
//
// To see a description of the changes please see the Changelog file that
// came with your tarball or type make ChangeLog if you are building from git
//
//========================================================================

#include "pdfaimg.h"

//#include "config.h"
#include <poppler/poppler-config.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <poppler/goo/GooString.h>
#include <poppler/goo/gmem.h>
#include <poppler/GlobalParams.h>
#include <poppler/Object.h>
#include <poppler/Stream.h>
#include <poppler/Array.h>
#include <poppler/Dict.h>
#include <poppler/XRef.h>
#include <poppler/Catalog.h>
#include <poppler/Page.h>
#include <poppler/PDFDoc.h>
#include "ImageOutputDev.h"
#include <poppler/Error.h>

void getImage(char ** data, int * len, const char * filen, int num, int gen, bool mask, int page) {
	int i = 0;
	*data = getImageLen(filen, num, gen, page, mask, i);
	*len = i;
}

char * getImageLen(const char * filen, int num, int gen, int page, bool mask, int & j) {
  PDFDoc *doc;
  GooString *fileName;
  char *imgRoot;
  ImageOutputDev *imgOut;
  GBool ok;
  char *result;
  //int jg = 0;

  fileName = new GooString(filen);
  imgRoot = "dummy";

  globalParams = new GlobalParams();

  doc = new PDFDoc(fileName, NULL, NULL);
  
  if (!doc->isOk()) {
    goto err1;
  }

  if (!doc->okToCopy()) {
    error(-1, "Copying of images from this document is not allowed.");
    goto err1;
  }

  // write image files
  //printf("imgOut\n");
  imgOut = new ImageOutputDev(imgRoot, gTrue, num, gen, mask);
  if (imgOut->isOk()) {
      doc->displayPages(imgOut, page, page, 72, 72, 0,
			gTrue, gFalse, gFalse);
  }
  result = imgOut->getResult(j);
  delete imgOut;

  // clean up
 err1:
  delete doc;
 err0:

  // check for memory leaks
  //Object::memCheck(stderr);
  //gMemReport(stderr);

	//char * res = (char *) malloc(1);

  return result;
}

