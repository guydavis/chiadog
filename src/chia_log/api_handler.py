import cgi
import json
import logging

from functools import partial
from http.server import BaseHTTPRequestHandler
from typing import Optional

from src.notifier.notify_manager import NotifyManager
from src.notifier import Event, EventType, EventPriority, EventService

import http.server
import socketserver
import threading

PORT = 8925

class RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, notify_manager, *args, **kwargs):
        self.notify_manager = notify_manager
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
    def do_HEAD(self):
        self._set_headers()
        
    # GET sends back a Hello world message
    def do_GET(self):
        self._set_headers()
        self.wfile.write(json.dumps({'hello': 'world', 'received': 'ok'}).encode('utf-8'))
        
    # POST echoes the message adding a JSON field
    def do_POST(self):
        ctype, pdict = cgi.parse_header(self.headers['content-type'])
        
        # refuse to receive non-json content
        if ctype != 'application/json':
            self.send_response(400)
            self.end_headers()
            return
            
        # read the message and convert it into a python dictionary
        length = int(self.headers['content-length'])
        message = json.loads(self.rfile.read(length))

        if 'type' in message:
            event_type = EventType[message['type'].upper()]
        else:
            self.send_response(400)
            self.end_headers()
            return

        if 'priority' in message:
            event_priority = EventPriority[message['priority'].upper()]
        else:
            self.send_response(400)
            self.end_headers()
            return

        if 'service' in message:
            event_service = EventService[message['service'].upper()]
        else:
            self.send_response(400)
            self.end_headers()
            return
        
        if not 'message' in message:
            self.send_response(400)
            self.end_headers()
            return

        event = Event(type=event_type, priority=event_priority, service=event_service, message=message['message'])
        self.notify_manager.process_events([event])

        # send the message back
        self._set_headers()
        self.wfile.write("Event received and notifications sent.".encode('utf-8'))

class ApiHandler():

    def __init__(self, notify_manager: NotifyManager):
        self._notify_manager = notify_manager
        handler = partial(RequestHandler, notify_manager)
        self.httpd = socketserver.TCPServer(("", PORT), handler)
        self.thread = threading.Thread(target=self.start_server)
        self.thread.start()

    def start_server(self):
        logging.info("Starting API event receiver on port 8925 within the container only.")
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            # Clean-up server (close socket, etc.)
            self.httpd.server_close()

    def stop_server(self):
        logging.info("Stopping API event receiver on port 8925 within the container only.")
        self.httpd.shutdown()
        self.thread.join()
