import os
from groq import Groq

# 1. Configuração da Chave (Lendo do .env via settings.py do Django)
# Nota: No Django real, você usaria 'settings.GROQ_API_KEY'
# Mas para o exemplo simples, vamos ler direto de uma variável de ambiente,
# que é a maneira recomendada pela documentação da Groq.
groq_service = Groq()
prompt_register = ("""
# Voce é um agente de agendamento capture se o usuario se deseja se cadastrar, se ele quiser capture seu nome e mande uma confirmação do nome.                   
Pode usar informações ficticias, segue o contexto da conversa e responda com base na ultima mensagem do usuario, segue {message}
"""
)

class agent_register():
    """
    Classe de serviço dedicada a interagir com a API da Groq.
    Mantém a lógica de IA separada do worker.
    """
    def __init__(self):
        try:
            # O client é a ponte para a API da Groq
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception as e:
            # É bom ter tratamento de erro se a chave não for encontrada
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada.") from e

    def gerar_resposta_simples(self, message: str) -> str:
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
                "content": message,
            }
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                
                temperature=0.7 
            )

            resposta_ia = chat_completion.choices[0].message.content
            return resposta_ia

        except Exception as e:
            print(f"Erro ao chamar a API da Groq: {e}")
            # Em caso de erro, retorne uma mensagem de fallback amigável
            return "Desculpe, estou tendo problemas técnicos para responder agora."