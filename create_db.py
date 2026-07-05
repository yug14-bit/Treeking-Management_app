"""
create_db.py
------------
Programmatic database initialisation for the Trekking Management App.

Run once (or whenever you want a clean reset):
    python create_db.py
What it does:
  1. Creates all SQLite tables via db.create_all()
  2. Seeds the default Admin account (username: admin / password: Admin@123)
  3. Seeds sample staff, users, treks, and bookings for development/demo
"""

import os
import sys
from datetime import date, timedelta, datetime
# Make sure the parent package is importable when run directly
sys.path.insert(0, os.path.dirname(__file__))


from flask import Flask
from models__1 import (db, User, Trek, Booking, Review, Notification,
    Role, TrekDifficulty, TrekStatus, BookingStatus, AccountStatus
)


from db_helpers import _generate_booking_ref, _notify


#app initialization
def create_seed_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="change-this-in-production",
        SQLALCHEMY_DATABASE_URI="sqlite:///trekking.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


#user creation by a function called _make_user
def _make_user(username, email, full_name, password,
        role=Role.USER, status=AccountStatus.ACTIVE,
        phone=None, **kwargs) -> User:
    
    u = User(
        username=username, email=email,
        full_name=full_name, role=role,
        status=status, phone=phone, **kwargs
    )

    u.set_password(password)
    return u


