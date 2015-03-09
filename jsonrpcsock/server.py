# -*- coding: utf-8 -*-

from . import Connection
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

class ServerHandler(SocketServer.StreamRequestHandler):
    def handle(self):
        conn = Connection(self.request, self.server.handler)
        conn.serve()

def _BaseServer(cls, addr, handler=None, *args, **kwargs):
    server = cls(addr, ServerHandler, *args, **kwargs)
    server.handler = handler
    return server

def TCPServer(*args, **kwargs):
    return _BaseServer(SocketServer.TCPServer, *args, **kwargs)

def ThreadingTCPServer(*args, **kwargs):
    return _BaseServer(SocketServer.ThreadingTCPServer, *args, **kwargs)

def UnixStreamServer(*args, **kwargs):
    return _BaseServer(SocketServer.UnixStreamServer, *args, **kwargs)

def ThreadingUnixStreamServer(*args, **kwargs):
    return _BaseServer(SocketServer.ThreadingUnixStreamServer, *args, **kwargs)
