#!/usr/bin/env python3
"""
Worker independente para processar fila do WhatsApp - VERSÃO COM FLUXO DO WEBHOOK FUNCIONAL
"""
import os
import json
import sys
import logging
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings')
django.setup() 

from chatbot_api.services.redis_client import (
    add_message_to_history, 
    get_recent_history,
    get_redis_client,
    check_and_set_message_id
)
from chatbot_api.services.waha_api import Waha
from chatbot_api.services.ia.ia_core import agent_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("whatsapp-worker")
QUEUE_NAME = "new_user_queue"

class WhatsAppWorker:
    def __init__(self):
        self.redis_client = None
        self.setup_connections()
        self.redis_client = get_redis_client()
        self.service_agent = agent_service()
        self.service_waha = Waha()
        
    def setup_connections(self):
        try:
            self.redis_client = get_redis_client()
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"❌ Erro na configuração do Worker: {e}")
            raise

    def process_incoming_message_data(self, raw_json_payload):
        """
        Lógica: Decodificar -> Duplicata Check -> Processar -> Re-enfileirar (se falhar).
        """
        try:
            main_data = json.loads(raw_json_payload.decode('utf-8'))
        except Exception as e:
            logger.error(f"❌ Erro ao decodificar JSON: {e}")
            return 

        try:
            message_data = main_data.get("payload", {})
            chat_id = message_data.get("from")
            message_text = message_data.get("body", "").strip()
            message_id = message_data.get("id")
            
            if not message_id:
                logger.warning("Payload sem message_id válido. Descartando (Ex: Notificação de leitura).")
                return 
            
            if not check_and_set_message_id(message_id):
                logger.warning(f"⚠️ Duplicata ID: {message_id} descartada pelo Worker (SETNX falhou).")
                return 

            if not chat_id:
                logger.warning(f"Mensagem ID: {message_id} sem chat_id válido. Descartando.")
                return

            logger.info(f"Processando nova mensagem ID: {message_id} de {chat_id}")
            add_message_to_history(chat_id, "User", message_text)
            history = get_recent_history(chat_id, limit=10)
            history_str = "\n".join(history)
            logger.info(f"{history_str}")
            response = self.service_agent.router(history_str, chat_id)

            if response == "SUCCESS_REGISTRATION":
                final_bot_response = "Cadastro realizado com sucesso! Seja bem-vindo(a). Como posso te ajudar hoje?"
                self.service_waha.send_whatsapp_message(chat_id, final_bot_response)
                return 
            
            add_message_to_history(chat_id, "Bot", response)
            self.service_waha.send_whatsapp_message(chat_id, response) 
            logger.info(f"Processamento para {chat_id} BEM-SUCEDIDO.")
            
        except Exception as e:
            logger.error(f"❌ Falha CRÍTICA no processamento para {chat_id}: {e}", exc_info=True)
            self.redis_client.rpush(QUEUE_NAME, raw_json_payload)
            logger.warning(f"♻️ Mensagem {message_id} re-enfileirada para reprocessamento.")
            raise 

    def listen_queue(self):
        queue_name = QUEUE_NAME
        logger.info(f"Worker INICIADO. Aguardando mensagens na fila persistente '{queue_name}' (BLPOP)...")

        while True:
            try:
                # Otimização: BLPOP não-bloqueante (com timeout para permitir o encerramento limpo)
                result = self.redis_client.blpop(queue_name, timeout=30) 
                
                if result:
                    raw_json_payload = result[1] 
                    logger.info(f"📨 Payload LIDO da fila persistente.")
                    self.process_incoming_message_data(raw_json_payload)

            except Exception as e:
                # Se houver erro no BLPOP (ex: desconexão do Redis), registre o erro e espere um pouco.
                logger.error(f"❌ Erro no loop de escuta (worker): {e}")
                import time; time.sleep(5) # Espera antes de tentar reconectar/re-escutar
                
    def run(self):
        logger.info("🚀 WhatsApp Worker INICIADO - Versão Corrigida")
        try:
            self.listen_queue()
        except KeyboardInterrupt:
            logger.info("⏹️ Worker interrompido pelo usuário")
        except Exception as e:
            logger.error(f"💥 Erro fatal no worker: {e}")
            raise

if __name__ == "__main__":
    worker = WhatsAppWorker()
    worker.run()