# Copyright (c) 2012 Johan Rydberg
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import unittest
import gevent

from guild import spawn_link, LinkBroken, Actor, Node, Mesh

class LinkTestCase(unittest.TestCase):

    def setUp(self):
        self.mesh = Mesh()
        self.node = Node(self.mesh, 'test-node')

    def test_spawn_link_normal_exit(self):
        def actor1(receive):
            return 'value'

        class Actor2(Actor):
            def main(self):
                #self.trap_exit = True
                spawn_link(actor1)
                gevent.sleep(10)

        addr = self.node.spawn(Actor2)
        self.assertRaises(LinkBroken, self.node.wait, addr)

    def test_link_trap_exit(self):
        def actor1(receive):
            return 'value'

        class Actor2(Actor):
            def main(self):
                self.trap_exit = True
                spawn_link(actor1)
                pat, msg = self.receive()
                return msg

        addr = self.node.spawn(Actor2)
        msg = self.node.wait(addr)
        self.assertTrue(isinstance(msg, dict))
        self.assertEquals(msg['value'], 'value')
