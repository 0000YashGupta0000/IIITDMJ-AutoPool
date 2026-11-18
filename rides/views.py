from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_POST

from .forms import ReportForm, RideForm
from .models import Notification, Report, Ride, RideRequest, UserProfile
from .notify import notify

WINDOW = timedelta(minutes=45)
DELAY = timedelta(minutes=30)
EXPIRE_AFTER = timedelta(minutes=30)


def _now():
    return timezone.localtime().replace(tzinfo=None)


def _profile(user):
    return UserProfile.objects.filter(user=user).first()


def _is_female(user):
    p = _profile(user)
    return bool(p and p.gender == "F")


def _name(user):
    return user.first_name or "A student"


def _route(ride):
    return f"{ride.location} → Campus" if ride.direction == Ride.INBOUND else f"Campus → {ride.location}"


def _expire_old_rides():
    """Open rides still unfilled 30 min after departure become EXPIRED (lazy version of the PDF's cron)."""
    now = _now()
    for r in Ride.objects.filter(status=Ride.OPEN, travel_date__lte=now.date()):
        if r.departure + EXPIRE_AFTER < now:
            r.status = Ride.EXPIRED
            r.save(update_fields=["status"])
            RideRequest.objects.filter(ride=r, status=RideRequest.PENDING).update(status=RideRequest.CANCELLED)


def home(request):
    if request.user.is_authenticated:
        return redirect("ride_feed")
    return render(request, "rides/landing.html")


@login_required
def ride_feed(request):
    _expire_old_rides()
    direction = request.GET.get("direction")
    if direction not in (Ride.INBOUND, Ride.OUTBOUND):
        direction = Ride.OUTBOUND
    now = _now()
    is_female = _is_female(request.user)

    qs = Ride.objects.filter(direction=direction, status=Ride.OPEN, seats_available__gt=0,
                             travel_date__gte=now.date()).select_related("creator")
    if not is_female:
        qs = qs.exclude(female_only=True)
    elif request.GET.get("female_only"):
        qs = qs.filter(female_only=True)

    try:
        d = parse_date(request.GET.get("date") or "")
        t = parse_time(request.GET.get("time") or "")
    except ValueError:
        d = t = None
    if t and not d:
        d = now.date()

    rides = [r for r in qs if r.departure >= now]
    if d and t:
        target = datetime.combine(d, t)
        rides = [r for r in rides if abs(r.departure - target) <= WINDOW]   # the ±45 min window
    elif d:
        rides = [r for r in rides if r.travel_date == d]
    rides.sort(key=lambda r: r.departure)

    mine = dict(RideRequest.objects.filter(requester=request.user, ride__in=rides).values_list("ride_id", "status"))
    for r in rides:
        r.my_status = mine.get(r.id)
    return render(request, "rides/ride_feed.html", {"rides": rides, "is_female": is_female})


@login_required
def create_ride(request):
    if _profile(request.user) is None:
        messages.error(request, "Finish your profile first. This account has no roll number or phone.")
        return redirect("ride_feed")
    form = RideForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        ride = form.save(commit=False)
        ride.creator = request.user
        ride.save()
        messages.success(request, f"Ride #{ride.ride_no} posted. Join requests will show up under My rides.")
        return redirect("my_rides")
    return render(request, "rides/create_ride.html", {"form": form})


@require_POST
@login_required
def request_join(request, ride_id):
    ride = get_object_or_404(Ride, pk=ride_id)
    if ride.creator_id == request.user.id:
        messages.error(request, "This is your own ride.")
    elif ride.status != Ride.OPEN or ride.departure < _now():
        messages.error(request, "This ride is no longer open.")
    elif ride.seats_available < 1:
        messages.error(request, "No seats left in this auto.")
    elif ride.female_only and not _is_female(request.user):
        messages.error(request, "This auto is for female co-riders only.")
    elif _profile(request.user) is None:
        messages.error(request, "Finish your profile before requesting a ride.")
    else:
        rr, created = RideRequest.objects.get_or_create(ride=ride, requester=request.user)
        if not created and rr.status == RideRequest.CANCELLED:
            rr.status = RideRequest.PENDING
            rr.save(update_fields=["status"])
            created = True
        if created:
            notify(ride.creator, f"{_name(request.user)} wants to join your ride {_route(ride)} (#{ride.ride_no}).")
            messages.success(request, "Request sent. You'll get their WhatsApp once they accept.")
            return redirect("my_rides")
        messages.info(request, "You already have a request on this ride.")
    return redirect("ride_feed")


@require_POST
@login_required
def handle_request(request, request_id):
    action = request.POST.get("action")
    with transaction.atomic():
        rr = get_object_or_404(RideRequest, pk=request_id, ride__creator=request.user)
        ride = Ride.objects.select_for_update().get(pk=rr.ride_id)
        rr.refresh_from_db()
        name = _name(rr.requester)
        if rr.status != RideRequest.PENDING:
            messages.info(request, f"{name}'s request was already handled.")
        elif action == "accept":
            if ride.seats_available < 1 or ride.status != Ride.OPEN:
                messages.error(request, "Your auto is full or closed. Decline this request instead.")
            else:
                rr.status = RideRequest.ACCEPTED
                rr.save(update_fields=["status"])
                ride.seats_available -= 1
                if ride.seats_available == 0:
                    ride.status = Ride.FULL
                    for q in RideRequest.objects.filter(ride=ride, status=RideRequest.PENDING):
                        notify(q.requester, f"Ride #{ride.ride_no} filled up, so your request was declined.")
                    RideRequest.objects.filter(ride=ride, status=RideRequest.PENDING).update(status=RideRequest.REJECTED)
                ride.save(update_fields=["seats_available", "status"])
                notify(rr.requester, f"{_name(request.user)} accepted you on {_route(ride)}. Open My rides to message them on WhatsApp.")
                messages.success(request, f"{name} is in. Message them on WhatsApp.")
        elif action == "reject":
            rr.status = RideRequest.REJECTED
            rr.save(update_fields=["status"])
            notify(rr.requester, f"Your request for {_route(ride)} was declined.")
            messages.info(request, f"Declined {name}.")
    return redirect("my_rides")


