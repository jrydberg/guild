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

from gevent_zookeeper.framework import ZookeeperFramework
from gevent.server import StreamServer

from pyact import actor
import random


class RemoteNode(object):
    """XXX"""

    def __init__(self, mesh, id, cookie):
        self.mesh = mesh
        self.id = id
        self.cookie = cookie

    def _cast(self, address, message):
        """For internal use.

        Send a message to an actor on this node.
        """
        _actor = self.actors.get(address.actor_id)
        if _actor is None or _actor.dead:
            # Silently drop the message.
            return
        _actor._cast(message)

from gevent import socket, queue
import gevent
import os.path
import msgpack

CONNECT = ('connect', str, str, int)
FORGET = ('forget', str)
NODEUP = ('node_up', str)
NODEDOWN = ('node_down', str)
EXIT = {'exit': object, 'address': actor.Address}
SUBSCRIBE = ('subscribe', Address)
DIE = ('die,')


HELLO = 0
LINK = 1
CAST = 2
EXIT = 3
UNLINK = 4
REG_SEND = 6


def recv(sock, mesh):
    """Receive."""
    unpacker = msgpack.Unpacker(object_hook=actor.generate_custom)
    while True:
        unpacker.feed(sock.read())
        while record in unpacker:
            tag = record[0]
            if tag == LINK:
                from_addr, to_addr = record[1:]
            elif tag == CAST:
                to_addr, message = record[1:]
            elif tag == EXIT:
                from_addr, to_addr, reason = record[1:]




class RemoteNode(object):

    def __init__(self, name, outq):
        self.id = name
        self.outq = outq

    def _cast(self, address, message):
        """For internal use.

        Send a message to an actor on the remote node.
        """
        self.outq.put((CAST, address, message))



def connection(sock, outq, mesh):
    """Handle a connection to a remote node.

    @param sock: The communication socket.  If the socket goes dead,
        so does this greenlet.
    @param outq: A C{Queue} where outgoing records are put.
    """

    def recv(sock, inq):
        """Process incoming messages."""
        unpacker = msgpack.Unpacker(object_hook=actor.generate_custom)
        while True:
            unpacker.feed(sock.read())
            while record in unpacker:
                inq.put(record)

    def send(sock, outq):
        """Queue."""
        packer = msgpack.Packer(default=actor.handle_custom)
        while True:
            record = outq.get()
            sock.write(packer.pack(record))

    inq = Queue()
    gevent.spawn(recv, sock, inq).link()
    gevent.spawn(send, sock, outq).link()

    try:
        while True:
            record = inq.get()
            tag = record[0]
            if tag == LINK:
                from_addr, to_addr = record[1:]
                mesh.link(from_addr, to_addr)
            elif tag == CAST:
                to_addr, message = record[1:]
                mesh.cast(to_addr, message)
            elif tag == EXIT:
                from_addr, to_addr, reason = record[1:]
                mesh.exit(from_addr, to_addr, reason)
    except gevent.LinkedExited:
        raise


class StaticCoordinator(object):
    """Network coordinator that only works with a static set of nodes.

    """

    def __init__(self, mesh, port, nodes):
        """Create a new static coordinator.

        @param nodes: A sequence of node names.
        """
        self.mesh = mesh
        self.nodes = nodes
        self.server = StreamServer(('0.0.0.0', port), self.accept)
        self.server.start()

    def accept(self, socket, address):
        """Accept an incoming connection.

        Note that this is called in an isolated greenlet, we can
        therefor block.
        """
        return handle_connection(socket, self.mesh)

    def handler(self, nodename):
        """."""
        # FIXME: parse node
        while True:
            sock = socket.socket(socket.AF_INET, sock.SOCK_STREAM)
            try:
                sock.connect((host, port))
            except socket.error:
                # FIXME: log something
                # FIXME: do exponential back-off here.
                gevent.sleep(1)
            else:
                # Wow, we're connected.
                outq = Queue()
                node = RemoteNode(nodename, outq)
                self.mesh.add(node)
                try:
                    connection(sock, outq, self.mesh)
                finally:
                    self.mesh.remove(nodename)
            sock.close()

    def start(self):
        """Start the coordinator."""
        for node in self.nodes:
            gevent.spawn(self.handler, node)


class Connection(object):

    def __init__(self, sock):
        self.sendq = Queue()
        self.sock = sock

    def recv(self, sock):
        """Process incoming messages."""
        unpacker = msgpack.Unpacker(object_hook=actor.generate_custom)
        while True:
            unpacker.feed(sock.read())
            while record in unpacker:
                tag = record[0]
                if tag == LINK:
                    from_addr, to_addr = record[1:]
                elif tag == SEND:
                    to_addr, message = record[1:]
                elif tag == EXIT:
                    from_addr, to_addr, reason = record[1:]

    def send(self, sock, queue):
        """Queue."""
        packer = msgpack.Packer(default=actor.handle_custom)
        while True:
            record = queue.get()
            sock.write(packer.pack(record))

    def cast(self, address, msg):
        """Send a message over the link."""
        self.sendq.put((SEND, address, msg))


