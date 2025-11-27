import os
from groq import Groq
from chatbot_api.services.services_agents.prompts_agents import prompt_info
from chatbot_api.services.services_agents.service_api_calendar import ServicesCalendar


groq_service = Groq()
services_calendar = ServicesCalendar()

class Agent_info():
    """
    Classe de serviço dedicada a interagir com a API da Groq, usando o histórico completo (history_str)
    para manter o contexto e delegar ações de registro via Tool Calling.
    """
    def __init__(self):
        try:
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception as e:
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada.") from e
    
    def generate_info(self, history_str: str, user_name: str) -> str:
        """
        Gera uma resposta da IA, usando a string do histórico completo como a última mensagem do usuário.
        """
        
        mensagens = [
            {
                "role": "system",
                "content": f"O NOME COMPLETO do usuário é: {user_name}. {prompt_info}",
            },
            {
                "role": "user",
                "content": history_str
            }
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                temperature=0.0 , 
            )

            response_message = chat_completion.choices[0].message
            resposta_ia = response_message.content
            
            return resposta_ia
            
        except Exception as e:
            print(f"Erro ao chamar a API da Groq: {e}")
            return "Desculpe, estou tendo problemas técnicos para responder agora."