@require_POST
@login_required
def cancel_request(request, request_id):
    rr = get_object_or_404(RideRequest, pk=request_id, requester=request.user)
    if rr.status == RideRequest.PENDING:
        rr.status = RideRequest.CANCELLED
        rr.save(update_fields=["status"])
        messages.info(request, "Request cancelled.")
    else:
        messages.error(request, "Only pending requests can be cancelled. Use Leave ride if you were accepted.")
    return redirect("my_rides")


@require_POST
@login_required
def leave_ride(request, ride_id):
    with transaction.atomic():
        ride = get_object_or_404(Ride.objects.select_for_update(), pk=ride_id)
        rr = RideRequest.objects.filter(ride=ride, requester=request.user, status=RideRequest.ACCEPTED).first()
        if not rr or not ride.is_active:
            messages.error(request, "You can't leave this ride.")
        else:
            rr.status = RideRequest.CANCELLED
            rr.save(update_fields=["status"])
            ride.seats_available += 1
            if ride.status == Ride.FULL:
                ride.status = Ride.OPEN
            ride.save(update_fields=["seats_available", "status"])
            notify(ride.creator, f"{_name(request.user)} left your ride {_route(ride)}. A seat is open again and the fare per person went up.")
            messages.info(request, "You left the ride.")
    return redirect("my_rides")


@require_POST
@login_required
def delay_ride(request, ride_id):
    ride = get_object_or_404(Ride, pk=ride_id, creator=request.user)
    if not ride.is_active:
        messages.error(request, "This ride is closed.")
        return redirect("my_rides")
    new_dt = ride.departure + DELAY
    ride.travel_date, ride.travel_time = new_dt.date(), new_dt.time()
    ride.save(update_fields=["travel_date", "travel_time"])
    label = new_dt.strftime("%I:%M %p").lstrip("0")
    for q in RideRequest.objects.filter(ride=ride, status=RideRequest.ACCEPTED).select_related("requester"):
        notify(q.requester, f"Ride {_route(ride)} was delayed. New time: {label}.")
    messages.success(request, f"Ride moved to {label}. Co-riders see the new time.")
    return redirect("my_rides")


@require_POST
@login_required
def cancel_ride(request, ride_id):
    with transaction.atomic():
        ride = get_object_or_404(Ride.objects.select_for_update(), pk=ride_id, creator=request.user)
        if not ride.is_active:
            messages.error(request, "This ride is already closed.")
        else:
            ride.status = Ride.CANCELLED
            ride.save(update_fields=["status"])
            live = RideRequest.objects.filter(ride=ride, status__in=[RideRequest.PENDING, RideRequest.ACCEPTED])
            for q in live.select_related("requester"):
                notify(q.requester, f"Ride {_route(ride)} on {ride.travel_date:%d %b} was cancelled by the creator.")
            live.filter(status=RideRequest.PENDING).update(status=RideRequest.CANCELLED)
            messages.info(request, "Ride cancelled. Co-riders were notified.")
    return redirect("my_rides")


@require_POST
@login_required
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, pk=ride_id, creator=request.user)
    if ride.is_active:
        ride.status = Ride.COMPLETED
        ride.save(update_fields=["status"])
        messages.success(request, "Ride marked as completed.")
    return redirect("my_rides")


@login_required
def report_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.id == request.user.id:
        return redirect("my_rides")
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        rep = form.save(commit=False)
        rep.reporter, rep.reported_user = request.user, target
        rid = request.GET.get("ride", "")
        rep.ride = Ride.objects.filter(pk=int(rid)).first() if rid.isdigit() else None
        rep.save()
        messages.success(request, "Report sent to the admins. Thank you for keeping the pool safe.")
        return redirect("my_rides")
    return render(request, "rides/report.html", {"form": form, "target": target})


@login_required
def my_rides(request):
    _expire_old_rides()
    notes = list(Notification.objects.filter(user=request.user)[:8])
    Notification.objects.filter(user=request.user, read=False).update(read=True)
    posted = list(Ride.objects.filter(creator=request.user, travel_date__gte=_now().date())
                  .exclude(status=Ride.EXPIRED)
                  .prefetch_related("riderequest_set__requester__userprofile")
                  .order_by("travel_date", "travel_time"))
    for r in posted:
        reqs = list(r.riderequest_set.all())
        r.pending = [q for q in reqs if q.status == RideRequest.PENDING]
        r.accepted = [q for q in reqs if q.status == RideRequest.ACCEPTED]
    joined = (RideRequest.objects.filter(requester=request.user)
              .select_related("ride__creator__userprofile").order_by("-ride__travel_date", "-ride__travel_time"))
    return render(request, "rides/my_rides.html",
                  {"posted_rides": posted, "joined_requests": joined, "notes": notes})
