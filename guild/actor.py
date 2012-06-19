# Copyright (c) 2012 Johan Rydberg
# Copyright (c) 2009 Donovan Preston
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

import uuid
import weakref

try:
    import simplejson as json
except ImportError:
    import json

from gevent import Greenlet, Timeout, local, core
from gevent.event import Event
from gevent.hub import GreenletExit
import gevent

from guild import exc, shape


class ActorError(RuntimeError):
    """Base class for actor exceptions.
    """


class LinkBroken(ActorError):
    """:"""

class Killed(ActorError):
    """Exception which is raised when an Actor is killed.
    """


class DeadActor(ActorError):
    """Exception which is raised when a message is sent to an Address which
    refers to an Actor which is no longer running.
    """


class ReceiveTimeout(ActorError):
    """Internal exception used to signal receive timeouts.
    """


class InvalidCallMessage(ActorError):
    """Message doesn't match call message shape.
    """


class RemoteAttributeError(ActorError, AttributeError):
    pass


class RemoteException(ActorError):
    pass


def build_call_pattern(method,message=object):
    call_pat = CALL_PATTERN.copy()
    call_pat['method'] = method
    call_pat['message'] = message
    return call_pat


def lazy_property(property_name, property_factory, doc=None):
    def get(self):
        if not hasattr(self, property_name):
            setattr(self, property_name, property_factory(self))
        return getattr(self, property_name)
    return property(get)


_curactor = local.local()

def curactor():
    """Return the current actor."""
    return _curactor.current

def _setcurrent(actor):
    _curactor.current = actor


def curaddr():
    """Return address of current actor."""
    return curactor().address


def curmesh():
    return curactor().mesh


def curnode():
    return curactor().node


def register(name, address):
    """Associates the name C{name} with the address C{address}."""
    curnode().register(name, address)


def whereis(name):
    """Returns the address registered under C{name}, or C{None} if the
    name is not registered.
    """
    return curnode().whereis(name)


def is_actor_type(obj):
    """Return True if obj is a subclass of Actor, False if not.
    """
    try:
        return issubclass(obj, Actor)
    except TypeError:
        return False


def spawn(spawnable, *args, **kw):
    """Start a new Actor. If spawnable is a subclass of Actor,
    instantiate it with no arguments and call the Actor's "main"
    method with *args and **kw.

    If spawnable is a callable, call it inside a new Actor with the first
    argument being the "receive" method to use to retrieve messages out
    of the Actor's mailbox,  followed by the given *args and **kw.

    Return the Address of the new Actor.
    """
    return curnode().spawn(spawnable, *args, **kw)


def spawn_link(spawnable, *args, **kw):
    """Just like spawn, but the currently running Actor will be linked
    to the new actor. If an exception occurs or the Actor finishes
    execution, a message will be sent to the Actor which called
    spawn_link with details.

    When an exception occurs, the message will have a pattern like:

        {'address': eventlet.actor.Address, 'exception': dict}

    The "exception" dict will have information from the stack trace extracted
    into a tree of simple Python objects.

    On a normal return from the Actor, the actor's return value is given
    in a message like:

        {'address': eventlet.actor.Address, 'exit': object}
    """
    return curnode().spawn_link(spawnable, *args, **kw)


def handle_custom(obj):
    if isinstance(obj, Address):
        return obj.to_json()
    if isinstance(obj, Ref):
        return obj.to_json()
    raise TypeError(obj)


def generate_custom(obj):
    address = Address.from_json(obj)
    if address:
        return address
    ref = Ref.from_json(obj)
    if ref:
        return ref
    return obj


class Ref(object):
    """A reference."""

    def __init__(self, node_id, ref_id):
        self._node_id = node_id
        self._ref_id = ref_id

    ref_id = property(lambda self: self._ref_id)
    node_id = property(lambda self: self._node_id)

    def to_json(self):
        return {'_pyact_ref_id': self._ref_id,
                '_pyact_node_id': self._node_id}

    @classmethod
    def from_json(cls, obj):
        if sorted(obj.keys()) == ['_pyact_ref_id', '_pyact_node_id']:
            return Ref(obj['_pyact_node_id'], obj['_pyact_ref_id'])
        return None

    def __eq__(self, other):
        return (isinstance(other, Ref)
                and other.node_id == self.node_id
                and other.ref_id == self.ref_id)

    def __hash__(self):
        return hash((self.node_id, self._ref_id))


