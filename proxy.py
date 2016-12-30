import socket
import sys
import threading
from urllib.parse import urlparse


class ServerThread(threading.Thread):
    def __init__(self, server, client):
        threading.Thread.__init__(self)
        self.server = server
        self.client = client
        self.daemon = True

    def run(self):
        while True:
            try:
                data = self.server.recv(2048)
            except:
                data = b''
            if not data:
                self.client.close()
                break
            self.client.send(data)


class ClientThread(threading.Thread):
    def __init__(self, client, addr):
        threading.Thread.__init__(self)
        self.client = client
        self.server = None
        self.addr = addr
        self.daemon = True

    def run(self):
        buffer = b''
        state = 0
        rest_len = 0
        while True:
            try:
                data = self.client.recv(2048)
            except:
                data = b''
            if not data:
                print(self.addr, 'closed')
                if self.server:
                    self.server.close()
                break
            if state == 0:  # reading headers
                buffer += data
                index = buffer.find(b'\r\n\r\n')
                if index >= 0:
                    headers = buffer[:index].split(b'\r\n')
                    print(self.addr, headers[0].decode("utf-8"))
                    method = headers[0].split(b' ')[0]
                    url = headers[0].split(b' ')[1]
                    if method == b'CONNECT':
                        index = url.find(b':')
                        host = url[:index]
                        port = int(url[index + 1:])
                        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.server.connect((host, port))
                        self.client.send(b'HTTP/1.1 200 Connection established\r\n\r\n')
                        self.server_thread = ServerThread(self.server, self.client)
                        self.server_thread.start()
                        state = 1

                    elif method == b'GET':

                        urlp = urlparse(url)
                        host, port = urlp.host, urlp.port
            elif state == 1:  # forwarding
                self.server.send(data)


class ProxyServer:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.threads = []

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.ip, self.port))
        s.listen()
        print('Server listening at', self.ip, self.port)
        while True:
            conn, addr = s.accept()
            print(addr, 'connected')
            c = ClientThread(conn, addr)
            self.threads.append(c)
            c.start()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        port = 8888
    else:
        port = int(sys.argv[1])
    try:
        ProxyServer('0.0.0.0', port).run()
    except KeyboardInterrupt:
        print('Server down')
