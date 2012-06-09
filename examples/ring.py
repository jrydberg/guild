# Copyright (c) 2012, Johan Rydberg
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

"""Example that builds a ring of actors and then send a message
through the ring.
"""

from guild import actor
import gevent


def forward(receive, address):
    pat, data = receive()
    address | data


def build(receive, n):
    ring = []
    for i in range(n):
        if not ring:
            node = actor.spawn(forward, actor.curaddr())
        else:
            node = actor.spawn(forward, ring[-1])
        ring.append(node)
        gevent.sleep()

    ring[-1] | {'text': 'hello around the ring'}
    pat, data = receive()
    return data


mesh = actor.Mesh()
node = actor.Node(mesh, 'cookie@localhost.local:3232')
addr = node.spawn(build, 10000)
print node.wait(addr)
