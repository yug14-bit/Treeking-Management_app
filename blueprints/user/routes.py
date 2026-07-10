"""
blueprints/user/routes.py
--------------------------
Trekker dashboard, browse/search treks, booking, history, profile, reviews.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
import random
from models__1 import db, User, Trek, Booking, Review, Role, AccountStatus, TrekStatus, BookingStatus
from db_helpers import book_trek, cancel_booking, add_review

user_bp = Blueprint("user", __name__)


# ---------------------------------------------------------------------------
# DECORATOR — trekkers only
# ---------------------------------------------------------------------------
def trekker_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != Role.USER:
            flash("Trekker access required.", "danger")
            return redirect(url_for("auth.login"))
        if current_user.status == AccountStatus.BLACKLISTED:
            flash("Your account has been suspended. Contact admin.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@user_bp.route("/dashboard")
@login_required
@trekker_required
def dashboard():
    open_treks = Trek.query.filter(Trek.status.in_([TrekStatus.OPEN, TrekStatus.APPROVED]))\
                           .order_by(Trek.start_date).limit(6).all()
    
    featured_trek = random.choice(open_treks) if open_treks else None

    my_bookings = current_user.bookings\
                              .filter(Booking.status != BookingStatus.CANCELLED)\
                              .order_by(Booking.booking_date.desc())\
                              .limit(5).all()
    # completed_count = current_user.bookings\
    #                               .filter_by(status=BookingStatus.COMPLETED).count()
    # return render_template("user/dashboard.html",
    #                        open_treks=open_treks,
    #                        my_bookings=my_bookings,
    #                        completed_count=completed_count)

    completed_count = current_user.bookings\
                              .filter_by(status=BookingStatus.COMPLETED).count()

    active_count = current_user.bookings\
                                .filter_by(status=BookingStatus.BOOKED).count()
    readiness_score = min(100, completed_count * 20 + active_count * 10)
    if completed_count >= 4:
        readiness_level = "Elite"
    elif completed_count >= 2:
        readiness_level = "Experienced"
    elif completed_count >= 1 or active_count >= 1:
        readiness_level = "Moderate"
    else:
        readiness_level = "Beginner"

    return render_template("user/dashboard.html",
                        open_treks=open_treks,
                        featured_trek=featured_trek,
                        my_bookings=my_bookings,
                        completed_count=completed_count,
                        readiness_score=readiness_score,
                        readiness_level=readiness_level)


# ---------------------------------------------------------------------------
# BROWSE & SEARCH TREKS
# ---------------------------------------------------------------------------
@user_bp.route("/treks")
@login_required
@trekker_required
def browse_treks():
    q = request.args.get("q", "").strip()
    difficulty = request.args.get("difficulty", "")
    location = request.args.get("location", "").strip()

    query = Trek.query.filter(Trek.status.in_([TrekStatus.OPEN, TrekStatus.APPROVED]))

    if q:
        query = query.filter(
            Trek.name.ilike(f"%{q}%") | Trek.location.ilike(f"%{q}%")
        )
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if location:
        query = query.filter(Trek.location.ilike(f"%{location}%"))

    treks = query.order_by(Trek.start_date).all()
    return render_template("user/browse_treks.html", treks=treks, q=q, difficulty=difficulty, location=location)


# ---------------------------------------------------------------------------
# TREK DETAIL & BOOKING
# ---------------------------------------------------------------------------
@user_bp.route("/treks/<int:trek_id>")
@login_required
@trekker_required
def trek_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    existing_booking = Booking.query.filter_by(
        user_id=current_user.id, trek_id=trek_id
    ).filter(Booking.status != BookingStatus.CANCELLED).first()

    reviews = trek.reviews.order_by(Review.created_at.desc()).all()

    user_review = Review.query.filter_by(
        user_id=current_user.id, trek_id=trek_id
    ).first()

    return render_template("user/trek_detail.html", trek=trek, existing_booking=existing_booking, reviews=reviews, user_review=user_review)


@user_bp.route("/treks/<int:trek_id>/book", methods=["POST"])
@login_required
@trekker_required
def do_book(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    try:
        num_persons = int(request.form.get("num_persons", 1))
    except ValueError:
        num_persons = 1

    emergency_name = request.form.get("emergency_name",  "").strip() or None
    emergency_phone = request.form.get("emergency_phone", "").strip() or None
    special = request.form.get("special_requests","").strip() or None

    ok, msg, booking = book_trek(
        current_user, trek,
        num_persons=num_persons,
        emergency_name=emergency_name,
        emergency_phone=emergency_phone,
        special_requests=special
    )
    flash(msg, "success" if ok else "danger")
    if ok:
        return redirect(url_for("user.my_bookings"))
    return redirect(url_for("user.trek_detail", trek_id=trek_id))


# ---------------------------------------------------------------------------
# MY BOOKINGS
# ---------------------------------------------------------------------------
@user_bp.route("/bookings")
@login_required
@trekker_required
def my_bookings():
    active = current_user.bookings\
                         .filter(Booking.status == BookingStatus.BOOKED)\
                         .order_by(Booking.booking_date.desc()).all()
    history = current_user.bookings\
                          .filter(Booking.status != BookingStatus.BOOKED)\
                          .order_by(Booking.booking_date.desc()).all()
    return render_template("user/my_bookings.html", active_bookings=active, history=history)


@user_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@trekker_required
def do_cancel(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("user.my_bookings"))
    ok, msg = cancel_booking(booking)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("user.my_bookings"))


# ---------------------------------------------------------------------------
# REVIEW
# ---------------------------------------------------------------------------
@user_bp.route("/treks/<int:trek_id>/review", methods=["POST"])
@login_required
@trekker_required
def do_review(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0
    title = request.form.get("title", "").strip() or None
    body = request.form.get("body",  "").strip() or None
    ok, msg, _ = add_review(current_user, trek, rating, title, body)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("user.trek_detail", trek_id=trek_id))


# ---------------------------------------------------------------------------
# PROFILE
# ---------------------------------------------------------------------------
@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
@trekker_required
def profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", "").strip() or current_user.full_name
        phone = request.form.get("phone", "").strip() or None
        if phone:
            if not phone.isdigit():
                flash("Phone number must contain digits only.", "danger")
                return redirect(url_for("user.profile"))
            if len(phone) not in range(10, 14):
                flash("Phone number must be between 10 and 13 digits.", "danger")
                return redirect(url_for("user.profile"))
        current_user.phone = phone
        current_user.address = request.form.get("address",   "").strip() or None
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("user.profile"))
    return render_template("user/profile.html")


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
@user_bp.route("/notifications")
@login_required
@trekker_required
def notifications():
    notifs = current_user.notifications.order_by(db.text("created_at desc")).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template("user/notifications.html", notifications=notifs)
