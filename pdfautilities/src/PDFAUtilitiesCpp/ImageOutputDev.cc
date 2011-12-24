//========================================================================
//
// ImageOutputDev.cc
//
// Copyright 1998-2003 Glyph & Cog, LLC
//
//========================================================================

//========================================================================
//
// Modified under the Poppler project - http://poppler.freedesktop.org
//
// All changes made under the Poppler project to this file are licensed
// under GPL version 2 or later
//
// Copyright (C) 2005, 2007 Albert Astals Cid <aacid@kde.org>
// Copyright (C) 2006 Rainer Keller <class321@gmx.de>
// Copyright (C) 2008 Timothy Lee <timothy.lee@siriushk.com>
// Copyright (C) 2008 Vasile Gaburici <gaburici@cs.umd.edu>
// Copyright (C) 2009 Carlos Garcia Campos <carlosgc@gnome.org>
// Copyright (C) 2009 William Bader <williambader@hotmail.com>
//
// Modified for PDFA/Utilities:
// Copyright (C) 2011 Tomasz Olejniczak <tomek.87@poczta.onet.pl>
//
// To see a description of the changes please see the Changelog file that
// came with your tarball or type make ChangeLog if you are building from git
//
//========================================================================

//#include "config.h"
#include <poppler/poppler-config.h>

#ifdef USE_GCC_PRAGMAS
#pragma implementation
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <ctype.h>
#include <poppler/goo/gmem.h>
#include <poppler/Error.h>
#include <poppler/GfxState.h>
#include <poppler/Object.h>
#include <poppler/Stream.h>
#ifdef ENABLE_LIBJPEG
#include <poppler/DCTStream.h>
#endif
#include "ImageOutputDev.h"

ImageOutputDev::ImageOutputDev(char *fileRootA, GBool dumpJPEGA, int num, int gen, bool mask) {
  //printf("fileRoot: %s\n", fileRootA);
  fileRoot = copyString(fileRootA);
  //printf("fileRootCopy %s\n", fileRoot);
  fileName = (char *)gmalloc(strlen(fileRoot) + 20);
  //printf("[fileName: %s]\n", fileName);
  dumpJPEG = dumpJPEGA;
  imgNum = 0;
  ok = gTrue;
  curLen = 0;
  res = NULL;
  last = NULL;
  this->num = num;
  this->gen = gen;
  this->mask = mask;
  w = 0;
  h = 0;
  jpeg = false;
  pbm = false;
}

ImageOutputDev::~ImageOutputDev() {
  gfree(fileName);
  gfree(fileRoot);
}

// TODOl C czy zawsze ImageMask bedzie w slowniku jak go potrzebujemy?
bool isMask(Stream * str) {
	//printf("is mask\n");
	Dict *d = str->getDict();
	Object obj;
	d->lookup("ImageMask", &obj);
	if (!obj.isNull()) {
		//printf("not null\n");
		if (obj.getBool()) {
			obj.free();
			return true;
		}
	}
	//printf("null\n");
	obj.free();
	return false;
}

