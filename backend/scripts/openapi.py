"""Write the API's OpenAPI schema, for the front end's generated client.

    uv run python scripts/openapi.py ../frontend/openapi.json

Built with fake sign-in, the test roster and the test content: no setting, no
GitHub.
"""

import json
import sys
from pathlib import Path

from app.main import create_app
from app.settings import Settings

fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
app = create_app(
    Settings(
        _env_file=None,
        sign_in="fake",
        roster_file=str(fixtures / "roster.csv"),
        content_dir=str(fixtures / "content"),
    )
)
Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2) + "\n")
