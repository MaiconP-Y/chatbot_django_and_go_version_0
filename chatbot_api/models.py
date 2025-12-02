from django.db import models

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
    
from uuid import uuid4

class LogMetrica(models.Model):
    """
    Tabela de auditoria e contadores para logs detalhados de eventos de métrica. 
    PostgreSQL é a ÚNICA fonte de verdade. 
    """
    
    TIPO_CHOICES = [
        ('agendamento', 'Agendamento'),
        ('cancelamento', 'Cancelamento'),
        ('lembrete', 'Lembrete Enviado'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Sucesso'),
        ('failed', 'Falha'),
        ('pending', 'Pendente'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    cliente_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="ID do cliente (telefone ou UUID)"
    )
    event_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="ID do evento no calendário"
    )
    
    tipo_metrica = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        db_index=True
    )
    status = models. CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='success'
    )
    
    detalhes = models.TextField(
        blank=True,
        help_text="Informações adicionais do evento"
    )
    
    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'logs_metricas'
        verbose_name = 'Log de Métrica'
        verbose_name_plural = 'Logs de Métricas'
        indexes = [
            models.Index(fields=['cliente_id', 'criado_em']),
            models.Index(fields=['tipo_metrica', 'criado_em']),
            models.Index(fields=['event_id']),
            models.Index(fields=['criado_em']),
        ]
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.get_tipo_metrica_display()} - {self.cliente_id} - {self.status}"
    
    @classmethod
    def registrar_evento(cls, cliente_id: str, event_id: str, tipo_metrica: str, status: str = 'success', detalhes: str = ''):
        """
        Cria um novo log de métrica no PostgreSQL.
        
        :param cliente_id: ID do cliente
        :param event_id: ID do evento
        :param tipo_metrica: 'agendamento', 'cancelamento', 'lembrete'
        :param status: 'success', 'failed', 'pending'
        :param detalhes: Informações adicionais
        :return: Instância criada
        """
        return cls.objects.create(
            cliente_id=cliente_id,
            event_id=event_id,
            tipo_metrica=tipo_metrica,
            status=status,
            detalhes=detalhes,
        )