"""Windows shell for the bundled Magic 1v1 Flask game.

The launcher owns a private localhost server and displays it inside a native
window. Closing the window shuts the server down, so no Python process remains.
"""

import threading

from werkzeug.serving import make_server

from app import app


class LocalGameServer:
    """Run Flask on an automatically selected loopback port."""

    def __init__(self):
        self.httpd = make_server("127.0.0.1", 0, app, threaded=True)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="Magic1v1Server",
            daemon=True,
        )

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_port}"

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=3)
        self.httpd.server_close()


def main():
    """Open the game window and guarantee server cleanup on exit."""
    import webview

    server = LocalGameServer()
    server.start()
    try:
        webview.create_window(
            "Magic 1v1",
            server.url,
            width=1280,
            height=880,
            min_size=(720, 620),
            background_color="#0c0e12",
        )
        # The UI uses modern JavaScript that the deprecated MSHTML/IE backend
        # cannot run. Edge Chromium is included with Windows 11 and almost all
        # supported Windows 10 installations through the WebView2 Runtime.
        webview.start(gui="edgechromium", debug=False, private_mode=True)
    finally:
        server.stop()


if __name__ == "__main__":
    main()
