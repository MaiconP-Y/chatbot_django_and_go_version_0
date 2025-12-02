import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone as django_timezone

from chatbot_api.models import LogMetrica

logger = logging.getLogger("metrics-service")

# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL: Registrar Evento
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_evento(
    cliente_id: str,
    event_id: str,
    tipo_metrica: str,
    status: str = 'success',
    detalhes: str = '',
) -> Dict[str, Any]:
    """
    Registra um evento de métrica no PostgreSQL (ÚNICA fonte de verdade).
    
    Função UNIFICADA com transação atômica para garantir integridade dos dados.
    
    :param cliente_id: ID do cliente (telefone ou UUID)
    :param event_id: ID do evento no calendário
    :param tipo_metrica: 'agendamento', 'cancelamento', 'lembrete'
    :param status: 'success', 'failed', 'pending'
    :param detalhes: Informações adicionais
    :return: Dict com status e informações do evento registrado
    """
    
    try:
        with transaction.atomic():
            log_metrica = LogMetrica.registrar_evento(
                cliente_id=cliente_id,
                event_id=event_id,
                tipo_metrica=tipo_metrica,
                status=status,
                detalhes=detalhes,
            )
        
        logger.info(
            f"✅ Evento registrado com sucesso | "
            f"Cliente: {cliente_id} | Tipo: {tipo_metrica} | Status: {status}"
        )
        
        return {
            'status': 'success',
            'log_id': str(log_metrica.id),
            'cliente_id': cliente_id,
            'event_id': event_id,
            'tipo_metrica': tipo_metrica,
            'timestamp': log_metrica.criado_em. isoformat(),
        }
    
    except Exception as e:
        logger.error(
            f"❌ Erro ao registrar evento: {e} | "
            f"Cliente: {cliente_id} | Event: {event_id}",
            exc_info=True
        )
        
        return {
            'status': 'error',
            'cliente_id': cliente_id,
            'event_id': event_id,
            'tipo_metrica': tipo_metrica,
            'error': str(e),
        }

# ═══════════════════════════════════════════════════════════════════════════════
# CONSULTAS: Totais Diários
# ═══════════════════════════════════════════════════════════════════════════════

def get_total_dia(tipo_metrica: str, date: Optional[str] = None) -> int:
    """
    Retorna o total agregado de uma métrica em um dia específico.
    
    Apenas eventos com status='success' são contabilizados.
    
    :param tipo_metrica: 'agendamento', 'cancelamento', 'lembrete'
    :param date: Data no formato YYYY-MM-DD (padrão: hoje)
    :return: Valor inteiro
    """
    
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    try:
        data_obj = datetime.strptime(date, "%Y-%m-%d"). date()

        total = LogMetrica.objects.filter(
            tipo_metrica=tipo_metrica,
            status='success',
            criado_em__date=data_obj,
        ).count()
        
        logger.debug(f"🔍 Query: {tipo_metrica} ({date}) = {total}")
        return total
    
    except Exception as e:
        logger.error(f"❌ Erro ao consultar total: {e}")
        return 0

def get_total_cliente_dia(cliente_id: str, tipo_metrica: str, date: Optional[str] = None) -> int:
    """
    Retorna o total de uma métrica para um cliente específico em um dia. 
    
    Apenas eventos com status='success' são contabilizados.
    
    :param cliente_id: ID do cliente
    :param tipo_metrica: 'agendamento', 'cancelamento', 'lembrete'
    :param date: Data no formato YYYY-MM-DD (padrão: hoje)
    :return: Valor inteiro
    """
    
    if date is None:
        date = datetime.now(timezone.utc). strftime("%Y-%m-%d")
    
    try:
        data_obj = datetime.strptime(date, "%Y-%m-%d").date()
        
        total = LogMetrica.objects.filter(
            cliente_id=cliente_id,
            tipo_metrica=tipo_metrica,
            status='success',
            criado_em__date=data_obj,
        ).count()
        
        logger.debug(f"🔍 Query: Cliente {cliente_id} | {tipo_metrica} ({date}) = {total}")
        return total
    
    except Exception as e:
        logger.error(f"❌ Erro ao consultar total do cliente: {e}")
        return 0

# ═══════════════════════════════════════════════════════════════════════════════
# CONSULTAS: Resumos
# ═══════════════════════════════════════════════════════════════════════════════

