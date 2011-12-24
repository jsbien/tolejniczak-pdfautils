#!/usr/bin/env python

from distutils.core import setup

setup(
    name='PDFAUtilities',
    version='0.2',
    description='PDFA structure browser, converter to hOCR and validator',
    author='Tomasz Olejniczak',
    author_email='to236111@students.mimuw.edu.pl',
    data_files=[('resources', ['next.png', 'prev.png', 'psb.ico', 'text.png'])],
    py_modules=['columnize', 'dialogs', 'fontmap', 'hocrdirectconverter',
			'hocrexport', 'imagextract', 'pdfa2hocr', 'pdfareader',
			'pdfastructurebrowser', 'pdfavalidate', 'pdfminerconverter',
			'pdfminermod', 'pdfminerparser', 'pdfreader', 'physbrowser',
			'taglib', 'test', 'ttFontMod', 'utils', 'exif'],
	scripts=['pdfa2hocr.py', 'pdfastructurebrowser.py', 'pdfavalidate.py']
)

