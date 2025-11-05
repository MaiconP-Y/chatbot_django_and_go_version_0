#!/usr/bin/env python3
"""
Worker independente para processar fila do WhatsApp - VERSÃO COM FLUXO DO WEBHOOK FUNCIONAL
"""
import os
import json
import sys
import logging
import django

# Configura Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings')
django.setup() 

from chatbot_api.services.redis_client import (
    get_session_state,
    update_session_state,
    add_message_to_history, 
    get_recent_history,
    publish_new_user, 
    enqueue_user, 
    is_user_in_queue,
    get_redis_client,
    check_and_set_message_id
)
from chatbot_api.services.waha_api import Waha
from chatbot_api.services.ia_service import agent_register

waha_api = Waha()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("whatsapp-worker")

class WhatsAppWorker:
    def __init__(self):
        self.redis_client = None
        self.setup_connections()
        self.redis_client = get_redis_client()
        self.agent_register = agent_register()
        
    def setup_connections(self):
        # ... (manter inalterado) ...
        try:
            self.redis_client = get_redis_client()
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"❌ Erro na configuração do Worker: {e}")
            raise

    def process_user_message(self, chat_id: str):
        """Processa a mensagem do usuário com a IA."""
        try:
            history = get_recent_history(chat_id, limit=10)
            response = self.generate_response(chat_id, history)
            waha_api.send_whatsapp_message(chat_id, response)
            logger.info(f"Resposta gerada e enviada via WAHA: {chat_id}")
            add_message_to_history(chat_id, "Bot", response)
            update_session_state(chat_id, step="EM_ATENDIMENTO")

        except Exception as e:
            logger.error(f"❌ Erro ao processar {chat_id}: {e}", exc_info=True)
            try:
                enqueue_user(chat_id)
                publish_new_user(chat_id)
                logger.info(f"🔄 Usuário re-adicionado na fila: {chat_id}")
            except Exception as retry_error:
                logger.error(f"💥 Erro ao re-adicionar na fila: {retry_error}")

    def generate_response(self, chat_id: str, history: str) -> str:
        history_str = "\n".join(history)
        logger.info(f"{history_str}")
        response = self.agent_register.gerar_resposta_simples(message=history_str)
        logger.info(f"Resposta generate_ia enviada via WAHA: {response}")
        return response

    def process_incoming_message_data(self, raw_json_payload: str):
        """
        Função central que implementa a lógica de fluxo do Webhook funcional.
        """
        try:
            main_data = json.loads(raw_json_payload.decode('utf-8'))
            message_data = main_data.get("payload", {})
            chat_id = message_data.get("from")
            message = message_data.get("body", "").strip().lower() 
            message_id = message_data.get("id")

            if not message or not chat_id:
                 logger.info(f"⏭️ Mensagem sem corpo ou sem chat_id. Ignorando. {chat_id}")
                 return
            
            if not check_and_set_message_id(message_id):
                 logger.info(f"⏭️ Mensagem {message_id} de {chat_id} duplicada. Ignorando.")
                 return 
            
            add_message_to_history(chat_id, "User", message)

            session_state = get_session_state(chat_id)
            raw_step = session_state.get(b'step') 
            current_step = raw_step.decode('utf-8') if raw_step else 'INICIO'
            logger.info(f"Estado de {chat_id}: {current_step}")

            if current_step == "EM_ATENDIMENTO":
                self.process_user_message(chat_id)
                return 

            elif not is_user_in_queue(chat_id): 
                
                queue_position = enqueue_user(chat_id)
                new_step = "IN_QUEUE"
                
                resposta = f"Você está na fila. Posição: {queue_position}. Aguarde o atendimento."
                waha_api.send_whatsapp_message(chat_id, resposta) 
                update_session_state(chat_id, step=new_step)
                
                if queue_position == 1:
                    logger.info("Worker notificado. Novo usuário é o primeiro. Chamando IA.")
                    self.process_user_message(chat_id) 

                return 

            else:
                 logger.info(f"⏭️ Usuário {chat_id} está na fila ({current_step}). Ignorando nova mensagem.")
                 return

        except json.JSONDecodeError:
            logger.error(f"❌ Erro ao decodificar JSON do Redis. Payload inválido.")
        except Exception as e:
            logger.error(f"❌ Erro CRÍTICO no processamento da mensagem: {e}", exc_info=True)


    def listen_queue(self):
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("new_user_queue")
        for message in pubsub.listen():
            if message['type'] == 'message':
                raw_json_payload = message['data']
                logger.info(f"📨 Payload de {len(raw_json_payload)} bytes recebido do Go.")
                self.process_incoming_message_data(raw_json_payload)

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