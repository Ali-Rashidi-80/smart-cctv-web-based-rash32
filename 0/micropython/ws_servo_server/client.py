"""
Websockets client for micropython

Based very heavily off
https://github.com/aaugustin/websockets/blob/master/websockets/client.py
"""

import logging
import usocket as socket
import ubinascii as binascii
import urandom as random
import ssl

from protocol import Websocket, urlparse

LOGGER = logging.getLogger(__name__)


class WebsocketClient(Websocket):
    is_client = True

def connect(uri, headers=None):
    """
    Connect a websocket.
    """

    uri = urlparse(uri)
    assert uri

    print(f"DEBUG: Connecting to {uri.hostname}:{uri.port}")

    sock = socket.socket()
    sock.settimeout(30)  # Set socket timeout to 30 seconds
    
    try:
        addr = socket.getaddrinfo(uri.hostname, uri.port)
        print(f"DEBUG: Resolved address: {addr[0][4]}")
        sock.connect(addr[0][4])
        print("DEBUG: Socket connected successfully")
    except Exception as e:
        print(f"DEBUG: Socket connection failed: {e}")
        sock.close()
        raise
    
    if uri.protocol == 'wss':
        try:
            sock = ssl.wrap_socket(sock, server_hostname=uri.hostname)
            print("DEBUG: SSL wrapped successfully")
        except Exception as e:
            print(f"DEBUG: SSL wrapping failed: {e}")
            sock.close()
            raise

    def send_header(header, *args):
        if __debug__: LOGGER.debug(str(header), *args)
        sock.write(header % args + '\r\n')

    # Sec-WebSocket-Key is 16 bytes of random base64 encoded
    key = binascii.b2a_base64(bytes(random.getrandbits(8)
                                    for _ in range(16)))[:-1]

    print("DEBUG: Sending WebSocket handshake...")
    send_header(b'GET %s HTTP/1.1', uri.path or '/')
    # اصلاح هدر Host
    if uri.port == 80:
        send_header(b'Host: %s', uri.hostname)
    else:
        send_header(b'Host: %s:%s', uri.hostname, uri.port)
    send_header(b'Connection: Upgrade')
    send_header(b'Upgrade: websocket')
    send_header(b'Sec-WebSocket-Key: %s', key)
    send_header(b'Sec-WebSocket-Version: 13')
    # اصلاح هدر Origin
    if uri.port == 80:
        origin = "http://{}".format(uri.hostname)
    else:
        origin = "http://{}:{}".format(uri.hostname, uri.port)
    send_header(b'Origin: %s', origin)
    send_header(b'User-Agent: MicroPython')
    
    # اضافه کردن هدرهای سفارشی
    if headers:
        for header in headers:
            if isinstance(header, tuple) and len(header) == 2:
                send_header(b'%s: %s', header[0].encode(), header[1].encode())
            else:
                send_header(header.encode())
    
    send_header(b'')

    print("DEBUG: Waiting for server response...")
    header = sock.readline()[:-2]
    print("DEBUG: WebSocket handshake response:", header)
    
    if not header.startswith(b'HTTP/1.1 101 '):
        print("DEBUG: Handshake failed, reading all headers...")
        # چاپ همه هدرهای پاسخ برای دیباگ
        while True:
            h = sock.readline()[:-2]
            print("DEBUG: handshake header:", h)
            if h.lower().startswith(b'location:'):
                print("DEBUG: Location header:", h)
            if not h:
                break
        sock.close()
        raise ValueError(f"WebSocket handshake failed: {header}")
    
    print("DEBUG: Handshake successful, reading remaining headers...")
    # We don't (currently) need these headers
    # FIXME: should we check the return key?
    while header:
        if __debug__: LOGGER.debug(str(header))
        header = sock.readline()[:-2]

    print("DEBUG: WebSocket connection established")
    return WebsocketClient(sock)
