# models.py
from extensions import db
from flask_login import UserMixin
from datetime import datetime
import uuid

def gen_invite():
    return str(uuid.uuid4())[:8]

class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    invite_code = db.Column(db.String(32), unique=True, default=gen_invite)
    budget = db.Column(db.Float, default=0.0)  # household budget
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Admin user ID

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # nullable for Google accounts
    display_name = db.Column(db.String(150))
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)  # Soft delete flag
    is_admin = db.Column(db.Boolean, default=False)  # Admin privileges

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(200))
    amount = db.Column(db.Float)
    payer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'))
    category = db.Column(db.String(80), nullable=True)
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Split(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    share_amount = db.Column(db.Float)  # explicit amount