"""Función serverless de Vercel (runtime Python). Todas las rutas se reescriben aquí."""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from earnings_tool.server import handle_request  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _respond(self, send_body: bool):
        code, ctype, body = handle_request(self.path)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if code == 200 and "ticker=" in self.path:
            # cachear reportes en el edge de Vercel 15 min (los datos cambian poco intradía)
            self.send_header("Cache-Control", "public, s-maxage=900, stale-while-revalidate=3600")
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def do_GET(self):
        self._respond(True)

    def do_HEAD(self):
        self._respond(False)
