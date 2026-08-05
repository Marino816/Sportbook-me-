"""QA account bootstrap tests. Run: python -m pytest tests/test_bootstrap_qa.py -v"""

import os
import re
import pytest
from unittest.mock import AsyncMock, Mock, patch
from scripts.bootstrap_qa import bootstrap_qa_account

ENV = {
    "QA_TEST_ACCOUNT_ENABLED": "true",
    "QA_TEST_EMAIL": "qa@sportbookme.ai",
    "QA_TEST_PASSWORD": "SecurePass16Min!",
}


def _make_mock_db(user_found=True, sub_found=True):
    """Create an AsyncMock db session — scalars() is sync on real SQLAlchemy Result."""
    db = AsyncMock()

    # User lookup: db.execute() returns a Result; result.scalars() is sync
    user_result = Mock()
    user_scalars = Mock()
    user_scalars.first.return_value = Mock(
        id=42, email="qa@sportbookme.ai",
        hashed_password="old_hash", is_active=True, is_pro=True,
        role="admin", active_subscription_id=99,
    ) if user_found else None
    user_result.scalars.return_value = user_scalars

    # Subscription lookup
    sub_result = Mock()
    sub_scalars = Mock()
    sub_scalars.first.return_value = Mock(
        id=99, user_id=42, plan_name="Elite Stack", status="active",
        current_period_end=None, stripe_subscription_id=None,
    ) if sub_found else None
    sub_result.scalars.return_value = sub_scalars

    db.execute.side_effect = [user_result, sub_result]
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

    async def test_production_refused(self):
        db = AsyncMock()
        with patch.dict(os.environ, {**ENV, "NODE_ENV": "production"}, clear=True):
            await bootstrap_qa_account(db)
        db.execute.assert_not_called()


class TestBootstrapORM:
    async def test_first_startup_creates_user_and_sub(self):
        db = _make_mock_db(user_found=False, sub_found=False)
        with patch.dict(os.environ, ENV, clear=True):
            await bootstrap_qa_account(db)
        assert db.add.call_count == 2
        db.commit.assert_called_once()

    async def test_startup_updates_existing(self):
        db = _make_mock_db(user_found=True, sub_found=True)
        with patch.dict(os.environ, ENV, clear=True):
            await bootstrap_qa_account(db)
        db.commit.assert_called_once()

    async def test_active_subscription_id_linked(self):
        db = _make_mock_db(user_found=False, sub_found=False)
        with patch.dict(os.environ, ENV, clear=True):
            await bootstrap_qa_account(db)

    async def test_rollback_on_error(self):
        db = AsyncMock()
        db.execute.side_effect = RuntimeError("DB failure")
        with patch.dict(os.environ, ENV, clear=True):
            with pytest.raises(RuntimeError):
                await bootstrap_qa_account(db)
        db.rollback.assert_awaited_once()


class TestNoSecrets:
    def test_no_hash_or_secret_in_logs(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "bootstrap_qa.py")
        with open(path) as f:
            source = f.read()
        for fn in ["info", "error", "warning"]:
            calls = re.findall(rf'logger\.{fn}\((.*?)\)', source, re.DOTALL)
            for call in calls:
                assert "hash" not in call.lower()
                assert "secret" not in call.lower()
                assert "database_url" not in call.lower()

    def test_no_fake_stripe_or_source_columns(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "bootstrap_qa.py")
        with open(path) as f:
            source = f.read()
        assert "cus_" not in source
        assert "sub_" not in source
        assert "pi_" not in source
        assert "source" not in source.split("logger.")[-1]  # No source column reference in non-comment code