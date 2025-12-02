import logging
from chatbot_api.models import UserRegister
from django.db import IntegrityError
from chatbot_api.services.redis_client import delete_session_date
from chatbot_api.services. metrics import registrar_evento

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("register_user")

def enviar_dados_user(chat_id: str, name: str) -> UserRegister | None:
    """
    Registra um novo usuário no sistema.
    Registra métrica de sucesso ou falha no PostgreSQL.
    """
    try:
        new_user = UserRegister. objects.create(
            username=name,
            chat_id=chat_id,
        )

        delete_session_date(chat_id)

        registrar_evento(
            cliente_id=chat_id,
            event_id=f"registro_{chat_id}",
            tipo_metrica='agendamento',
            status='success',
            detalhes=f"Novo usuário registrado: {name}"
        )
        
        logger.info(f"✅ Usuário {name} registrado com sucesso.  ID: {new_user.chat_id}")
        return new_user
        
    except IntegrityError:

        registrar_evento(
            cliente_id=chat_id,
            event_id=f"registro_{chat_id}",
            tipo_metrica='agendamento',
            status='failed',
            detalhes="Usuário com este chat_id já existe"
        )
        logger.warning(f"⚠️ Usuário com chat_id {chat_id} já existe no sistema.")
        return None
        
    except Exception as e:

        registrar_evento(
            cliente_id=chat_id,
            event_id=f"registro_{chat_id}",
            tipo_metrica='agendamento',
            status='failed',
            detalhes=f"Erro ao registrar: {str(e)}"
        )
        logger.error(f"❌ Erro ao registrar o usuário: {e}")
        return None

def is_user_registered(chat_id: str) -> bool:
    """
    Verifica de forma otimizada se o usuário existe no banco de dados.
    """
    try:
        return UserRegister.objects.filter(chat_id=chat_id). exists()
    except Exception as e:
        logger.error(f"❌ Erro ao verificar se usuário já existe: {e}")
        return False