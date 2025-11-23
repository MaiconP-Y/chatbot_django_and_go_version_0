from django.db import models

# --- MODELO PRINCIPAL: IDENTIDADE DO CLIENTE E AGENDAMENTOS (Slots Fixos) ---
class UserRegister(models.Model):
    """
    Armazena a identidade principal do usuário e os dados de até 2 agendamentos.
    Os agendamentos são armazenados em um único campo DateTimeField para otimização.
    """
    username = models.CharField(max_length=100)
    chat_id = models.CharField(max_length=30, unique=True)
    
    # ----------------------------------------------------
    # --- SLOT 1: PRIMEIRA CONSULTA ---
    # ----------------------------------------------------
    appointment1_datetime = models.DateTimeField(null=True, blank=True, verbose_name="Data/Hora 1ª Consulta")
    appointment1_gcal_id = models.CharField(max_length=255, null=True, blank=True, unique=True, verbose_name="ID Google Calendar 1")

    # ----------------------------------------------------
    # --- SLOT 2: SEGUNDA CONSULTA ---
    # ----------------------------------------------------
    appointment2_datetime = models.DateTimeField(null=True, blank=True, verbose_name="Data/Hora 2ª Consulta")
    appointment2_gcal_id = models.CharField(max_length=255, null=True, blank=True, unique=True, verbose_name="ID Google Calendar 2")

    def __str__(self):
        return self.chat_id