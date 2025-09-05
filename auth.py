import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Household
from flask_dance.contrib.google import make_google_blueprint, google

auth_bp = Blueprint("auth", __name__)

def make_google_bp():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    google_bp = make_google_blueprint(
        client_id=client_id,
        client_secret=client_secret,
        scope=["profile", "email"],
        redirect_url="/auth/google/authorized"
    )
    return google_bp

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        user = User.query.filter_by(email=email, is_active=True).first()
        if not user or not user.password_hash:
            flash("Invalid credentials")
            return render_template("login.html")
        if check_password_hash(user.password_hash, pw):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid credentials")
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        display = request.form.get("display_name") or email.split("@")[0]
        invite = request.form.get("invite_code") or None
        household_name = request.form.get("household_name") or f"{display}'s Household"

        # Check if user already exists (including inactive ones)
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.is_active:
                flash("Email already registered. Try login.")
                return render_template("register.html")
            else:
                # Reactivate inactive user
                existing_user.is_active = True
                existing_user.password_hash = generate_password_hash(pw)
                existing_user.display_name = display
                db.session.commit()
                login_user(existing_user)
                return redirect(url_for("dashboard"))

        if invite:
            hh = Household.query.filter_by(invite_code=invite).first()
            if not hh:
                flash("Invalid invite code")
                return render_template("register.html")
            # Regular user joining existing household
            user = User(
                email=email, 
                password_hash=generate_password_hash(pw), 
                display_name=display, 
                household_id=hh.id,
                is_admin=False  # New users are not admins by default
            )
        else:
            # First user creating a new household becomes admin
            hh = Household(name=household_name)
            db.session.add(hh)
            db.session.commit()
            
            user = User(
                email=email, 
                password_hash=generate_password_hash(pw), 
                display_name=display, 
                household_id=hh.id,
                is_admin=True  # First user becomes admin
            )
            # Set the household creator
            hh.created_by = user.id
            db.session.add(hh)

        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

@auth_bp.route("/google/authorized")
def google_authorized():
    # This route is used after OAuth flow; handled in app.py via blueprint registration
    # If Google blueprint is present, handle logic in app.py or here by reading google.session
    # Keep a placeholder if needed.
    return redirect(url_for("dashboard"))