# -*- coding: utf-8 -*-

try:
    import simplejson as json
except ImportError:
    import json
import socket

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_ERROR = -32000

class BaseHandler(object):
    def __init__(self, connection):
        self._connection = connection

class JSONObject(object):
    @property
    def json(self):
        return json.dumps(self)

class Base(dict, JSONObject):
    def __init__(self, **kwargs):
        super(Base, self).__init__(jsonrpc="2.0", **kwargs)

    @property
    def id(self):
        return self["id"]

class Batch(list, JSONObject):
    def __init__(self, *args):
        super(Batch, self).__init__(*args)

    def append_not_none(self, obj):
        if not obj is None:
            self.append(obj)

class RemoteError(Exception):
    def __init__(self, message, code=SERVER_ERROR, data=None):
        super(RemoteError, self).__init__(message)
        self.code = code
        self.data = data

class Error(RemoteError):
    code = SERVER_ERROR
    message = "Server error"

    def __init__(self, message=None, code=None, data=None):
        if message is None: message = self.message
        if code is None: code = self.code
        super(Error, self).__init__(message, code, data)

    def to_response(self, id=None):
        return ResponseError(id, self.code, str(self), self.data)

class ParseError(Error):
    code = PARSE_ERROR
    message = "Parse error"

class InvalidRequestError(Error):
    code = INVALID_REQUEST
    message = "Invalid request"

class MethodNotFoundError(Error):
    code = METHOD_NOT_FOUND
    message = "Method not found"

class InvalidParamsError(Error):
    code = INVALID_PARAMS
    message = "Invalid params"

class InternalError(Error):
    code = INTERNAL_ERROR
    message = "Internal Error"

class Response(Base):
    def __init__(self, id, **kwargs):
        super(Response, self).__init__(id=id, **kwargs)

class ResponseResult(Response):
    def __init__(self, id, result):
        super(ResponseResult, self).__init__(id=id, result=result)

class ResponseError(Response):
    def __init__(self, id, code, message, data=None):
        obj = {"code": code, "message": message }
        if not data is None:
            obj["data"] = data
        super(ResponseError, self).__init__(id=id, error=obj)

class Notification(Base):
    def __init__(self, conn, method, *args, **kwargs):
        self.conn = conn
        obj = { "method": method }
        if len(kwargs) > 0:
            obj["params"] = kwargs
        else:
            obj["params"] = args
        super(Notification, self).__init__(**obj)

class Request(Notification):
    def __init__(self, *args, **kwargs):
        super(Request, self).__init__(*args, **kwargs)
        self["id"] = self.conn.getid()
        self._response = None
        self.has_response = False

    def set_response(self, response):
        self._response = response
        self.has_response = True

    def wait(self, timeout=None):
        while not self.has_response:
            result = self.conn.read_and_dispatch(timeout)
            if not result:
                return result

    @property
    def response(self):
        self.wait()
        return self._response

class Proxy(object):
    def __init__(self, conn, notify, name=None, parent=None):
        self._conn = conn
        self._notify = notify
        self._name = name
        self._parent = parent

    def __getattr__(self, name):
        return Proxy(self._conn, self._notify, name, self)
    
    def __str__(self):
        if self._parent and self._parent._name:
            return "%s.%s" %(str(self._parent), self._name)
        return self._name

    def __call__(self, *args, **kwargs):
        return self._conn.proxy(str(self), self._notify, None, *args, **kwargs)

