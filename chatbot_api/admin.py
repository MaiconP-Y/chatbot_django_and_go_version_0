from django.contrib import admin
from .models import UserRegister, LogMetrica # <--- APPOINTMENT REMOVIDO DA IMPORTAÇÃO

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

@admin.register(LogMetrica)
class LogMetricaAdmin(admin.ModelAdmin):
    # Campos que aparecerão diretamente como colunas na lista de objetos
    list_display = (
        'criado_em', 
        'tipo_metrica', 
        'status', 
        'cliente_id', 
        'event_id',
        'detalhes', # Adicionando detalhes para ter a visão completa
    )
    
    # Filtros laterais para navegar pelos dados (muito útil)
    list_filter = (
        'tipo_metrica', 
        'status', 
        'criado_em' # Permite filtrar por data
    )
    
    # Permite buscar pelo cliente ou evento
    search_fields = (
        'cliente_id', 
        'event_id', 
        'detalhes'
    )
    
    # Ordem padrão (do mais novo para o mais antigo)
    ordering = ('-criado_em',)
    
    # Impede a edição/criação direta, pois é uma tabela de auditoria
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False