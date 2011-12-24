%module pdfaimg
%include "cdata.i"
%include "cstring.i"
%newobject getImage;
%cstring_output_allocate_size(char **data, int *len, free(*$1));
%inline %{
extern void getImage(char ** data, int * len, const char * filen, int num, int gen, bool mask, int page);
%}
