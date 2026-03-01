from .live_prediction_system import LivePredictionSystem


def create_server(host: str = "127.0.0.1", port: int = 8000):
    """Lazy proxy to avoid importing app.http_api during package import."""
    from .http_api import create_server as _create_server

    return _create_server(host, port)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Lazy proxy to avoid importing app.http_api during package import."""
    from .http_api import run_server as _run_server

    _run_server(host, port)


__all__ = ["LivePredictionSystem", "run_server", "create_server"]
