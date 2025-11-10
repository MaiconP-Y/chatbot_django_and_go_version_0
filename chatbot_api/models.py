from django.db import models

class UserRegister(models.Model):
    username = models.CharField(max_length=100)
    chat_id = models.CharField(max_length=30, unique=True)
    consultas_marcadas = models.JSONField(blank=True, default=list)

    def __str__(self):
        return self.chat_id
