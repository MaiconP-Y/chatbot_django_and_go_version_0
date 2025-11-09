import os
import time
import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class ChatbotApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot_api'
    
    def ready(self):
        """
        Método chamado quando o Django está totalmente inicializado.
        Inicia um thread para garantir que a sessão do WAHA esteja ativa
        e que a chave HMAC esteja configurada no CLIENTE WAHA.
        """

        # O Django precisa saber a chave HMAC para que o WAHA possa usá-la.
        # Ele não precisa saber a URL do webhook, que é configurada no Docker Compose.

        def configure_waha_session():
            from .services.waha_api import Waha
            
            waha = Waha()
            
            # A chave continua sendo WEBHOOK_HMAC_SECRET, usada tanto pelo Go quanto pelo WAHA
            hmac_key = os.environ.get("WEBHOOK_HMAC_SECRET") 
            
            if not hmac_key:
                # O ambiente do Django (django-web) precisa dessa chave, assim como o Go.
                logger.error("❌ WEBHOOK_HMAC_SECRET não encontrado. Não é possível configurar o cliente WAHA para enviar mensagens.")
                return

            max_retries = 10
            delay_seconds = 10
            time.sleep(delay_seconds)            
            # O nome da função deve refletir que ela está ativando o WAHA, 
            # não necessariamente configurando a URL do webhook (que agora é via Docker).
            logger.info(f"⏳ Tentando ATIVAR e configurar HMAC do WAHA (máx. {max_retries}x)")

            for attempt in range(1, max_retries + 1):
                # O nome da função está bom, mas é vital que o Waha.start_session_with_hmac
                # apenas garanta que a chave HMAC está definida no cliente WAHA, e tente 
                # subir a sessão (start session), se ainda não estiver ativa.
                success = waha.start_session_with_hmac(hmac_key)
                
                if success:
                    logger.info("✅ Ativação da sessão e configuração HMAC do WAHA concluídas com sucesso.")
                    return
                else:
                    logger.warning(f" Tentativa {attempt}/{max_retries} falhou. Aguardando {delay_seconds}s...")
                    time.sleep(delay_seconds)
            
            logger.error("❌ Falha crítica: Não foi possível configurar a sessão do WAHA após todas as tentativas.")

        # Inicia a função de configuração em um novo thread
        # Esta é a melhor prática para não travar a inicialização do Django.
        threading.Thread(target=configure_waha_session, daemon=True).start()