def seed_database(app: Flask) -> None:
    with app.app_context():
        # 1. Drop & recreate (clean slate for dev/demo)
        db.drop_all()
        db.create_all()
        print("[OK] Tables created.")

        # 2. Admin (pre-existing superuser — no public registration)
        admin = _make_user(
            username="admin",
            email="admin@trekking.app",
            full_name="System Administrator",
            password="Admin@123",
            role=Role.ADMIN,
            status=AccountStatus.ACTIVE,
            phone="+91-9000000000",
        )
        db.session.add(admin)
        db.session.flush()   # get admin.id without committing
        print(f"[OK] Admin created  →  username=admin  password=Admin@123")



        # ----------------------------------------------------------------
        # 3. Sample Trek Staff
        # ----------------------------------------------------------------
        staff1 = _make_user(
            username="rajan_guide",
            email="rajan@trekking.app",
            full_name="Rajan Sharma",
            password="Staff@123",
            role=Role.STAFF,
            status=AccountStatus.ACTIVE,
            phone="+91-9111111111",
            experience_years=8,
            certifications="Wilderness First Responder, NOLS Leader",
            bio="Seasoned Himalayan guide with 8 years of high-altitude experience.",
        )

        staff2 = _make_user(
            username="priya_lead",
            email="priya@trekking.app",
            full_name="Priya Nair",
            password="Staff@123",
            role=Role.STAFF,
            status=AccountStatus.ACTIVE,
            phone="+91-9222222222",
            experience_years=5,
            certifications="Rock Climbing Level 2, Avalanche Safety",
            bio="Expert in Western Ghats treks and jungle survival.",
        )

        staff3_pending = _make_user(
            username="arjun_new",
            email="arjun@trekking.app",
            full_name="Arjun Patel",
            password="Staff@123",
            role=Role.STAFF,
            status=AccountStatus.PENDING,  # awaiting admin approval
            phone="+91-9333333333",
            experience_years=2,
        )

        db.session.add_all([staff1, staff2, staff3_pending])
        db.session.flush()
        print(f"[OK] 3 staff accounts created (2 active, 1 pending).")


        # ----------------------------------------------------------------
        # 4. Sample Users (Trekkers)
        # ----------------------------------------------------------------
        users = []
        sample_users = [
            ("aarav_t", "aarav@mail.com", "Aarav Mehta", "+91-9444444441"),
            ("nisha_d", "nisha@mail.com", "Nisha Desai", "+91-9444444442"),
            ("kabir_v", "kabir@mail.com", "Kabir Verma", "+91-9444444443"),
            ("sana_k",  "sana@mail.com",  "Sana Khan", "+91-9444444444"),
            ("rohit_s", "rohit@mail.com", "Rohit Singh", "+91-9444444445"),
            ("meera_g", "meera@mail.com",  "Meera Gupta", "+91-9444444446"),
        ]


        for uname, email, full, phone in sample_users:
            u = _make_user(username=uname, email=email,full_name=full, password="User@123",phone=phone)
            users.append(u)
    
        db.session.add_all(users)
        db.session.flush()
        print(f"[OK] {len(users)} trekker accounts created  →  password=User@123")


        # ----------------------------------------------------------------
        # 5. Sample Treks
        # ----------------------------------------------------------------
        today = date.today()
        treks_data = [
            dict(
                name="Roopkund Skeleton Lake",
                location="Uttarakhand, India",
                description=(
                    "A high-altitude glacial lake trek in the Himalayas famous for "
                    "ancient human skeletons at the rim. Breathtaking views of "
                    "Trishul and Nanda Ghunti peaks."
                ),
                difficulty=TrekDifficulty.HARD,
                duration_days=8,
                total_slots=20, available_slots=17,
                price=8500.0, altitude_m=5029, distance_km=53.0,
                status=TrekStatus.OPEN,
                start_date=today + timedelta(days=15),
                end_date=today + timedelta(days=23),
                staff_id=staff1.id, created_by=admin.id,
            ),
            dict(
                name="Valley of Flowers",
                location="Chamoli, Uttarakhand, India",
                description=(
                    "A UNESCO World Heritage Site bursting with alpine wildflowers "
                    "and glacial rivers. Perfect for nature photographers and "
                    "moderate trekkers."
                ),
                difficulty=TrekDifficulty.MODERATE,
                duration_days=6,
                total_slots=25, available_slots=21,
                price=6000.0, altitude_m=3658, distance_km=38.0,
                status=TrekStatus.OPEN,
                start_date=today + timedelta(days=10),
                end_date=today + timedelta(days=16),
                staff_id=staff1.id, created_by=admin.id,
            ),
            dict(
                name="Kudremukh National Park Trail",
                location="Chikkamagaluru, Karnataka, India",
                description=(
                    "A lush evergreen shola-grassland trail through one of India's "
                    "richest biodiversity zones. Gentle ascents and stunning ridgeline views."
                ),
                difficulty=TrekDifficulty.EASY,
                duration_days=2,
                total_slots=30, available_slots=30,
                price=2500.0, altitude_m=1894, distance_km=22.0,
                status=TrekStatus.OPEN,
                start_date=today + timedelta(days=5),
                end_date=today + timedelta(days=7),
                staff_id=staff2.id, created_by=admin.id,
            ),
            dict(
                name="Hampta Pass Crossing",
                location="Kullu, Himachal Pradesh, India",
                description=(
                    "A dramatic crossing from lush Kullu valley to the arid moonscapes "
                    "of Lahaul. One of Himachal's most scenic high-altitude passes."
                ),
                difficulty=TrekDifficulty.MODERATE,
                duration_days=5,
                total_slots=18, available_slots=18,
                price=7200.0, altitude_m=4270, distance_km=35.0,
                status=TrekStatus.APPROVED,
                start_date=today + timedelta(days=30),
                end_date=today + timedelta(days=35),
                staff_id=None, created_by=admin.id,
            ),
            dict(
                name="Kedarkantha Winter Summit",
                location="Uttarkashi, Uttarakhand, India",
                description=(
                    "A popular winter summit covered in deep snow with 360° views "
                    "of major Himalayan peaks. Great for first-time summit trekkers."
                ),
                difficulty=TrekDifficulty.MODERATE,
                duration_days=6,
                total_slots=22, available_slots=22,
                price=6800.0, altitude_m=3810, distance_km=20.0,
                status=TrekStatus.PENDING,
                start_date=today + timedelta(days=60),
                end_date=today + timedelta(days=66),
                staff_id=None, created_by=admin.id,
            ),
            dict(
                name="Dudhsagar Waterfall Trail",
                location="Goa-Karnataka Border, India",
                description=(
                    "A short, rewarding trail leading to one of India's tallest "
                    "waterfalls. Jungle canopy, railway bridges, and a cool plunge pool await."
                ),
                difficulty=TrekDifficulty.EASY,
                duration_days=1,
                total_slots=40, available_slots=40,
                price=1200.0, altitude_m=310, distance_km=14.0,
                status=TrekStatus.COMPLETED,
                start_date=today - timedelta(days=20),
                end_date=today - timedelta(days=19),
                staff_id=staff2.id, created_by=admin.id,
            ),
        ]

        trek_objs = []
        for td in treks_data:
            t = Trek(**td)
            trek_objs.append(t)
            db.session.add(t)
        db.session.flush()
        print(f"[OK] {len(trek_objs)} treks created.")

        # Alias for readability
        t_roopkund, t_vof, t_kudremukh, t_hampta, t_kedarkantha, t_dudhsagar = trek_objs

        # ----------------------------------------------------------------
        # 6. Sample Bookings
        # ----------------------------------------------------------------
        def _book(user, trek, num=1, status=BookingStatus.BOOKED):
            b = Booking(
                booking_ref=_generate_booking_ref(),
                user_id=user.id,
                trek_id=trek.id,
                num_persons=num,
                total_amount=trek.price * num,
                status=status,
            )
            db.session.add(b)
            # Decrement slots for active bookings
            if status == BookingStatus.BOOKED:
                trek.available_slots -= num
            return b

        # Roopkund bookings (3 slots taken → available = 17)
        _book(users[0], t_roopkund)   # aarav
        _book(users[1], t_roopkund)   # nisha
        _book(users[2], t_roopkund)   # kabir

        # Valley of Flowers (4 slots taken → available = 21)
        _book(users[3], t_vof)        # sana
        _book(users[4], t_vof, num=2) # rohit books 2

        # Dudhsagar (all completed)
        b1 = _book(users[0], t_dudhsagar, status=BookingStatus.COMPLETED)
        b2 = _book(users[1], t_dudhsagar, status=BookingStatus.COMPLETED)
        b3 = _book(users[5], t_dudhsagar, status=BookingStatus.COMPLETED)

        db.session.flush()
        print(f"[OK] Sample bookings created.")


        # ----------------------------------------------------------------
        # 7. Sample Reviews (for completed trek)
        # ----------------------------------------------------------------
        reviews = [
            Review(user_id=users[0].id, trek_id=t_dudhsagar.id,
                   rating=5, title="Absolutely stunning!",
                   body="The waterfall is even more spectacular in person. "
                        "The guide was excellent and the trail well-maintained."),
            Review(user_id=users[1].id, trek_id=t_dudhsagar.id,
                   rating=4, title="Great experience",
                   body="Loved every bit of it. The jungle section was magical. "
                        "Only minor complaint: the last kilometer is slippery."),
            Review(user_id=users[5].id, trek_id=t_dudhsagar.id,
                   rating=5, title="Best day trek I've done",
                   body="Perfect length for a day out. The plunge pool at the base "
                        "of the falls is incredible. Will definitely return."),
        ]
        db.session.add_all(reviews)

        # ----------------------------------------------------------------
        # 8. Sample Notifications
        # ----------------------------------------------------------------
        _notify(staff3_pending,
                "Registration Received",
                "Your registration as Trek Staff has been received and is "
                "pending admin approval.",
                category="info")

        _notify(users[0],
                "Upcoming Trek Reminder",
                f"Your trek '{t_roopkund.name}' starts in 15 days. "
                f"Make sure you are physically prepared!",
                category="info",
                link=f"/user/bookings")

        # ----------------------------------------------------------------
        # 9. Final commit
        # ----------------------------------------------------------------
        db.session.commit()
        print("\n" + "=" * 60)
        print("DATABASE SEEDED SUCCESSFULLY")
        print("=" *60)
        print("\n Login Credentials")
        print("  -----------------")
        print("Admin : admin / Admin@123")
        print("Staff : rajan_guide / Staff@123  (approved)")
        print("Staff : priya_lead / Staff@123  (approved)")
        print("Staff : arjun_new / Staff@123  (pending approval)")
        print("Trekker : aarav_t / User@123")
        print("Trekker : nisha_d / User@123")
        print("Trekker : kabir_v /  User@123")
        print("(and 3 more trekkers with the same password)")
        print("\n  Database → instance/trekking.db")
        print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_seed_app()
    # Ensure instance directory exists
    os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)
    seed_database(app)