class Connection(object):
    """Main class that handles the connection over a socket.
    Takes an optional handler object to handle method requests.
    """
    def __init__(self, socket=None, handler=None, encoding="utf-8"):
        """
        @param socket: optional socket to use for communication
        @param handler: optional instance to call method requests from
        """
        self._buffer = ""
        self._id = 0
        self._requests = {}
        self.call = Proxy(self, False)
        self.notify = Proxy(self, True)
        self.handler = handler(self) if callable(handler) else None
        self.socket = socket
        self.encoding = encoding

    def getid(self):
        """Returns next numeric request ID
        
        @return: numeric ID
        """
        self._id += 1
        return self._id

    def read_next(self, timeout=None):
        """Read next JSON object from socket

        @param timeout: optional socket read timeout
        @return: Python object on success,
                 None on timeout,
                 False on connection end
        """
        buf = self._buffer
        dec = json.JSONDecoder()
        self.socket.settimeout(timeout)
        while True:
            if buf:
                try:
                    obj, i = dec.raw_decode(buf)
                    self._buffer = buf[i:].lstrip()
                    return obj
                except ValueError:
                    pass
            try:
                tmp = self.socket.recv(4096)
                if not tmp:
                    return False
                tmp = tmp.decode(self.encoding)
                if buf:
                    buf += tmp
                else:
                    buf = tmp.lstrip()
            except socket.timeout:
                return None

    def send(self, obj, timeout=None):
        """Send JSON object on socket

        @param obj: object to send, has to inherit from Base
        @param timeout: optional socket timeout
        @return: True on success,
                 False on timeout
        """
        self.socket.settimeout(timeout)
        try:
            data = obj.json.encode(self.encoding + "\n")
            self.socket.sendall(data)
            return True
        except socket.timeout:
            return False

    def proxy(self, method, notify, timeout=None, *args, **kwargs):
        """Proxy a method call or notification

        @param method: remote method name
        @param notify: True if notification, False if request
        @param timeout: optional socket timeout
        @param *args: optional positional method args
        @param **kwargs: optional keyword method args
        @return: None for notifactions,
                 remote method return value for requests
        """
        if notify:
            request = Notification(self, method, *args, **kwargs)
        else:
            request = Request(self, method, *args, **kwargs)
            self._requests[request.id] = request
        self.send(request, timeout)
        if not notify:
            return request.response

    def _dispatch_method(self, obj):
        id = obj.get("id", None)
        route = obj["method"].split(".")
        try:
            if not self.handler:
                raise MethodNotFoundError()
            method = self.handler
            for attr in route:
                if attr.startswith("_") or not hasattr(method, attr):
                    raise MethodNotFoundError()
                method = getattr(method, attr)
            try:
                if "params" in obj:
                    if type(obj["params"]) is dict:
                        result = method(**obj["params"])
                    elif type(obj["params"]) is list:
                        result = method(*obj["params"])
                    else:
                        raise InvalidRequestError()
                else:
                    result = method()
                response = ResponseResult(id, result)
            except TypeError as e:
                raise InvalidParamsError()
            except Exception as e:
                raise InternalError()
        except Error as e:
            response = e.to_response(id)
        if response.id:
            return response

    def _validate_response(self, obj):
        if not "id" in obj or \
                "error" in obj and "result" in obj or \
                obj["id"] is None and "result" in obj:
            raise InvalidRequestError()

    def _update_request(self, id, response=None):
        request = self._requests.pop(id, None)
        if request:
            request.set_response(response)

    def _dispatch_error(self, obj):
        self._validate_response(obj)
        try:
            error = RemoteError(**obj["error"])
            self._update_request(obj["id"])
            raise error
        except TypeError:
            raise InvalidRequestError()

    def _dispatch_result(self, obj):
        self._validate_response(obj)
        self._update_request(obj["id"], obj["result"]) 

    def _dispatch(self, obj):
        """Dispatch JSON object

        @param obj: object to process
        @return: True if object was handled successful
        """
        response = None
        try:
            if not "jsonrpc" in obj or obj["jsonrpc"] != "2.0":
                raise InvalidRequestError()
            if "error" in obj:
                self._dispatch_error(obj)
            elif "result" in obj:
                self._dispatch_result(obj)
            elif "method" in obj:
                response = self._dispatch_method(obj)
            else:
                raise InvalidRequestError()
        except Error as e:
            response = e.to_response()
        return response

    def dispatch(self, obj):
        response = None
        try:
            if isinstance(obj, list):
                batch = Batch()
                for o in obj:
                    batch.append_not_none(self._dispatch(o))
                if len(batch):
                    response = batch
            elif isinstance(obj, dict):
                response = self._dispatch(obj)
            else:
                raise InvalidRequestError()
        except Error as e:
            response = e.to_response()
        if response:
            self.send(response)

    def read_and_dispatch(self, timeout=None):
        """Read next JSON object from socket and dispatch it

        @param timeout: optional socket read timeout
        @return: True if object was read and handled,
                 None on timeout,
                 False on connection end
        """
        obj = self.read_next(timeout)
        if not obj:
            return obj
        if type(obj) is list:
            for o in obj: self.dispatch(o)
        elif type(obj) is dict:
            self.dispatch(obj)
        return True

    def serve(self):
        """Loop read_and_dispatch until connection ends"""
        while not self.read_and_dispatch() is False:
            pass
