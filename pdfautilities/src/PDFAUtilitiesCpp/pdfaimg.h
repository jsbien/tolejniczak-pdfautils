#ifndef __PDFAIMG_H_
#define __PDFAIMG_H_

//char ** getImage(const char * filen, const char * name, int page);
void getImage(char ** data, int * len, const char * filen, int num, int gen, bool mask, int page);
char * getImageLen(const char * filen, int num, int gen, int page, bool mask, int & j);

#endif
