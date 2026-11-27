from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import NameForm, ProfileForm, SignupForm
from .models import StudentProfile


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("profile")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    student, _ = StudentProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        name_form = NameForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, instance=student)
        if name_form.is_valid() and profile_form.is_valid():
            name_form.save()
            profile_form.save()
            messages.success(request, "Profil gespeichert.")
            return redirect("profile")
    else:
        name_form = NameForm(instance=request.user)
        profile_form = ProfileForm(instance=student)
    return render(request, "accounts/profile.html", {"name_form": name_form, "profile_form": profile_form})
