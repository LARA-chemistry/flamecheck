from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    RedirectView,
    UpdateView,
)

from . import views
from .models import TodoItem, TodoList

# Create your views here.


class TodoListView(ListView):
    model = TodoList
    template_name = "to_dos_app/list.html"
    context_object_name = "todo_lists"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_link'] = 'to_dos_app:to-dos-list-create'
        return context

    def get_queryset(self):
        return TodoList.objects.filter(user=self.request.user)

class TodoListCreateView(SuccessMessageMixin, CreateView):
    model = TodoList
    template_name = "to_dos_app/todo_list_form.html"
    fields = ["title"]
    success_message = _("Todo list created successfully.")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class TodoItemListView(ListView):
    model = TodoItem
    template_name = "to_dos_app/todo_item_list.html"
    context_object_name = "todo_items"

    def get_queryset(self):
        todo_list_id = self.kwargs.get("todo_list_id")
        return TodoItem.objects.filter(
            todo_list_id=todo_list_id, todo_list__user=self.request.user
        )

# CRUD Views for TodoItem
class TodoItemCreateView(SuccessMessageMixin, CreateView):
    model = TodoItem
    template_name = "to_dos_app/todo_item_form.html"
    fields = ["title", "description", "completed", "todo_list"]
    success_message = _("Todo item created successfully.")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class TodoItemUpdateView(SuccessMessageMixin, UpdateView):
    model = TodoItem
    template_name = "to_dos_app/todo_item_form.html"
    fields = ["title", "description", "completed"]
    success_message = _("Todo item updated successfully.")

    def get_queryset(self):
        return TodoItem.objects.filter(todo_list__user=self.request.user)


class TodoItemDeleteView(SuccessMessageMixin, DeleteView):
    model = TodoItem
    template_name = "to_dos_app/todo_item_confirm_delete.html"
    success_message = _("Todo item deleted successfully.")

    def get_queryset(self):
        return TodoItem.objects.filter(todo_list__user=self.request.user)

