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

"""A somewhat crappy example of how you can implement a FMS."""

from pyact import actor
import gevent
import time

EVENT = {'name': str}


class StateMachine(actor.Actor):
    """Base class for state machine actors.

    Create FMS actors with the initial state name and data as
    arguments.

    Method with the name of the state will be called when an event is
    received.  First argument is the current data, and then comes the
    event name and possible some data provided with the event.

    The state method should return a tuple of new state and new data,
    and an optional timeout.  If the next state times out, a "timeout"
    event will be sent to the state.  If the state method cannot
    handle the event then it should return *None* which will result in
    a call to `handle_event`.

    The state `stop` is special so that it will halt the state machine
    and end the actor with the current data as result.

    Events are sent with `send_event`.
    """

    def main(self, state, data):
        """Main function for the state machinery.

        @param state: Name of the initial state.
        @param data: Initial data state.
        """
        timeout = None

        while state != 'stop':
            pat, msg = self.receive(EVENT, timeout=timeout)
            if pat is None:
                msg = {'name': 'timeout'}

            print "state", state, "event", msg['name']

            result = getattr(self, state)(data, msg['name'],
                 *msg.get('data', tuple()))

            if result is None:
                result = self.handle_event(state, data, msg['name'],
                    *msg.get('data', tuple()))

            try:
                state, data, timeout = result
            except ValueError:
                state, data = result
                timeout = None

        return data

    def handle_event(self, state, data, event, *args):
        """Handle incoming event regardless of current state."""
        return state, data


def send_event(actor, event, *args):
    """Send an event to a state machine."""
    actor | {'name': event, 'data': args}


class DoorLock(StateMachine):
    """Example state machine that simulates a digital door lock that
    opens for 3 seconds if the correct code was entered.
    """

    def locked(self, (incomplete, code), event, digit):
        if event == 'button':
            incomplete = incomplete + [digit]
            if incomplete == code:
                # open for three seconds, and then have a timeout
                # being sent to us.
                return 'open', ([], code), 3
            elif len(incomplete) == len(code):
                return 'locked', ([], code)
            else:
                return 'locked', (incomplete, code)

    def open(self, (incomplete, code), event):
        if event == 'timeout':
            # Here we should really return to locked, but
            # lets die instead:
            #return 'locked', ([], code)
            return 'stop', None


def start(node, code):
    """Start a new door lock actor with the given code.
    """
    return node.spawn(DoorLock, 'locked', ([], code))


def button(addr, digit):
    """Send a digit to the door lock."""
    send_event(addr, 'button', digit)


def tester(receive, addr):
    button(addr, '1')
    button(addr, '2')
    button(addr, '3')
    button(addr, '4')


mesh = actor.Mesh()
node = actor.Node(mesh, 'jrydberg@localhost.local:3232')
addr = start(node, ['1', '2', '3', '4'])
test = node.spawn(tester, addr)
node.wait(test)
node.wait(addr)
