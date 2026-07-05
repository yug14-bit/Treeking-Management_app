from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timezone
from sqlalchemy import Numeric

db = SQLAlchemy()

class Role:
    ADMIN = "admin"
    STAFF = "staff"
    USER  = "user"

class TrekDifficulty:
    EASY     = "Easy"
    MODERATE = "Moderate"
    HARD     = "Hard"

class TrekStatus:
    PENDING   = "Pending"
    APPROVED  = "Approved"
    OPEN      = "Open"
    CLOSED    = "Closed"
    COMPLETED = "Completed"

class BookingStatus:
    BOOKED    = "Booked"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"

class AccountStatus:
    ACTIVE      = "Active"
    PENDING     = "Pending"
    BLACKLISTED = "Blacklisted"
    INACTIVE    = "Inactive"


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash= db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    profile_pic  = db.Column(db.String(255), nullable=True, default="default.png")
    role = db.Column(db.String(20), nullable=False, default=Role.USER)
    status = db.Column(db.String(20), nullable=False, default=AccountStatus.ACTIVE)
    experience_years = db.Column(db.Integer, nullable=True)
    certifications = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


    bookings = db.relationship("Booking", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")
    assigned_treks= db.relationship("Trek", back_populates="assigned_staff", foreign_keys="Trek.staff_id", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        return self.status not in (AccountStatus.BLACKLISTED, AccountStatus.INACTIVE)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_staff(self) -> bool:
        return self.role == Role.STAFF

    @property
    def is_trekker(self) -> bool:
        return self.role == Role.USER

    @property
    def is_approved_staff(self) -> bool:
        return self.role == Role.STAFF and self.status == AccountStatus.ACTIVE

    def total_bookings(self) -> int:
        return self.bookings.count()

    def completed_treks(self) -> int:
        return self.bookings.filter_by(status=BookingStatus.COMPLETED).count()

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class Trek(db.Model):
    __tablename__ = "treks"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    location = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default=TrekDifficulty.EASY)
    duration_days = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots= db.Column(db.Integer, nullable=False)
    price = db.Column(Numeric(10, 2), nullable=False, default=0.0)
    altitude_m = db.Column(db.Integer, nullable=True)
    distance_km = db.Column(db.Float, nullable=True)
    image = db.Column(db.String(255), nullable=True, default="trek_default.jpg")
    status = db.Column(db.String(20), nullable=False, default=TrekStatus.PENDING, index=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    staff_id  = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    #date and slot constraints
    __table_args__ = (
        db.CheckConstraint("end_date >= start_date",name="ck_trek_dates"),
        db.CheckConstraint("available_slots >= 0",name="ck_slots_positive"),
        db.CheckConstraint("available_slots <= total_slots",name="ck_slots_max"),
        db.CheckConstraint("total_slots > 0",name="ck_total_slots_positive"),
        db.CheckConstraint("price >= 0",name="ck_price_positive"),
    )

    assigned_staff = db.relationship("User", back_populates="assigned_treks", foreign_keys=[staff_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    bookings = db.relationship("Booking", back_populates="trek", lazy="dynamic", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="trek", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def is_bookable(self) -> bool:
        return self.status == TrekStatus.OPEN and self.available_slots > 0

    @property
    def booked_slots(self) -> int:
        return self.total_slots - self.available_slots

    @property
    def occupancy_pct(self) -> float:
        if self.total_slots == 0:
            return 0.0
        return round((self.booked_slots / self.total_slots) * 100, 1)

    def average_rating(self) -> float:
        all_reviews = self.reviews.all()
        if not all_reviews:
            return 0.0
        return round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)

    def total_revenue(self) -> float:
        confirmed = self.bookings.filter(
            Booking.status.in_([BookingStatus.BOOKED, BookingStatus.COMPLETED])
        ).count()
        return confirmed * float(self.price)

    def __repr__(self) -> str:
        return f"<Trek id={self.id} name={self.name!r} status={self.status}>"


class Booking(db.Model):
    __tablename__ = "bookings"
    id  = db.Column(db.Integer, primary_key=True)
    booking_ref = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trek_id = db.Column(db.Integer, db.ForeignKey("treks.id", ondelete="CASCADE"),nullable=False, index=True)
    booking_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=BookingStatus.BOOKED, index=True)
    num_persons = db.Column(db.Integer, nullable=False, default=1)
    total_amount = db.Column(Numeric(10, 2), nullable=False, default=0.0)
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone= db.Column(db.String(20), nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    #include status so cancelled users can rebook
    __table_args__ = (
        db.UniqueConstraint("user_id", "trek_id", "status", name="uq_booking_user_trek"),
        db.CheckConstraint("num_persons > 0", name="ck_num_persons_positive"),
        db.CheckConstraint("total_amount >= 0", name="ck_amount_positive"),
    )

    user = db.relationship("User", back_populates="bookings")
    trek = db.relationship("Trek", back_populates="bookings")

    def __repr__(self) -> str:
        return (f"<Booking id={self.id} ref={self.booking_ref!r} " f"user={self.user_id} trek={self.trek_id} status={self.status}>")


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("treks.id", ondelete="CASCADE"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(150), nullable=True)
    body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "trek_id", name="uq_review_user_trek"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    )
    user = db.relationship("User", back_populates="reviews")
    trek = db.relationship("Trek", back_populates="reviews")

    def __repr__(self) -> str:
        return f"<Review trek={self.trek_id} user={self.user_id} rating={self.rating}>"


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default="info")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return (f"<Notification id={self.id} user={self.user_id} " f"title={self.title!r} read={self.is_read}>")