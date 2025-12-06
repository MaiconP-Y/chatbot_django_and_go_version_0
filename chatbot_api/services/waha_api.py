import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

class Waha():

    def __init__(self):
        self.__api_url = os.environ.get("WAHA_API_URL", "http://waha:3000")
        self.waha_api_chave = os.environ.get("WAHA_API_KEY")
        self.waha_instance = os.environ.get("WAHA_INSTANCE_KEY", "default")
        
    def __get_headers(self):
        """Método auxiliar para obter cabeçalhos de forma consistente."""
        return {
            'Content-Type': 'application/json',
            'X-Api-Key': self.waha_api_chave
        }

    def start_typing(self, chat_id: str):
        """Envia o sinal 'digitando...' (typing) para o chat via WAHA API."""
        url = f"{self.__api_url}/api/{self.waha_instance}/presence"
        payload = {"chatId": chat_id, "presence": "typing"}
        
        try:
            # Requisito de eficiência GoLang: Timeout curto (1s) para não travar o worker
            requests.post(url, json=payload, headers=self.__get_headers(), timeout=1)
        except Exception:
            # Falha visual (typing) não deve gerar erro crítico
            pass 

    def stop_typing(self, chat_id: str):
        """Envia o sinal 'pausado' (paused) para limpar o status 'digitando...'."""
        url = f"{self.__api_url}/api/{self.waha_instance}/presence"
        # 'paused' é o status correto para resetar o typing
        payload = {"chatId": chat_id, "presence": "paused"}
        
        try:
            requests.post(url, json=payload, headers=self.__get_headers(), timeout=1)
        except Exception:
            pass
    def send_whatsapp_message(self, chat_id, message):
        """ Envia uma mensagem de texto via API WAHA. """
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
        
        response = None 
        
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
            logger.error(f"❌ Erro ao enviar mensagem para WAHA: {e}")
            if response is not None and response.status_code == 401:
                logger.error("ERRO 401: Verifique se o WAHA_API_KEY está correto.")
            return None
        
        
    def start_existing_session(self):
        """
        Chama POST /api/sessions/{session}/start para iniciar uma sessão existente.
        Trata 200, 201 e 422 (já iniciado) como sucesso.
        """
        import time
        session_name = self.waha_instance
        url = f"{self.__api_url}/api/sessions/{session_name}/start"
        api_key = self.waha_api_chave 
        
        headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': api_key
        }
        time.sleep(10)
        response = None 
        
        try:
            logger.info(f"⏳ Tentando INICIAR a sessão WAHA '{session_name}' (POST /start)")
            response = requests.post(
                url, 
                headers=headers
            )
            
            if response.status_code in (201, 200, 422):
                if response.status_code == 422:
                    logger.warning(f"Sessão '{session_name}' já está ativa ou iniciando (422), considerado sucesso.")
                else:
                    logger.info(f"✅ Início da sessão WAHA '{session_name}' solicitado com sucesso. Status: {response.status_code}")
                return True
            
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao iniciar sessão WAHA: {e}")
            if response is not None and response.status_code == 401:
                logger.error("ERRO 401: Verifique se o 'WAHA_API_KEY' no .env está correto.")
                
            return False
        
        return False


    def start_session_with_hmac(self, hmac_key: str):
        """
        1. Configura o HMAC (PUT /api/sessions/{session}) e 
        2. Inicia a sessão (POST /api/sessions/{session}/start) se a configuração for bem-sucedida.
        """
        session_name = self.waha_instance
        
        url = f"{self.__api_url}/api/sessions/{session_name}" 
        api_key = self.waha_api_chave 
        
        headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': api_key
        }
        
        webhook_url = os.environ.get("WHATSAPP_HOOK_URL")
        hook_events = os.environ.get("WHATSAPP_HOOK_EVENTS", "message")
        
        payload = {    
            "config": {
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
        response = None 
        
        try:
            # Tenta Reconfiguração (PUT)
            response = requests.put(
                url, 
                headers=headers, 
                data=json.dumps(payload)
            )
            
            response.raise_for_status() 
            logger.info(f"✅ Sessão '{session_name}' reconfigurada (PUT) com HMAC com sucesso. Status: {response.status_code}")
            
            return self.start_existing_session()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao reconfigurar sessão WAHA (PUT): {e}")
            
            if response is not None:
                if response.status_code == 401:
                    logger.error("ERRO 401: Verifique se o 'WAHA_API_KEY' no .env está correto.")
                if response.status_code == 422:
                     logger.warning(f"Sessão '{session_name}' já existe (422), prosseguindo para o START.")
                     return self.start_existing_session()

            return False # Falhou na configuração, aborta
        
    def send_support_contact(self, chat_id: str):
        """
        Envia APENAS o seu contato de suporte para o usuário.
        Lê do .env ou usa o número fixo como fallback.
        """
        url = f"{self.__api_url}/api/sendContactVcard"
        
        # Variáveis sensíveis do .env ou seu número fixo
        wa_id = os.environ.get("SUPORTE_WA_ID", "554399817467")
        full_name = os.environ.get("SUPORTE_FULL_NAME", "Suporte Técnico")
        
        # Constrói o VCard único
        vcard = f"BEGIN:VCARD\nVERSION:3.0\nFN:{full_name}\nTEL;type=CELL;waid={wa_id}:+{wa_id}\nEND:VCARD"

        payload = {
            "chatId": chat_id,
            "contacts": [{"vcard": vcard}],
            "session": self.waha_instance
        }

        try:
            requests.post(url, headers=self.__get_headers(), json=payload, timeout=5)
        except Exception as e:
            logger.error(f"❌ Falha ao enviar contato de suporte: {e}")