from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expenses = db.relationship("Expense", backref="owner", cascade="all, delete-orphan", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def load_user(user_id):
    """Reload a logged-in user from the ID stored in the session."""
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    vendor = db.Column(db.String(120), nullable=False, default="Unknown vendor")
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    category = db.Column(db.String(40), nullable=False, default="Other")
    notes = db.Column(db.String(500), default="")
    receipt_filename = db.Column(db.String(255), default="")
    ocr_text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Budget(db.Model):
    """Per-user monthly budget for one spending category."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False, index=True)  # YYYY-MM
    category = db.Column(db.String(40), nullable=False)
    limit_amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "month", "category", name="uq_user_month_category_budget"),)
