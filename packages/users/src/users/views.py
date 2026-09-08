from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView, UpdateView

from users.models import User


class UserCreateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Profile successfully created")
    template_name = "users/create_form.html"

    def get_success_url(self) -> str:
        """
        Returns the URL to redirect to after the form is successfully submitted.

        This method assumes that the user is authenticated.
        """
        from django.core.exceptions import PermissionDenied
        if not self.request.user.is_authenticated:
            raise PermissionDenied("User must be authenticated.")
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        """Return the current authenticated user for profile onboarding."""
        assert self.request.user.is_authenticated  # type guard
        return self.request.user

    def form_valid(self, form):
        """If the form is valid, save the associated user instance."""
        form.instance.user = self.request.user
        return super().form_valid(form)


class UserDetailView(LoginRequiredMixin, DetailView):
    """View to display user details."""

    model = User
    # should be removed, if e-mail login is used
    # slug_field = "username"
    # slug_url_kwarg = "username"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """View to update user information."""

    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"username": self.request.user.username})


user_redirect_view = UserRedirectView.as_view()


class UserProfileView(SuccessMessageMixin, UpdateView):
    model = User
    fields = ["entity", "username",  "first_name", "last_name", "email" ]
    success_message = _("Information successfully updated")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section_title'] = "LaraUser - Profile - Update"
        context['update_link'] = 'lara_django_people:lara-user-update'

        return context

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user

user_profile_view = UserProfileView.as_view()