void ImageOutputDev::drawImageMask(GfxState *state, Object *ref, Stream *str,
				   int width, int height, GBool invert,
				   GBool interpolate, GBool inlineImg) {
  FILE *f;
  int c;
  int size, i;

  printf("[%d.%d.%d]\n", num, gen, mask);
  printf("%d.%d.%d\n", ref->getRef().num, ref->getRef().gen, isMask(str));

  if (ref->getRef().num != num || ref->getRef().gen != gen || isMask(str) != mask) {
  	  return;
  }

  // dump JPEG file
  if (dumpJPEG && str->getKind() == strDCT && !inlineImg) {

	jpeg = true;

    // open the image file
    sprintf(fileName, "%s-%03d.jpg", fileRoot, imgNum);
    ++imgNum;
    if (!(f = fopen(fileName, "wb"))) {
    	//printf(fileName);
      error(-1, "Couldn't open image file '%s'", fileName);
      return;
    }

    // initialize stream
    str = ((DCTStream *)str)->getRawStream();
    str->reset();

    // copy the stream
    while ((c = str->getChar()) != EOF)
     // fputc(c, f);
      myput(c);

    str->close();
    fclose(f);

  // dump PBM file
  } else {

	pbm = true;

    // open the image file and write the PBM header
    sprintf(fileName, "%s-%03d.pbm", fileRoot, imgNum);
    ++imgNum;
    if (!(f = fopen(fileName, "wb"))) {
     // printf(fileName);
      error(-1, "Couldn't open image file '%s'", fileName);
      return;
    }
    fprintf(f, "P4\n");
    fprintf(f, "%d %d\n", width, height);
    //printf("%d %d\n", width, height);
    w = width;
    h = height;

    // initialize stream
    str->reset();

    // copy the stream
    size = height * ((width + 7) / 8);
    for (i = 0; i < size; ++i) {
      //fputc(str->getChar(), f);
    //printf("fputc\n");
      myput(str->getChar());
      //myput(str->getChar());
      //myput(str->getChar());
    }

    str->close();
    fclose(f);
  }
}

void ImageOutputDev::drawImage(GfxState *state, Object *ref, Stream *str,
			       int width, int height,
			       GfxImageColorMap *colorMap,
			       GBool interpolate, int *maskColors, GBool inlineImg) {
  FILE *f;
  ImageStream *imgStr;
  Guchar *p;
  Guchar zero = 0;
  GfxGray gray;
  GfxRGB rgb;
  int x, y;
  int c;
  int size, i;
  int pbm_mask = 0xff;

  //printf("[%d.%d.%d]\n", num, gen, mask);
  //printf("%d.%d.%d\n", ref->getRef().num, ref->getRef().gen, isMask(str));

  if (ref->getRef().num != num || ref->getRef().gen != gen || isMask(str) != mask) {
	  return;
  }

  // dump JPEG file
  if (dumpJPEG && str->getKind() == strDCT &&
      (colorMap->getNumPixelComps() == 1 ||
       colorMap->getNumPixelComps() == 3) &&
      !inlineImg) {

	jpeg = true;

    // open the image file
    //sprintf(fileName, "%s-%03d.jpg", fileRoot, imgNum);
    ++imgNum;
    //if (!(f = fopen(fileName, "wb"))) {
    //  //printf(fileName);
    //  error(-1, "Couldn't open image file '%s'", fileName);
    //  return;
    //}

    // initialize stream
    str = ((DCTStream *)str)->getRawStream();
    str->reset();

    // copy the stream
    while ((c = str->getChar()) != EOF)
      //fputc(c, f);
      myput(c);

    str->close();
    //fclose(f);

  // dump PBM file
  } else if (colorMap->getNumPixelComps() == 1 &&
	     colorMap->getBits() == 1) {

	pbm = true;

    // open the image file and write the PBM header
    //sprintf(fileName, "%s-%03d.pbm", fileRoot, imgNum);
    ++imgNum;
    //if (!(f = fopen(fileName, "wb"))) {
    //  //printf(fileName);
    //  error(-1, "Couldn't open image file '%s'", fileName);
    //  return;
    //}
    //fprintf(f, "P4\n");
    //fprintf(f, "%d %d\n", width, height);
    //printf("%d %d\n", width, height);
    w = width;
    h = height;

    // initialize stream
    str->reset();

    // if 0 comes out as 0 in the color map, the we _flip_ stream bits
    // otherwise we pass through stream bits unmolested
    colorMap->getGray(&zero, &gray);
    if(colToByte(gray))
      pbm_mask = 0;

    // copy the stream
    size = height * ((width + 7) / 8);
    for (i = 0; i < size; ++i) {
      //fputc(str->getChar() ^ pbm_mask, f);
    	//printf("fputc 2\n");
      myput(str->getChar() ^ pbm_mask);
      //myput(str->getChar());
      //myput(str->getChar());
    }

    str->close();
    //fclose(f);

  // dump PPM file
  } else {

    // open the image file and write the PPM header
    //sprintf(fileName, "%s-%03d.papm", fileRoot, imgNum);
    ++imgNum;
    //if (!(f = fopen(fileName, "wb"))) {
    // // printf(fileName);
    //  error(-1, "Couldn't open image file '%s'", fileName);
    //  return;
    //}
    //fprintf(f, "P6\n");
    //printf("%d %d\n", width, height);
    w = width;
    h = height;
    //fprintf(f, "%d %d\n", width, height);
    //fprintf(f, "255\n");

    // initialize stream
    imgStr = new ImageStream(str, width, colorMap->getNumPixelComps(),
			     colorMap->getBits());
    imgStr->reset();

    // for each line...
    for (y = 0; y < height; ++y) {

      // write the line
      p = imgStr->getLine();
      for (x = 0; x < width; ++x) {
	colorMap->getRGB(p, &rgb);
	//fputc(colToByte(rgb.r), f);
	//fputc(colToByte(rgb.g), f);
	//fputc(colToByte(rgb.b), f);
	//printf("fputc 3\n");
	myput(colToByte(rgb.r));
	myput(colToByte(rgb.g));
	myput(colToByte(rgb.b));
	p += colorMap->getNumPixelComps();
      }
    }
    imgStr->close();
    delete imgStr;

    //fclose(f);
  }
}

