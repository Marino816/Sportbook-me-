from services.paykings_recurring import (
    build_delete_subscription_fields,
    parse_recurring_snapshots,
    parse_transact_response,
)


def test_build_delete_subscription_fields():
    fields = build_delete_subscription_fields(subscription_id="12574008155", key="sec")
    assert fields == {
        "security_key": "sec",
        "recurring": "delete_subscription",
        "subscription_id": "12574008155",
    }
    assert "amount" not in fields
    assert "payment_token" not in fields


def test_parse_delete_approved_response():
    parsed = parse_transact_response(
        "response=1&responsetext=Recurring Transaction Deleted&authcode=&transactionid=12574008155"
        "&avsresponse=&cvvresponse=&orderid=&type=&response_code=100&subscription_id=12574008155"
    )
    assert parsed.approved is True
    assert parsed.responsetext == "Recurring Transaction Deleted"
    assert parsed.subscription_id == "12574008155"
    assert parsed.response_code == "100"


def test_parse_recurring_snapshots_omits_card_data():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<nm_response>
  <subscription id="12574008155">
    <subscription_id>12574008155</subscription_id>
    <plan>
      <plan_id>SBME_PRO_MONTHLY</plan_id>
      <plan_amount>49.99</plan_amount>
    </plan>
    <next_charge_date>2026-11-17</next_charge_date>
    <cc_number>4xxxxxxxxxxx8963</cc_number>
  </subscription>
</nm_response>
"""
    rows = parse_recurring_snapshots(xml)
    assert len(rows) == 1
    assert rows[0].subscription_id == "12574008155"
    assert rows[0].plan_id == "SBME_PRO_MONTHLY"
    assert rows[0].plan_amount == "49.99"
    assert rows[0].next_charge_date == "2026-11-17"
    assert not hasattr(rows[0], "cc_number")


def test_parse_empty_recurring_response():
    assert parse_recurring_snapshots("<?xml version='1.0'?><nm_response></nm_response>") == []
