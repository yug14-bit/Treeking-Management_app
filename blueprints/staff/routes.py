"""
blueprints/staff/routes.py
---------------------------
Trek Staff dashboard, assigned treks, slot/status updates, participant list.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user
from functools import wraps

from models__1 import db, User, Trek, Booking, Role, AccountStatus, TrekStatus, BookingStatus
from db_helpers import close_trek, complete_trek, update_available_slots, open_trek

staff_bp = Blueprint("staff", __name__)


# ---------------------------------------------------------------------------
# DECORATOR — approved staff only
# ---------------------------------------------------------------------------
def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != Role.STAFF:
            flash("Staff access required.", "danger")
            return redirect(url_for("auth.login"))
        if current_user.status == AccountStatus.PENDING:
            logout_user()
            flash("Your account is pending admin approval.", "warning")
            return redirect(url_for("auth.login"))
        if current_user.status == AccountStatus.BLACKLISTED:
            logout_user()
            flash("Your account has been suspended.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@staff_bp.route("/dashboard")
@login_required
@staff_required
def dashboard():
    assigned = Trek.query.filter_by(staff_id=current_user.id).all()
    total_participants = sum(
        t.bookings.filter_by(status=BookingStatus.BOOKED).count()
        for t in assigned
    )
    return render_template("staff/dashboard.html",
                           assigned_treks=assigned,
                           total_participants=total_participants)


# ---------------------------------------------------------------------------
# MY TREKS
# ---------------------------------------------------------------------------
@staff_bp.route("/my-treks")
@login_required
@staff_required
def my_treks():
    assigned = Trek.query.filter_by(staff_id=current_user.id)\
                         .order_by(Trek.start_date).all()
    return render_template("staff/my_treks.html", treks=assigned)


# ---------------------------------------------------------------------------
# TREK DETAIL — update slots/status + view participants
# ---------------------------------------------------------------------------
@staff_bp.route("/treks/<int:trek_id>")
@login_required
@staff_required
def trek_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.staff_id != current_user.id:
        flash("You are not assigned to this trek.", "danger")
        return redirect(url_for("staff.my_treks"))

    participants = trek.bookings.filter(
        Booking.status != BookingStatus.CANCELLED
    ).all()

    return render_template("staff/trek_detail.html",
                           trek=trek,
                           participants=participants)


# ---------------------------------------------------------------------------
# UPDATE SLOTS
# ---------------------------------------------------------------------------
@staff_bp.route("/treks/<int:trek_id>/update-slots", methods=["POST"])
@login_required
@staff_required
def update_slots(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.staff_id != current_user.id:
        flash("You are not assigned to this trek.", "danger")
        return redirect(url_for("staff.my_treks"))

    try:
        new_slots = int(request.form.get("available_slots", 0))
    except ValueError:
        flash("Invalid slot value.", "danger")
        return redirect(url_for("staff.trek_detail", trek_id=trek_id))

    ok, msg = update_available_slots(trek, new_slots, current_user)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("staff.trek_detail", trek_id=trek_id))


# ---------------------------------------------------------------------------
# UPDATE TREK STATUS
# ---------------------------------------------------------------------------
@staff_bp.route("/treks/<int:trek_id>/close", methods=["POST"])
@login_required
@staff_required
def do_close_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.staff_id != current_user.id:
        flash("You are not assigned to this trek.", "danger")
        return redirect(url_for("staff.my_treks"))
    ok, msg = close_trek(trek)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("staff.trek_detail", trek_id=trek_id))


@staff_bp.route("/treks/<int:trek_id>/open", methods=["POST"])
@login_required
@staff_required
def do_open_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.staff_id != current_user.id:
        flash("You are not assigned to this trek.", "danger")
        return redirect(url_for("staff.my_treks"))
    ok, msg = open_trek(trek)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("staff.trek_detail", trek_id=trek_id))


@staff_bp.route("/treks/<int:trek_id>/complete", methods=["POST"])
@login_required
@staff_required
def do_complete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.staff_id != current_user.id:
        flash("You are not assigned to this trek.", "danger")
        return redirect(url_for("staff.my_treks"))
    ok, msg = complete_trek(trek)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("staff.trek_detail", trek_id=trek_id))


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
@staff_bp.route("/notifications")
@login_required
@staff_required
def notifications():
    notifs = current_user.notifications.order_by(db.text("created_at desc")).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template("staff/notifications.html", notifications=notifs)


@staff_bp.route("/profile")
@login_required
@staff_required
def profile():
    return render_template("staff/profile.html")