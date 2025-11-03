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
        Inicia um thread para configurar o WAHA com HMAC.
        """

        def configure_waha_session():
            from .services.waha_api import Waha
            
            waha = Waha()
            hmac_key = os.environ.get("WEBHOOK_HMAC_SECRET")
            
            if not hmac_key:
                logger.error("❌ WEBHOOK_HMAC_SECRET não encontrado. Não é possível configurar o WAHA.")
                return

            max_retries = 10
            delay_seconds = 8
            
            logger.info(f"⏳ Tentando configurar WAHA com HMAC (máx. {max_retries}x)")

            for attempt in range(1, max_retries + 1):
                success = waha.start_session_with_hmac(hmac_key)
                
                if success:
                    logger.info("✅ Configuração HMAC do WAHA concluída com sucesso.")
                    return
                else:
                    logger.warning(f" Tentativa {attempt}/{max_retries} falhou. Aguardando {delay_seconds}s...")
                    time.sleep(delay_seconds)
            
            logger.error("❌ Falha crítica: Não foi possível configurar a sessão do WAHA após todas as tentativas.")

        # Inicia a função de configuração em um novo thread
        threading.Thread(target=configure_waha_session, daemon=True).start()