# QA Staging Account — Sportsbook Me DFS AI

**Purpose**: Provide a reproducible, secure admin account for QA testing on Railway staging.

**Do NOT use this account in Production. It must never exist outside staging.**

## Required Railway Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `QA_TEST_EMAIL` | `qa@sportbookme.ai` | QA account identifier |
| `QA_TEST_PASSWORD` | (secure value) | At least 8 UTF-8 bytes. Rotate regularly. |
| `QA_TEST_ACCOUNT_ENABLED` | `true` | Must be set to enable the seeder |
| `NODE_ENV` | `staging` | Must NOT be `production` |

## Running the Seeder

```bash
# On Railway staging (from backend directory):
python -m scripts.seed_qa_account
```

The command:
- Refuses to run in production
- Refuses to run unless `QA_TEST_ACCOUNT_ENABLED=true`
- Reads email and password from environment variables only
- Creates or updates the account idempotently
- Sets `role=admin`, `is_active=true`, `is_pro=true`
- Assigns Elite Stack entitlement with `source=qa_seed`, `environment=staging`
- Never creates fake Stripe customer or subscription IDs
- Commits atomically
- Logs only safe confirmation details (never password or hash)

## Verifying the Account

```sql
-- Check user record
SELECT id, email, role, is_active, is_pro FROM users WHERE email = 'qa@sportbookme.ai';

-- Check subscription entitlement
SELECT id, user_id, plan_name, status, source, environment FROM subscriptions WHERE source = 'qa_seed';
```

Expected: `role = 'admin'`, `is_active = true`, `is_pro = true`, `plan_name = 'Elite Stack'`, `source = 'qa_seed'`.

## Rotating the Password

1. Update `QA_TEST_PASSWORD` in Railway Variables to the new value.
2. Run `python -m scripts.seed_qa_account` again.
3. The seeder will update the existing account with the new hashed password.
4. Verify login works with the new password.

## Disabling the Account

Set `QA_TEST_ACCOUNT_ENABLED=false`. The seeder will refuse to run. The account remains in the database but cannot be re-seeded.

To disable login access without deleting:

```sql
UPDATE users SET is_active = false WHERE email = 'qa@sportbookme.ai';
UPDATE subscriptions SET status = 'inactive' WHERE source = 'qa_seed';
```

## Deleting the Account

```sql
DELETE FROM subscriptions WHERE source = 'qa_seed';
DELETE FROM users WHERE email = 'qa@sportbookme.ai';
```

## Warnings

- This account must NEVER exist in Production.
- The password must NEVER appear in source code, logs, migrations, or Git history.
- No fake Stripe IDs are created — the subscription uses `source=qa_seed`.
- The `is_pro` flag is set directly on the user record, bypassing Stripe webhook validation.
- This entitlement applies ONLY to the QA staging user, not globally.