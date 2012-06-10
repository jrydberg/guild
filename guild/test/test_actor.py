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

from guild import spawn_link, LinkBroken, Actor, Node, Mesh, spawn

class LinkTestCase(unittest.TestCase):

    def setUp(self):
        self.mesh = Mesh()
        self.node = Node(self.mesh, 'test-node')

    def test_spawn_link_abnormal_exit(self):
        def actor1(receive):
            return 1 / 0

        class Actor2(Actor):
            def main(self):
                spawn_link(actor1)
                gevent.sleep(1)

        addr = self.node.spawn(Actor2)
        self.assertRaises(LinkBroken, self.node.wait, addr)

    def test_spawn_link_normal_exit(self):
        def actor1(receive):
            return 'value'

        class Actor2(Actor):
            def main(self):
                #self.trap_exit = True
                spawn_link(actor1)
                gevent.sleep(0.1)
                return 'other'

        addr = self.node.spawn(Actor2)
        self.assertEquals(self.node.wait(addr), 'other')

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


class MonitorTestCase(unittest.TestCase):

    def setUp(self):
        self.mesh = Mesh()
        self.node = Node(self.mesh, 'test-node')

    def test_noproc_on_monitor_dead_actor(self):
        pass

    def test_demonitor_no_exit_signal(self):
        def child(receive):
            gevent.sleep(0.05)
            return 'exit-value'

        class Parent(Actor):

            def main(self):
                self.trap_exit = True
                addr = spawn(child)
                ref = addr.monitor()
                ref.demonitor()
                pat, msg = self.receive(timeout=0.1)
                return msg

        addr = self.node.spawn(Parent)
        msg = self.node.wait(addr)

    def test_receive_exit_signal(self):

        def child(receive):
            return 'exit-value'

        class Parent(Actor):

            def main(self):
                self.trap_exit = True
                addr = spawn(child)
                ref = addr.monitor()
                pat, msg = self.receive(timeout=0.1)
                return msg

        addr = self.node.spawn(Parent)
        msg = self.node.wait(addr)
        self.assertEquals(msg['value'], 'exit-value')
        self.assertTrue('exit' in msg)
        self.assertTrue('ref' in msg)

    def test_monitor_finished_actor(self):

        def child(receive):
            return 'exit-value'

        class Parent(Actor):

            def main(self):
                self.trap_exit = True
                addr = spawn(child)
                gevent.sleep()
                ref = addr.monitor()
                pat, msg = self.receive(timeout=0.1)
                return msg

        addr = self.node.spawn(Parent)
        msg = self.node.wait(addr)
        self.assertEquals(msg['value'], 'exit-value')
        self.assertTrue('exit' in msg)
        self.assertTrue('ref' in msg)
