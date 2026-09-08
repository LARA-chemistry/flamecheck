# This is a Django model file for the To-Do application.
# It defines the data structure for the To-Do items in the application.
# The model includes fields for the title, description, and completion status of each To-Do item.
# We also define multiple to-dos lists for each user.

from django.conf import settings
from django.db import models


class TodoList(models.Model):
    title = models.CharField(max_length=100, help_text="Title of the to-dos list")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

class TodoItem(models.Model):
    title = models.CharField(max_length=100, help_text="Title of the to-do item")
    description = models.TextField(help_text="Detailed description of the to-do item")
    completed = models.BooleanField(default=False, help_text="Indicates whether the to-do item is completed")
    datetime_created = models.DateTimeField(auto_now_add=True, help_text="The date and time when the to-do item was created")
    datetime_updated = models.DateTimeField(auto_now=True, help_text="The date and time when the to-do item was last updated")
    todo_list = models.ForeignKey(TodoList, related_name="items", on_delete=models.CASCADE, help_text="The to-do list this item belongs to")


