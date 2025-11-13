from chatbot_api.models import UserRegister
from django.db import IntegrityError

def enviar_dados_user(chat_id: str, name: str) -> UserRegister | None:
    try:
        new_user = UserRegister.objects.create(
            username=name,
            chat_id=chat_id,
        )
        print(f"✅ Usuário {name} registrado com sucesso. ID: {new_user.chat_id}")
        return new_user
        
    except IntegrityError:
        print(f"⚠️ Usuário com chat_id {chat_id} já existe no sistema.")
        return None
    except Exception as e:
        print(f"❌ Erro ao registrar o usuário: {e}")
        return None