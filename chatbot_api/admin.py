from django.contrib import admin
from .models import UserRegister # <--- APPOINTMENT REMOVIDO DA IMPORTAÇÃO

@admin.register(UserRegister)
class UserRegisterAdmin(admin.ModelAdmin):
    # Agora, você pode querer adicionar os novos campos do UserRegister aqui,
    # como 'appointment1_datetime', 'appointment2_datetime', para visualização.
    list_display = (
        'chat_id', 
        'username', 
        'appointment1_datetime', 
        'appointment2_datetime'
    )
    search_fields = ('chat_id', 'username')
    list_display_links = ('chat_id', 'username')

# O BLOCO AppointmentAdmin FOI REMOVIDO COMPLETAMENTE.