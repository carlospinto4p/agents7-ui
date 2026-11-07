"""Load the repository's `.env` into the environment, on import.

The Compose stack hands that file to the backend container through
`env_file:`, so a container start already sees its variables. Running
the backend directly (``uv run uvicorn main:app``) did not, which left
every non-Ollama provider reporting "not ready" on the Chatter page
even when its key was sitting in the file. Importing this module
closes that gap, so both ways of starting the backend read the same
configuration.

Real environment variables always win: a name already present in
``os.environ`` is left untouched. That keeps the priority order the
file's own header documents — values set in `docker-compose.yml`'s
`environment:` block, and an explicit ``VAR=... uvicorn ...``, both
override the file.

The work happens **on import**, not in a function callers must
remember to call, because `logging_setup`, `routers.engine` and
`routers.catalog` all read variables at import time. The values have
to be in ``os.environ`` before those modules are imported, so `main`
imports this one first.
"""

from pathlib import Path

from dotenv import load_dotenv

#: The UI project's gitignored `.env`, one level above `backend/`.
ENV_PATH = Path(__file__).parents[1] / ".env"


def load_env(path: Path = ENV_PATH) -> bool:
    """Load `path` into ``os.environ`` without overriding real values.

    :param path: The dotenv file to read. A missing file is ignored,
        which is the normal case inside the Compose container.
    :return: ``True`` if the file was found and held entries.
    """
    return load_dotenv(path, override=False)


load_env()
