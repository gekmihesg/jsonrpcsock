#!/usr/bin/env python
import jsonrpcsock

class Handler(jsonrpcsock.BaseHandler):
    def echo(self, value):
        print(self._connection.call.echo(value))
        return "Server: " + str(value)

server = jsonrpcsock.server.ThreadingUnixStreamServer("/tmp/json.sock", Handler)
server.serve_forever()
