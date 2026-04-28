from django.contrib.auth import login, logout
from django.shortcuts import redirect, render

from auth.backends import DjangoAuthBackend

backend = DjangoAuthBackend()


def get_safe_redirect_url(next_url: str | None) -> str:
    if not next_url or not isinstance(next_url, str):
        return "/"
    next_url = next_url.strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = backend.authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            redirect_to = get_safe_redirect_url(request.GET.get("next"))
            return redirect(redirect_to)
        else:
            return render(request, "auth/login.html", {"error": "Invalid credentials"})
    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")
