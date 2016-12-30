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
            if state!=0 and not buffer or state==0 and buffer.find(b'\r\n\r\n')<0:
                try:
                    data = self.client.recv(2048)
                except:
                    data = b''
                if not data:
                    print(self.addr, 'closed')
                    if self.server:
                        self.server.close()
                    break
                buffer+=data
            if state == 0:  # reading headers
                index = buffer.find(b'\r\n\r\n')
                if index >= 0:
                    headers = buffer[:index].split(b'\r\n')
                    buffer=buffer[index+4:]
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
                    else:
                        urlp = urlparse(url)
                        host, port = urlp.hostname, urlp.port
                        if not port:
                            port=80
                        url=urlp.path
                        if urlp.query:url+=b'?'+urlp.query
                        if urlp.fragment:url+=b'#'+urlp.fragment
                        new_headers=[b' '.join([headers[0].split(b' ')[0],url,headers[0].split(b' ')[2]])]
                        for header in headers:
                            if header.startswith(b'Proxy-Connection:'):
                                new_headers.append(header[6:])
                            else:
                                new_headers.append(header)
                            if header.startswith(b'Content-Length:'):
                                rest_len=int(header[16:])
                                if rest_len>0:
                                    state=2
                        if not self.server:
                            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            self.server.connect((host, port))
                            self.server_thread = ServerThread(self.server, self.client)
                            self.server_thread.start()
                        self.server.send(b'\r\n'.join(new_headers)+b'\r\n\r\n')
            elif state == 1:  # forwarding
                self.server.send(buffer)
                buffer=b''
            elif state==2: # post content
                if len(buffer)<rest_len:
                    rest_len-=len(buffer)
                    self.server.send(buffer)
                    buffer=b''
                else:
                    self.server.send(buffer[:rest_len])
                    buffer=buffer[rest_len:]
                    rest_len=0
                    state=0


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
