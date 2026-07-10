"""
db_helpers.py
-------------
Database-layer helper functions that encapsulate business logic
(booking, slot management, status transitions, etc.).
All functions accept and return plain Python objects — no HTTP
concerns here.
"""
import random
import string
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models__1 import (db,User, Trek, Booking, Review, Notification,Role, TrekStatus, BookingStatus, AccountStatus)


# ---------------------------------------------------------------------------
# BOOKING REFERENCE GENERATOR
# ---------------------------------------------------------------------------
def _generate_booking_ref() -> str:
    """Return a unique 10-char uppercase alphanumeric booking reference."""
    chars = string.ascii_uppercase + string.digits
    while True:
        ref = "TRK-" + "".join(random.choices(chars, k=6))
        if not Booking.query.filter_by(booking_ref=ref).first():
            return ref


# ---------------------------------------------------------------------------
# BOOKING
# ---------------------------------------------------------------------------
def book_trek(user: User, trek: Trek,
              num_persons: int = 1,
              emergency_name: str = None,
              emergency_phone: str = None,
              special_requests: str = None) -> tuple[bool, str, "Booking | None"]:
    """
    Safely book a trek for a user.
    Returns (success: bool, message: str, booking_or_None)
    Business rules enforced:
      1. Trek must be Open.
      2. Available slots must cover num_persons.
      3. User must not have an active booking for the same trek.
    """
    if trek.status != TrekStatus.OPEN:
        return False, "This trek is not open for bookings.", None

    if trek.available_slots < num_persons:
        return False, (
            f"Only {trek.available_slots} slot(s) available, "
            f"but {num_persons} requested."
        ), None

    # Check existing active booking
    existing = Booking.query.filter_by(
        user_id=user.id, trek_id=trek.id
    ).filter(Booking.status != BookingStatus.CANCELLED).first()

    if existing:
        return False, "You already have an active booking for this trek.", None

    try:
        booking = Booking(
            booking_ref=_generate_booking_ref(),
            user_id=user.id,
            trek_id=trek.id,
            num_persons=num_persons,
            total_amount=trek.price * num_persons,
            emergency_contact_name=emergency_name,
            emergency_contact_phone=emergency_phone,
            special_requests=special_requests,
        )
        trek.available_slots -= num_persons
        db.session.add(booking)
        # Flush to get booking.id before commit
        db.session.flush()

        # Notify user
        _notify(user, "Booking Confirmed",
                f"Your booking for '{trek.name}' (Ref: {booking.booking_ref}) "
                f"is confirmed.",
                category="success",
                link=f"/user/bookings")

        # Auto-close trek if fully booked
        if trek.available_slots == 0:
            trek.status = TrekStatus.CLOSED

        db.session.commit()
        return True, "Booking confirmed successfully.", booking

    except IntegrityError:
        db.session.rollback()
        return False, "You already have a booking for this trek.", None
    except Exception as exc:
        db.session.rollback()
        return False, f"An error occurred: {exc}", None



def cancel_booking(booking: Booking, cancelled_by_admin: bool = False):
    """
    Cancel a booking and release the slot back to the trek.
    Rules:
      - Only Booked bookings can be cancelled.
      - Completed bookings cannot be cancelled.
    """
    if booking.status == BookingStatus.COMPLETED:
        return False, "Completed bookings cannot be cancelled."

    if booking.status == BookingStatus.CANCELLED:
        return False, "Booking is already cancelled."

    trek = booking.trek
    trek.available_slots += booking.num_persons

    # Re-open a closed-but-not-yet-started trek
    if trek.status == TrekStatus.CLOSED and trek.start_date and trek.start_date > datetime.utcnow().date():
        trek.status = TrekStatus.OPEN

    booking.status = BookingStatus.CANCELLED
    note = "by admin" if cancelled_by_admin else ""
    _notify(booking.user,
            "Booking Cancelled",
            f"Your booking (Ref: {booking.booking_ref}) for "
            f"'{trek.name}' has been cancelled {note}.".strip(),
            category="warning")
    db.session.commit()
    return True, "Booking cancelled successfully."


def complete_booking(booking: Booking) -> tuple[bool, str]:
    """Mark a single booking as Completed (called when trek completes)."""
    if booking.status != BookingStatus.BOOKED:
        return False, "Only active bookings can be marked as completed."
    booking.status = BookingStatus.COMPLETED
    db.session.commit()
    return True, "Booking marked as completed."


# ---------------------------------------------------------------------------
# TREK STATUS TRANSITIONS
# ---------------------------------------------------------------------------
def approve_trek(trek: Trek) -> tuple[bool, str]:
    if trek.status != TrekStatus.PENDING:
        return False, "Only Pending treks can be approved."
    trek.status = TrekStatus.APPROVED
    db.session.commit()
    return True, f"Trek '{trek.name}' approved."

 