class MonitorRef(object):

    def __init__(self, address, ref):
        self.address = address
        self.ref = ref

    def demonitor(self):
        curmesh().demonitor(self.address, self.ref)


class Address(object):
    """An Address is a reference to another Actor.

    Any Actor which has an Address can asynchronously put a message in
    that Actor's mailbox. This is called a "cast". To send a message
    to another Actor and wait for a response, use "call" instead.

    Note that an Address instance itself is rather useless.  You need
    node or a mesh to actually send a message.
    """

    def __init__(self, node_id, actor_id):
        self._node_id = node_id
        self._actor_id = actor_id

    actor_id = property(lambda self: self._actor_id)
    node_id = property(lambda self: self._node_id)

    def to_json(self):
        return {'_pyact_actor_id': self._actor_id,
                '_pyact_node_id': self._node_id}

    @classmethod
    def from_json(cls, obj):
        if sorted(obj.keys()) == ['_pyact_actor_id', '_pyact_node_id']:
            return Address(obj['_pyact_node_id'], obj['_pyact_actor_id'])
        return None

    def __eq__(self, other):
        return (isinstance(other, Address)
                and other.node_id == self.node_id
                and other.actor_id == self.actor_id)

    def __hash__(self):
        return hash((self.node_id, self._actor_id))

    def cast(self, message):
        """Send a message to the Actor this object addresses."""
        curnode().send(self, message)

    def __repr__(self):
        return "<%s %s/%s>" % (self.__class__.__name__,
                               self._node_id, self._actor_id)

    def __str__(self):
        return "<actor %s/%s>" % (self._node_id, self._actor_id)

    def __or__(self, message):
        """Use Erlang-y syntax (| instead of !) to send messages.
               addr | msg
        is equivalent to:
               addr.cast(msg)
        """
        self.cast(message)

    def monitor(self):
        """Monitor the Actor this object addresses.

        When the actor dies, a exit message will be sent to the
        current actor.

        This call returns a reference that can be used to cancel the
        monitor with the C{demonitor} function.
        """
        ref = curnode().make_ref()
        curmesh().monitor(self, curaddr(), ref)
        return MonitorRef(self, ref)

    def demonitor(self, ref):
        """Cancel a monitor."""
        curmesh().demonitor(self, ref)

    def link(self):
        """Link the current actor to the actor this object addresses.
        """
        print "addr.link curr %s to %s" % (curaddr(), self)
        curactor().link(self)
        #curmesh().link(self, curaddr())

    def call(self, method, message=None, timeout=None):
        """Send a message to the Actor this object addresses.  Wait
        for a result. If a timeout in seconds is passed, raise
        C{gevent.Timeout} if no result is returned in less than the
        timeout.

        This could have nicer syntax somehow to make it look like an
        actual method call.
        """
        message_id = str(uuid.uuid4())
        my_address = curaddr()

        self.cast(
                {'call': message_id, 'method': method,
                'address': my_address, 'message': message})

        if timeout is None:
            cancel = None
        else:
            # Raise any TimeoutError to the caller so they can handle
            # it.
            cancel = gevent.Timeout(timeout)
            cancel.start()

        RSP = {'response': message_id, 'message': object}
        EXC = {'response': message_id, 'exception': object}
        INV = {'response': message_id, 'invalid_method': str}

        pattern, response = curactor().receive(RSP, EXC, INV)

        if cancel is not None:
            cancel.cancel()

        if pattern is INV:
            raise RemoteAttributeError(method)
        elif pattern is EXC:
            raise RemoteException(response)

        return response['message']

    def __getattr__(self, method):
        """Support address.<method>(message, timout) call pattern.

        For example:
              addr.call('test') could be written as addr.test()
        """
        f = lambda message=None, timeout=None: self.call(
            method, message, timeout)
        return f


class _Greenlet(Greenlet):
    """Private version of the greenlet that doesn't dump a stacktrace
    to stderr when a greenlet dies.
    """

    def _report_error(self, exc_info):
        self._exc_info = exc_info
        exception = exc_info[1]
        if isinstance(exception, GreenletExit):
            self._report_result(exception)
            return

        self._exception = exception
        if self._links and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)


CALL_PATTERN = {'call': str, 'method': str, 'address': Address,
                'message': object}
