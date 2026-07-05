"""
blueprints/admin/routes.py
---------------------------
Admin dashboard, trek management, user/staff management.
"""

import os
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from functools import wraps

from models__1 import db, User, Trek, Booking, Role, AccountStatus, TrekStatus, TrekDifficulty
from db_helpers import (
    approve_trek, open_trek, close_trek, complete_trek,
    approve_staff, assign_staff_to_trek,
    blacklist_user, unblacklist_user,
    get_dashboard_stats, cancel_booking, get_chart_data,
    delete_trek_helper
)

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# DECORATOR — admin only
# ---------------------------------------------------------------------------
def admin_required(f):
    @wraps(f) # keep the original fun value and metdata intact
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != Role.ADMIN:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
# @admin_bp.route("/dashboard")
# @login_required
# @admin_required
# def dashboard():
#     stats = get_dashboard_stats()
#     pending_staff = User.query.filter_by(role=Role.STAFF, status=AccountStatus.PENDING).all()
#     recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(8).all()
#     return render_template("admin/dashboard.html",
#                            stats=stats,
#                            pending_staff=pending_staff,
#                            recent_bookings=recent_bookings)


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
@admin_bp.route("/notifications")
@login_required
@admin_required
def notifications():
    notifs = current_user.notifications.order_by(db.text("created_at desc")).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template("admin/notifications.html", notifications=notifs)


# ---------------------------------------------------------------------------
# TREK MANAGEMENT
# ---------------------------------------------------------------------------
@admin_bp.route("/treks")
@login_required
@admin_required
def treks():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = Trek.query #it is creating query object of our trek
    if q:
        if q.isdigit():
            query = query.filter(
                (Trek.id == int(q)) |
                Trek.name.ilike(f"%{q}%") |
                Trek.location.ilike(f"%{q}%")
            )
        else:
            query = query.filter(
                Trek.name.ilike(f"%{q}%") |
                Trek.location.ilike(f"%{q}%")
            )
    if status:
        query = query.filter_by(status=status)
    all_treks = query.order_by(Trek.created_at.desc()).all()
    return render_template("admin/treks.html", treks=all_treks, q=q, status=status)

#---------------------------------------------------------------
# TREK CREATE
#---------------------------------------------------------------
@admin_bp.route("/treks/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_trek():
    active_staff = User.query.filter_by(role=Role.STAFF, status=AccountStatus.ACTIVE).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        difficulty = request.form.get("difficulty", TrekDifficulty.EASY) #by default it sets to easy
        duration = request.form.get("duration_days", "1")
        total_slots = request.form.get("total_slots", "10")
        price = request.form.get("price", "0")
        altitude = request.form.get("altitude_m", "").strip()
        distance = request.form.get("distance_km", "").strip()
        start_date_str = request.form.get("start_date", "").strip() or None
        end_date_str = request.form.get("end_date",   "").strip() or None
        staff_id = request.form.get("staff_id", "")   or None
        

        # Making sure user enter necessecary details..... some kind of validation
        errors = []
        if not name: errors.append("Trek name is required.")
        if not location: errors.append("Location is required.")
        try:
            duration = int(duration)
            total_slots = int(total_slots)
            price = float(price)
        except ValueError:
            errors.append("Duration, slots and price must be numbers.")

        # additional few quality checks
        if isinstance(total_slots, int) and total_slots < 1:
            errors.append("Total slots can not be negative")
            
        if isinstance(duration, int) and duration < 1:
            errors.append("Duration must be at least 1 day.")

        if altitude:
            if not altitude.isdigit():
                errors.append("Altitude must be a non-negative whole numbers")
        if distance:
            try:
                if(float(distance)) < 0:
                    errors.append("Distance can not be negative")
            except:
                errors.append("Distance must be a valid number")


        # Parse date strings → Python date objects (SQLite requires this)
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
            except ValueError:
                errors.append("Invalid start date format (expected YYYY-MM-DD).")
        if end_date_str:
            try:
                end_date = date.fromisoformat(end_date_str)
            except ValueError:
                errors.append("Invalid end date format (expected YYYY-MM-DD).")
        if start_date and end_date and end_date < start_date:
            errors.append("End date cannot be before start date.")

        # Handle Image Upload
        image_filename = None
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            filename = image_file.filename
            if "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif", "webp"}:
                import uuid
                ext = filename.rsplit(".", 1)[1].lower()
                image_filename = f"trek_{uuid.uuid4().hex}.{ext}"
                os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
                image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename))
            else:
                errors.append("Invalid image format. Allowed formats: png, jpg, jpeg, gif, webp.")

        if errors:
            for e in errors: flash(e, "danger")
            return render_template("admin/trek_form.html",
            active_staff=active_staff,
            form_data=request.form,
            action="Create")

        trek = Trek(
            name = name,
            location = location,
            description = description or None,
            difficulty = difficulty,
            duration_days = duration,
            total_slots = total_slots,
            available_slots = total_slots,
            price = price,
            altitude_m = int(altitude) if altitude.isdigit()  else None,
            distance_km = float(distance) if distance.replace(".","").isdigit() else None,
            start_date = start_date,
            end_date = end_date,
            staff_id = int(staff_id) if staff_id else None,
            created_by = current_user.id,
            image = image_filename or "trek_default.jpg"
        )
        db.session.add(trek)
        db.session.commit()
        flash(f"Trek '{trek.name}' created successfully.", "success")
        return redirect(url_for("admin.treks"))

    return render_template("admin/trek_form.html",
        active_staff=active_staff,
        form_data={},
        action="Create")


