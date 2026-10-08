import http.server
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHROMIUM = shutil.which("chromium") or shutil.which("google-chrome")


@unittest.skipUnless(CHROMIUM, "Chromium is required for offline UI regression checks")
class OfflinePhotoTest(unittest.TestCase):
    def test_queued_photo_overlays_and_offline_reopen(self):
        # Expose the real closure only in the test response, without starting network sync.
        source = (ROOT / "static/app.js").read_text()
        self.assertEqual(source.count("  init();"), 1)
        source = source.replace(
            "  init();",
            "  window.testApp = { state, logs, logModal, additionalModal, "
            "store, cacheSession, rememberPhoto, loadQueue, photoRecord };",
        )
        checks = (ROOT / "tests/app_queue_checks.js").read_text()
        page = (
            '<!doctype html><div id="app"></div><div id="toast"></div>'
            '<dialog id="modal"></dialog><pre id="result">RUNNING</pre>'
            "<script>const report = window.fetch.bind(window);"
            "new MutationObserver(() => report('/result', {method: 'POST', "
            "body: document.querySelector('#result').textContent})).observe("
            "document.querySelector('#result'), {childList: true});</script>"
            f"<script>{source}</script><script>{checks}</script>"
        ).encode()
        finished = threading.Event()
        outcome = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, *args):
                pass

            def do_POST(self):
                outcome.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
                self.send_response(204)
                self.end_headers()
                finished.set()

        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as httpd:
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                # Keep Unix socket paths short and all browser files inside the project.
                with tempfile.TemporaryDirectory(prefix=".c", dir=ROOT) as profile:
                    browser = subprocess.Popen(
                        [CHROMIUM, "--headless", "--no-sandbox", "--disable-gpu",
                         "--disable-background-networking", "--no-proxy-server",
                         f"--user-data-dir={profile}",
                         f"http://127.0.0.1:{httpd.server_port}/"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                        cwd=ROOT, env={**os.environ, "TMPDIR": profile},
                    )
                    try:
                        completed = finished.wait(20)
                    finally:
                        browser.terminate()
                        _, errors = browser.communicate(timeout=10)
                self.assertTrue(completed, f"Chromium checks timed out: {errors[-2000:]}")
                self.assertEqual(outcome, ["PASS"])
            finally:
                httpd.shutdown()
                thread.join()
