from django.urls import path

from . import views

# Add your {{ django_app }} urls here.


# !! this sets the apps namespace to be used in the template
app_name = "to_dos_app"

urlpatterns = [
    path("to-dos/list/", views.TodoListView.as_view(), name="to-dos-list"),
    path("to-dos/list/create/", views.TodoListCreateView.as_view(), name="to-dos-list-create"),
    # path("to-dos/create/", views.TodoCreateView.as_view(), name="to-dos-create"),
    # path("to-dos/update/<uuid:pk>", views.TodoUpdateView.as_view(), name="to-dos-update"),
    # path("to-dos/delete/<uuid:pk>", views.TodoDeleteView.as_view(), name="to-dos-delete"),
    # path("to-dos/<uuid:pk>/", views.TodoDetailView.as_view(), name="to-dos-detail"),
    path("", views.TodoListView.as_view(), name="to-dos-root"),
]
