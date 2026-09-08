from django.urls import path

from . import views

app_name = "users"
urlpatterns = [
    path("onboarding/", view=views.UserCreateView.as_view(), name="profile-onboarding"),
    path("~redirect/", view=views.user_redirect_view, name="redirect"),
    path("~update/", view=views.user_update_view, name="update"),
    # path("<str:username>/", view=views.user_detail_view, name="detail"),
    path("update/<int:pk>/", view=views.user_update_view, name="update"),
]
