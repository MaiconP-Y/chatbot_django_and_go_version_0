import os
import redis
import logging

logger = logging.getLogger("redis-lembretes")

def get_lembrete_redis_client():
    """
    Inicializa e retorna o cliente Redis para o DB 1 (lembretes).
    """
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=1,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=None,
    )

def lembrete_ja_enviado(event_id, ttl_seconds):
    """
    Verifica e registra se lembrete já foi enviado para um evento único.
    Usa SET NX, expira no TTL definido (ttl_seconds).
    
    :param event_id: identificador único do evento no calendário
    :param ttl_seconds: TTL em segundos (ex: 7200 para 2h)
    :return: True se já foi enviado, False se é o primeiro envio
    """
    r = get_lembrete_redis_client()

    enviado = r.set(f"lembrete_enviado:{event_id}", 1, nx=True, ex=ttl_seconds)
    
    if enviado is not None:
        logger.info(f"🔑 Chave de lembrete criada para {event_id} com TTL de {ttl_seconds}s ({(ttl_seconds/3600):.2f}h).")
        
    return enviado is None