REMOTE_CALL_PATTERN = {'remotecall':str,
                       'method':str,
                       'message':object,
                       'timeout':object}
RESPONSE_PATTERN = {'response': str, 'message': object}
INVALID_METHOD_PATTERN = {'response': str, 'invalid_method': str}
EXCEPTION_PATTERN = {'response': str, 'exception':object}


class Monitor(object):

    def __init__(self, actor, ref, to_addr):
        self.actor = actor
        self.ref = ref
        self.to_addr = to_addr

    def _send_exit(self, *args):
        self.actor._send_exit(self.to_addr, self.ref)


class Actor(object):
    """An Actor is a Greenlet which has a mailbox.  Any other Actor
    which has the Address can asynchronously put messages in this
    mailbox.

    The Actor extracts messages from this mailbox using a technique
    called selective receive. To receive a message, the Actor calls
    self.receive, passing in any number of "shapes" to match against
    messages in the mailbox.

    A shape describes which messages will be extracted from the
    mailbox.  For example, if the message ('credit', 250.0) is in the
    mailbox, it could be extracted by calling self.receive(('credit',
    int)). Shapes are Python object graphs containing only simple
    Python types such as tuple, list, dictionary, integer, and string,
    or type object constants for these types.

    Since multiple patterns may be passed to receive, the return value
    is (matched_pattern, message). To receive any message which is in
    the mailbox, simply call receive with no patterns.
    """

    _wevent = None
    _args = (), {}

    actor_id = property(lambda self: self._actor_id)
    dead = property(lambda self: self.greenlet.ready())

    def __init__(self, run=None, node=None, mesh=None):
        if run is None:
            self._to_run = self.main
        else:
            self._to_run = lambda *args, **kw: run(self.receive, *args, **kw)
        self._actor_id = str(uuid.uuid4())
        print "created actor", self._actor_id
        self.greenlet = _Greenlet(self._run)
        self.start = self.greenlet.start
        self.start_later = self.greenlet.start_later
        self.node = node
        self.mesh = mesh
        self._mailbox = []
        self.address = Address(node.id, self._actor_id)
        self.trap_exit = False
        self.monitors = {}

    def _run(self):
        """Run the actor."""
        args, kw = self._args
        del self._args
        to_run = self._to_run
        del self._to_run
        _setcurrent(self)
        return to_run(*args, **kw)

    def _match_patterns(self,patterns):
        """Internal method to match a list of patterns against
        the mailbox. If message matches any of the patterns,
        that message is removed from the mailbox and returned
        along with the pattern it matched. If message doesn't
        match any pattern then None,None is returned.
        """
        for i, message in enumerate(self._mailbox):
            for pattern in patterns:
                if shape.is_shaped(message, pattern):
                    del self._mailbox[i]
                    return pattern, message
        return None,None

    def receive(self, *patterns, **kw):
        """Select a message out of this Actor's mailbox. If patterns
        are given, only select messages which match these shapes.
        Otherwise, select the next message.
        """
        timeout = kw.get('timeout', None)
        if timeout == 0 :
            if not patterns:
                if self._mailbox:
                    return {object: object}, self._mailbox.pop(0)
                else:
                    return None,None
            return self._match_patterns(patterns)

        if timeout is not None:
            timer = gevent.Timeout(timeout, ReceiveTimeout)
            timer.start()
        else:
            timer = None

        try:
            while True:
                if patterns:
                    matched_pat, matched_msg = self._match_patterns(patterns)
                elif self._mailbox:
                    matched_pat, matched_msg = ({object:object},
                                                self._mailbox.pop(0))
                else:
                    matched_pat = None
                if matched_pat is not None:
                    if timer:
                        timer.cancel()
                    return matched_pat, matched_msg

                self._wevent = Event()
                try:
                    # wait until at least one message or timeout
                    self._wevent.wait()
                finally:
                    self._wevent = None
        except ReceiveTimeout:
            return (None,None)

    def link(self, to_addr):
        """Link this actor to a remote address."""
        self._link(to_addr)
        self.mesh.link(to_addr, self.address)

    def _send_exit(self, to_addr, ref=None):
        """Send an exit message to the remote address."""
        if self.greenlet.exception:
            message = {'exit': self.address, 'exception': exc.format_exc(
                    self.greenlet._exc_info)}
        else:
            message = {'exit': self.address, 'value': self.greenlet.value}
        if ref:
            message['ref'] = ref
        #message = json.dumps(message, default=handle_custom)
        self.mesh.exit(self.address, to_addr, message)

    def _link(self, to_addr):
        """For internal use.

        Link the Actor at the given Address to this Actor.

        If this Actor has an unhandled exception, cast a message
        containing details about the exception to the Address.
        """
        print "we link %s to %s" % (self.address, to_addr)
        self.greenlet.link(lambda g: self._send_exit(to_addr))

    def _monitor(self, to_addr, ref):
        """For internal use.

        XXX
        """
        if self.greenlet.ready():
            self._send_exit(to_addr, ref)
        else:
            monitor = Monitor(self, ref, to_addr)
            self.greenlet.link(monitor._send_exit)
            self.monitors[ref] = monitor

    def _demonitor(self, to_addr, ref):
        if ref in self.monitors:
            monitor = self.monitors.pop(ref)
            self.greenlet.unlink(monitor._send_exit)

    def _cast(self, message):
        """For internal use.

        Nodes uses this to insert a message into this Actor's mailbox.
        """
        self._mailbox.append(message)
        if self._wevent and not self._wevent.is_set():
            self._wevent.set()

    def _exit(self, from_addr, message):
        """For internal use.

        Handle a received exit signal.
        """
        if self.trap_exit:
            self._cast(message)
        else:
            # The actor do not trap the exit, which means we should
            # terminate it.  But only if it was an abnormal
            # termination.
            if not message.has_key('value'):
                self.greenlet.kill(LinkBroken(from_addr, message),
                                   block=False)

    def _get(self, timeout=None):
        """For internal use.

        Wait until the actor finishes.
        """
        return self.greenlet.get(timeout=timeout)

    def main(self, *args, **kw):
        """If subclassing Actor, override this method to implement the Actor's
        main loop.
        """
        raise NotImplementedError("Implement in subclass.")

    def sleep(self, amount):
        gevent.sleep(amount)

    def cast(self, address, message):
        """Send a message to the given address."""
        self.mesh.cast(address, message)


