"""Unit tests for SQL allowlist / safety (no DB required)."""

import pytest

from opsmind.tools.sql_templates import SqlTemplate, get_template, list_templates
from opsmind.tools.sql_tool import SqlToolError, _assert_template_safe, _validate_params


def test_unknown_template_raises():
    with pytest.raises(KeyError, match="Unknown SQL template"):
        get_template("drop_everything")


def test_list_templates_nonempty():
    keys = {t["key"] for t in list_templates()}
    assert "revenue_week_totals" in keys
    assert "inventory_by_sku" in keys
    assert "inventory_low_stock" in keys


def test_writable_verbs_blocked_in_template():
    evil = SqlTemplate(
        key="evil_update",
        description="should never run",
        sql="UPDATE products SET name = 'x' WHERE id = 1",
        required_params=(),
        allowlisted_tables=("products",),
    )
    with pytest.raises(SqlToolError, match="forbidden SQL verb"):
        _assert_template_safe(evil)


def test_insert_delete_drop_blocked():
    for sql in (
        "INSERT INTO orders(id) VALUES (1)",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "TRUNCATE orders",
    ):
        evil = SqlTemplate(
            key="evil",
            description="x",
            sql=sql,
            required_params=(),
            allowlisted_tables=("orders",),
        )
        with pytest.raises(SqlToolError):
            _assert_template_safe(evil)


def test_non_allowlisted_table_blocked():
    evil = SqlTemplate(
        key="evil",
        description="x",
        sql="SELECT * FROM investigations",
        required_params=(),
        allowlisted_tables=("investigations",),
    )
    with pytest.raises(SqlToolError, match="non-allowlisted table"):
        _assert_template_safe(evil)


def test_missing_params_blocked():
    template = get_template("revenue_by_day")
    with pytest.raises(SqlToolError, match="Missing required params"):
        _validate_params(template, {"start_date": "2026-08-17"})


def test_allowlisted_templates_are_select_safe():
    for key in (
        "revenue_by_day",
        "revenue_week_totals",
        "sku_revenue_mix",
        "inventory_by_sku",
        "carrier_sla",
        "campaign_activity",
        "returns_by_reason",
        "cancelled_orders",
    ):
        _assert_template_safe(get_template(key))
