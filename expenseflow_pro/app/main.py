import csv
import io
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, extract
from . import db
from .models import Expense, Budget
from .ocr import extract_text, parse_receipt, suggest_category

main_bp = Blueprint("main", __name__)
CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Health", "Office", "Other"]

def owned_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not expense:
        abort(404)
    return expense

@main_bp.route("/")
@login_required
def dashboard():
    today = date.today()
    month_start = today.replace(day=1)
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(8).all()
    all_total = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter_by(user_id=current_user.id).scalar()
    month_total = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= month_start,
        Expense.expense_date <= today
    ).scalar()
    count = Expense.query.filter_by(user_id=current_user.id).count()
    category_rows = db.session.query(Expense.category, func.sum(Expense.amount)).filter_by(
        user_id=current_user.id
    ).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    chart_rows = db.session.query(Expense.category, func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= month_start,
        Expense.expense_date <= today
    ).group_by(Expense.category).all()
    current_month = today.strftime("%Y-%m")
    current_budgets = Budget.query.filter_by(user_id=current_user.id, month=current_month).order_by(Budget.category).all()
    current_actuals = {category: float(amount or 0) for category, amount in chart_rows}
    budget_alerts = []
    for budget in current_budgets:
        limit = float(budget.limit_amount)
        spent = current_actuals.get(budget.category, 0.0)
        pct = (spent / limit * 100) if limit else 0
        if pct >= 80:
            budget_alerts.append({"category": budget.category, "spent": spent, "limit": limit,
                                  "pct": pct, "over": pct >= 100,
                                  "remaining": max(0.0, limit - spent)})
    # Build a six-month trend, including months with no activity.
    month_labels, month_values = [], []
    for offset in range(5, -1, -1):
        year, month_num = today.year, today.month - offset
        while month_num <= 0:
            year -= 1
            month_num += 12
        start = date(year, month_num, 1)
        end = date(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1)
        value = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.user_id == current_user.id, Expense.expense_date >= start, Expense.expense_date < end
        ).scalar()
        month_labels.append(start.strftime("%b %y"))
        month_values.append(float(value or 0))
    return render_template("dashboard.html", expenses=expenses, all_total=all_total,
        month_total=month_total, count=count, category_rows=category_rows,
        chart_labels=[r[0] for r in chart_rows], chart_values=[float(r[1]) for r in chart_rows],
        month_labels=month_labels, month_values=month_values,
        category_labels=[r[0] for r in category_rows], category_values=[float(r[1]) for r in category_rows],
        categories=CATEGORIES, today=today, budget_alerts=budget_alerts)

@main_bp.route("/expenses")
@login_required
def expenses():
    query = Expense.query.filter_by(user_id=current_user.id)
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    month = request.args.get("month", "").strip()
    if q:
        query = query.filter(db.or_(Expense.vendor.ilike(f"%{q}%"), Expense.notes.ilike(f"%{q}%")))
    if category in CATEGORIES:
        query = query.filter_by(category=category)
    if re.fullmatch(r"\d{4}-\d{2}", month):
        query = query.filter(db.func.strftime("%Y-%m", Expense.expense_date) == month)
    items = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    return render_template("expenses.html", expenses=items, q=q, category=category, month=month, categories=CATEGORIES)

@main_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("receipt")
        if not file or not file.filename:
            flash("Choose a receipt image to continue.", "error")
            return redirect(url_for("main.upload"))
        original = secure_filename(file.filename)
        extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if extension not in current_app.config["ALLOWED_EXTENSIONS"]:
            flash("Please upload a PNG, JPG, WEBP, TIFF, BMP image, or PDF.", "error")
            return redirect(url_for("main.upload"))
        filename = f"{uuid.uuid4().hex}.{extension}"
        path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
        file.save(path)
        text, error = extract_text(path)
        parsed = parse_receipt(text)
        category = suggest_category(text, parsed["vendor"])
        if error:
            flash(error, "error")
        elif not text.strip():
            flash("No readable text found. You can still enter the details manually.", "info")
        return render_template("review.html", filename=filename, original_name=original,
            vendor=parsed["vendor"], amount=f'{parsed["amount"]:.2f}', expense_date=parsed["expense_date"],
            ocr_text=text, category=category, categories=CATEGORIES)
    return render_template("upload.html")

