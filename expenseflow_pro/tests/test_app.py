from datetime import date
from pathlib import Path

import pytest

from app import create_app, db
from app.models import Expense, User, Budget
from app.ocr import parse_receipt, suggest_category


@pytest.fixture()
def app(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "UPLOAD_FOLDER": str(upload_dir),
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client):
    response = client.post("/auth/register", data={
        "name": "Test User", "email": "test@example.com",
        "password": "test-password-123", "confirm_password": "test-password-123",
    }, follow_redirects=True)
    assert response.status_code == 200
    return response


def test_register_and_dashboard(client):
    response = register(client)
    assert b"Total recorded spending" in response.data
    assert b"Analytics" in response.data
    assert b"Budgets" in response.data


def test_manual_expense_analytics_and_csv(client, app):
    register(client)
    response = client.post("/expenses/new", data={
        "vendor": "Corner Cafe", "amount": "125.50",
        "expense_date": date.today().isoformat(), "category": "Food", "notes": "Lunch",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Corner Cafe" in response.data
    assert client.get("/analytics").status_code == 200
    csv_response = client.get("/export.csv")
    assert csv_response.status_code == 200
    assert b"Corner Cafe" in csv_response.data
    with app.app_context():
        assert Expense.query.count() == 1


def test_budget_create_and_remove(client, app):
    register(client)
    response = client.post("/budgets", data={
        "month": date.today().strftime("%Y-%m"), "category": "Food", "limit_amount": "5000",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Food" in response.data
    with app.app_context():
        budget = Budget.query.one()
        budget_id = budget.id
    response = client.post(f"/budgets/{budget_id}/delete", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Budget.query.count() == 0


def test_receipt_parser_prioritizes_total_and_date():
    parsed = parse_receipt("GREEN CAFE\nCoffee 100.00\nDate: 2026-10-20\nGrand Total ₹125.50\nThank you")
    assert parsed["vendor"] == "GREEN CAFE"
    assert parsed["amount"] == 125.50
    assert parsed["expense_date"] == "2026-10-20"
    assert suggest_category("GREEN CAFE latte", parsed["vendor"]) == "Food"


def test_expense_routes_require_login(client):
    response = client.get("/expenses")
    assert response.status_code in (302, 303)