def open_trek(trek: Trek) -> tuple[bool, str]:
    if trek.status not in (TrekStatus.APPROVED, TrekStatus.CLOSED):
        return False, "Trek must be Approved or Closed before it can be opened."
    if not trek.staff_id:
        return False, "Assign a staff member before opening the trek."
    
    # Check if start date is in the future
    if trek.start_date and trek.start_date <= datetime.now().date():
        return False, "Trek start date must be in the future to be opened."

    trek.status = TrekStatus.OPEN

    # Notify assigned staff
    if trek.assigned_staff:
        _notify(trek.assigned_staff,
                "Trek Opened",
                f"The trek '{trek.name}' is now open for bookings.",
                category="info")

    db.session.commit()
    return True, f"Trek '{trek.name}' is now Open."


def close_trek(trek: Trek) -> tuple[bool, str]:
    if trek.status not in (TrekStatus.OPEN, TrekStatus.APPROVED):
        return False, "Trek must be Open or Approved to be closed."
    trek.status = TrekStatus.CLOSED
    db.session.commit()
    return True, f"Trek '{trek.name}' closed."


def complete_trek(trek: Trek) -> tuple[bool, str]:
    """
    Mark trek as Completed and bulk-update all active bookings.
    """
    if trek.status not in (TrekStatus.OPEN, TrekStatus.CLOSED):
        return False, "Trek must be Open or Closed before completion."

    trek.status = TrekStatus.COMPLETED
    active_bookings = trek.bookings.filter_by(status=BookingStatus.BOOKED).all()
    for b in active_bookings:
        b.status = BookingStatus.COMPLETED
        _notify(b.user,
                "Trek Completed",
                f"Your trek '{trek.name}' has been completed. "
                f"We hope you had a great experience!",
                category="success")

    db.session.commit()
    return True, f"Trek '{trek.name}' marked as completed. {len(active_bookings)} bookings updated."


# ---------------------------------------------------------------------------
# STAFF MANAGEMENT
# ---------------------------------------------------------------------------
def approve_staff(staff: User) -> tuple[bool, str]:
    if staff.role != Role.STAFF:
        return False, "User is not registered as staff."
    if staff.status == AccountStatus.ACTIVE:
        return False, "Staff is already approved."
    staff.status = AccountStatus.ACTIVE
    _notify(staff,
            "Account Approved",
            "Your staff account has been approved by the admin. "
            "You can now log in and manage your assigned treks.",
            category="success")
    db.session.commit()
    return True, f"Staff '{staff.full_name}' approved."


def assign_staff_to_trek(staff: User, trek: Trek) -> tuple[bool, str]:
    if staff.role != Role.STAFF or staff.status != AccountStatus.ACTIVE:
        return False, "Only active staff can be assigned to treks."
    if trek.status == TrekStatus.COMPLETED:
        return False, "Cannot assign staff to a completed trek."

    trek.staff_id = staff.id
    _notify(staff,
            "Trek Assignment",
            f"You have been assigned to manage the trek: '{trek.name}'.",
            category="info")
    db.session.commit()
    return True, f"Staff '{staff.full_name}' assigned to trek '{trek.name}'."


def blacklist_user(user: User, reason: str = "") -> tuple[bool, str]:
    if user.role == Role.ADMIN:
        return False, "Admin accounts cannot be blacklisted."
    user.status = AccountStatus.BLACKLISTED
    _notify(user,
            "Account Suspended",
            f"Your account has been suspended. {reason}".strip(),
            category="danger")
    db.session.commit()
    return True, f"User '{user.username}' has been blacklisted."


def unblacklist_user(user: User) -> tuple[bool, str]:
    if user.status != AccountStatus.BLACKLISTED:
        return False, "User is not blacklisted."
    user.status = AccountStatus.ACTIVE
    _notify(user,
            "Account Reinstated",
            "Your account has been reinstated. You can log in again.",
            category="success")
    db.session.commit()
    return True, f"User '{user.username}' has been reinstated."


# ---------------------------------------------------------------------------
# SLOT UPDATE (by staff)
# ---------------------------------------------------------------------------
def update_available_slots(trek: Trek, new_available: int, staff: User) -> tuple[bool, str]:
    """Staff can adjust available slots (cannot exceed total_slots)."""
    if trek.staff_id != staff.id:
        return False, "You are not assigned to this trek."
    if new_available < 0:
        return False, "Available slots cannot be negative."
    if new_available > trek.total_slots:
        return False, f"Cannot exceed total slots ({trek.total_slots})."

    booked = trek.booked_slots
    if new_available + booked > trek.total_slots:
        return False, (
            f"Cannot set {new_available} available slots — "
            f"{booked} slots already booked."
        )

    trek.available_slots = new_available
    db.session.commit()
    return True, "Available slots updated."


