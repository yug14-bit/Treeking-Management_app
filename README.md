# 🏔️ TrailMaster — Trekking Management Application

A full-stack web application for managing trekking operations, built with Flask and SQLAlchemy. TrailMaster connects three types of users — **Admin**, **Trek Staff**, and **Trekkers** — through a role-based platform that handles trek creation, booking management, staff coordination, and analytics.

---

## 🚀 Features

### Admin
- Create, edit, and delete treks with full lifecycle management (Pending → Approved → Open → Closed → Completed)
- Approve and assign Trek Staff to specific treks
- Blacklist or reinstate users and staff
- View dashboard analytics with Chart.js (bookings by trek, trek status breakdown)
- Search and filter treks, users, and bookings
- Cancel any booking from the admin side
- JSON API endpoints for treks, bookings, and stats

### Trek Staff
- Self-register (requires admin approval before login)
- View all assigned treks with participant lists
- Update available slots and change trek status (Close / Complete)
- Receive in-app notifications for assignments and approvals

### Trekker (User)
- Self-register and login immediately (no approval required)
- Browse and search open treks by name, location, and difficulty
- Book treks with emergency contact details and special requests
- Cancel active bookings (slots released back automatically)
- Leave reviews (1–5 stars) after completing a trek
- View booking history (Active and Completed tabs)
- Edit personal profile

### General
- Role-based access control with custom decorators
- Secure password hashing via Werkzeug
- In-app notification system with unread count bell indicator
- Auto-dismiss flash messages (JavaScript)
- Fully responsive UI using Bootstrap 5 with custom purple-blue gradient theme
- Frontend + backend validation on all forms

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Database | SQLite via SQLAlchemy ORM |
| Authentication | Flask-Login |
| Password Security | Werkzeug |
| Templating | Jinja2 |
| Frontend | Bootstrap 5, Bootstrap Icons |
| Charts | Chart.js |
| Version Control | Git / GitHub |

---

## 📁 Project Structure

```
trailmaster/
├── app.py                  # Application factory, config, blueprint registration
├── models.py               # SQLAlchemy ORM models (5 tables)
├── db_helpers.py           # Business logic service layer
├── create_db.py            # Database creation and seed data
│
├── blueprints/
│   ├── auth/routes.py      # Login, Register, Logout
│   ├── admin/routes.py     # Admin dashboard and management
│   ├── staff/routes.py     # Staff dashboard and trek management
│   ├── user/routes.py      # Trekker features
│   └── api/routes.py       # JSON API endpoints
│
├── templates/
│   ├── base.html           # Shared layout (navbar, footer, flash messages)
│   ├── auth/               # login.html, register.html
│   ├── admin/              # dashboard, treks, users, bookings, trek_form
│   ├── staff/              # dashboard, my_treks, trek_detail, profile
│   └── user/               # dashboard, browse_treks, trek_detail, bookings, profile
│
├── static/
│   └── uploads/            # Profile pictures and trek images
│
└── instance/
    └── trekking.db         # SQLite database file (auto-created)
```

---

## 🗄️ Database Schema

Five tables connected via SQLAlchemy relationships:

- **users** — Admin, Staff, and Trekker all in one table (discriminator pattern via `role` column)
- **treks** — Trek events with full lifecycle status management
- **bookings** — Links users to treks; unique constraint prevents double-booking
- **reviews** — 1–5 star ratings, allowed only after a booking is Completed
- **notifications** — In-app alerts auto-created on key events

---

## ⚙️ Setup and Installation

### 1. Clone the repository
```bash
git clone <your-github-repo-url>
cd trailmaster
```

### 2. Create and activate virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install flask flask-sqlalchemy flask-login werkzeug
```

### 4. Create the database with seed data
```bash
python create_db.py
```

### 5. Run the application
```bash
python app.py
```

### 6. Open in browser
```
http://localhost:5000
```

---

## 👤 Demo Credentials

| Role | Username | Password |
|---|---|---|
| Admin | admin | admin123 |
| Trek Staff | Register via /register?role=staff | — |
| Trekker | Register via /register?role=user | — |

> ⚠️ Check `create_db.py` for the exact admin credentials used during seeding.

---

## 🌐 API Endpoints

All API routes return JSON and are accessible under `/api/`:

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/treks` | Public | All currently Open treks |
| GET | `/api/treks/<id>` | Public | Single trek detail with reviews |
| GET | `/api/bookings` | Admin only | All bookings |
| GET | `/api/stats` | Admin only | Dashboard statistics |

**Example response** (`/api/treks`):
```json
{
  "status": "success",
  "count": 3,
  "treks": [
    {
      "id": 1,
      "name": "Roopkund Skeleton Lake",
      "location": "Uttarakhand, India",
      "difficulty": "Hard",
      "price": 8500.0,
      "available_slots": 6,
      "status": "Open"
    }
  ]
}
```

---

## 🎯 Key Design Decisions

**1. Single User Table for 3 Roles**
Instead of separate Admin/Staff/Trekker tables, a single `users` table with a `role` column (discriminator pattern) simplifies authentication and relationships.

**2. Service Layer (`db_helpers.py`)**
All business logic lives in `db_helpers.py`, completely separated from route handlers. Routes only validate input, call a helper function, and flash the result — keeping route functions short and testable.

**3. Blueprint Architecture**
Routes are split into 5 Blueprints (auth, admin, staff, user, api) to keep the codebase modular. Each Blueprint has its own URL prefix and role-based decorator protection.

**4. Notification System**
`_notify()` adds notifications to the session without committing — the calling function commits everything in one transaction, so notifications are rolled back if the main operation fails.

---

## 📹 Video Walkthrough

[Link to demo video — add your Google Drive link here]

---

## 👨‍💻 Author

- **Name:** Yug Poniya
- **Roll Number:** 24f2003357
- **Course:** IIT Madras BS Degree — MAD1 (Modern Application Development)

---

## 📄 License

This project was built for educational purposes as part of the IIT Madras BS Degree program.