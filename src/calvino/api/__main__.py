"""Run the demo API locally: ``uv run python -m calvino.api``.

Serves the production app on port 7860, the Space's port, so a local run
matches the deployment. Needs laya installed (``uv pip install laya``): the
real loader preloads at startup and fails fast when it is missing.
"""

import uvicorn


def main() -> None:
    uvicorn.run("calvino.api.server:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
