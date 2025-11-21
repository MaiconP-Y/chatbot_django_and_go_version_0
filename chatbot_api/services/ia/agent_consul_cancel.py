import os
import json 
from groq import Groq
from chatbot_api.services.services_agents.service_register import enviar_dados_user
from chatbot_api.services.services_agents.prompts_agents import prompt_cancel

groq_service = Groq()

REGISTRATION_TOOL_SCHEMA = {
    "type": "function", 
    "function": {
        "name": "",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {
                "chat_id": {
                    "type": "string",
                    "description": "O ID único do chat/usuário do WhatsApp. Essencial para o registro."
                },
            },
            "required": ["chat_id"] 
        }
    }
}

class Agent_cancel():
    """
    Classe de serviço dedicada a interagir com a API da Groq, usando o histórico completo (history_str)
    para manter o contexto e delegar ações de registro via Tool Calling.
    """
    def __init__(self):
        try:
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception as e:
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada.") from e
    
    def generate_cancel(self, history_str: str, chat_id: str) -> str:
        """
        Gera uma resposta da IA, usando a string do histórico completo como a última mensagem do usuário.
        
        :param history_str: O histórico completo da conversa como uma string (User: ... \n Assistant: ...).
        :return: A string de resposta gerada pela IA.
        """
        
        mensagens = [
            {
                "role": "system",
                "content": prompt_cancel,
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
                tools=[REGISTRATION_TOOL_SCHEMA],
                tool_choice="auto",
                temperature=0.1 , 
            )

            response_message = chat_completion.choices[0].message
            resposta_ia = response_message.content
            
            if response_message.tool_calls:
                available_functions = {
                    "enviar_dados_user": enviar_dados_user, 
                }
                
                mensagens.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    
                    function_args = json.loads(tool_call.function.arguments)
                    function_args['chat_id'] = chat_id 
                    
                    registration_result = function_to_call(**function_args) 
                    if registration_result == "SUCCESS_CANCEL": 
                        return "COMPLETED"
                    else:
                        tool_content = "FALHA: Usuário já existe ou erro no banco de dados. Informe o usuário."                   
                    
                    mensagens.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool", 
                            "name": function_name,
                            "content": f"Resultado da Ferramenta {function_name}: {tool_content}"
                        }
                    )
                    
                final_completion = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=mensagens 
                )
            
                return final_completion.choices[0].message.content
            
            return resposta_ia
            
        except Exception as e:
            print(f"Erro ao chamar a API da Groq: {e}")
            return "Desculpe, estou tendo problemas técnicos para responder agora."