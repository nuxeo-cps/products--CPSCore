# (C) Copyright 2004-2006 Nuxeo SARL <http://nuxeo.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$

from Globals import DTMLFile
from ZServer.HTTPServer import zhttp_server
from App.Management import Navigation
from portal import CPSSite

vlist = [str(x) for x in CPSSite.cps_version]
vstr = ' ' + vlist[0] + '/' + '.'.join(vlist)
vsuffix = getattr(CPSSite, 'cps_version_suffix', '')
if vsuffix:
    vstr += '-' + vsuffix

zhttp_server.SERVER_IDENT += vstr


manage_copyright = DTMLFile('zmi/copyright', globals())

Navigation.manage_copyright = manage_copyright
