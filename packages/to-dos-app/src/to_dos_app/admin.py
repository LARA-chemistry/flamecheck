from django.contrib import admin

# Register your models here.

from .models import TodoItem, TodoList

@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'completed', 'datetime_created', 'datetime_updated')
    search_fields = ('title', 'description')
    list_filter = ('completed', 'datetime_created')

@admin.register(TodoList)
class TodoListAdmin(admin.ModelAdmin):
    list_display = ('title', 'user')
    search_fields = ('title',)
    list_filter = ('user',)
    prepopulated_fields = {'title': ('user',)}
    raw_id_fields = ('user',)
