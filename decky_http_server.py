"""HTTP compatibility layer for DeckyShare on frozen Decky Python."""
from __future__ import annotations
import email.utils
import io
import socket
import sys
import threading
from http import HTTPStatus
import http.client

SOCKET_BUFFER_BYTES = 8 * 1024 * 1024
KEEP_ALIVE_TIMEOUT_SECONDS = 30


class _SocketWriter(io.BufferedIOBase):
    """Unbuffered writer whose write contract always sends the full payload."""

    def __init__(self, sock):
        self._sock = sock

    def writable(self):
        return True

    def write(self, data):
        view = memoryview(data)
        self._sock.sendall(view)
        return len(view)

    def fileno(self):
        return self._sock.fileno()

class ThreadingHTTPServer:
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, server_address, RequestHandlerClass):
        self.RequestHandlerClass = RequestHandlerClass
        self._shutdown = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(server_address)
        self.socket.listen(32)
        self.socket.settimeout(0.5)
        self.server_address = self.socket.getsockname()
        self.server_name = str(self.server_address[0] or '0.0.0.0')
        self.server_port = self.server_address[1]
    def serve_forever(self, poll_interval=0.5):
        while not self._shutdown.is_set():
            try:
                request, client_address = self.socket.accept()
                request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                request.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCKET_BUFFER_BYTES)
                request.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFFER_BYTES)
                request.settimeout(KEEP_ALIVE_TIMEOUT_SECONDS)
            except socket.timeout:
                continue
            except OSError:
                if self._shutdown.is_set(): break
                raise
            threading.Thread(target=self._handle_request,args=(request,client_address),name='DeckyShareHTTPClient',daemon=True).start()
    def _handle_request(self, request, client_address):
        try:
            self.RequestHandlerClass(request, client_address, self)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            pass
        finally:
            try: request.close()
            except Exception: pass
    def shutdown(self):
        self._shutdown.set()
        try:
            with socket.create_connection(self.server_address, timeout=0.2): pass
        except Exception: pass
    def server_close(self):
        try: self.socket.close()
        except Exception: pass

class BaseHTTPRequestHandler:
    server_version = 'BaseHTTP/0.1'
    sys_version = 'Python/' + sys.version.split()[0]
    protocol_version = 'HTTP/1.1'
    default_request_version = 'HTTP/0.9'
    def __init__(self, request, client_address, server):
        self.request=request; self.connection=request; self.client_address=client_address; self.server=server
        self.close_connection=True; self.requestline=''; self.request_version=self.default_request_version
        self.command=None; self.path=''; self._headers_buffer=[]
        self.rfile=request.makefile('rb',buffering=1024*1024); self.wfile=_SocketWriter(request)
        try: self.handle()
        finally:
            try: self.wfile.flush()
            except Exception: pass
            try: self.rfile.close()
            except Exception: pass
            try: self.wfile.close()
            except Exception: pass
    def handle(self):
        self.close_connection = True
        self.handle_one_request()
        while not self.close_connection:
            self.handle_one_request()
    def handle_one_request(self):
        try:
            self.raw_requestline=self.rfile.readline(65537)
        except (TimeoutError, socket.timeout, OSError):
            self.close_connection=True; return
        if not self.raw_requestline:
            self.close_connection=True; return
        if len(self.raw_requestline)>65536:
            self.send_error(414,'Request URI too long'); return
        try: requestline=self.raw_requestline.decode('iso-8859-1').rstrip('\r\n')
        except Exception:
            self.send_error(400,'Bad request'); return
        self.requestline=requestline; parts=requestline.split()
        if len(parts) not in (2,3):
            self.send_error(400,'Bad request syntax'); return
        self.command=parts[0]; self.path=parts[1]; self.request_version=parts[2] if len(parts)==3 else 'HTTP/0.9'
        try: self.headers=http.client.parse_headers(self.rfile)
        except Exception:
            self.send_error(431,'Bad request headers'); return
        connection=str(self.headers.get('Connection','')).lower()
        if self.request_version>='HTTP/1.1':
            self.close_connection=(connection=='close')
        else:
            self.close_connection=(connection!='keep-alive')
        method=getattr(self,'do_'+self.command,None)
        if method is None:
            self.send_error(501,'Unsupported method'); return
        method()
    def version_string(self): return f'{self.server_version} {self.sys_version}'
    def date_time_string(self,timestamp=None): return email.utils.formatdate(timestamp,usegmt=True)
    def send_response(self,code,message=None):
        self.log_request(code); self.send_response_only(code,message); self.send_header('Server',self.version_string()); self.send_header('Date',self.date_time_string())
    def send_response_only(self,code,message=None):
        try: code_int=int(code)
        except Exception: code_int=500
        if message is None:
            try: message=HTTPStatus(code_int).phrase
            except Exception: message=''
        self._headers_buffer=[f'{self.protocol_version} {code_int} {message}\r\n'.encode('latin-1','strict')]
    def send_header(self,keyword,value):
        if not hasattr(self,'_headers_buffer'): self._headers_buffer=[]
        self._headers_buffer.append(f'{keyword}: {value}\r\n'.encode('latin-1','strict'))
    def end_headers(self): self._headers_buffer.append(b'\r\n'); self.flush_headers()
    def flush_headers(self):
        if self._headers_buffer:
            self.wfile.write(b''.join(self._headers_buffer)); self._headers_buffer=[]
    def send_error(self,code,message=None,explain=None):
        try: code_int=int(code)
        except Exception: code_int=500
        if message is None:
            try: message=HTTPStatus(code_int).phrase
            except Exception: message='Error'
        body=(f'{code_int} {message}\n'+(f'{explain}\n' if explain else '')).encode('utf-8','replace')
        self.send_response(code_int,message); self.send_header('Content-Type','text/plain; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Connection','close'); self.end_headers()
        if self.command!='HEAD': self.wfile.write(body)
    def log_request(self,code='-',size='-'): self.log_message('"%s" %s %s',self.requestline,str(code),str(size))
    def log_message(self,fmt,*args): pass