class Server(Actor):
    """An actor which responds to the call protocol by looking for the
    specified method and calling it.

    Also, Server provides start and stop methods which can be overridden
    to customize setup.
    """

    def respond(self, orig_message, response=None):
        if not shape.is_shaped(orig_message, CALL_PATTERN):
            raise InvalidCallMessage(str(orig_message))
        orig_message['address'].cast({'response':orig_message['call'],
                                      'message':response})

    def respond_invalid_method(self, orig_message, method):
        if not shape.is_shaped(orig_message, CALL_PATTERN):
            raise InvalidCallMessage(str(orig_message))
        orig_message['address'].cast({'response':orig_message['call'],
                                      'invalid_method':method})

    def respond_exception(self, orig_message, exception):
        if not shape.is_shaped(orig_message, CALL_PATTERN):
            raise InvalidCallMessage(str(orig_message))
        orig_message['address'].cast({'response':orig_message['call'],
                                      'exception':exception})

    def start(self, *args, **kw):
        """Override to be notified when the server starts.
        """
        pass

    def stop(self, *args, **kw):
        """Override to be notified when the server stops.
        """
        pass

    def main(self, *args, **kw):
        """Implement the actor main loop by waiting forever for messages.

        Do not override.
        """
        self.start(*args, **kw)
        try:
            while True:
                pattern, message = self.receive(CALL_PATTERN)
                method = getattr(self, message['method'], None)
                if method is None:
                    self.respond_invalid_method(message, message['method'])
                    continue
                try:
                    self.respond(message,  method(message['message']))
                except Exception:
                    formatted = exc.format_exc()
                    self.respond_exception(message, formatted)
        finally:
            self.stop(*args, **kw)


