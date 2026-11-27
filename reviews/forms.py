from django import forms

from .models import Review

STAR_CHOICES = [(n, f"{n} Stern{'e' if n > 1 else ''}") for n in range(1, 6)]


class ReviewForm(forms.ModelForm):
    stars = forms.TypedChoiceField(label="Sterne", choices=STAR_CHOICES, coerce=int, widget=forms.RadioSelect)

    class Meta:
        model = Review
        fields = ["stars", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "maxlength": 500})}
        labels = {"text": "Wie war es bei der Firma?"}