@main_bp.post("/expenses/save")
@login_required
def save_expense():
    vendor = request.form.get("vendor", "").strip()[:120] or "Unknown vendor"
    notes = request.form.get("notes", "").strip()[:500]
    filename = request.form.get("filename", "").strip()
    ocr_text = request.form.get("ocr_text", "")[:15000]
    category = request.form.get("category", "Other")
    try:
        amount = Decimal(request.form.get("amount", "0")).quantize(Decimal("0.01"))
        if not amount.is_finite() or amount < 0 or amount > Decimal("100000000"):
            raise InvalidOperation()
        expense_date = datetime.strptime(request.form.get("expense_date", ""), "%Y-%m-%d").date()
    except (InvalidOperation, ValueError):
        flash("Check that the amount and date are valid.", "error")
        return redirect(url_for("main.upload"))
    if category not in CATEGORIES:
        category = "Other"
    if filename and not (Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(filename)).is_file():
        filename = ""
    expense = Expense(user_id=current_user.id, vendor=vendor, amount=amount, expense_date=expense_date,
                      category=category, notes=notes, receipt_filename=secure_filename(filename), ocr_text=ocr_text)
    db.session.add(expense)
    db.session.commit()
    flash("Expense saved successfully.", "success")
    budget = Budget.query.filter_by(user_id=current_user.id, month=expense.expense_date.strftime("%Y-%m"), category=category).first()
    if budget:
        spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.user_id == current_user.id, Expense.category == category,
            func.strftime("%Y-%m", Expense.expense_date) == budget.month).scalar()
        spent_value, limit_value = float(spent or 0), float(budget.limit_amount)
        if spent_value >= limit_value:
            flash(f"Budget alert: {category} spending is ₹{spent_value-limit_value:,.2f} over your ₹{limit_value:,.2f} limit. Consider pausing non-essential purchases and reviewing recent expenses.", "warning")
        elif spent_value >= limit_value * 0.8:
            flash(f"Budget heads-up: you've used {spent_value/limit_value:.0%} of your {category} budget. Check planned purchases and keep a little room for essentials.", "warning")
    return redirect(url_for("main.dashboard"))

@main_bp.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    expense = owned_expense(expense_id)
    if request.method == "POST":
        try:
            expense.amount = Decimal(request.form.get("amount", "0")).quantize(Decimal("0.01"))
            if not expense.amount.is_finite() or expense.amount < 0:
                raise InvalidOperation()
            expense.expense_date = datetime.strptime(request.form.get("expense_date", ""), "%Y-%m-%d").date()
        except (InvalidOperation, ValueError):
            flash("Enter a valid amount and date.", "error")
            return redirect(url_for("main.edit_expense", expense_id=expense.id))
        expense.vendor = request.form.get("vendor", "").strip()[:120] or "Unknown vendor"
        expense.category = request.form.get("category", "Other")
        if expense.category not in CATEGORIES:
            expense.category = "Other"
        expense.notes = request.form.get("notes", "").strip()[:500]
        db.session.commit()
        flash("Expense updated.", "success")
        return redirect(url_for("main.expenses"))
    return render_template("edit.html", expense=expense, categories=CATEGORIES)

@main_bp.post("/expenses/<int:expense_id>/delete")
@login_required
def delete_expense(expense_id):
    expense = owned_expense(expense_id)
    if expense.receipt_filename:
        path = Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(expense.receipt_filename)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(request.referrer or url_for("main.expenses"))

@main_bp.route("/receipt-preview/<path:filename>")
@login_required
def preview_receipt(filename):
    # Upload names are random UUIDs; this route is used only before the
    # receipt is attached to a saved expense record.
    safe = secure_filename(filename)
    if safe != filename:
        abort(404)
    path = Path(current_app.config["UPLOAD_FOLDER"]) / safe
    if not path.is_file():
        abort(404)
    return send_file(path)

@main_bp.route("/receipt/<path:filename>")
@login_required
def view_receipt(filename):
    safe = secure_filename(filename)
    expense = Expense.query.filter_by(user_id=current_user.id, receipt_filename=safe).first()
    if not expense:
        abort(404)
    path = Path(current_app.config["UPLOAD_FOLDER"]) / safe
    if not path.is_file():
        abort(404)
    return send_file(path)

@main_bp.route("/export.csv")
@login_required
def export_csv():
    rows = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Vendor", "Category", "Amount", "Notes"])
    for e in rows:
        writer.writerow([e.expense_date.isoformat(), e.vendor, e.category, str(e.amount), e.notes or ""])
    memory = io.BytesIO(("\ufeff" + output.getvalue()).encode("utf-8"))
    memory.seek(0)
    return send_file(memory, mimetype="text/csv", as_attachment=True, download_name="expenseflow-export.csv")


@main_bp.route("/expenses/new", methods=["GET", "POST"])
@login_required
def manual_expense():
    """Create an expense without needing a receipt or OCR."""
    if request.method == "POST":
        try:
            amount = Decimal(request.form.get("amount", "0")).quantize(Decimal("0.01"))
            if not amount.is_finite() or amount <= 0 or amount > Decimal("100000000"):
                raise InvalidOperation()
            expense_date = datetime.strptime(request.form.get("expense_date", ""), "%Y-%m-%d").date()
        except (InvalidOperation, ValueError):
            flash("Enter a valid positive amount and date.", "error")
            return redirect(url_for("main.manual_expense"))
        category = request.form.get("category", "Other")
        if category not in CATEGORIES:
            category = "Other"
        expense = Expense(
            user_id=current_user.id,
            vendor=request.form.get("vendor", "").strip()[:120] or "Manual expense",
            amount=amount, expense_date=expense_date, category=category,
            notes=request.form.get("notes", "").strip()[:500],
        )
        db.session.add(expense)
        db.session.commit()
        flash("Manual expense added.", "success")
        return redirect(url_for("main.expenses"))
    return render_template("manual_expense.html", categories=CATEGORIES, today=date.today())


