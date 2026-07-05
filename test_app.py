import unittest
from app import create_app
from models__1 import db, User, Trek, Role, AccountStatus, TrekStatus, BookingStatus, Booking

class TrekkingAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("development")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()

    def test_admin_search_by_id(self):
        # Authenticate admin
        with self.client.session_transaction() as sess:
            admin = User.query.filter_by(role=Role.ADMIN).first()
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        # Test searching treks by ID
        trek = Trek.query.first()
        if trek:
            response = self.client.get(f'/admin/treks?q={trek.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(trek.name.encode('utf-8'), response.data)

        # Test searching users by ID
        user = User.query.filter(User.role != Role.ADMIN).first()
        if user:
            response = self.client.get(f'/admin/users?q={user.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(user.full_name.encode('utf-8'), response.data)

    def test_staff_open_trek(self):
        # Get active staff
        staff = User.query.filter_by(role=Role.STAFF, status=AccountStatus.ACTIVE).first()
        # Find a trek assigned to this staff
        trek = Trek.query.filter_by(staff_id=staff.id).first()
        self.assertIsNotNone(trek)
        
        # Set trek status to Closed and start_date to future
        from datetime import date, timedelta
        trek.start_date = date.today() + timedelta(days=10)
        trek.status = TrekStatus.CLOSED
        db.session.commit()

        # Log in staff
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(staff.id)
            sess['_fresh'] = True

        # Open the trek via staff route
        response = self.client.post(f'/staff/treks/{trek.id}/open', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify status is now OPEN
        db.session.refresh(trek)
        self.assertEqual(trek.status, TrekStatus.OPEN)

    def test_user_browse_approved_and_open_treks(self):
        # Ensure we have at least one approved and one open trek
        open_trek = Trek.query.filter_by(status=TrekStatus.OPEN).first()
        approved_trek = Trek.query.filter_by(status=TrekStatus.APPROVED).first()
        
        self.assertIsNotNone(open_trek)
        self.assertIsNotNone(approved_trek)

        # Log in trekker
        user = User.query.filter_by(role=Role.USER).first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        # Check browse page
        response = self.client.get('/user/treks')
        self.assertEqual(response.status_code, 200)
        self.assertIn(open_trek.name.encode('utf-8'), response.data)
        self.assertIn(approved_trek.name.encode('utf-8'), response.data)

    def test_admin_create_trek_with_image(self):
        import io
        # Authenticate admin
        with self.client.session_transaction() as sess:
            admin = User.query.filter_by(role=Role.ADMIN).first()
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        # Mock image data
        image_data = (io.BytesIO(b"dummy image data"), "test_trek_pic.jpg")

        form_data = {
            "name": "Test Image Trek",
            "location": "Test Location",
            "description": "Test Description",
            "difficulty": "Easy",
            "duration_days": "3",
            "total_slots": "15",
            "price": "4500",
            "image": image_data
        }

        response = self.client.post('/admin/treks/create', data=form_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Check that it exists in the database with custom image
        created_trek = Trek.query.filter_by(name="Test Image Trek").first()
        self.assertIsNotNone(created_trek)
        self.assertTrue(created_trek.image.startswith("trek_"))
        self.assertTrue(created_trek.image.endswith(".jpg"))

        # Clean up the created image file
        import os
        from flask import current_app
        image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], created_trek.image)
        if os.path.exists(image_path):
            os.remove(image_path)

    def test_admin_delete_trek_with_bookings(self):
        # Authenticate admin
        with self.client.session_transaction() as sess:
            admin = User.query.filter_by(role=Role.ADMIN).first()
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        # Create fresh user, staff, and trek
        import random
        from datetime import date, timedelta
        rand_num = random.randint(10000, 99999)
        
        test_user = User(
            username=f"temp_user_{rand_num}",
            email=f"temp_user_{rand_num}@example.com",
            full_name="Temp User",
            role=Role.USER,
            status=AccountStatus.ACTIVE
        )
        test_user.set_password("User@123")
        db.session.add(test_user)

        test_staff = User(
            username=f"temp_staff_{rand_num}",
            email=f"temp_staff_{rand_num}@example.com",
            full_name="Temp Staff",
            role=Role.STAFF,
            status=AccountStatus.ACTIVE
        )
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.flush()

        test_trek = Trek(
            name="Fresh Test Trek",
            location="Himalayas",
            difficulty="Moderate",
            duration_days=5,
            total_slots=10,
            available_slots=10,
            price=3000,
            status=TrekStatus.OPEN,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
            staff_id=test_staff.id
        )
        db.session.add(test_trek)
        db.session.commit()

        # Book the trek for user
        from db_helpers import book_trek
        success, msg, booking = book_trek(test_user, test_trek, num_persons=1)
        self.assertTrue(success, f"Booking failed: {msg}")
        self.assertIsNotNone(booking)

        # Run deletion
        response = self.client.post(f'/admin/treks/{test_trek.id}/delete', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Verify trek is deleted
        deleted_trek = Trek.query.get(test_trek.id)
        self.assertIsNone(deleted_trek)

        # Verify notification exists for the user about cancellation
        from models__1 import Notification
        notif = Notification.query.filter_by(user_id=test_user.id, title="Trek Cancelled").first()
        self.assertIsNotNone(notif)
        self.assertIn("cancelled", notif.message.lower())

    def test_duplicate_booking_prevention(self):
        import random
        from datetime import date, timedelta
        rand_num = random.randint(100000, 999999)
        test_user = User(username=f"u_{rand_num}", email=f"u_{rand_num}@example.com", full_name="User", role=Role.USER, status=AccountStatus.ACTIVE)
        test_user.set_password("User@123")
        db.session.add(test_user)

        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.ACTIVE)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.flush()

        test_trek = Trek(
            name="Duplicate Test Trek", location="Himalayas", difficulty="Moderate", duration_days=5,
            total_slots=10, available_slots=10, price=3000, status=TrekStatus.OPEN,
            start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=15),
            staff_id=test_staff.id
        )
        db.session.add(test_trek)
        db.session.commit()

        # Book first time
        from db_helpers import book_trek
        success, msg, booking = book_trek(test_user, test_trek, num_persons=1)
        self.assertTrue(success)

        # Attempt to book second time
        success2, msg2, booking2 = book_trek(test_user, test_trek, num_persons=1)
        self.assertFalse(success2)
        self.assertIn("already have", msg2.lower())

    def test_overbooking_prevention(self):
        import random
        from datetime import date, timedelta
        rand_num = random.randint(100000, 999999)
        test_user = User(username=f"u_{rand_num}", email=f"u_{rand_num}@example.com", full_name="User", role=Role.USER, status=AccountStatus.ACTIVE)
        test_user.set_password("User@123")
        db.session.add(test_user)

        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.ACTIVE)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.flush()

        test_trek = Trek(
            name="Overbook Test Trek", location="Himalayas", difficulty="Moderate", duration_days=5,
            total_slots=2, available_slots=2, price=3000, status=TrekStatus.OPEN,
            start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=15),
            staff_id=test_staff.id
        )
        db.session.add(test_trek)
        db.session.commit()

        # Try to book 3 slots when only 2 available
        from db_helpers import book_trek
        success, msg, booking = book_trek(test_user, test_trek, num_persons=3)
        self.assertFalse(success)
        self.assertIn("only 2 slot", msg.lower())

    def test_blacklisted_staff_assignment(self):
        import random
        from datetime import date, timedelta
        rand_num = random.randint(100000, 999999)
        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.BLACKLISTED)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)

        test_trek = Trek(
            name="Blacklist Test Trek", location="Himalayas", difficulty="Moderate", duration_days=5,
            total_slots=10, available_slots=10, price=3000, status=TrekStatus.PENDING,
            start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=15)
        )
        db.session.add(test_trek)
        db.session.commit()

        # Try to assign staff
        from db_helpers import assign_staff_to_trek
        success, msg = assign_staff_to_trek(test_staff, test_trek)
        self.assertFalse(success)
        self.assertIn("only active staff", msg.lower())

    def test_pending_staff_access_block(self):
        import random
        rand_num = random.randint(100000, 999999)
        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.PENDING)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.commit()

        # Log in pending staff
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(test_staff.id)
            sess['_fresh'] = True

        # Attempt to access dashboard
        response = self.client.get('/staff/dashboard', follow_redirects=True)
        self.assertIn(b"pending admin approval", response.data)

    def test_staff_update_slots(self):
        import random
        from datetime import date, timedelta
        rand_num = random.randint(100000, 999999)
        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.ACTIVE)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.flush()

        test_trek = Trek(
            name="Slots Update Trek", location="Himalayas", difficulty="Moderate", duration_days=5,
            total_slots=10, available_slots=10, price=3000, status=TrekStatus.OPEN,
            start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=15),
            staff_id=test_staff.id
        )
        db.session.add(test_trek)
        db.session.commit()

        # Update slots via helper
        from db_helpers import update_available_slots
        # 1. Success case
        success, msg = update_available_slots(test_trek, 5, test_staff)
        self.assertTrue(success)
        self.assertEqual(test_trek.available_slots, 5)

        # 2. Negative slots case
        success, msg = update_available_slots(test_trek, -1, test_staff)
        self.assertFalse(success)

        # 3. Exceed total slots case
        success, msg = update_available_slots(test_trek, 11, test_staff)
        self.assertFalse(success)

    def test_user_review_constraints(self):
        import random
        from datetime import date, timedelta
        rand_num = random.randint(100000, 999999)
        test_user = User(username=f"u_{rand_num}", email=f"u_{rand_num}@example.com", full_name="User", role=Role.USER, status=AccountStatus.ACTIVE)
        test_user.set_password("User@123")
        db.session.add(test_user)

        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.ACTIVE)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.flush()

        test_trek = Trek(
            name="Review Constraints Trek", location="Himalayas", difficulty="Moderate", duration_days=5,
            total_slots=10, available_slots=10, price=3000, status=TrekStatus.OPEN,
            start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=15),
            staff_id=test_staff.id
        )
        db.session.add(test_trek)
        db.session.commit()

        # Attempt to review before booking completed
        from db_helpers import add_review
        success, msg, review = add_review(test_user, test_trek, rating=5, title="Great", body="Enjoyed")
        self.assertFalse(success)
        self.assertIn("completing the trek", msg.lower())

        # Book and complete booking
        from db_helpers import book_trek, complete_booking
        success_b, msg_b, booking = book_trek(test_user, test_trek, num_persons=1)
        self.assertTrue(success_b)
        
        success_c, msg_c = complete_booking(booking)
        self.assertTrue(success_c)

        # Submit review
        success_r, msg_r, review = add_review(test_user, test_trek, rating=5, title="Great", body="Enjoyed")
        self.assertTrue(success_r)
        self.assertIsNotNone(review)

        # Attempt to submit review again
        success_r2, msg_r2, review2 = add_review(test_user, test_trek, rating=5, title="Great", body="Enjoyed")
        self.assertFalse(success_r2)
        self.assertIn("already submitted", msg_r2.lower())

    def test_trek_auto_close_and_reopen(self):
        import random
        from datetime import date, timedelta
        rand_num = random.randint(100000, 999999)
        test_user = User(username=f"u_{rand_num}", email=f"u_{rand_num}@example.com", full_name="User", role=Role.USER, status=AccountStatus.ACTIVE)
        test_user.set_password("User@123")
        db.session.add(test_user)

        test_staff = User(username=f"s_{rand_num}", email=f"s_{rand_num}@example.com", full_name="Staff", role=Role.STAFF, status=AccountStatus.ACTIVE)
        test_staff.set_password("Staff@123")
        db.session.add(test_staff)
        db.session.flush()

        test_trek = Trek(
            name="Auto Close Trek", location="Himalayas", difficulty="Moderate", duration_days=5,
            total_slots=1, available_slots=1, price=3000, status=TrekStatus.OPEN,
            start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=15),
            staff_id=test_staff.id
        )
        db.session.add(test_trek)
        db.session.commit()

        # Book the last slot
        from db_helpers import book_trek, cancel_booking
        success, msg, booking = book_trek(test_user, test_trek, num_persons=1)
        self.assertTrue(success)
        
        # Verify trek status is now CLOSED
        self.assertEqual(test_trek.status, TrekStatus.CLOSED)

        # Cancel booking and verify it opens again
        success_cancel, msg_cancel = cancel_booking(booking)
        self.assertTrue(success_cancel)
        self.assertEqual(test_trek.status, TrekStatus.OPEN)

if __name__ == '__main__':
    unittest.main()

