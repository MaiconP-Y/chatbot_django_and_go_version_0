from chatbot_api.services.redis_client import get_session_state, update_session_state
from chatbot_api.services.services_agents.service_register import is_user_registered
from chatbot_api.services.ia.agent_register import Agent_register
from chatbot_api.services.ia.agent_date import Agent_date
from chatbot_api.services.ia.agent_router import Agent_router
from chatbot_api.services.ia.agent_consul_cancel import Agent_cancel
from chatbot_api.services.ia.agent_info import Agent_info

def get_user_name_from_db(chat_id: str) -> str | None:
    """Busca o nome do usuário no banco de dados Django."""
    try:
        from chatbot_api.models import UserRegister
        user = UserRegister.objects.get(chat_id=chat_id)
        return user.username
    except UserRegister.DoesNotExist:
        return None
    except Exception as e:
        print(f"Erro ao buscar o nome do usuário {chat_id}: {e}")
        return None

class agent_service(): 
    """
    Serviço de IA minimalista. Atua como proxy entre o Worker e o Roteador de Agentes.
    Gerencia o estado e formata o histórico para a API Groq.
    """
    def __init__(self):
        self.registration_agent = Agent_register()
        self.date_agent = Agent_date(router_agent_instance=self) 
        self.router_agent = Agent_router()
        self.agent_consul_cancel = Agent_cancel()
        self.agent_info = Agent_info()
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
                user_name = get_user_name_from_db(chat_id)
                if step_decode:
                    
                    if step_decode == 'AGENT_MARC_CONFIRM':
                        response = self.date_agent.generate_date(history_str, chat_id, user_name)
                    
                    elif step_decode == 'AGENT_CAN_VERIF':
                        response = self.agent_consul_cancel.generate_cancel(history_str, chat_id) 
                    return response
                        
                else: 
                    response = self.router_agent.route_intent(history_str, user_name)
                    if response == 'ativar_agent_marc':
                        update_session_state(chat_id, registration_step='AGENT_MARC_CONFIRM')
                        response = self.date_agent.generate_date(history_str, chat_id, user_name)
                        
                    elif response == 'ativar_agent_ver_cancel':
                        update_session_state(chat_id, registration_step='AGENT_CAN_VERIF')
                        response = self.agent_consul_cancel.generate_cancel(history_str, chat_id)
                    elif response == 'ativar_agent_info':
                        response = self.agent_info.generate_info(history_str, user_name)
                    return response
            else:
                LGPD_MESSAGE = """Olá! Para prosseguir e usar o assistente, precisamos do seu nome completo para cadastro.
Ao fornecer seu nome, você concorda que o utilizemos para fins de cadastro, atendimento (LGPD) e lembretes. 
Caso deseje solicitar a exclusão de seus dados no futuro, envie um email para exclusao@seusistema.com.br.
                """

                if not step_decode:
                    update_session_state(chat_id, registration_step='WAITING_NAME')
                    response = LGPD_MESSAGE
                
                elif step_decode == 'WAITING_NAME':
                    response = self.registration_agent.generate_register(history_str, chat_id)

            return response
            
        except Exception as e:
            print(f"Erro CRÍTICO no serviço de IA: {e}")
            return "Desculpe, nosso sistema de inteligência artificial está temporariamente fora de serviço. Tente novamente mais tarde."