class NodeHandler(actor.Actor):
    """Actor that operates against remote node.

    Note that this actor is only responsible for communication with
    the remote node once a connection has been established.
    """

    def _pack(self, data):
        return msgpack.dumps(data)

    def _wait(self, unpacker, sock):
        while True:
            data = sock.read()
            unpacker.feed(data)
            try:
                return msgpack.unpack()
            except StopIteration:
                pass

    def main(self, me, mesh, sock):
        self.unpacker = msgpack.Unpacker()

        # Start with our handshake.
        sock.send(self._pack(['hello', 0, me.id]))
        hello_msg = self._wait(self.unpacker, sock)
        


class _NodeHandler(actor.Actor):
    """."""
    variance = 10

    DIE = ('die',)
    DATA = ('data', str)

    def recv(self, sock, queue):
        """Receiver."""
        # Note that this is not really an actor, but we want to send
        # messages anyway, so we need to access the actor.
        sock.setTimeout(None)
        while True:
            data = sock.read()
            queue.put_nowait(data)
            self.send(self.address, ('data',))

    def main(self, name, mesh, host, port, parent):
        """."""
        state = 'unconnected'
        sock = None
        to = 1
        up = False

        dataq = queue.Queue()
        last_heard_from = None

        while True:

            if state == 'unconnected':
                if sock is None:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                sock.setTimeout(0.1)
                try:
                    sock.connect((host, port))
                except (socket.error, gevent.Timeout):
                    to = to + random.random() * self.variance
                else:
                    state = 'connected'
                    receiver = gevent.spawn_link(self.recv, sock, dataq)
                    sender = gevent.spawn_link(self.send, sock, dataq)
                    to = 0

                to = to + random.random() * self.variance

            if up and state != 'connected':
                if last_heard_from 

            try:
                pat, msg = self.receive(self.DIE, self.DATA,
                                        timeout=to)
            except gevent.LinkedExited:
                # Our receiver died for some reason.
                state, sock = 'unconnected', None
                continue
            else:
                if pat is self.DIE:
                    # The endgame.  Someone told us to die.
                    break
                elif pat is self.DATA:
                    pass


class NetKernel(actor.Actor):

    def main(self, mesh):
        """."""
        handlers = {}
        subscriptions = set()

        while True:
            pat, msg = self.receive(CONNECT, FORGET,
                                    NODEUP, NODEDOWN,
                                    EXIT, SUBSCRIBE)
            if pat is CONNECT:
                name, host, port = msg[1:]
                handlers[name] = self.spawn_link(NodeHandler, name, mesh,
                   host, port, actor.curaddr())
            elif pat is FORGET:
                name, = msg[1:]
                handlers[msg[1:]] | ('die',)
            elif pat is NODEUP or pat is NODEDOWN:
                for sub in subscriptions:
                    sub | msg
            elif pat is SUBSCRIBE:
                msg[1].monitor()
                subscriptions.add(msg[1])
            elif pat is EXIT:
                for name, addr in handlers.items():
                    if addr == msg['address']:
                        del handlers[name]
                        break
                else:
                    if pat['address'] in subscriptions:
                        subscriptions.remove(pat['address'])


def handle_connection(socket, mesh):
    """."""
    unpacker = msgpack.Unpacker()
    while True:
        try:
            data = socket.read()
            if not data:
                break
            unpacker.feed(data)
        except socket.error:
            break
        else:
            for message in unpacker.unpack():
                if message[0] == 2:
                    msgtype, method, params = message
                    if method == 'cast':
                        mesh.cast(actor.Address.from_json(
                                params[0]), params[1])
                elif message[0] == 0:
                    msg



class ZookeeperCoordinator(object):
    """Network coordinator that discovers nodes using zookeeper."""

    def __init__(self, mesh, localnode, coordinator, address=None, port=45429):
        self.framework = ZookeeperFramework(coordinator, chroot='/pyact')
        self.localnode = localnode
        self.mesh = mesh
        self.port = port
        self.address = address

    def _publish(self):
        """Publish the local node."""
        self.framework.create().parents_if_needed().as_ephemeral().with_data(
            '%s:%d' % (self.address, self.port)).for_path(
            os.path.join('nodes', self.localnode.id))

    def accept(self, socket, address):
        """Accept an incoming connection.

        Note that this is called in an isolated greenlet, we can
        therefor block.
        """
        return handle_connection(socket, self.mesh)

    def start(self):
        """Start the coordinator.

        This will connect to the ZooKeeper cluster and register our
        local node.  It will also establish connections to other
        parties of the mesh.
        """
        self.server = StreamServer(('0.0.0.0', self.port), self.accept)
        self.server.start()
        self.framework.connect()

