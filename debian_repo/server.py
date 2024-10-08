import base64
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class AuthHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, auth="basic", users=None, **kwargs):
        self.auth = auth
        self.users = users
        super().__init__(*args, **kwargs)

    def __check_credentials__(self, credentials: str):
        username, password = credentials.split(':')
        return username in self.users and self.users[username] == password

    def do_GET(self):
        if not self.auth.lower() == "basic":
            super().do_GET()
            return

        # Extract the authorization header
        auth_header = self.headers.get('Authorization')

        # Check if the header is present and starts with 'Basic'
        if auth_header and auth_header.startswith('Basic '):
            # Decode the base64-encoded credentials
            credentials = base64.b64decode(auth_header.split(' ')[1]).decode('utf-8')

            # Check if the credentials match the expected username and password
            if self.__check_credentials__(credentials):
                # If authentication is successful, serve the requested file
                super().do_GET()
            else:
                # If authentication fails, return a 401 Unauthorized response
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm=\"Restricted\"')
                self.end_headers()
                self.wfile.write(b'401 Unauthorized - Invalid credentials')
        else:
            # If no authorization header is present, return a 401 Unauthorized response
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm=\"Restricted\"')
            self.end_headers()
            self.wfile.write(b'401 Unauthorized - Authentication required')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass