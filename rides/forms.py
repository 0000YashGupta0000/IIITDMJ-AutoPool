from datetime import date

from django import forms

from .models import Report, Ride

PLACES = [(p, p) for p in ["Railway Station", "Madan Mahal Station", "Sadar", "Civic Center", "Russell Chowk", "Dumna Airport", "Other"]]
PICKUPS = [(p, p) for p in ["Main Gate", "Hall-1 / Hall-3 Circle", "Hall-4 Gate", "Nescafe Point", "Railway Station Platform 1", "Madan Mahal Platform 1"]]


class RideForm(forms.ModelForm):
    direction = forms.ChoiceField(choices=[("INBOUND", "To campus"), ("OUTBOUND", "From campus")],
                                  widget=forms.RadioSelect, initial="OUTBOUND")
    location = forms.ChoiceField(choices=PLACES, label="City point")
    pickup_point = forms.ChoiceField(choices=PICKUPS, label="Meeting point")
    seats_available = forms.TypedChoiceField(
        choices=[(1, "1 seat"), (2, "2 seats")], coerce=int, initial=2, label="Seats open for others",
        help_text="You take the third seat.")

    class Meta:
        model = Ride
        fields = ["direction", "location", "pickup_point", "travel_date", "travel_time", "seats_available",
                  "has_luggage_space", "female_only", "estimated_total_fare", "notes"]
        widgets = {
            "travel_date": forms.DateInput(attrs={"type": "date"}),
            "travel_time": forms.TimeInput(attrs={"type": "time"}),
            "estimated_total_fare": forms.NumberInput(attrs={"min": 50, "max": 2000, "step": 10, "inputmode": "numeric"}),
            "notes": forms.Textarea(attrs={"rows": 2, "maxlength": 200, "placeholder": "Optional: e.g. Train 12187, arriving 6:10 PM"}),
        }
        labels = {"has_luggage_space": "Room for trolley bags", "female_only": "Female co-riders only",
                  "estimated_total_fare": "Total fare for the auto (₹)", "notes": "Notes for co-riders"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["travel_date"].widget.attrs["min"] = date.today().isoformat()

    def clean_travel_date(self):
        d = self.cleaned_data["travel_date"]
        if d < date.today():
            raise forms.ValidationError("That date has passed.")
        return d

    def clean_estimated_total_fare(self):
        f = self.cleaned_data["estimated_total_fare"]
        if not 1 <= f <= 2000:
            raise forms.ValidationError("Enter a fare between ₹1 and ₹2000.")
        return f

    def clean(self):
        data = super().clean()
        if data.get("female_only") and self.user is not None:
            if getattr(self.user.userprofile, "gender", None) != "F":
                self.add_error("female_only", "Only female riders can post a female-only auto.")
        return data


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4, "maxlength": 500, "placeholder": "What happened? (optional)"})}
