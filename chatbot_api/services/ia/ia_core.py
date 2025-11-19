from chatbot_api.services.redis_client import get_session_state, update_session_state
from chatbot_api.services.services_agents.service_register import is_user_registered
from chatbot_api.services.ia.agent_register import Agent_register
from chatbot_api.services.ia.agent_date import Agent_date
from chatbot_api.services.ia.agent_router import Agent_router

class agent_service(): 
    """
    Serviço de IA minimalista. Atua como proxy entre o Worker e o Roteador de Agentes.
    Gerencia o estado e formata o histórico para a API Groq.
    """
    def __init__(self):
        self.registration_agent = Agent_register()
        self.date_agent = Agent_date()
        self.router_agent = Agent_router()
        pass

    def router(self, history_str: str, chat_id: str) -> str:
        """
        Delega o trabalho de roteamento.
        """
        try:
            is_registered = is_user_registered(chat_id)
            session_state_data = get_session_state(chat_id)
            step_bytes = session_state_data.get(b'registration_step') 
            step_decode = step_bytes.decode('utf-8') if step_bytes else None
            response = ""
            
            if is_registered:
                
                if step_decode:
                    
                    if step_decode == 'AGENT_MARC_CONFIRM':
                        response = f"Chamando Agente de Data para continuação do agendamento (chat_id: {chat_id})" 
                    
                    elif step_decode == 'AGENT_CAN_VERIF':
                        response = f"Chamando Agente de Consultas/Cancelamento (chat_id: {chat_id})" 
                        
                else: 
                    response = self.router_agent.route_intent(history_str)
                    if response == 'ativar_agent_marc':
                        update_session_state(chat_id, registration_step='AGENT_MARC_CONFIRM')
                        response = "Intenção de Agendamento detectada. Por favor, forneça a data e hora desejadas." 
                        
                    elif response == 'ativar_agent_ver_cancel':
                        update_session_state(chat_id, registration_step='AGENT_CAN_VERIF')
                        response = "Intenção de Consulta/Cancelamento detectada. Qual o ID da consulta ou o seu CPF?"
                        
            else:
                LGPD_MESSAGE = "Olá! Para prosseguir, precisamos do seu nome completo para cadastro. Ao fornecer seu nome, você concorda que o utilizemos para fins de cadastro, atendimento (LGPD) e lembretes. Caso deseje solicitar a exclusão de seus dados no futuro, envie um email para exclusao@seusistema.com.br. Por favor se concorda informe seu nome completo."

                if not step_decode:
                    update_session_state(chat_id, registration_step='WAITING_NAME')
                    response = LGPD_MESSAGE
                
                elif step_decode == 'WAITING_NAME':
                    response = self.registration_agent.generate_register(history_str, chat_id)

            return response
            
        except Exception as e:
            print(f"Erro CRÍTICO no serviço de IA: {e}")
            return "Desculpe, nosso sistema de inteligência artificial está temporariamente fora de serviço. Tente novamente mais tarde."