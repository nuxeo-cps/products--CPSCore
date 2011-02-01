# (C) Copyright 2006 Nuxeo SAS <http://nuxeo.com>
# Author: Georges Racinet <gracinet@nuxeo.com>
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

#$Id$

import unittest
from zope.testing import doctest

# functions defined in doctest can't be pickled, we have to provide
# sample handlers from this module
def up_my_app_1_0_1_1(portal):
    print "my_app: 1.0 -> 1.1"
def up_my_app_1_1_1_2(portal):
    print "my_app: 1.1 -> 1.2"
def up_my_app_1_1_1_2first(portal):
    print "my_app: 1.1 -> 1.2 (first)"
def up_my_app_1_2_2_0(portal):
    print "my_app: 1.2 -> 2.0"
def up_my_app_2_0_3_0(portal):
    print "my_app: 2.0 -> 3.0"
def up_noop(portal):
    pass

handlers = dict((k, v) for k, v in globals().items()
                if k.startswith('up_'))

def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite('Products.CPSCore.upgrade'),
        doctest.DocFileTest('doc/upgrade-steps.txt',
                            package='Products.CPSCore',
                            globs=handlers,
                            optionflags=doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS),
        ))
