from guild import Actor, spawn_link, curaddr, Address, spawn, Mesh, Node
import gevent


class Server(Actor):
    """Server process for the messenger."""

    def transfer(self, user_list, from_addr, to_name, msg):
        """Send a message."""
        if from_addr not in user_list:
            from_addr | ('you-re-not-logged-on',)
            return
        from_name = user_list[from_addr]

        for to_addr, name in user_list.items():
            if name == to_name:
                break
        else:
            from_addr | ('receiver-not-found',)
            return

        to_addr | {'message': msg, 'from': from_name}

    def main(self):
        self.trap_exit = True

        LOGON = {'login': str, 'from': Address}
        EXIT = {'exit': Address}
        MESS = {'message': str, 'from': Address, 'to': str}

        user_list = {}

        while True:
            pat, msg = self.receive(LOGON, MESS, EXIT)
            if pat is EXIT:
                from_addr = msg['exit']
                if from_addr in user_list:
                    print "user %s signed off" % (user_list[from_addr],)
                    del user_list[from_addr]
            elif pat is LOGON:
                from_addr, name = msg['from'], msg['login']
                if from_addr not in user_list:
                    print "user %s logs in" % (name,)
                    user_list[from_addr]= name
                    from_addr.link()
            elif pat is MESS:
                self.transfer(user_list, msg['from'], msg['to'],
                              msg['message'])


class Client(Actor):

    def main(self, server, name):
        LOGOFF = ('log-off',)
        MESS_TO = {'message': str, 'to': str}
        MESS_FROM = {'message': str, 'from': str}

        # start by signing on
        server | {'login': name, 'from': curaddr()}
        # start the loop
        while True:
            pat, msg = self.receive(LOGOFF, MESS_TO, MESS_FROM)
            if pat is LOGOFF:
                break
            elif pat is MESS_TO:
                print "forward message", msg
                server | {'message': msg['message'], 'from': curaddr(),
                          'to': msg['to']}
            elif pat is MESS_FROM:
                print "client %s: received '%s' from %s" % (
                    name, msg['message'], msg['from'])
                if msg['message'] == '!div-zero':
                    print "client %s: i will die now" % (name,)
                    print 1 / 0


def test(receive):
    """start up some tests"""

    def send_message(c, to, msg):
        c | {'message': msg, 'to': to}

    server = spawn_link(Server)
    c1 = spawn(Client, server, 'joe')
    c2 = spawn(Client, server, 'bjarne')
    gevent.sleep()
    send_message(c1, 'bjarne', 'hello there')
    send_message(c2, 'joe', '!div-zero')
    send_message(c2, 'bjarne', '!div-zero')
    receive(timeout=2)


mesh = Mesh()
node = Node(mesh, 'localnode')
addr = node.spawn(test)
node.wait(addr)