@main_bp.route("/analytics")
@login_required
def analytics():
    today = date.today()
    category_rows = db.session.query(Expense.category, func.sum(Expense.amount)).filter_by(
        user_id=current_user.id).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    vendor_rows = db.session.query(Expense.vendor, func.sum(Expense.amount), func.count(Expense.id)).filter_by(
        user_id=current_user.id).group_by(Expense.vendor).order_by(func.sum(Expense.amount).desc()).limit(8).all()
    month_labels, month_values = [], []
    for offset in range(11, -1, -1):
        year, month_num = today.year, today.month - offset
        while month_num <= 0:
            year -= 1
            month_num += 12
        start = date(year, month_num, 1)
        end = date(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1)
        value = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.user_id == current_user.id, Expense.expense_date >= start, Expense.expense_date < end).scalar()
        month_labels.append(start.strftime("%b %y"))
        month_values.append(float(value or 0))
    total = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter_by(user_id=current_user.id).scalar()
    return render_template("analytics.html", categories=CATEGORIES, category_rows=category_rows,
        category_labels=[r[0] for r in category_rows], category_values=[float(r[1]) for r in category_rows],
        vendor_rows=vendor_rows, month_labels=month_labels, month_values=month_values, total=float(total or 0))


@main_bp.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    today = date.today()
    selected_month = request.values.get("month", today.strftime("%Y-%m"))
    if not re.fullmatch(r"\d{4}-\d{2}", selected_month):
        selected_month = today.strftime("%Y-%m")
    try:
        month_start = datetime.strptime(selected_month + "-01", "%Y-%m-%d").date()
    except ValueError:
        selected_month = today.strftime("%Y-%m")
        month_start = today.replace(day=1)
    if request.method == "POST":
        category = request.form.get("category", "")
        try:
            limit_amount = Decimal(request.form.get("limit_amount", "0")).quantize(Decimal("0.01"))
            if category not in CATEGORIES or not limit_amount.is_finite() or limit_amount <= 0:
                raise InvalidOperation()
        except (InvalidOperation, ValueError):
            flash("Choose a category and enter a budget greater than zero.", "error")
            return redirect(url_for("main.budgets", month=selected_month))
        budget = Budget.query.filter_by(user_id=current_user.id, month=selected_month, category=category).first()
        if budget:
            budget.limit_amount = limit_amount
        else:
            db.session.add(Budget(user_id=current_user.id, month=selected_month, category=category, limit_amount=limit_amount))
        db.session.commit()
        flash(f"{category} budget saved for {selected_month}.", "success")
        return redirect(url_for("main.budgets", month=selected_month))
    budgets_list = Budget.query.filter_by(user_id=current_user.id, month=selected_month).order_by(Budget.category).all()
    actual_rows = db.session.query(Expense.category, func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= month_start,
        Expense.expense_date < (date(month_start.year + (month_start.month == 12), 1 if month_start.month == 12 else month_start.month + 1, 1))
    ).group_by(Expense.category).all()
    actuals = {category: float(amount or 0) for category, amount in actual_rows}
    budget_alerts = []
    tips = {
        "Food": "Plan a few meals ahead, compare prices, and limit unplanned food delivery.",
        "Travel": "Combine errands, use public transport when practical, and plan trips in advance.",
        "Shopping": "Try a 24-hour pause before non-essential purchases and compare alternatives.",
        "Bills": "Review subscriptions and switch off services you no longer use.",
        "Health": "Prioritize necessary care; check for generic options or covered services where appropriate.",
        "Office": "Group supply orders and check what you already have before buying more.",
        "Other": "Review recent entries and separate needs from optional purchases."
    }
    for budget in budgets_list:
        limit = float(budget.limit_amount)
        spent = actuals.get(budget.category, 0.0)
        pct = (spent / limit * 100) if limit else 0
        if pct >= 80:
            budget_alerts.append({"category": budget.category, "spent": spent, "limit": limit,
                                  "pct": pct, "over": pct >= 100, "tip": tips.get(budget.category, tips["Other"])})
    return render_template("budgets.html", categories=CATEGORIES, budgets=budgets_list,
        actuals=actuals, month=selected_month, budget_alerts=budget_alerts)


@main_bp.post("/budgets/<int:budget_id>/delete")
@login_required
def delete_budget(budget_id):
    budget = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first_or_404()
    month = budget.month
    db.session.delete(budget)
    db.session.commit()
    flash("Budget removed.", "success")
    return redirect(url_for("main.budgets", month=month))
