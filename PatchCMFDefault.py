# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""This file contains all patches for the CMFDefault product."""

from zLOG import LOG, DEBUG, INFO
from DateTime.DateTime import DateTime
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl


#############################################################
# Fix overflow error when using DateIndex for expires
#
LOG('PatchCMFDefault.DefaultDublinCoreImpl', INFO,
    'CPSCore patch __CEILING_DATE to year 3000 to prevent DateIndex overflow')

DefaultDublinCoreImpl._DefaultDublinCoreImpl__CEILING_DATE = DateTime(3000, 0)

