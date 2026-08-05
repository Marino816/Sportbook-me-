"""QA account seeder tests. Run: python -m pytest tests/test_seed_qa.py -v"""

import os
import re
import pytest
from scripts.seed_qa_account import _validate


class TestValidation:
    def test_production_refused(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "production")
        monkeypatch.setenv("QA_TEST_ACCOUNT_ENABLED", "true")
        monkeypatch.setenv("QA_TEST_EMAIL", "qa@test.com")
        monkeypatch.setenv("QA_TEST_PASSWORD", "SecurePass123!")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        with pytest.raises(SystemExit):
            _validate()

    def test_disabled_refused(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "staging")
        monkeypatch.setenv("QA_TEST_ACCOUNT_ENABLED", "false")
        monkeypatch.setenv("QA_TEST_EMAIL", "qa@test.com")
        monkeypatch.setenv("QA_TEST_PASSWORD", "SecurePass123!")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        with pytest.raises(SystemExit):
            _validate()

    def test_missing_password_refused(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "staging")
        monkeypatch.setenv("QA_TEST_ACCOUNT_ENABLED", "true")
        monkeypatch.setenv("QA_TEST_EMAIL", "qa@test.com")
        monkeypatch.delenv("QA_TEST_PASSWORD", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        with pytest.raises(SystemExit):
            _validate()

    def test_short_password_refused(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "staging")
        monkeypatch.setenv("QA_TEST_ACCOUNT_ENABLED", "true")
        monkeypatch.setenv("QA_TEST_EMAIL", "qa@test.com")
        monkeypatch.setenv("QA_TEST_PASSWORD", "short")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        with pytest.raises(SystemExit):
            _validate()

    def test_valid_passes_validation(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "staging")
        monkeypatch.setenv("QA_TEST_ACCOUNT_ENABLED", "true")
        monkeypatch.setenv("QA_TEST_EMAIL", "qa@sportbookme.ai")
        monkeypatch.setenv("QA_TEST_PASSWORD", "SecurePass16Min!")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        _validate()


class TestNoSecretsInLogs:
    def test_log_calls_exclude_password(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "seed_qa_account.py")
        with open(path) as f:
            source = f.read()
        log_lines = re.findall(r'logger\.(info|error|warning|debug)\(.*\)', source)
        for line in log_lines:
            assert "password" not in line.lower()
            assert "hash" not in line.lower()


class TestStripeSafety:
    def test_no_stripe_ids_in_seed(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "seed_qa_account.py")
        with open(path) as f:
            source = f.read()
        assert not re.search(r'cus_[A-Za-z0-9]{8,}', source)
        assert not re.search(r'sub_[A-Za-z0-9]{8,}', source)
        assert not re.search(r'pi_[A-Za-z0-9]{8,}', source)
        assert "stripe_customer_id" not in source
        assert "stripe_subscription_id" not in source