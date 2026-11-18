from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from rides.models import Ride, UserProfile

DEMO = [  # name, roll, gender, phone
    ("Aarav", "21BCS001", "M", "9876500001"),
    ("Diya", "21BEC014", "F", "9876500002"),
    ("Rohan", "22BME007", "M", "9876500003"),
    ("Meera", "22BCS031", "F", "9876500004"),
]


class Command(BaseCommand):
    help = "Create demo students and rides. Password for all: demo12345"

    def handle(self, *args, **opts):
        users = {}
        for name, roll, g, phone in DEMO:
            email = f"{name.lower()}@iiitdmj.ac.in"
            u, created = User.objects.get_or_create(username=email, defaults={"email": email, "first_name": name})
            if created:
                u.set_password("demo12345"); u.save()
                UserProfile.objects.create(user=u, roll_number=roll, phone_number=phone, gender=g)
            users[name] = u
        now = timezone.localtime().replace(tzinfo=None, second=0, microsecond=0)
        if not Ride.objects.filter(creator__in=users.values()).exists():
            def mk(who, direction, loc, mins, seats, fare, lug=False, fem=False, note=""):
                dt = now + timedelta(minutes=mins)
                Ride.objects.create(creator=users[who], direction=direction, location=loc, travel_date=dt.date(),
                                    travel_time=dt.time(), seats_available=seats, estimated_total_fare=fare,
                                    has_luggage_space=lug, female_only=fem, pickup_point="Main Gate", notes=note)
            mk("Aarav", "OUTBOUND", "Railway Station", 120, 2, 360, lug=True, note="Train 12187 at 8:40 PM, one trolley bag")
            mk("Rohan", "OUTBOUND", "Sadar", 140, 1, 300)
            mk("Diya", "OUTBOUND", "Railway Station", 150, 2, 360, fem=True)
            mk("Meera", "INBOUND", "Railway Station", 180, 2, 380, lug=True)
        self.stdout.write(self.style.SUCCESS("Demo ready. Log in as aarav@iiitdmj.ac.in / demo12345 (also diya, rohan, meera)."))
