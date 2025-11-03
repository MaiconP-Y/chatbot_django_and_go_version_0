import os
import requests
import json
import logging

# Adicionando logger para melhor rastreamento no console
logger = logging.getLogger(__name__)

class Waha():

    def __init__(self):
        self.__api_url = os.environ.get("WAHA_API_URL", "http://waha:3000")
        self.waha_api_chave = os.environ.get("WAHA_API_KEY") 
        self.waha_instance = os.environ.get("WAHA_INSTANCE_KEY", "default")

    def send_whatsapp_message(self, chat_id, message):
        # Mantenha este método como está, exceto por mudar print() para logger.info()/logger.error()
        # ... (código send_whatsapp_message)
        url = f"{self.__api_url}/api/sendText"
        api_key = self.waha_api_chave 
        session_name = self.waha_instance
        
        headers = {
        'Content-Type': 'application/json',
        'X-Api-Key': api_key
        }
        
        payload = {    
            "chatId": chat_id,         
            "text": message,
            "session": session_name
        }
        
        response = None # Correção para evitar UnboundLocalError
        
        try:
            response = requests.post(
                url, 
                headers=headers, 
                data=json.dumps(payload)
            )
            response.raise_for_status() 
            
            logger.info(f"Mensagem enviada com sucesso! Status: {response.status_code}")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao enviar mensagem para WAHA: {e}")
            if response is not None and response.status_code == 401:
                logger.error("ERRO 401: Verifique se o WAHA_API_KEY está correto.")
            return None


    def start_session_with_hmac(self, hmac_key: str):
        """
        USA PUT /api/sessions/{session} para reconfigurar o webhook,
        lidando com sessões que já existem (erro 422), conforme a documentação.
        """
        session_name = self.waha_instance
        
        # 1. Endpoint específico da sessão (PUT para UPDATE)
        url = f"{self.__api_url}/api/sessions/{session_name}" 
        api_key = self.waha_api_chave 
        
        headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': api_key
        }
        
        webhook_url = os.environ.get("WHATSAPP_HOOK_URL", "http://django-web:8000/api/whatsapp/webhook/")
        hook_events = os.environ.get("WHATSAPP_HOOK_EVENTS", "message")
        
        # NOVO PAYLOAD CONFORME SUA DOCUMENTAÇÃO (apenas o bloco 'config')
        payload = {    
            "config": {
                # Opcional: manter configuração 'webjs' ou 'noweb' aqui se necessário. 
                # Estamos focando apenas no 'webhooks' que é o que precisamos alterar.
                "webhooks": [
                    {
                        "url": webhook_url,
                        "events": [e.strip() for e in hook_events.split(',')],
                        "hmac": { 
                            "key": hmac_key,
                            "algorithm": "sha512",
                            "header": "X-Webhook-Hmac"
                        }
                    }
                ]
            }
        }
        
        # CORREÇÃO CRÍTICA: Inicializar response
        response = None 
        
        try:
            # 2. Uso do método PUT no endpoint da sessão
            response = requests.put(
                url, 
                headers=headers, 
                data=json.dumps(payload)
            )
            
            # O status 200/204 indica sucesso na atualização
            response.raise_for_status() 
            logger.info(f"✅ Sessão '{session_name}' reconfigurada (PUT) com HMAC com sucesso. Status: {response.status_code}")
            return True
            
        except requests.exceptions.RequestException as e:
            # Captura erros de conexão, timeout ou status (4xx/5xx)
            logger.error(f"❌ Erro ao reconfigurar sessão WAHA: {e}")
        
        # Diagnóstico de erro 401
        if response is not None and response.status_code == 401:
            logger.error("ERRO 401: Verifique se o 'WAHA_API_KEY' no .env está correto.")
            
        return False