@admin_bp.route("/treks/<int:trek_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    #Block the edit after we complete our trek
    if trek.status == TrekStatus.COMPLETED:
        flash("Completed treks cannot be edited.", "danger")
        return redirect(url_for("admin.treks"))
    
    active_staff = User.query.filter_by(role=Role.STAFF, status=AccountStatus.ACTIVE).all()

    if request.method == "POST":
        trek.name = request.form.get("name", trek.name).strip()
        trek.location = request.form.get("location", trek.location).strip()
        trek.description = request.form.get("description", "").strip() or None
        trek.difficulty = request.form.get("difficulty", trek.difficulty)
        trek.price = float(request.form.get("price", trek.price) or 0)
        start_date_str = request.form.get("start_date", "").strip() or None
        end_date_str = request.form.get("end_date",   "").strip() or None
        staff_id = request.form.get("staff_id")   or None
        trek.staff_id = int(staff_id) if staff_id else None
        altitude = request.form.get("altitude_m", "").strip()
        distance = request.form.get("distance_km", "").strip()
        trek.altitude_m  = int(altitude) if altitude.isdigit()  else None
        trek.distance_km = float(distance) if distance.replace(".","").isdigit() else None

        # Parse date strings → Python date objects
        if start_date_str:
            try:
                trek.start_date = date.fromisoformat(start_date_str)
            except ValueError:
                flash("Invalid start date format.", "danger")
                return redirect(url_for("admin.edit_trek", trek_id=trek_id))
        else:
            trek.start_date = None

        if end_date_str:
            try:
                trek.end_date = date.fromisoformat(end_date_str)
            except ValueError:
                flash("Invalid end date format.", "danger")
                return redirect(url_for("admin.edit_trek", trek_id=trek_id))
        else:
            trek.end_date = None

        if trek.start_date and trek.end_date and trek.end_date < trek.start_date:
            flash("End date cannot be before start date.", "danger")
            return redirect(url_for("admin.edit_trek", trek_id=trek_id))

        # Handle Image Upload
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            filename = image_file.filename
            if "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif", "webp"}:
                import uuid
                ext = filename.rsplit(".", 1)[1].lower()
                image_filename = f"trek_{uuid.uuid4().hex}.{ext}"
                os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
                image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename))
                # Delete old image if it's not the default image
                if trek.image and trek.image != "trek_default.jpg":
                    old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], trek.image)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
                trek.image = image_filename
            else:
                flash("Invalid image format. Allowed formats: png, jpg, jpeg, gif, webp.", "danger")
                return redirect(url_for("admin.edit_trek", trek_id=trek_id))

        db.session.commit()
        flash(f"Trek '{trek.name}' updated.", "success")
        return redirect(url_for("admin.treks"))

    return render_template("admin/trek_form.html",
        trek=trek,active_staff=active_staff,
        form_data=trek, #changed
        action="Edit")

