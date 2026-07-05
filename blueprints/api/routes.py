"""
blueprints/api/routes.py
-------------------------
Read-only JSON API endpoints for TrailMaster.
These return JSON instead of rendered HTML — demonstrating
that Flask can serve both a web app and an API from the same codebase.

Endpoints:
  GET /api/treks          → all currently Open treks (public)
  GET /api/treks/<id>     → single trek detail (public)
  GET /api/bookings       → all bookings (admin only)
  GET /api/stats          → dashboard statistics (admin only)
"""

from flask import Blueprint, jsonify
from flask_login import current_user

from models__1 import Trek, Booking, User, TrekStatus, BookingStatus, Role

api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# HELPER — check if current user is admin (for protected API routes)
# ---------------------------------------------------------------------------
def _is_admin():
    return current_user.is_authenticated and current_user.role == Role.ADMIN


# ---------------------------------------------------------------------------
# GET /api/treks
# Returns all currently Open treks as a JSON array.
# Public — no login required.
# ---------------------------------------------------------------------------
@api_bp.route("/treks", methods=["GET"])
def get_treks():
    treks = Trek.query.filter_by(status=TrekStatus.OPEN).all()
    return jsonify({
        "status": "success",
        "count": len(treks),
        "treks": [
            {
                "id":              t.id,
                "name":            t.name,
                "location":        t.location,
                "difficulty":      t.difficulty,
                "duration_days":   t.duration_days,
                "price":           t.price,
                "available_slots": t.available_slots,
                "total_slots":     t.total_slots,
                "altitude_m":      t.altitude_m,
                "distance_km":     t.distance_km,
                "start_date":      str(t.start_date) if t.start_date else None,
                "end_date":        str(t.end_date)   if t.end_date   else None,
                "status":          t.status,
                "average_rating":  t.average_rating(),
            }
            for t in treks
        ]
    })


# ---------------------------------------------------------------------------
# GET /api/treks/<int:trek_id>
# Returns a single trek's full detail including reviews.
# Public — no login required.
# ---------------------------------------------------------------------------
@api_bp.route("/treks/<int:trek_id>", methods=["GET"])
def get_trek(trek_id):
    trek = Trek.query.get(trek_id)

    if not trek:
        return jsonify({
            "status": "error",
            "message": f"Trek with id {trek_id} not found."
        }), 404

    reviews = trek.reviews.all()

    return jsonify({
        "status": "success",
        "trek": {
            "id":              trek.id,
            "name":            trek.name,
            "location":        trek.location,
            "description":     trek.description,
            "difficulty":      trek.difficulty,
            "duration_days":   trek.duration_days,
            "price":           trek.price,
            "available_slots": trek.available_slots,
            "total_slots":     trek.total_slots,
            "altitude_m":      trek.altitude_m,
            "distance_km":     trek.distance_km,
            "start_date":      str(trek.start_date) if trek.start_date else None,
            "end_date":        str(trek.end_date)   if trek.end_date   else None,
            "status":          trek.status,
            "assigned_staff":  trek.assigned_staff.full_name if trek.assigned_staff else None,
            "average_rating":  trek.average_rating(),
            "occupancy_pct":   trek.occupancy_pct,
            "reviews": [
                {
                    "user":       r.user.full_name,
                    "rating":     r.rating,
                    "title":      r.title,
                    "body":       r.body,
                    "created_at": str(r.created_at.date()),
                }
                for r in reviews
            ]
        }
    })


# ---------------------------------------------------------------------------
# GET /api/bookings
# Returns all bookings. Admin only.
# ---------------------------------------------------------------------------
@api_bp.route("/bookings", methods=["GET"])
def get_bookings():
    if not _is_admin():
        return jsonify({
            "status": "error",
            "message": "Unauthorized. Admin access required."
        }), 403

    bookings = Booking.query.order_by(Booking.booking_date.desc()).all()

    return jsonify({
        "status": "success",
        "count": len(bookings),
        "bookings": [
            {
                "id":           b.id,
                "booking_ref":  b.booking_ref,
                "user":         b.user.full_name,
                "trek":         b.trek.name,
                "num_persons":  b.num_persons,
                "total_amount": b.total_amount,
                "status":       b.status,
                "booking_date": str(b.booking_date.date()),
            }
            for b in bookings
        ]
    })


# ---------------------------------------------------------------------------
# GET /api/stats
# Returns admin dashboard statistics. Admin only.
# ---------------------------------------------------------------------------
@api_bp.route("/stats", methods=["GET"])
def get_stats():
    if not _is_admin():
        return jsonify({
            "status": "error",
            "message": "Unauthorized. Admin access required."
        }), 403

    from db_helpers import get_dashboard_stats
    stats = get_dashboard_stats()

    return jsonify({
        "status": "success",
        "stats": {
            "total_treks":    stats["total_treks"],
            "total_users":    stats["total_users"],
            "total_staff":    stats["total_staff"],
            "total_bookings": stats["total_bookings"],
            "open_treks":     stats["open_treks"],
            "pending_staff":  stats["pending_staff"],
            "total_revenue":  stats["total_revenue"],
            "popular_treks": [
                {"name": name, "bookings": count}
                for name, count in stats["popular_treks"]
            ]
        }
    })