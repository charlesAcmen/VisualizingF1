"""
Main entry point for the FastF1 telemetry API server.
"""
from http.server import ThreadingHTTPServer

from api.handlers import TelemetryHandler


def main():
    """
    Start the FastF1 telemetry API server.
    """
    host = "0.0.0.0"
    port = 8000
    server = ThreadingHTTPServer((host, port), TelemetryHandler)
    print(f"FastF1 API server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