#----------------------- DELETE TREK------------------------------
@admin_bp.route("/treks/<int:trek_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    name = trek.name
    ok, msg = delete_trek_helper(trek)
    flash(msg, "warning" if ok else "danger")
    return redirect(url_for("admin.treks"))

#------------------------------- APPROVE TREK -----------------------------------------------------------------
# Trek status transitions
@admin_bp.route("/treks/<int:trek_id>/approve", methods=["POST"])
@login_required
@admin_required
def do_approve_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    ok, msg = approve_trek(trek) # function I wrote in helpers.py
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.treks"))


@admin_bp.route("/treks/<int:trek_id>/open", methods=["POST"])
@login_required
@admin_required
def do_open_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    ok, msg = open_trek(trek)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.treks"))


@admin_bp.route("/treks/<int:trek_id>/close", methods=["POST"])
@login_required
@admin_required
def do_close_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    ok, msg = close_trek(trek)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.treks"))


@admin_bp.route("/treks/<int:trek_id>/complete", methods=["POST"])
@login_required
@admin_required
def do_complete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    ok, msg = complete_trek(trek)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.treks"))


@admin_bp.route("/treks/<int:trek_id>/assign-staff", methods=["POST"])
@login_required
@admin_required
def do_assign_staff(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    staff_id = request.form.get("staff_id")
    if not staff_id:
        flash("Please select a staff member.", "warning")
        return redirect(request.referrer or url_for("admin.treks"))
    staff = User.query.get_or_404(int(staff_id))
    ok, msg = assign_staff_to_trek(staff, trek)
    flash(msg,"success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.treks"))


# ---------------------------------------------------------------------------
# USER MANAGEMENT
# ---------------------------------------------------------------------------
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "")
    query = User.query.filter(User.role != Role.ADMIN)
    if q:
        if q.isdigit():
            query = query.filter(
                (User.id == int(q)) |
                User.full_name.ilike(f"%{q}%") |
                User.username.ilike(f"%{q}%")  |
                User.email.ilike(f"%{q}%")
            )
        else:
            query = query.filter(
                User.full_name.ilike(f"%{q}%") |
                User.username.ilike(f"%{q}%")  |
                User.email.ilike(f"%{q}%")
            )
    if role:
        query = query.filter_by(role=role)
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users, q=q, role=role)


@admin_bp.route("/users/<int:user_id>/approve-staff", methods=["POST"])
@login_required
@admin_required
def do_approve_staff(user_id):
    staff = User.query.get_or_404(user_id)
    ok, msg = approve_staff(staff)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/blacklist", methods=["POST"])
@login_required
@admin_required
def do_blacklist(user_id):
    user = User.query.get_or_404(user_id)
    reason = request.form.get("reason", "")
    ok, msg = blacklist_user(user, reason)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/unblacklist", methods=["POST"])
@login_required
@admin_required
def do_unblacklist(user_id):
    user = User.query.get_or_404(user_id)
    ok, msg = unblacklist_user(user)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.users"))


# ---------------------------------------------------------------------------
# BOOKINGS
# ---------------------------------------------------------------------------
# @admin_bp.route("/bookings")
# @login_required
# @admin_required
# def bookings():
#     q = request.args.get("q", "").strip()
#     query = Booking.query
#     if q:
#         query = query.join(User).join(Trek).filter(
#             User.full_name.ilike(f"%{q}%") |
#             Trek.name.ilike(f"%{q}%")      |
#             Booking.booking_ref.ilike(f"%{q}%")
#         )
#     all_bookings = query.order_by(Booking.booking_date.desc()).all()
#     return render_template("admin/bookings.html", bookings=all_bookings, q=q)
@admin_bp.route("/bookings")
@login_required
@admin_required
def bookings():
    q = request.args.get("q", "").strip()
    query = Booking.query
    if q:
        query = query.join(User, Booking.user_id == User.id) \
                     .join(Trek, Booking.trek_id == Trek.id) \
                     .filter(
            User.full_name.ilike(f"%{q}%") |
            Trek.name.ilike(f"%{q}%")      |
            Booking.booking_ref.ilike(f"%{q}%")
        )
    all_bookings = query.order_by(Booking.booking_date.desc()).all()
    return render_template("admin/bookings.html", bookings=all_bookings, q=q)

@admin_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@admin_required
def do_cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    ok, msg = cancel_booking(booking, cancelled_by_admin=True)
    flash(msg, "success" if ok else "danger")
    return redirect(request.referrer or url_for("admin.bookings"))



#----------chart---------
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = get_dashboard_stats()
    pending_staff = User.query.filter_by(role=Role.STAFF, status=AccountStatus.PENDING).all()
    recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(8).all()
    chart_data = get_chart_data()

    return render_template("admin/dashboard.html",
                           stats=stats,
                           pending_staff=pending_staff,
                           recent_bookings=recent_bookings,
                           chart_data=chart_data)