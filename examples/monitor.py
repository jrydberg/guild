import gevent

from guild import actor


def actor1(receive):
    return 'value'

class Actor2(actor.Actor):

    def main(self, addr1):
        self.trap_exit = True
        addr1.monitor()
        pat, msg = self.receive()
        print msg


mesh = actor.Mesh()
node1 = actor.Node(mesh, 'node1')
node2 = actor.Node(mesh, 'node2')


addr1 = node1.spawn(actor1)
addr2 = node2.spawn(Actor2, addr1)

try:
    print node2.wait(addr2)
except Exception:
    print "GOT ERROR"
    raise

