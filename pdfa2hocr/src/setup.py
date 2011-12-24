#!/usr/bin/env python

from distutils.core import setup

setup(
    name='pdfa2hocr',
    version='0.2',
    description='PDF/A to hOCR converter',
    author='Tomasz Olejniczak',
    author_email='to236111@students.mimuw.edu.pl',
    py_modules=['columnize', 'fontmap', 'hocrdirectconverter',
			'hocrexport', 'pdfa2hocr',
			'pdfminerconverter',
			'pdfminermod', 'pdfminerparser', 'pdfreader',
			'taglib', 'ttFontMod', 'utils'],
	scripts=['pdfa2hocr.py']
)