# ---------------------------------------------------------------------------
# REVIEW
# ---------------------------------------------------------------------------

def add_review(user: User, trek: Trek, rating: int, title: str = None, body: str = None) -> tuple[bool, str, "Review | None"]:
    """
    User can review only after their booking is Completed.
    """
    completed = Booking.query.filter_by(
        user_id=user.id, trek_id=trek.id, status=BookingStatus.COMPLETED
    ).first()
    if not completed:
        return False, "You can review only after completing the trek.", None

    if Review.query.filter_by(user_id=user.id, trek_id=trek.id).first():
        return False, "You have already submitted a review for this trek.", None

    if not (1 <= rating <= 5):
        return False, "Rating must be between 1 and 5.", None

    review = Review(user_id=user.id, trek_id=trek.id, rating=rating, title=title, body=body)
    db.session.add(review)
    db.session.commit()
    return True, "Review submitted successfully.", review


# ---------------------------------------------------------------------------
# INTERNAL: NOTIFICATION HELPER
# ---------------------------------------------------------------------------
def _notify(user: User, title: str, message: str, category: str = "info", link: str = None) -> None:
    """Create an in-app notification for the given user (no commit here)."""
    notif = Notification(
        user_id=user.id,
        title=title,
        message=message,
        category=category,
        link=link,
    )
    db.session.add(notif)


# ---------------------------------------------------------------------------
# STATISTICS (used by Admin dashboard)
# ---------------------------------------------------------------------------
def get_dashboard_stats() -> dict:
    from sqlalchemy import func
    total_treks  = Trek.query.count()
    total_users = User.query.filter_by(role=Role.USER).count()
    total_staff = User.query.filter_by(role=Role.STAFF).count()
    total_bookings = Booking.query.count()
    open_treks = Trek.query.filter_by(status=TrekStatus.OPEN).count()
    pending_staff = User.query.filter(
        User.role == Role.STAFF,
        User.status == AccountStatus.PENDING
    ).count()
    revenue = db.session.query(func.sum(Booking.total_amount)).filter(
        Booking.status.in_([BookingStatus.BOOKED, BookingStatus.COMPLETED])
    ).scalar() or 0.0

    # Popular treks (top 5 by confirmed bookings)
    popular = (
        db.session.query(Trek.name,
                         func.count(Booking.id).label("cnt"))
        .join(Booking, Booking.trek_id == Trek.id)
        .filter(Booking.status != BookingStatus.CANCELLED)
        .group_by(Trek.id)
        .order_by(func.count(Booking.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_treks": total_treks,
        "total_users": total_users,
        "total_staff": total_staff,
        "total_bookings": total_bookings,
        "open_treks": open_treks,
        "pending_staff": pending_staff,
        "total_revenue":  round(revenue, 2),
        "popular_treks": popular,
    }

#----------------------------
#CHART JS
#----------------------------
def get_chart_data() -> dict:
    """
    Prepares data for the admin dashboard charts.
    Returns plain Python dicts/lists — Jinja2 converts them to JSON for Chart.js.
    """
    bookings_by_trek = (
        db.session.query(Trek.name, db.func.count(Booking.id))
        .join(Booking, Booking.trek_id == Trek.id)
        .filter(Booking.status != BookingStatus.CANCELLED)
        .group_by(Trek.id)
        .order_by(db.func.count(Booking.id).desc())
        .limit(6)
        .all()
    )

    status_counts = {}
    for status in [TrekStatus.PENDING, TrekStatus.APPROVED, TrekStatus.OPEN,
                    TrekStatus.CLOSED, TrekStatus.COMPLETED]:
        status_counts[status] = Trek.query.filter_by(status=status).count()

    return {
        "trek_labels": [name for name, count in bookings_by_trek],
        "trek_counts": [count for name, count in bookings_by_trek],
        "status_labels": list(status_counts.keys()),
        "status_counts": list(status_counts.values()),
    }


def delete_trek_helper(trek: Trek) -> tuple[bool, str]:
    """
    Delete a trek.
    If booked slots > 0 (meaning active bookings exist), cancel them, notify users, then delete.
    """
    # Active bookings are in BOOKED status
    active_bookings = Booking.query.filter_by(trek_id=trek.id, status=BookingStatus.BOOKED).all()
    
    # Notify users & cancel active bookings
    for booking in active_bookings:
        booking.status = BookingStatus.CANCELLED
        # Notify
        _notify(booking.user,
                "Trek Cancelled",
                f"Your booking (Ref: {booking.booking_ref}) for '{trek.name}' has been cancelled because the trek was deleted by the admin.",
                category="danger")

    # Actually delete the trek from db
    db.session.delete(trek)
    db.session.commit()
    return True, f"Trek '{trek.name}' deleted successfully."