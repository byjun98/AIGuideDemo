from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
from threading import Thread

import pytest


@pytest.mark.skipif(not shutil.which('pwsh'), reason='PowerShell 7 is required')
@pytest.mark.parametrize('ids,success', [([0, 1, 2], True), ([0, 1], False), ([1, 2, 3], False)])
def test_adapter_preflight_reads_flat_array_and_checks_order(ids, success):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps([{'id': index} for index in ids]).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        script = (Path(__file__).resolve().parents[2] / 'eval/finish_retraining.ps1').read_text(encoding='utf-8')
        snippet = re.search(r'    \$loaded = Invoke-RestMethod[^\n]*\n    if [^\n]*', script).group()
        snippet = snippet.replace('http://127.0.0.1:8083', f'http://127.0.0.1:{server.server_port}')
        result = subprocess.run(['pwsh', '-NoProfile', '-Command', snippet], capture_output=True, timeout=15)
        assert (result.returncode == 0) == success, result.stderr.decode(errors='replace')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
