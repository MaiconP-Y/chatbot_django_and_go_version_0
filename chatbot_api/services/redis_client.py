import redis
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

_redis_client = None 

def get_redis_client():
    """
    Inicializa e retorna o cliente Redis de forma lazy (sob demanda) e segura.
    Implementa o padrão Singleton: cria a conexão apenas uma vez por processo.
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST, 
            port=settings.REDIS_PORT, 
            db=settings.REDIS_DB,
            decode_responses=False, 
            socket_connect_timeout=5, 
            socket_timeout=None,
        )
        _redis_client.ping()
        logger.info("Conexão com Redis estabelecida com sucesso via get_redis_client!")
        return _redis_client
        
    except Exception as e:
        _redis_client = None
        logger.error(f"Erro CRÍTICO ao conectar ao Redis: {e}", exc_info=True)
        raise ConnectionError(f"Falha na inicialização do cliente Redis: {e}") 

# --- Funções de Histórico (Todas devem usar get_redis_client()) ---

def get_history_key(chat_id: str) -> str:
    return f"history:{chat_id}"

TTL_TWO_HOURS = 7200

def add_message_to_history(chat_id: str, sender: str, message: str) -> int:
    """
    Adiciona uma mensagem ao histórico do usuário (Bot ou User) 
    e renova o TTL para 2 horas (7200s).
    """
    r = get_redis_client()
    history_key = get_history_key(chat_id)
    message_entry = f"[{sender}]: {message}"
    
    # 1. Adiciona a mensagem à lista (LPUSH) e ARMAZENA o resultado (o novo tamanho)
    new_size = r.lpush(history_key, message_entry)
    
    # 2. Define/Renova o TTL para 2 horas
    r.expire(history_key, TTL_TWO_HOURS)
    
    logger.info(f"⏰ TTL do histórico de {chat_id} renovado para 2 horas.")
    
    # 3. Retorna o novo tamanho da lista, mantendo a assinatura original da função
    return new_size

def get_recent_history(chat_id: str, limit: int = 10) -> list:
    """Retorna as N mensagens mais recentes do histórico."""
    r = get_redis_client() # Assume que r agora entrega BYTES
    history = r.lrange(get_history_key(chat_id), 0, limit - 1)
    
    # DECODIFICAR AQUI ANTES DE RETORNAR!
    decoded_history = [item.decode('utf-8') for item in history]
    
    return decoded_history[::-1] # Retorna strings

def get_full_history(chat_id: str) -> list:
    """Retorna todo o histórico de mensagens (mais recente primeiro)"""
    r = get_redis_client()
    history = r.lrange(get_history_key(chat_id), 0, -1)
    return history[::-1]

# --- Funções de Estado de Sessão (Todas devem usar get_redis_client()) ---

def get_session_key(chat_id: str) -> str:
    return f"session:{chat_id}"

def get_session_state(chat_id: str) -> dict:
    """Recupera os dados de estado da sessão do usuário."""
    r = get_redis_client() # <<< OBTÉM A CONEXÃO AQUI
    state = r.hgetall(get_session_key(chat_id))
    return state

def update_session_state(chat_id: str, **kwargs):
    """Atualiza estado da sessão"""
    r = get_redis_client()
    session_key = f"session:{chat_id}"
    
    for field, value in kwargs.items():
        r.hset(session_key, field, str(value))
    
    logger.info(f"Estado atualizado: {chat_id} -> {kwargs}")

def set_session_ttl(chat_id: str, ttl_seconds: int = 3600):
    """Define TTL (Time To Live) para a sessão (padrão: 1 hora)"""
    r = get_redis_client()
    r.expire(get_session_key(chat_id), ttl_seconds)
    logger.info(f"⏰ TTL de {ttl_seconds}s definido para sessão de {chat_id}")

def check_and_set_message_id(message_id: str) -> bool:
    """
    Verifica se o ID da mensagem já foi processado.
    Se não, armazena o ID e retorna True. O ID expira em 60 segundos (TTL).

    :param message_id: O ID único da mensagem.
    :return: True se a mensagem é NOVA, False se for DUPLICADA.
    """
    r = get_redis_client()
    key = f"processed_msg:{message_id}"
    is_new = r.set(key, 1, ex=60, nx=True)
    return is_new is not None # Se for 'None', é porque já existia (duplicado)

#FINALIZAÇÃO:
def delete_session_state(chat_id: str):
    """Remove o estado de sessão temporário do usuário."""
    r = get_redis_client()
    r.delete(get_session_key(chat_id))
    logger.info(f"🗑️ Estado de sessão DELETADO para {chat_id}.")

def delete_history(chat_id: str):
    """Remove todo o histórico de conversas do usuário."""
    r = get_redis_client()
    r.delete(get_history_key(chat_id))
    logger.info(f"🗑️ Histórico de conversas DELETADO para {chat_id}.")

def delete_session_date(chat_id: str) -> bool:
    """Remove o estado de sessão temporário e o histórico do usuário."""
    r = get_redis_client()
    
    # Exclui tanto o estado quanto o histórico (melhor otimização com um único .delete)
    keys_deleted = r.delete(get_session_key(chat_id), get_history_key(chat_id))
    
    # ✅ BOA PRÁTICA: Retorna True se a operação foi um sucesso (pelo menos uma chave deletada)
    return keys_deleted > 0