from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 9001

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Hello world\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Gör loggningen lite tystare (valfritt)
    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"Serving on http://{HOST}:{PORT}")
    httpd.serve_forever()

