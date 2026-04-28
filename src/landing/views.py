from django.shortcuts import redirect
from django.views import View
from django.shortcuts import render


class LandingView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("/checks/")
        return render(request, "landing/landing.html")
