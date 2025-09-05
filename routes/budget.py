from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import Budget, Expense
from extensions import db   # if you created extensions.py

from models import Budget, Expense
import datetime

budget_bp = Blueprint('budget', __name__)

# Set a budget
@budget_bp.route('/budget', methods=['POST'])
@login_required
def set_budget():
    data = request.json
    amount = data.get("amount")
    period = data.get("period")   # daily / monthly / yearly
    start_date = datetime.date.fromisoformat(data.get("start_date"))
    end_date = datetime.date.fromisoformat(data.get("end_date"))

    budget = Budget(
        amount=amount,
        period=period,
        start_date=start_date,
        end_date=end_date,
        household_id=current_user.household_id
    )
    db.session.add(budget)
    db.session.commit()

    return jsonify({"message": "Budget set successfully!"}), 201


# Get current budget + spent + remaining
@budget_bp.route('/budget', methods=['GET'])
@login_required
def get_budget():
    today = datetime.date.today()
    budget = Budget.query.filter(
        Budget.household_id == current_user.household_id,
        Budget.start_date <= today,
        Budget.end_date >= today
    ).order_by(Budget.start_date.desc()).first()

    if not budget:
        return jsonify({"budget": 0, "spent": 0, "remaining": 0})

    # Calculate spent
    expenses = Expense.query.filter(
        Expense.household_id == current_user.household_id,
        Expense.date >= budget.start_date,
        Expense.date <= budget.end_date
    ).all()

    spent = sum([e.amount for e in expenses])
    remaining = budget.amount - spent

    return jsonify({
        "budget": budget.amount,
        "spent": spent,
        "remaining": remaining
    })
