# Guild, actors for python (and gevent)

Since the dawn of concurrency research, there have been two camps:
shared everything, and shared nothing. Most modern applications use
threads for concurrency, a shared everything architecture.

Actors, however, use a shared nothing architecture where lightweight
processes communicate with each other using message passing. Actors
can change their state, create a new Actor, send a message to any
Actor it has the Address of, and wait for a specific kind of message
to arrive in it's mailbox.

*guild* is a small package that provides actors in a python+gevent
environment.  It is quite closely modelled after probably the most
known actor-based language and runtime: Erlang.

Requirements:

 * gevent 0.13
 * a large dose of patience

# How Are Actors Implemented in guild?

*gevent* and greenlet threads are used to implement the actor
processes.  This doesn't provide real isolation: but python doesn't
provide private either.

*guild* has no copy-on-send semantics and leave the responsibility of
sending immutable messages on the user.  It is also recommended to use
the persisntent data structures that comes with guild.  There's a
whole section on those later in this document.

It is also recommended that you stay away from writing code that
absule global module state.

# How To Use guild

Most stuff lives in the `guild` package:

 * `guild.Mesh` represents the mesh of connected nodes.
 * `guild.Node` is a local node.
 * `guild.Actor` is an actor.

To get going you need to create a mesh and a local node:

    mesh = guild.Mesh()
    node = guild.Node(mesh, 'node-id')

The second argument to `Node` is the name of the node and must be
unique within your mesh.

When the node is set up the first actor can be created:

    address = node.spawn(fn)

`fn` is a function that receives a *receive* funcion as the first
argument.

There are two ways to create an actor: either by subclassing `Actor`
or by just passing a function to `spawn`.  Arguments passed to `spawn`
are forwarded to the actor:

    import guild, gevent

    def forward(receive, address):
        pat, data = receive()
        address | data

    def build(receive, n):
        ring = []
        for i in range(n):
            if not ring:
                node = guild.spawn(forward, guild.curaddr())
            else:
                node = guild.spawn(forward, ring[-1])
            ring.append(node)

        ring[-1] | {'text': 'hello around the ring'}
        pat, data = receive()
        return data

    mesh = guild.Mesh()
    node = guild.Node(mesh, 'node-id')
    addr = node.spawn(build, 10000)
    print node.wait(addr)

This passes *10000* as `n` to the actor function `build`.  This
creates 10,000 sub-actors, where actor N will forward any received
message to actor N+1 and then die.  When all actors has been created a
message is sent through the ring.

Worth noting is the `curaddr()` function that returns the address of
the current actor.  Another neat function is the `node.wait` function
that waits for a local actor to finish and returns the result.

## Receiving Messages

*guild* has just like Erlang selective receive.  This means that if
messages in the mailbox will be left there if the call to *receive* do
not provide a matching pattern.

Patterns are python objects that can contain "wildcard types".  A
simple example is the following dictionary pattern: `{"name": int}`.
This will match `{"name": 1}` but not `{"name": "data"}`.  The type
`object` will match anything.

    DATA = ('data', str)
    EVENT = {'event': str, 'data': object}

    pat, msg = receive(DATA, EVENT)
    if pat is DATA:
       print "we got some data", msg[1]
    if pat is EVENT:
       print "wow, an event", msg['event'], msg['data']

Note that tuples must match is length.  This is not true for lists,
which is used to match arrays.  The first element in an array match is
a type: `[str]` will match `['a', 'b']` but not `[1, 'b']`.


# Persistent Data Structures

From Wikipedia:

> [...] a persistent data structure is a data structure that always
> preserves the previous version of itself when it is modified. Such
> data structures are effectively immutable, as their operations do
> not (visibly) update the structure in-place, but instead always
> yield a new updated structure. (A persistent data structure is not a
> data structure committed to persistent storage, such as a disk; this
> is a different and unrelated sense of the word "persistent.")

*guild* comes with two persistent data structures: a list and a
dictionary.  The list, `guild.plist`, looks pretty much like a list in
Scheme or Clojure.  The list has two properties: `first` is the first
element of the list and `rest` is the following elements of the list
as another `plist`.  The list has a function `cons` that can be used
to create a list with a given value as the first element:

    >>> plist([1, 2, 3]).cons(0)
    plist([0, 1, 2, 3])

Use `concat` to concatenate two lists.  Returns the new list:

    >>> plist([0, 1]).concat(plist([2, 3]))
    plist([0, 1, 2, 3])

(It is also possible to concatenate a regular list to a *plist*.).  If
you just want to append a single value to the list, use `append`.

It is also possible to create a new list where a single element has
been replaced.  Do this with `replace`:

    >>> plist([0, 2, 3]).replace(2, 1)
    plist([0, 1, 3])

To get a new list with some values filtered out, use the `without`
method:

    >>> plist([1, 2, 3]).without(2, 3)
    plist([0])

The persistent dictionary, `guild.pdict`, is a regular `dict` except
it is immutable. It has two extra methods, `using` and `without`, as
demostrated below:

    >>> pdict(a=1).using(b=2)
    {'a': 1, 'b': 2}
    >>> pdict(a=1, b=2).without('b')
    {'a': 1}

# Roadmap

* Get remote nodes working so we can build actual networks
* Proper linking and monitoring
* Create basic constructs such as supervisors and routers
* Slicing of persistent lists.

# Credits

*guild* is based on Donovan Preston's python-actors.  Many thanks to
him and his great work.
