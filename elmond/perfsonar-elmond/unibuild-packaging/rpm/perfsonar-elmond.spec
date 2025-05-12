%define install_base        /usr/lib/perfsonar
%define elmond_base         %{install_base}/elmond
%define config_base         /etc/perfsonar/elmond
%define httpd_config_base   /etc/httpd/conf.d
%define wsgi_config_base    /var/www/html/perfsonar/elmond

#Version variables set by automated scripts
%define perfsonar_auto_version 5.2.0
%define perfsonar_auto_relnum 0.2.b1

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
Requires:       python3-opensearch-py
Requires:       python3-dateutil
Requires:       python3-isodate
Requires:       python3-urllib3
Requires:       httpd
Requires:       mod_ssl
Requires:       mod_wsgi > 4.0

%description
A package that installs the perfSONAR Elmond which converts Esmond queries to queries understood by Elastic.

%prep
%setup -q -n %{name}-%{version}

%build

%install
make ROOTPATH=%{buildroot}%{elmond_base} CONFIGPATH=%{buildroot}%{config_base} HTTPD-CONFIGPATH=%{buildroot}/%{httpd_config_base} WSGI-CONFIGPATH=%{buildroot}/%{wsgi_config_base} install

%clean
rm -rf %{buildroot}

%post
# This link is necessary because the WSGI script imports the application using a path relative to the WSGI config directory.
ln -sT -f %{elmond_base} %{wsgi_config_base}/elmond
if [ "$1" = "1" ]; then
    #Enable and restart apache for wsgi and reverse proxy
    systemctl enable httpd
    systemctl restart httpd
fi

%postun
+%{__rm} -f %{wsgi_config_base}/elmond

%files
%defattr(0644,perfsonar,perfsonar,0755)
%config(noreplace) %{config_base}/elmond.json
%config(noreplace) %{config_base}/logging.conf
%{elmond_base}/*.py
%exclude %{elmond_base}/*.pyc
%exclude %{elmond_base}/*.pyo
%exclude %{elmond_base}/__pycache__/*.pyc
%attr(0644, perfsonar, perfsonar) %{httpd_config_base}/apache-elmond.conf
%attr(0644, perfsonar, perfsonar) %{wsgi_config_base}/elmond.wsgi

%changelog
* Tue Mar 29 2022 Daniel Neto <daniel.neto@rnp.br> - 5.0.0-0.0.a1
- Adding apache reverse proxy file

* Fri Jul 30 2021 Daniel Neto <daniel.neto@rnp.br> - 4.4.0-0.0.a1
- Initial spec file created
