import os
from flask import Flask, render_template, redirect, url_for, request, jsonify, send_file
from flask_login import LoginManager, current_user, login_required, login_user
from extensions import db
from models import User, Household, Expense, Split
from auth import auth_bp, make_google_bp
from datetime import datetime, date
import pandas as pd
import os
from keep_alive import run_keep_alive
# Check if we are running on Render and start the keep_alive thread
if os.environ.get('RENDER'):  # Render sets this environment variable to 'true'
    run_keep_alive()
    print("Keep-alive thread started for Render deployment.")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
REPORTS_DIR = os.path.join(APP_DIR, "reports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-locally")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DATA_DIR, "expenses.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))

# Register auth blueprint
app.register_blueprint(auth_bp, url_prefix="/auth")
# Register Google blueprint if configured
google_bp = make_google_bp()
if google_bp:
    app.register_blueprint(google_bp, url_prefix="/login")

with app.app_context():
    db.create_all()

# ---------- UI routes ----------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/dashboard")
@login_required
def dashboard():
    hh = db.session.get(Household, current_user.household_id) if current_user.household_id else None
    budget = hh.budget if hh else 0.0
    expenses = Expense.query.filter_by(household_id=current_user.household_id).all() if hh else []
    total_spent = sum(e.amount for e in expenses)
    remaining = budget - total_spent
    invite = hh.invite_code if hh else ""
    
    # Check if current user is admin
    is_admin = current_user.is_admin if current_user else False
    
    return render_template("dashboard.html", budget=budget, total_spent=total_spent, 
                         remaining=remaining, invite=invite, is_admin=is_admin)

@app.route("/invite")
@login_required
def invite_page():
    return render_template("invite.html")

# ---------- API: household invite join ----------
@app.route("/join/<invite_code>", methods=["GET"])
@login_required
def join_invite(invite_code):
    hh = Household.query.filter_by(invite_code=invite_code).first()
    if not hh:
        return "Invalid invite code", 404
    current_user.household_id = hh.id
    db.session.commit()
    return redirect(url_for("dashboard"))

# ---------- API: Get household members ----------
@app.route("/api/members", methods=["GET"])
@login_required
def api_get_members():
    if not current_user.household_id:
        return jsonify({"error": "user not in household"}), 400
    
    members = User.query.filter_by(household_id=current_user.household_id, is_active=True).all()
    members_data = []
    for member in members:
        members_data.append({
            "id": member.id,
            "display_name": member.display_name,
            "email": member.email,
            "is_admin": member.is_admin
        })
    
    return jsonify({"members": members_data})

# ---------- API: set household budget (Admin only) ----------
@app.route("/api/budget", methods=["GET", "POST"])
@login_required
def api_budget():
    if request.method == "GET":
        hh = db.session.get(Household, current_user.household_id)
        budget = hh.budget if hh else 0.0
        # calculate spent in whole household (all-time) or we could support range
        total_spent = sum(e.amount for e in Expense.query.filter_by(household_id=current_user.household_id).all()) if hh else 0.0
        return jsonify({"budget": budget, "spent": total_spent, "remaining": (budget - total_spent)})
    else:
        # Check if current user is admin
        if not current_user.is_admin:
            return jsonify({"error": "admin access required"}), 403
            
        data = request.get_json(force=True)
        amount = float(data.get("amount") or 0)
        hh = db.session.get(Household, current_user.household_id)
        if not hh:
            return jsonify({"error": "no household"}), 400
        hh.budget = amount
        db.session.commit()
        return jsonify({"message": "budget set", "amount": amount})

# ---------- API: add expense (automatically split equally among all active members) ----------
@app.route("/api/expense", methods=["POST"])
@login_required
def api_add_expense():
    data = request.get_json(force=True)
    item = data.get("item")
    amount = float(data.get("amount") or 0)
    category = data.get("category")
    date_str = data.get("date")
    time_str = data.get("time")

    if not item or amount <= 0:
        return jsonify({"error": "invalid input"}), 400
    if not current_user.household_id:
        return jsonify({"error": "user not in household"}), 400

    dt_date = date.fromisoformat(date_str) if date_str else date.today()
    dt_time = datetime.strptime(time_str, "%H:%M").time() if time_str else datetime.now().time()

    exp = Expense(item=item, amount=amount, payer_id=current_user.id,
                  household_id=current_user.household_id, category=category,
                  date=dt_date, time=dt_time)
    db.session.add(exp)
    db.session.commit()
    sp = Split(expense_id=exp.id, user_id=current_user.id, share_amount=amount)
    db.session.add(sp)

    
    db.session.commit()
    return jsonify({"message": "expense added", "expense_id": exp.id})

# ---------- API: list expenses with shares (optionally filter by range) ----------
@app.route("/api/expenses", methods=["GET"])
@login_required
def api_list_expenses():
    start = request.args.get("start")  # YYYY-MM-DD
    end = request.args.get("end")
    q = Expense.query.filter_by(household_id=current_user.household_id)
    if start:
        q = q.filter(Expense.date >= date.fromisoformat(start))
    if end:
        q = q.filter(Expense.date <= date.fromisoformat(end))
    rows = []
    for e in q.order_by(Expense.date.desc(), Expense.time.desc()).all():
        shares = Split.query.filter_by(expense_id=e.id).all()
        shares_out = []
        for s in shares:
            user = db.session.get(User, s.user_id)
            # Handle case where user might be None or inactive
            display_name = "Unknown User"
            if user and user.is_active:
                display_name = user.display_name if user.display_name else user.email
            shares_out.append({"user_id": s.user_id, "share_amount": s.share_amount, "display_name": display_name})
        payer = db.session.get(User, e.payer_id)
        payer_name = "Unknown Payer"
        if payer and payer.is_active:
            payer_name = payer.display_name if payer.display_name else payer.email
        rows.append({
            "id": e.id, "item": e.item, "amount": e.amount,
            "payer_id": e.payer_id, "payer_name": payer_name,
            "category": e.category, "date": e.date.isoformat(), "time": e.time.strftime("%H:%M"),
            "shares": shares_out
        })
    total = sum(r["amount"] for r in rows)
    return jsonify({"expenses": rows, "total": total})

