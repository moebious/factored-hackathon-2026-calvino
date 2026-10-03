"""The production ASGI app: ``uvicorn calvino.api.server:app``.

Wires the real ``LayaLoader`` and environment settings. Importing this module
is safe without laya installed (the client imports the package lazily); the
boot then fails fast at preload, which is what a container with baked-in
weights should do when something is missing.
"""

from calvino.api.app import create_app
from calvino.api.loader import LayaLoader

app = create_app(LayaLoader())
