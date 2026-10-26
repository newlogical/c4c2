import http.server, json, urllib.parse, sys
STATE = {"mode": "10", "stuck": len(sys.argv) > 1}
CODES = {"bluetooth": "41", "line-in": "40", "optical": "43", "wifi": "10"}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        cmd = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("command", [""])[0]
        if cmd.startswith("setPlayerCmd:switchmode:"):
            if not STATE["stuck"]: STATE["mode"] = CODES[cmd.split(":")[-1]]
            body = "OK"
        elif cmd == "getPlayerStatus": body = json.dumps({"status": "play", "vol": "50", "mode": STATE["mode"], "Title": "", "Artist": ""})
        else: body = "{}"
        b = body.encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8098), H).serve_forever()