# ---------- API: Delete user (admin only) ----------
@app.route("/api/user/<int:user_id>", methods=["DELETE"])
@login_required
def api_delete_user(user_id):
    # Check if current user is admin
    if not current_user.is_admin:
        return jsonify({"error": "admin access required"}), 403
    
    user_to_delete = db.session.get(User, user_id)
    if not user_to_delete or user_to_delete.household_id != current_user.household_id:
        return jsonify({"error": "user not found"}), 404
    
    # Cannot delete yourself
    if user_to_delete.id == current_user.id:
        return jsonify({"error": "cannot delete yourself"}), 400
    
    # Soft delete - mark as inactive
    user_to_delete.is_active = False
    db.session.commit()
    
    return jsonify({"message": "user deactivated successfully"})

# ---------- API: Transfer expenses to another user ----------
@app.route("/api/user/<int:from_user_id>/transfer/<int:to_user_id>", methods=["POST"])
@login_required
def api_transfer_expenses(from_user_id, to_user_id):
    # Check if current user is admin
    if not current_user.is_admin:
        return jsonify({"error": "admin access required"}), 403
    
    from_user = db.session.get(User, from_user_id)
    to_user = db.session.get(User, to_user_id)
    
    if not from_user or not to_user or from_user.household_id != current_user.household_id or to_user.household_id != current_user.household_id:
        return jsonify({"error": "invalid users"}), 400
    
    # Transfer expenses
    expenses = Expense.query.filter_by(payer_id=from_user_id).all()
    for expense in expenses:
        expense.payer_id = to_user_id
    
    # Transfer splits
    splits = Split.query.filter_by(user_id=from_user_id).all()
    for split in splits:
        split.user_id = to_user_id
    
    # Soft delete the user
    from_user.is_active = False
    db.session.commit()
    
    return jsonify({"message": "expenses transferred and user deactivated"})

# ---------- API: Make user admin ----------
@app.route("/api/user/<int:user_id>/make_admin", methods=["POST"])
@login_required
def api_make_admin(user_id):
    # Check if current user is admin
    if not current_user.is_admin:
        return jsonify({"error": "admin access required"}), 403
    
    user = db.session.get(User, user_id)
    if not user or user.household_id != current_user.household_id:
        return jsonify({"error": "user not found"}), 404
    
    user.is_admin = True
    db.session.commit()
    
    return jsonify({"message": "user is now an admin"})

# ---------- API: report export (daily/monthly/yearly/full) ----------
@app.route("/api/report/<period>", methods=["GET"])
@login_required
def api_report(period):
    today = date.today()
    q = Expense.query.filter_by(household_id=current_user.household_id)
    if period == "daily":
        q = q.filter(Expense.date == today)
    elif period == "monthly":
        start = today.replace(day=1)
        q = q.filter(Expense.date >= start)
    elif period == "yearly":
        start = date(today.year, 1, 1)
        q = q.filter(Expense.date >= start)
    # full -> no filter

    rows = []
    total_spent = 0.0
    for e in q.order_by(Expense.date.asc(), Expense.time.asc()).all():
        shares = Split.query.filter_by(expense_id=e.id).all()
        participant_list = []
        for s in shares:
            user = db.session.get(User, s.user_id)
            user_name = user.display_name if user and user.is_active else "Unknown User"
            participant_list.append(f"{user_name} ({s.share_amount})")
        participants = "; ".join(participant_list)
        payer = db.session.get(User, e.payer_id)
        payer_name = payer.display_name if payer and payer.is_active else "Unknown Payer"
        rows.append({"Item": e.item, "Amount": e.amount, "Payer": payer_name, "Category": e.category or "", "Date": e.date.isoformat(), "Time": e.time.strftime("%H:%M"), "Participants (share)": participants})
        total_spent += float(e.amount)

    hh = db.session.get(Household, current_user.household_id)
    budget = hh.budget if hh else 0.0
    remaining = budget - total_spent

    df = pd.DataFrame(rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"report_{period}_{stamp}.xlsx"
    outpath = os.path.join(REPORTS_DIR, fname)
    with pd.ExcelWriter(outpath, engine="openpyxl") as writer:
        if not df.empty:
            df.to_excel(writer, sheet_name="Expenses", index=False)
        else:
            pd.DataFrame(columns=["Item","Amount","Payer","Category","Date","Time","Participants (share)"]).to_excel(writer, sheet_name="Expenses", index=False)
        summary = pd.DataFrame([{"Metric":"Budget","Value":budget},{"Metric":"Total Spent","Value":total_spent},{"Metric":"Remaining","Value":remaining}])
        summary.to_excel(writer, sheet_name="Summary", index=False)
    return send_file(outpath, as_attachment=True)

# ---------- run ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)