import os
import json 
from groq import Groq
from chatbot_api.services.services_agents.prompts_agents import prompt_router

groq_service = Groq()

class Agent_router():
    def __init__(self):
        try:
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            self.prompt = prompt_router
        except Exception as e:
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada.") from e
    
    def route_intent(self, message: str) -> str:
        """
        Gera uma resposta simples da IA para uma única mensagem do usuário, ou retorna a função a ser chamada.
        
        :param message: O histórico completo da conversa como uma string.
        :return: A string de resposta (texto ou chamada de função).
        """

        mensagens = [
            {
                "role": "system",
                "content": prompt_router,
            },
            {
                "role": "user",
                "content": message
            }
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                temperature=0.0 , 
            )
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            print(f"Erro ao chamar a API da Groq: {e}")
            return "Desculpe, estou tendo problemas técnicos para responder agora."