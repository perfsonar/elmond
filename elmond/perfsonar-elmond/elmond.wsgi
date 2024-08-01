#
# WSGI File for elmond
#
import sys

sys.path.insert(0, '/var/www/html/elmond')

from elmond.app import app as application
