# -*- coding: utf-8 -*-

from . import Connection
import socket

class BaseClient(Connection):
    def __init__(self, handler=None):
        super(BaseClient, self).__init__(handler=handler)

    def connect(self, *args, **kwargs):
        pass
    
    def close(self):
        self.socket.close()

class TCPClient(BaseClient):
    def connect(self, host, port, timeout=None):
        self.socket = socket.create_connection((host, port), timeout)

class UnixClient(BaseClient):
    def connect(self, unix_socket, timeout=None):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(unix_socket)
        self.socket = sock
