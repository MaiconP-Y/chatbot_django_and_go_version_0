from django.contrib import admin
from .models import UserRegister

@admin.register(UserRegister)
class UserRegisterAdmin(admin.ModelAdmin):
    list_display = ('chat_id', 'username')
    search_fields = ('chat_id', 'username')
    list_display_links = ('chat_id', 'username')
