from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import RegistrationForm
from .models import Ride, RideRequest, UserProfile

PW = "pw12345678"


def mkuser(name, gender="M", phone="9876543210"):
    email = f"{name}@iiitdmj.ac.in"
    u = User.objects.create_user(email, email, PW, first_name=name)
    UserProfile.objects.create(user=u, roll_number=f"R-{name}", phone_number=phone, gender=gender)
    return u


def mkride(creator, mins=120, seats=2, fare=300, **kw):
    dt = timezone.localtime().replace(tzinfo=None) + timedelta(minutes=mins)
    return Ride.objects.create(creator=creator, direction="OUTBOUND", location="Sadar", pickup_point="Main Gate",
                               travel_date=dt.date(), travel_time=dt.time(), seats_available=seats,
                               estimated_total_fare=fare, **kw)


class FareTests(TestCase):
    def test_fare_split(self):
        u = mkuser("a")
        self.assertEqual(mkride(u, seats=2).fare_now, 300)   # creator alone
        self.assertEqual(mkride(u, seats=1).fare_now, 150)   # 2 riders
        r = mkride(u, seats=0)
        self.assertEqual(r.fare_now, 100)                    # 3 riders
        self.assertEqual(r.fare_full, 100)


class RegistrationTests(TestCase):
    def _data(self, email):
        return dict(first_name="Z", email=email, roll_number="22BCS999", gender="M", phone_number="9876500099",
                    password1="Str0ngPass!77", password2="Str0ngPass!77")

    def test_rejects_non_institute_email(self):
        self.assertIn("email", RegistrationForm(data=self._data("z@gmail.com")).errors)

    def test_accepts_institute_email(self):
        self.assertTrue(RegistrationForm(data=self._data("z@iiitdmj.ac.in")).is_valid())


class FlowTests(TestCase):
    def setUp(self):
        self.a, self.b, self.c = mkuser("aarav"), mkuser("rohan", phone="9111111111"), mkuser("kabir", phone="9222222222")
        self.f = mkuser("diya", gender="F")

    def login(self, u):
        self.client.logout()
        self.assertTrue(self.client.login(username=u.username, password=PW))

    def test_phone_hidden_until_accepted(self):
        ride = mkride(self.a)
        self.login(self.b)
        self.client.post(reverse("request_join", args=[ride.id]))
        self.login(self.a)
        html = self.client.get(reverse("my_rides")).content.decode()
        self.assertNotIn("9111111111", html)
        rr = RideRequest.objects.get()
        self.client.post(reverse("handle_request", args=[rr.id]), {"action": "accept"})
        html = self.client.get(reverse("my_rides")).content.decode()
        self.assertIn("919111111111", html)
        ride.refresh_from_db()
        self.assertEqual(ride.seats_available, 1)

    def test_last_seat_declines_other_pending(self):
        ride = mkride(self.a, seats=1)
        for u in (self.b, self.c):
            self.login(u)
            self.client.post(reverse("request_join", args=[ride.id]))
        self.login(self.a)
        first = RideRequest.objects.get(requester=self.b)
        self.client.post(reverse("handle_request", args=[first.id]), {"action": "accept"})
        ride.refresh_from_db()
        self.assertEqual((ride.seats_available, ride.status), (0, "FULL"))
        self.assertEqual(RideRequest.objects.get(requester=self.c).status, "REJECTED")

    def test_only_creator_can_accept(self):
        ride = mkride(self.a)
        self.login(self.b)
        self.client.post(reverse("request_join", args=[ride.id]))
        rr = RideRequest.objects.get()
        self.login(self.c)
        self.assertEqual(self.client.post(reverse("handle_request", args=[rr.id]), {"action": "accept"}).status_code, 404)

    def test_female_only_blocks_male(self):
        ride = mkride(self.f, female_only=True)
        self.login(self.b)
        self.client.post(reverse("request_join", args=[ride.id]))
        self.assertEqual(RideRequest.objects.count(), 0)

    def test_leave_restores_seat(self):
        ride = mkride(self.a, seats=1)
        self.login(self.b)
        self.client.post(reverse("request_join", args=[ride.id]))
        self.login(self.a)
        self.client.post(reverse("handle_request", args=[RideRequest.objects.get().id]), {"action": "accept"})
        self.login(self.b)
        self.client.post(reverse("leave_ride", args=[ride.id]))
        ride.refresh_from_db()
        self.assertEqual((ride.seats_available, ride.status), (1, "OPEN"))

    def test_window_filter(self):
        near, far = mkride(self.a, mins=120), mkride(self.a, mins=300)
        self.login(self.b)
        target = timezone.localtime().replace(tzinfo=None) + timedelta(minutes=140)
        resp = self.client.get(reverse("ride_feed"), {"direction": "OUTBOUND", "date": target.date().isoformat(),
                                                      "time": target.strftime("%H:%M")})
        ids = [r.id for r in resp.context["rides"]]
        self.assertIn(near.id, ids)
        self.assertNotIn(far.id, ids)
