# Makefile for perfSONAR Elmond
#

default:
	@true

install:
ifndef ROOTPATH
	@echo No ROOTPATH specified for installation
	@false
endif
ifndef CONFIGPATH
	@echo No CONFIGPATH specified for installation
	@false
endif
	mkdir -p ${ROOTPATH}
	mkdir -p ${CONFIGPATH}
	cp -r elmond/* ${ROOTPATH}
	cp -r config/* ${CONFIGPATH}