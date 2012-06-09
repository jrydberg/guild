# Copyright (c) 2012, Johan Rydberg
# Copyright (c) 2009, Donovan Preston
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

"""This is a little example of how symbolic names can be registered
to addresses and that other actors can use the `whereis` function to
look them up.

Note that `actor.register` and `actor.whereis` only works from within
an actor.  A `Node` object provides the same functions.
"""

from pyact import actor


def caller(receive, parent):
    actor.whereis('test') | {'text': 'hello world'}


def server(receive):
    actor.register('test', actor.curaddr())
    actor.spawn(caller, actor.curaddr())
    pat, data = receive()
    return data


mesh = actor.Mesh()
node = actor.Node(mesh, 'jrydberg@localhost.local')
addr = node.spawn(server)
print node.wait(addr)
# Make sure that the address is no longer there when the actor has
# died.
print node.whereis('test')