void ImageOutputDev::drawMaskedImage(
  GfxState *state, Object *ref, Stream *str,
  int width, int height, GfxImageColorMap *colorMap, GBool interpolate,
  Stream *maskStr, int maskWidth, int maskHeight, GBool maskInvert, GBool maskInterpolate) {
  drawImage(state, ref, str, width, height, colorMap, interpolate, NULL, gFalse);
  drawImageMask(state, ref, maskStr, maskWidth, maskHeight, maskInvert,
		maskInterpolate, gFalse);
}

void ImageOutputDev::drawSoftMaskedImage(
  GfxState *state, Object *ref, Stream *str,
  int width, int height, GfxImageColorMap *colorMap, GBool interpolate,
  Stream *maskStr, int maskWidth, int maskHeight,
  GfxImageColorMap *maskColorMap, GBool maskInterpolate) {
  drawImage(state, ref, str, width, height, colorMap, interpolate, NULL, gFalse);
  drawImage(state, ref, maskStr, maskWidth, maskHeight,
	    maskColorMap, maskInterpolate, NULL, gFalse);
}

void ImageOutputDev::myput(int c) {
  list *newLast;
 // printf("a\n");
	if (res == NULL) {
	 // printf("b\n");
		res = new list();
		 // printf("c\n");
		last = res;
		 // printf("d\n");
	} else {
	 // printf("e\n");
		newLast = new list();
		 // printf("f\n");
		last->next = newLast;
		//  printf("g\n");
		last = newLast;
		//  printf("h\n");
	}
	 // printf("i\n");
	curLen++;
	 // printf("j\n");
	last->val = c;
	 // printf("k\n");
	//printf("l\n");
}

char *ImageOutputDev::getResult(int & j) {
    //printf("m\n");
	//printf("%d\n", curLen);
	if (curLen == 0) {
		//printf("ZERO");
		char *result = (char *) malloc(6);
		j = 6;
		return result;
	}
	//char *result = new char[curLen];'
	char *result = (char *) malloc(curLen + 6);
	list *cur = res;
	result[0] = w >> 8;
	result[1] = w & 0xff;
	result[2] = h >> 8;
	result[3] = h & 0xff;
	//printf("%d %d %d %d\n", w >> 8, w & 0xff, h >> 8, h & 0xff);
	result[4] = jpeg;
	result[5] = pbm;
  for (int i = 6; i < curLen + 6; i++) {
    list *next = cur->next;
    result[i] = (unsigned char) cur->val;
    delete cur;
    cur = next;
	}
	//printf("n\n");
	j = curLen + 6;
	//w = this->w;
	//h = this->h;
	//jpeg = this->jpeg;
	return result;
}
