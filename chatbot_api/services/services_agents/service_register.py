from chatbot_api.models import UserRegister
from django.db import IntegrityError
from chatbot_api.services.redis_client import delete_session_date
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("register_user")

def enviar_dados_user(chat_id: str, name: str) -> UserRegister | None:
    try:
        new_user = UserRegister.objects.create(
            username=name,
            chat_id=chat_id,
        )
        delete_session_date(chat_id)
        logger.info(f"Usuário {name} registrado com sucesso. ID: {new_user.chat_id}")
        if new_user:
            return "SUCCESS_REGISTRATION" 
        
    except IntegrityError:
        print(f"⚠️ Usuário com chat_id {chat_id} já existe no sistema.")
        return None
    except Exception as e:
        print(f"❌ Erro ao registrar o usuário: {e}")
        return None

def is_user_registered(chat_id: str) -> bool:
    """Verifica de forma performática se o usuário existe no banco de dados."""
    try:
        return UserRegister.objects.filter(chat_id=chat_id).exists()
    except Exception as e:
        print(f"❌ Erro ao verificar se usuário já existe: {e}")
        return False 