class Mesh(object):
    """A mesh of nodes.

    Nodes are registed using C{add} when they arrive into the mesh.
    It is up to an external coordinator to detect when new nodes
    arrive.
    """

    def __init__(self):
        self._nodes = {}

    def add(self, node):
        """Add a reachable node to the mesh."""
        self._nodes[node.id] = node

    def remove(self, id):
        """Remove a node from the mesh."""
        del self._nodes[id]

    def _forward(self, address, fn, *args):
        """For internal use."""
        node = self._nodes.get(address.node_id)
        return getattr(node, fn)(*args)

    def exit(self, from_addr, to_addr, message):
        """Send an exit signal from Actor C{form_addr}."""
        print "exit", from_addr, "to", to_addr, "message", message
        self._forward(to_addr, '_exit', to_addr, from_addr, message)

    def cast(self, address, message):
        """Send a message to a node in the mesh designated by the given
        address.

        The message may be silently dropped if the remote node do not
        exit or if the actor is dead.
        """
        self._forward(address, '_cast', address, message)

    def link(self, address, to_addr):
        """Link actor C{pid1} to actor with address C{pid2}.
        """
        self._forward(address, '_link', address, to_addr)

    def monitor(self, address, to_addr, ref):
        """Monitor C{address}."""
        self._forward(address, '_monitor', address, to_addr, ref)

    def demonitor(self, address, ref):
        """."""
        self._forward(address, '_demonitor', address, ref)


class Node(object):
    """Representation of a node in a mesh of nodes."""

    id = property(lambda self: self._id)

    def __init__(self, mesh, id):
        """Create a new node."""
        self._id = id
        self._mesh = mesh
        self.actors = weakref.WeakValueDictionary()
        mesh.add(self)
        self.registry = {}

    def make_ref(self):
        """Return a new reference."""
        return Ref(self._id, str(uuid.uuid4()))

    def register(self, name, address):
        """Associates the name C{name} with the process C{address}."""
        assert address.node_id == self.id
        if address.actor_id not in self.actors:
            raise DeadActor()
        if name in self.registry:
            raise Exception("Conflicting name")
        actor = self.actors[address.actor_id]
        self.registry[name] = actor
        actor._link(lambda _: self.registry.pop(name))

    def whereis(self, name):
        """Return address of registered name C{name} or C{None} if
        there's no address with that name.
        """
        if name in self.registry:
            return self.registry[name].address

    def wait(self, address, timeout=None):
        """Wait for actor designated by address to finish."""
        assert address.node_id == self._id
        if address.actor_id not in self.actors:
            raise DeadActor()
        return self.actors[address.actor_id]._get(timeout=timeout)

    def spawn(self, spawnable, *args, **kw):
        """Start a new actor.

        If spawnable is a subclass of Actor, instantiate it with no
        arguments and call the Actor's "main" method with *args and
        **kw.

        If spawnable is a callable, call it inside a new Actor with
        the first argument being the "receive" method to use to
        retrieve messages out of the Actor's mailbox, followed by the
        given *args and **kw.

        Return the Address of the new Actor.
        """
        if is_actor_type(spawnable):
            spawnable = spawnable(node=self, mesh=self._mesh)
        else:
            spawnable = Actor(spawnable, node=self, mesh=self._mesh)

        # Add the actor to the registry, and have it removed when the
        # actor dies.
        self.actors[spawnable.actor_id] = spawnable

        # FIXME (jrydberg): We could pass this as to the ctor.
        spawnable._args = (args, kw)
        spawnable.start()
        return spawnable.address

    def spawn_link(self, spawnable, *args, **kw):
        """."""
        address = self.spawn(spawnable, *args, **kw)
        print "spawned", address
        address.link()
        return address

    def send(self, address, message):
        """Send a message to an actor on this node or another one.
        """
        self._mesh.cast(address, message)

    def _cast(self, address, message):
        """For internal use.

        Send a message to an actor on this node.
        """
        _actor = self.actors.get(address.actor_id)
        if _actor is None or _actor.dead:
            # Silently drop the message.
            return
        _actor._cast(message)

    def _exit(self, address, from_addr, message):
        try:
            _actor = self.actors[address.actor_id]
        except KeyError:
            # FIXME: Send an exit message.
            pass
        else:
            _actor._exit(from_addr, message)

    def _link(self, from_addr, to_addr):
        """For internal use."""
        try:
            _actor = self.actors[from_addr.actor_id]
        except KeyError:
            # FIXME: Send an exit message.
            pass
        else:
            _actor._link(to_addr)

    def _monitor(self, address, to_addr, ref):
        try:
            _actor = self.actors[address.actor_id]
        except KeyError:
            # FIXME: Send an exit message.
            pass
        else:
            _actor._monitor(to_addr, ref)

    def _demonitor(self, address, ref):
        try:
            _actor = self.actors[address.actor_id]
        except KeyError:
            # FIXME: Send an exit message.
            pass
        else:
            _actor._demonitor(address, ref)
