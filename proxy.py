import socket
import sys
import threading
from urllib.parse import urlparse


class ServerThread(threading.Thread):
    '''
    Forward all server response to client
    '''

    def __init__(self, server, client, clientaddr):
        threading.Thread.__init__(self)
        self.server = server
        self.client = client
        self.clientaddr = clientaddr
        self.daemon = True

    def run(self):
        while True:
            try:
                data = self.server.recv(2048)  # try to read server response
            except:
                data = b''
            if not data:
                print(self.clientaddr, 'Server closed connection')
                self.client.close()  # server closed connection, so I close client connection
                break
            self.client.send(data)  # send to client


class ClientThread(threading.Thread):
    def __init__(self, client, addr):
        threading.Thread.__init__(self)
        self.client = client
        self.server = None
        self.addr = addr
        self.daemon = True

    def run(self):
        buffer = b''
        state = 0  # initial state = 0
        rest_len = 0  # rest content-length to forward
        while True:
            if state != 0 and not buffer or state == 0 and buffer.find(b'\r\n\r\n') < 0:  # new data required
                try:
                    data = self.client.recv(2048)  # try to read client request
                except:
                    data = b''
                if not data:
                    print(self.addr, 'Client closed connection')
                    if self.server:
                        self.server.close()  # client closed connection, so I close server connection
                    break
                buffer += data
            if state == 0:  # reading headers
                index = buffer.find(b'\r\n\r\n')
                if index >= 0:
                    headers = buffer[:index].split(b'\r\n')  # split header into lines
                    buffer = buffer[index + 4:]  # extract header
                    print(self.addr, headers[0].decode("utf-8"))  # print request line
                    first_line = headers[0].split(b' ')  # process request line
                    method = first_line[0]
                    url = first_line[1]
                    version = first_line[2]
                    if method == b'CONNECT':  # https
                        index = url.find(b':')  # parse hostname and port
                        host = url[:index]
                        port = int(url[index + 1:])
                        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        print(self.addr, 'Connecting to', host.decode("utf-8"), port)
                        self.server.connect((host, port))  # connect to server
                        print(self.addr, 'Connected to', host.decode("utf-8"), port)
                        self.client.send(version + b' 200 Connection established\r\n\r\n')
                        self.server_thread = ServerThread(self.server, self.client, self.addr)
                        self.server_thread.start()  # start new server_thread
                        state = 1  # go to https forwarding mode
                    else:
                        urlp = urlparse(url)  # parse url
                        host, port = urlp.hostname, urlp.port
                        if host.endswith(b'csdn.net'):  # csdn.net is forbidden
                            self.client.send(version + b' 403 Forbidden\r\n\r\n')
                            self.client.close()
                            break
                        if not port:
                            port = 80
                        url = urlp.path  # generate url without http://domain:port
                        if urlp.query: url += b'?' + urlp.query
                        if urlp.fragment: url += b'#' + urlp.fragment
                        new_headers = [
                            b' '.join([headers[0].split(b' ')[0], url, headers[0].split(b' ')[2]])]  # new request line
                        for header in headers[1:]:  # generate new headers
                            if header.startswith(b'Proxy-Connection:'):
                                new_headers.append(header[6:])  # replace Proxy-Connection by Connection:
                            else:
                                new_headers.append(header)
                            if header.startswith(b'Content-Length:'):
                                rest_len = int(header[16:])  # get content length
                                if rest_len > 0:
                                    state = 2  # goto forwarding content mode
                        if not self.server:
                            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            print(self.addr, 'Connecting to', host.decode("utf-8"), port)
                            self.server.connect((host, port))  # connect to server
                            print(self.addr, 'Connected', host.decode("utf-8"), port)
                            self.server_thread = ServerThread(self.server, self.client, self.addr)
                            self.server_thread.start()  # start new server_thread
                        self.server.send(b'\r\n'.join(new_headers) + b'\r\n\r\n')  # send new headers to server
            elif state == 1:  # forward everything
                self.server.send(buffer)
                buffer = b''
            elif state == 2:  # forward post content
                if len(buffer) < rest_len:  # still forwarding
                    rest_len -= len(buffer)
                    self.server.send(buffer)
                    buffer = b''
                else:  # the last content
                    self.server.send(buffer[:rest_len])
                    buffer = buffer[rest_len:]
                    rest_len = 0
                    state = 0  # process next header


class ProxyServer:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.threads = []

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.ip, self.port))
        s.listen()  # listen for connections
        print('Server listening at', self.ip, self.port)
        while True:
            conn, addr = s.accept()
            print(addr, 'Client connected')
            c = ClientThread(conn, addr)  # start a new client_thread to process the new connection
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
