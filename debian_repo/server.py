import base64
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from .logger import log

unauthorized_access_map = {}


class AuthHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, auth="basic", users=None, **kwargs):
        self.auth = auth
        self.users = users
        super().__init__(*args, **kwargs)

    def __check_credentials__(self, credentials: str):
        username, password = credentials.split(':')
        return username in self.users and self.users[username] == password

    @staticmethod
    def add_to_unauthorized_access_map(client_ip):
        log(f"Unauthorized access IP: {client_ip}")
        if client_ip in unauthorized_access_map:
            unauthorized_access_map[client_ip]["count"] += 1
        else:
            unauthorized_access_map[client_ip] = {"count": 1, "first": datetime.now()}

    @staticmethod
    def check_multiple_unauthorized_access(client_ip):
        if client_ip in unauthorized_access_map and unauthorized_access_map[client_ip]["count"] >= 5:
            elapsed_time_from_first = datetime.now() - unauthorized_access_map[client_ip]["first"]
            if elapsed_time_from_first.total_seconds() >= (
                    30 * 60):  # Passed 30 mins. Allow 5 failed requests for each 30 mins
                del unauthorized_access_map[client_ip]
                return False
            return True
        return False

    def send_unauthorized_response(self, client_ip):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Restricted\"')
        self.end_headers()
        self.wfile.write(b'401 Unauthorized - Invalid credentials')
        self.add_to_unauthorized_access_map(client_ip)

    def do_GET(self):
        if not self.auth.lower() == "basic":
            super().do_GET()
            return

        forwarded_for = self.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = self.client_address[0]

        if self.check_multiple_unauthorized_access(client_ip):
            self.send_response(429)
            self.end_headers()
            self.wfile.write(b'429 Too Many Requests - Rate limit exceeded')
            return

        auth_header = self.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Basic '):  # No authorization header
            self.send_unauthorized_response(client_ip)
            return

        # Decode the base64-encoded credentials
        credentials = base64.b64decode(auth_header.split(' ')[1]).decode('utf-8')

        # Check if the credentials match the expected username and password
        if self.__check_credentials__(credentials):  # Authentication success
            super().do_GET()
        else:  # Authentication fails
            self.send_unauthorized_response(client_ip)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass
