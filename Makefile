# Makefile for perfSONAR Elmond
#
PACKAGE=perfsonar-elmond
ROOTPATH=/usr/lib/perfsonar/elmond
CONFIGPATH=/etc/perfsonar/elmond
HTTPD-CONFIGPATH=/etc/httpd/conf.d
PERFSONAR_AUTO_VERSION=5.0.0
PERFSONAR_AUTO_RELNUM=0.b2.1
VERSION=${PERFSONAR_AUTO_VERSION}
RELEASE=${PERFSONAR_AUTO_RELNUM}
DC_CMD_BASE=docker-compose
DC_CMD=${DC_CMD_BASE} -p ${PACKAGE}

centos7:
	mkdir -p ./artifacts/centos7
	${DC_CMD} -f docker-compose.build.yml up --build --no-start centos7
	docker cp ${PACKAGE}_centos7_1:/root/rpmbuild/SRPMS ./artifacts/centos7/SRPMS
	docker cp ${PACKAGE}_centos7_1:/root/rpmbuild/RPMS/noarch ./artifacts/centos7/RPMS

dist:
	mkdir /tmp/${PACKAGE}-${VERSION}.${RELEASE}
	cp -rf ./apache ./config ./elmond ./systemd ./Makefile ./perfsonar-elmond.spec /tmp/${PACKAGE}-${VERSION}.${RELEASE}
	tar czf ${PACKAGE}-${VERSION}.${RELEASE}.tar.gz -C /tmp ${PACKAGE}-${VERSION}.${RELEASE}
	rm -rf /tmp/${PACKAGE}-${VERSION}.${RELEASE}

install:
	mkdir -p ${ROOTPATH}
	mkdir -p ${CONFIGPATH}
	mkdir -p ${HTTPD-CONFIGPATH}
	cp -r elmond/* ${ROOTPATH}
	cp -r config/* ${CONFIGPATH}
	cp -r apache/* ${HTTPD-CONFIGPATH}/

dc_clean:
	${DC_CMD} -f docker-compose.build.yml down -v
