import os
import json 
from groq import Groq
from chatbot_api.services.service_register import enviar_dados_user

groq_service = Groq()
prompt_register = ("""
# **AGENTE DE REGISTRO, COLETA DE NOME E CONFORMIDADE LGPD**

**OBJETIVO PRINCIPAL:** Obter o nome completo do usuário após aviso de LGPD e registrar usando a ferramenta `enviar_dados_user`.

**FLUXO OBRIGATÓRIO:**
1.  **Aviso/LGPD:** Comece a interação com o texto: "Olá! Para prosseguir, precisamos do seu nome completo para cadastro. Ao fornecer seu nome, você concorda que o utilizemos para fins de cadastro e atendimento (LGPD). Por favor, informe seu nome completo agora."
2.  **Captura de Nome:** ESPERE a resposta do usuário, que deve ser o nome.
3.  **GATILHO ÚNICO DE CHAMADA:** A ferramenta `enviar_dados_user` **SÓ PODE SER CHAMADA** no turno em que o usuário **INFORMAR SEU NOME REAL**. Nunca use placeholders.

**REGRAS CRÍTICAS DE CHAMADA DA FERRAMENTA:**
* **PROIBIDO** inventar nomes ou usar variáveis/placeholders como argumento para `name`.
* O parâmetro `name` DEVE ser o nome REAL e COMPLETO extraído da mensagem do usuário.
""")

REGISTRATION_TOOL_SCHEMA = {
    "type": "function", 
    "function": {
        "name": "enviar_dados_user",
        "description": "Registra um novo usuário no banco de dados com seu ID de chat e nome. Use esta ferramenta APENAS se o usuário pedir para se cadastrar e fornecer seu nome VERDADEIRO **NUNCA USE PLACEHOLDERS**.",
        "parameters": {
            "type": "object",
            "properties": {
                "chat_id": {
                    "type": "string",
                    "description": "O ID único do chat/usuário do WhatsApp. Essencial para o registro."
                },
                "name": {
                    "type": "string",
                    "description": "O nome fornecido pelo usuário para o registro na conversa."
                }
            },
            "required": ["chat_id", "name"] # Os argumentos que a IA deve OBRIGATORIAMENTE extrair
        }
    }
}

class agent_register():
    """
    Classe de serviço dedicada a interagir com a API da Groq.
    Mantém a lógica de IA separada do worker.
    """
    def __init__(self):
        try:
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception as e:
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada.") from e

    def gerar_resposta_simples(self, message: str, chat_id: str) -> str:
        """
        Gera uma resposta simples da IA para uma única mensagem do usuário.
        
        :param mensagem_usuario: O texto enviado pelo cliente.
        :return: A string de resposta gerada pela IA.
        """
        mensagens = [
            {
                "role": "system",
                "content": prompt_register,
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
                tools=[REGISTRATION_TOOL_SCHEMA],
                tool_choice="auto",
                temperature=0.1 , 
            )

            response_message = chat_completion.choices[0].message
            resposta_ia = chat_completion.choices[0].message.content
            
            if response_message.tool_calls:

                available_functions = {
                    "enviar_dados_user": enviar_dados_user, # Função importada do service_register
                }
                
                mensagens.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    
                    function_args = json.loads(tool_call.function.arguments)
                    function_args['chat_id'] = chat_id 
                    
                    registration_result = function_to_call(**function_args) # Executa enviar_dados_user
                    
                    if registration_result:
                        tool_content = "SUCESSO: Usuário registrado com o nome fornecido."
                    else:
                        tool_content = "FALHA: Usuário já existe ou erro no banco de dados. Informe o usuário."
                    
                    # 5. Adiciona o RESULTADO da execução ao histórico (role: tool)
                    mensagens.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool", 
                            "name": function_name,
                            "content": f"Resultado do registro de usuário: {tool_content}"
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
            # Em caso de erro, retorne uma mensagem de fallback amigável
            return "Desculpe, estou tendo problemas técnicos para responder agora."