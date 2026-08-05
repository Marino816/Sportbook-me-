"""QA account bootstrap tests. Run: python -m pytest tests/test_bootstrap_qa.py -v"""

import os
import re
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from scripts.bootstrap_qa import bootstrap_qa_account


ENV = {
    "QA_TEST_ACCOUNT_ENABLED": "true",
    "QA_TEST_EMAIL": "qa@sportbookme.ai",
    "QA_TEST_PASSWORD": "SecurePass16Min!",
}


async def _make_mock_db(user_row=None, sub_row=None):
    """Create an AsyncMock db session — fetchone is sync, not awaitable."""
    db = AsyncMock()
    results = []

    # User lookup
    r0 = AsyncMock()
    r0.fetchone.return_value = user_row
    results.append(r0)

    # User mutation
    r1 = AsyncMock()
    r1.fetchone.return_value = None
    results.append(r1)

    # Subscription lookup
    r2 = AsyncMock()
    r2.fetchone.return_value = sub_row
    results.append(r2)

    # Subscription mutation
    r3 = AsyncMock()
    r3.fetchone.return_value = None
    results.append(r3)

    db.execute.side_effect = results
    return db


class TestBootstrapValidation:
    async def test_disabled_skips(self):
        db = AsyncMock()
        with patch.dict(os.environ, {"QA_TEST_ACCOUNT_ENABLED": "false"}):
            await bootstrap_qa_account(db)
        db.execute.assert_not_called()

    async def test_missing_email_skips(self):
        db = AsyncMock()
        with patch.dict(os.environ, {
            "QA_TEST_ACCOUNT_ENABLED": "true",
            "QA_TEST_PASSWORD": "SecurePass123!",
        }, clear=True):
            await bootstrap_qa_account(db)
        db.execute.assert_not_called()

    async def test_missing_password_skips(self):
        db = AsyncMock()
        with patch.dict(os.environ, {
            "QA_TEST_ACCOUNT_ENABLED": "true",
            "QA_TEST_EMAIL": "qa@sportbookme.ai",
        }, clear=True):
            await bootstrap_qa_account(db)
        db.execute.assert_not_called()

    async def test_short_password_skips(self):
        db = AsyncMock()
        with patch.dict(os.environ, {
            "QA_TEST_ACCOUNT_ENABLED": "true",
            "QA_TEST_EMAIL": "qa@sportbookme.ai",
            "QA_TEST_PASSWORD": "short",
        }, clear=True):
            await bootstrap_qa_account(db)
        db.execute.assert_not_called()


class TestBootstrap:
    async def test_first_startup_creates(self):
        db = await _make_mock_db(user_row=None)
        with patch.dict(os.environ, ENV, clear=True):
            await bootstrap_qa_account(db)
        assert db.execute.call_count >= 3
        db.commit.assert_called_once()

    async def test_second_startup_updates(self):
        db = await _make_mock_db(user_row=(42, "qa@sportbookme.ai"), sub_row=(99,))
        with patch.dict(os.environ, ENV, clear=True):
            await bootstrap_qa_account(db)
        db.commit.assert_called_once()

    async def test_production_refused(self):
        db = AsyncMock()
        with patch.dict(os.environ, {**ENV, "NODE_ENV": "production"}, clear=True):
            await bootstrap_qa_account(db)
        db.execute.assert_not_called()


class TestNoSecretsInLogs:
    def test_module_no_credential_logging(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "bootstrap_qa.py")
        with open(path) as f:
            source = f.read()
        for fn in ["info", "error", "warning"]:
            log_calls = re.findall(rf'logger\.{fn}\((.*?)\)', source, re.DOTALL)
            for call in log_calls:
                # Exclude env var name references like QA_TEST_PASSWORD
                assert "hash" not in call.lower()
                assert "secret" not in call.lower()
                assert "database_url" not in call.lower()