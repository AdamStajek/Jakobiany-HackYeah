"""Disposable API for browser integration tests; never uses the project database or a live AI service."""

import os
import tempfile
from pathlib import Path
from secrets import token_bytes

import uvicorn
from account_fixture import create_database
from pydantic_ai.models.test import TestModel

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="hackyeah-account-browser-") as folder:
        path = Path(folder) / "accounts.sqlite3"
        create_database(path)
        os.environ.update(
            DATABASE_PATH=str(path),
            SESSION_COOKIE_SECURE="false",
            OPENAI_API_KEY="browser-test-key",
        )
        from hackyeah import auth
        from hackyeah import models as m
        from hackyeah.main import app
        from hackyeah.needs import needs_agent

        salt = token_bytes(16)
        auth.users["moderator@example.com"] = (
            m.User(
                id="test-moderator",
                display_name="Moderator",
                roles=["user", "moderator"],
            ),
            salt,
            auth._hash("moderator-test-password", salt),
        )
        output = {
            "constraints": {
                **{key: None for key in m.Constraints.model_fields},
                "max_steps": 0,
                "require_step_free_access": True,
                "max_distance_without_rest_m": 300,
            },
            "summary": "Bez schodów, odpoczynek co 300 metrów.",
            "questions": [],
            "requires_confirmation": True,
        }
        with needs_agent.override(model=TestModel(custom_output_args=output)):
            uvicorn.run(app, host="127.0.0.1", port=8137)
