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
ifndef HTTPD-CONFIGPATH
	@echo No HTTPD-CONFIGPATH specified for installation
	@false
endif
	mkdir -p ${ROOTPATH}
	mkdir -p ${CONFIGPATH}
	mkdir -p ${HTTPD-CONFIGPATH}
	cp -r elmond/* ${ROOTPATH}
	cp -r config/* ${CONFIGPATH}
	cp -r apache/* ${HTTPD-CONFIGPATH}/