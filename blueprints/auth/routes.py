"""
blueprints/auth/routes.py
--------------------------
Authentication routes: login, register, logout.
Handles all three roles — Admin, Trek Staff, and Trekker.
"""

from flask import (
    Blueprint, render_template, redirect,
    url_for, flash, request
)
from flask_login import (
    login_user, logout_user,
    login_required, current_user
)
from models__1 import db, User, Role, AccountStatus

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# HELPER — role based redirect after login
# ---------------------------------------------------------------------------

def _dashboard_for(user: User):
    """Redirect user to their role-specific dashboard."""
    if user.role == Role.ADMIN:
        return redirect(url_for("admin.dashboard"))
    if user.role == Role.STAFF:
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("user.dashboard"))


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _dashboard_for(current_user)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        if not username or not password:
            flash("Please enter both username and password.", "warning")
            return render_template("auth/login.html")

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html")

        if user.status == AccountStatus.BLACKLISTED:
            flash("Your account has been suspended. Please contact admin.", "danger")
            return render_template("auth/login.html")

        if user.role == Role.STAFF and user.status == AccountStatus.PENDING:
            flash("Your staff account is pending admin approval.", "warning")
            return render_template("auth/login.html")

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.full_name}!", "success")

        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)

        return _dashboard_for(user)

    return render_template("auth/login.html")


# ---------------------------------------------------------------------------
# REGISTER
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _dashboard_for(current_user)

    requested_role = request.args.get("role", Role.USER).lower()
    if requested_role not in (Role.STAFF, Role.USER):
        requested_role = Role.USER

    if request.method == "POST":
        full_name  = request.form.get("full_name",  "").strip()
        username   = request.form.get("username",   "").strip()
        email      = request.form.get("email",      "").strip().lower()
        phone      = request.form.get("phone",      "").strip()
        password   = request.form.get("password",   "")
        confirm    = request.form.get("confirm",    "")
        role       = request.form.get("role",       Role.USER)
        experience = request.form.get("experience_years", "").strip()
        certs      = request.form.get("certifications",   "").strip()
        bio        = request.form.get("bio",               "").strip()

        errors = []

        if not full_name:
            errors.append("Full name is required.")
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if role not in (Role.STAFF, Role.USER):
            errors.append("Invalid role selected.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered.")
        # experience validation
        if role == Role.STAFF and experience:
            if not experience.isdigit():
                errors.append("Years of experience cannot be negative.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", role=role, form_data=request.form)

        status = AccountStatus.PENDING if role == Role.STAFF else AccountStatus.ACTIVE

        new_user = User(
            full_name = full_name,
            username  = username,
            email     = email,
            phone     = phone or None,
            role      = role,
            status    = status,
        )
        new_user.set_password(password)

        if role == Role.STAFF:
            new_user.experience_years = int(experience) if experience.isdigit() else None
            new_user.certifications   = certs or None
            new_user.bio              = bio   or None

        db.session.add(new_user)
        db.session.commit()

        if role == Role.STAFF:
            flash("Registration successful! Your account is pending admin approval. "
                  "You will be notified once approved.", "info")
        else:
            flash("Registration successful! You can now log in.", "success")

        return redirect(url_for("auth.login"))

    return render_template("auth/register.html",
                           role=requested_role,
                           form_data={})


# ---------------------------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------------------------

@auth_bp.route("/logout")
@login_required
def logout():
    name = current_user.full_name
    logout_user()
    flash(f"You have been logged out. See you soon, {name}!", "info")
    return redirect(url_for("auth.login"))
