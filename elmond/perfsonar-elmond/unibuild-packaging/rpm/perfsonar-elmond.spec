%define install_base        /usr/lib/perfsonar
%define elmond_base         %{install_base}/elmond
%define config_base         /etc/perfsonar/elmond
%define httpd_config_base   /etc/httpd/conf.d

#Version variables set by automated scripts
%define perfsonar_auto_version 5.0.0
%define perfsonar_auto_relnum 0.b2.1

Name:			perfsonar-elmond
Version:		%{perfsonar_auto_version}
Release:		%{perfsonar_auto_relnum}%{?dist}
Summary:		perfSONAR Elmond
License:		ASL 2.0
Group:			Development/Libraries
URL:			http://www.perfsonar.net
Source0:		perfsonar-elmond-%{version}.tar.gz
BuildArch:		noarch
Requires:       perfsonar-common
Requires:       python3
Requires:       python3-flask
Requires:       python3-elasticsearch
Requires:       python3-dateutil
Requires:       python3-isodate
Requires:       python3-urllib3
Requires:       httpd
Requires:       mod_ssl

%description
A package that installs the perfSONAR Elmond which converts Esmond queries to queries understood by Elastic.

%prep
%setup -q -n %{name}-%{version}

%build

%install
make ROOTPATH=%{buildroot}%{elmond_base} CONFIGPATH=%{buildroot}%{config_base} HTTPD-CONFIGPATH=%{buildroot}/%{httpd_config_base} install
%{__install} -D -p -m 0644 systemd/elmond.service %{buildroot}%{_unitdir}/elmond.service

%clean
rm -rf %{buildroot}

%post
#Restart/enable elmond 
%systemd_post elmond.service
if [ "$1" = "1" ]; then
    #if new install, then enable
    systemctl enable elmond.service
    systemctl start elmond.service
    #Enable and restart apache for reverse proxy
    systemctl enable httpd
    systemctl restart httpd
fi

%preun
%systemd_preun elmond.service

%postun
%systemd_postun_with_restart elmond.service

%files
%defattr(0644,perfsonar,perfsonar,0755)
%config(noreplace) %{config_base}/elmond.json
%config(noreplace) %{config_base}/logging.conf
%{elmond_base}/*.py
%{_unitdir}/elmond.service
%exclude %{elmond_base}/*.pyc
%exclude %{elmond_base}/*.pyo
%exclude %{elmond_base}/__pycache__/*.pyc
%attr(0644, perfsonar, perfsonar) %{httpd_config_base}/apache-elmond.conf

%changelog
* Tue Mar 29 2022 Daniel Neto <daniel.neto@rnp.br> - 5.0.0-0.0.a1
- Adding apache reverse proxy file

* Fri Jul 30 2021 Daniel Neto <daniel.neto@rnp.br> - 4.4.0-0.0.a1
- Initial spec file created
