#!/usr/bin/env python
import jsonrpcsock

class Handler(jsonrpcsock.BaseHandler):
    def echo(self, value):
        return "Client: " + str(value)

client = jsonrpcsock.client.UnixClient(Handler)
client.connect("/tmp/json.sock")
for x in range(0,100):
    print(client.call.echo(value=x))
client.close()