def get_resumo_dia(date: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna um resumo COMPLETO de todas as métricas de um dia.
    
    :param date: Data no formato YYYY-MM-DD (padrão: hoje)
    :return: Dict com {data, agendamentos, cancelamentos, lembretes}
    """
    
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    return {
        'data': date,
        'agendamentos': get_total_dia('agendamento', date),
        'cancelamentos': get_total_dia('cancelamento', date),
        'lembretes': get_total_dia('lembrete', date),
    }

def get_resumo_cliente_dia(cliente_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna um resumo COMPLETO de todas as métricas de um cliente em um dia.
    
    :param cliente_id: ID do cliente
    :param date: Data no formato YYYY-MM-DD (padrão: hoje)
    :return: Dict com {cliente_id, data, agendamentos, cancelamentos, lembretes}
    """
    
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    return {
        'cliente_id': cliente_id,
        'data': date,
        'agendamentos': get_total_cliente_dia(cliente_id, 'agendamento', date),
        'cancelamentos': get_total_cliente_dia(cliente_id, 'cancelamento', date),
        'lembretes': get_total_cliente_dia(cliente_id, 'lembrete', date),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# CONSULTAS: Histórico e Auditoria
# ═══════════════════════════════════════════════════════════════════════════════

def get_historico_cliente(
    cliente_id: str,
    limite_dias: int = 30,
    tipo_filtro: Optional[str] = None,
    status_filtro: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna o histórico completo de um cliente (últimos N dias).
    
    :param cliente_id: ID do cliente
    :param limite_dias: Número de dias a retroceder (padrão: 30)
    :param tipo_filtro: Filtrar por tipo ('agendamento', 'cancelamento', 'lembrete')
    :param status_filtro: Filtrar por status ('success', 'failed')
    :return: Lista de dicts com logs detalhados
    """
    
    try:
        data_limite = datetime.now(timezone.utc) - timedelta(days=limite_dias)
        
        queryset = LogMetrica.objects. filter(
            cliente_id=cliente_id,
            criado_em__gte=data_limite,
        ). order_by('-criado_em')
        
        if tipo_filtro:
            queryset = queryset.filter(tipo_metrica=tipo_filtro)
        
        if status_filtro:
            queryset = queryset.filter(status=status_filtro)
        
        return [
            {
                'id': str(log.id),
                'cliente_id': log.cliente_id,
                'event_id': log.event_id,
                'tipo_metrica': log.get_tipo_metrica_display(),
                'status': log.status,
                'detalhes': log.detalhes,
                'criado_em': log.criado_em.isoformat(),
            }
            for log in queryset
        ]
    
    except Exception as e:
        logger.error(f"❌ Erro ao consultar histórico: {e}")
        return []

def get_log_evento(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Retorna o log detalhado de um evento específico. 
    
    :param event_id: ID do evento
    :return: Dict com dados do evento ou None
    """
    
    try:
        log = LogMetrica. objects.filter(event_id=event_id).first()
        
        if not log:
            return None
        
        return {
            'id': str(log. id),
            'cliente_id': log.cliente_id,
            'event_id': log.event_id,
            'tipo_metrica': log.get_tipo_metrica_display(),
            'status': log.status,
            'detalhes': log.detalhes,
            'criado_em': log.criado_em.isoformat(),
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao consultar evento: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# CONSULTAS: Relatórios Agregados
# ═══════════════════════════════════════════════════════════════════════════════

def get_estatisticas_diarias(data_inicio: str, data_fim: str) -> Dict[str, Any]:
    """
    Retorna estatísticas agregadas entre duas datas.
    
    Ideal para relatórios mensal/semanal.
    
    :param data_inicio: Data no formato YYYY-MM-DD
    :param data_fim: Data no formato YYYY-MM-DD
    :return: Dict com agregações por tipo e status
    """
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d"). date()
        data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
        
        queryset = LogMetrica.objects. filter(
            criado_em__date__gte=data_inicio_obj,
            criado_em__date__lte=data_fim_obj,
        )
        
        stats = queryset.values('tipo_metrica', 'status').annotate(
            count=Count('id')
        ).order_by('tipo_metrica', 'status')
        
        por_tipo = queryset.filter(status='success').values('tipo_metrica').annotate(
            count=Count('id')
        ).order_by('tipo_metrica')
        
        return {
            'periodo': {
                'inicio': data_inicio,
                'fim': data_fim,
            },
            'total_eventos': queryset.count(),
            'total_sucesso': queryset.filter(status='success').count(),
            'total_falhas': queryset.filter(status='failed').count(),
            'por_tipo_status': list(stats),
            'por_tipo_sucesso': list(por_tipo),
        }
    
    except Exception as e:
        logger. error(f"❌ Erro ao consultar estatísticas: {e}")
        return {}

def get_resumo_cliente_periodo(cliente_id: str, data_inicio: str, data_fim: str) -> Dict[str, Any]:
    """
    Retorna resumo de um cliente em um período específico.
    
    :param cliente_id: ID do cliente
    :param data_inicio: Data no formato YYYY-MM-DD
    :param data_fim: Data no formato YYYY-MM-DD
    :return: Dict com agregações do cliente
    """
    
    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
        
        queryset = LogMetrica.objects.filter(
            cliente_id=cliente_id,
            criado_em__date__gte=data_inicio_obj,
            criado_em__date__lte=data_fim_obj,
            status='success',
        )
        
        por_tipo = queryset.values('tipo_metrica').annotate(
            count=Count('id')
        ).order_by('tipo_metrica')
        
        return {
            'cliente_id': cliente_id,
            'periodo': {
                'inicio': data_inicio,
                'fim': data_fim,
            },
            'total_eventos': queryset.count(),
            'por_tipo': {item['tipo_metrica']: item['count'] for item in por_tipo},
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao consultar resumo do cliente: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# LIMPEZA: Função para Remover Dados Antigos (Opcional)
# ═══════════════════════════════════════════════════════════════════════════════

def limpar_dados_antigos(dias_retencao: int = 90) -> Dict[str, int]:
    """
    Remove registros de métricas com mais de N dias.
    
    ⚠️ Use com cuidado!  Dados deletados NÃO podem ser recuperados. 
    
    :param dias_retencao: Número de dias a manter (padrão: 90)
    :return: Dict com número de registros deletados
    """
    
    try:
        data_limite = datetime.now(timezone.utc) - timedelta(days=dias_retencao)
        
        deleted_count, _ = LogMetrica.objects. filter(
            criado_em__lt=data_limite
        ).delete()
        
        logger.warning(f"🗑️ {deleted_count} registros antigos foram deletados")
        
        return {
            'status': 'success',
            'deletados': deleted_count,
            'data_limite': data_limite.isoformat(),
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao limpar dados: {e}")
        return {'status': 'error', 'error': str(e)}