import os
import datetime
from datetime import datetime, timedelta, timezone
import logging

# --- IMPORTAÇÕES NECESSÁRIAS PARA O GOOGLE API ---
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    logging.warning("Bibliotecas Google API não encontradas. Usando mocks para compilação.")
    class service_account:
        @staticmethod
        def Credentials(): pass
    def build(): pass

BR_TIMEZONE = timezone(timedelta(hours=-3))
logging.basicConfig(level=logging. INFO)

# ═══════════════════════════════════════════════════════════════════════════════
# VALIDAÇÃO DE DATA
# ═══════════════════════════════════════════════════════════════════════════════

def validar_data_nao_passada(data_str: str) -> dict:
    """
    Valida se a data não é no passado.
    
    :param data_str: Data no formato YYYY-MM-DD
    :return: {'valid': True} ou {'valid': False, 'mensagem': 'erro'}
    """
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d"). date()
        hoje = datetime.now(BR_TIMEZONE).date()
        
        if data_obj < hoje:
            return {
                'valid': False,
                'mensagem': f"❌ A data {data_obj. strftime('%d/%m/%Y')} é no passado. Escolha uma data futura."
            }
        
        return {'valid': True}
        
    except ValueError:
        return {
            'valid': False,
            'mensagem': f"❌ Formato de data inválido: '{data_str}'. Use YYYY-MM-DD."
        }

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDÊNCIAS
# ═══════════════════════════════════════════════════════════════════════════════

class ToolException(Exception):
    """Exceção customizada para erros de ferramenta."""
    pass

def validar_dia(data_formatada: str) -> str | None:
    """Função mock para simular a validação se o dia é útil/válido (ex: não é feriado)."""
    return None

def gerar_horarios_disponiveis() -> list:
    """
    Gera uma lista de slots de 60 minutos (HH:MM) dentro do horário de trabalho (7:00h às 20:00h).
    """
    horarios = []
    start_time = datetime.strptime("07:00", "%H:%M")
    end_time = datetime. strptime("20:00", "%H:%M")
    
    current_time = start_time
    while current_time < end_time:
        horarios.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=60)
        
    return horarios

def is_slot_busy(slot_time_str: str, busy_blocks: list, data: str, duration_minutos: int) -> bool:
    """Verifica se o slot de agendamento (HH:MM) se sobrepõe a qualquer bloco ocupado."""
    slot_start_dt = datetime.strptime(f"{data}T{slot_time_str}:00", "%Y-%m-%dT%H:%M:%S"). replace(tzinfo=BR_TIMEZONE)
    
    slot_end_dt = slot_start_dt + timedelta(minutes=duration_minutos)
    
    for block in busy_blocks:
        try:
            busy_start_dt = datetime.fromisoformat(block['start'])
            busy_end_dt = datetime.fromisoformat(block['end'])
        except ValueError:
            continue 

        if slot_start_dt < busy_end_dt and slot_end_dt > busy_start_dt:
            return True
            
    return False

# --- CONFIGURAÇÃO DO GOOGLE CALENDAR ---
GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', 'maiconwantuil@gmail.com')
CALENDAR_SCOPE = ['https://www.googleapis.com/auth/calendar'] 
GOOGLE_CREDENTIALS_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'caminho/para/o/seu-arquivo-de-credenciais.json')
calendar_id = GOOGLE_CALENDAR_ID 

class ServicesCalendar:
    
    service = None 
    
    @staticmethod
    def inicializar_servico():
        """
        Inicializa o objeto de serviço do Google Calendar com credenciais de serviço.
        Chame esta função APENAS UMA VEZ antes de qualquer outra chamada de API.
        """
        if ServicesCalendar.service:
            logging.info("Serviço do Google Calendar já inicializado.")
            return True
            
        logging.info(f"Tentando inicializar serviço com arquivo em: {GOOGLE_CREDENTIALS_PATH}")
        
        try:
            credentials = service_account.Credentials. from_service_account_file(
                GOOGLE_CREDENTIALS_PATH, 
                scopes=CALENDAR_SCOPE
            )
            
            ServicesCalendar.service = build('calendar', 'v3', credentials=credentials)
            logging.info("Serviço do Google Calendar inicializado com sucesso.")
            return True
            
        except Exception as e:
            logging.error(f"ERRO DE INICIALIZAÇÃO E AUTENTICAÇÃO: {e}")
            logging.error("Verifique se o GOOGLE_CREDENTIALS_PATH e o arquivo JSON estão corretos.")
            return False

    @staticmethod
    def buscar_eventos_do_dia(service, data: str) -> list:
        """
        Busca todos os eventos ocupados no dia especificado (Método events(). list()). 
        Mantido para fins de teste de eventos brutos, mas freebusy é preferível.
        """
        try:
            time_min = f'{data}T07:00:00-03:00'
            time_max = f'{data}T20:00:00-03:00'

            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
            
        except Exception as e:
            return []

    @staticmethod
    def buscar_horarios_disponiveis(service, data: str, duracao_minutos: int = 60):
        """
        Calcula os horários disponíveis (livres) usando o endpoint freebusy do Google. 
        
        ⚠️ VALIDA SE A DATA NÃO É NO PASSADO ANTES DE BUSCAR! 
        
        Retorna um dicionário estruturado:
        - Sucesso: {'status': 'SUCCESS', 'available_slots': ['07:00', '08:00', ...]}
        - Erro:    {'status': 'ERROR', 'message': 'Mensagem de erro detalhada. '}
        """
        try:
            
            # 1. Validação de data
            try:
                data_date_obj = datetime.strptime(data, "%Y-%m-%d").date() # ALTERAÇÃO: data_date_obj
            except ValueError:
                return {"status": "ERROR", "message": f"Formato inválido para a data: '{data}'.  Use 'YYYY-MM-DD'. "}

            # ⚠️ VALIDAÇÃO: Data não pode ser no passado
            validacao = validar_data_nao_passada(data)
            if not validacao['valid']:
                return {"status": "ERROR", "message": validacao['mensagem']}

            data_formatada = data_date_obj.strftime("%d-%m-%Y")
            mensagem_erro = validar_dia(data_formatada)
            if mensagem_erro:
                return {"status": "ERROR", "message": mensagem_erro}

            # 2.  Definição do intervalo de tempo (07:00 a 20:00)
            time_min = f'{data}T07:00:00-03:00'
            time_max = f'{data}T20:00:00-03:00'
            
            # 3.  CHAMADA AO FREEBUSY
            query_body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": calendar_id}]
            }

            freebusy_response = service.freebusy().query(body=query_body).execute()
            
            # 4.  Extrai os blocos ocupados
            busy_blocks = freebusy_response.get('calendars', {}).get(calendar_id, {}).get('busy', [])
            
            # 5. Gera todos os slots possíveis
            horarios = gerar_horarios_disponiveis() 
            livres = []
            
            # --- INÍCIO DA MUDANÇA: Safety Margin (30 minutos) ---
            hoje = datetime.now(BR_TIMEZONE).date()
            now_with_margin = datetime.now(BR_TIMEZONE) + timedelta(minutes=30)
            past_margin_passed = False # ⬅️ NOVO: Flag de otimização
            
            for h in horarios:
                is_busy = is_slot_busy(h, busy_blocks, data, duracao_minutos)
                
                if not is_busy:
                    if data_date_obj == hoje:
                        
                        # --- Otimização: Se já passou do limite de 30 minutos, não precisa comparar novamente ---
                        if past_margin_passed:
                            livres.append(h)
                            continue # Vai para o próximo 'h'

                        # Cria objeto datetime para o slot (com timezone)
                        slot_dt = datetime.strptime(f"{data}T{h}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=BR_TIMEZONE)
                        
                        # ⚠️ VALIDAÇÃO 2 (Safety Margin): Verifica se está à frente dos 30 minutos
                        if slot_dt >= now_with_margin:
                            livres.append(h)
                            past_margin_passed = True # ⬅️ Define a flag para True
                    
                    else:
                        # Para datas futuras, todos os horários livres são válidos
                        livres.append(h)


            if not livres:
                return {"status": "SUCCESS", "available_slots": [], "message": f"Não há horários disponíveis para {data}. "}

            # Retorno estruturado de sucesso
            return {"status": "SUCCESS", "available_slots": livres}
            
        except ToolException as e:
            return {"status": "ERROR", "message": f"Erro na validação da ferramenta: {e}"}
        except Exception as e:
            logging.error(f"Erro inesperado no cálculo de disponibilidade (freebusy): {e}")
            return {"status": "ERROR", "message": f"Erro inesperado ao buscar horários disponíveis: {e}"}

    @staticmethod
    def criar_evento(
        service, 
        start_time_str: str, 
        chat_id: str,
        name: str,
        summary: str = None, 
        time_zone: str = 'America/Sao_Paulo'
    ):
        """
        Cria um novo evento de 1 hora de duração (60 minutos) na agenda principal.
        
        Retorna um dicionário estruturado:
        - Sucesso: {'status': 'SUCCESS', 'event_link': 'link_do_evento', 'start_time': 'YYYY-MM-DDTHH:MM:SS-03:00'}
        - Erro:    {'status': 'ERROR', 'message': 'Mensagem de erro detalhada.'}
        """
        if not service:
            return {"status": "ERROR", "message": "Erro: Objeto de serviço do Google Calendar não inicializado."}

        try:
            # 1. Converte a string de início em objeto datetime
            start_dt = datetime.fromisoformat(start_time_str)
        except ValueError:
            return {"status": "ERROR", "message": f"Formato inválido para start_time_str: '{start_time_str}'.  Use o formato ISO 8601 completo (e.g., 'YYYY-MM-DDTHH:MM:SS-03:00')."}
            
        # ═══════════════════════════════════════════════════════════════════════════
        # 🛡️ VERIFICAÇÃO DE DISPONIBILIDADE DE ÚLTIMO SEGUNDO (NOVA LÓGICA)
        # ═══════════════════════════════════════════════════════════════════════════
        
        # 1. Extrair Data e Hora para a verificação (YYYY-MM-DD e HH:MM)
        data_str = start_dt.strftime("%Y-%m-%d")
        hora_str = start_dt.strftime("%H:%M")

        logging.info(f"🛡️ Iniciando verificação de disponibilidade de último segundo para: {data_str} às {hora_str}")

        # 2. Chamar a função de busca de horários disponíveis
        disponiveis = ServicesCalendar.buscar_horarios_disponiveis(
            service=service, 
            data=data_str, 
            duracao_minutos=60 
        )
        
        if disponiveis['status'] == 'ERROR':
            # Se a busca falhou (ex: data inválida/passado), retornamos o erro
            return disponiveis
        
        # 3. Verificar se o horário desejado está na lista de horários livres
        available_slots = disponiveis.get('available_slots', [])
        
        if hora_str not in available_slots:
            logging.warning(f"❌ Tentativa de agendamento em slot indisponível: {start_time_str}")
            # Retorno de erro amigável para o Worker enviar ao usuário
            return {
                "status": "ERROR", 
                "message": f"❌ O horário {hora_str} do dia {start_dt.strftime('%d/%m/%Y')} não está mais disponível (ou foi marcado há pouco). Por favor, escolha outro."
            }
            
        logging.info(f"✅ Slot {start_time_str} confirmado como disponível.")
        
        # ═══════════════════════════════════════════════════════════════════════════
        # FIM DA VERIFICAÇÃO. PROSSEGUIR COM O AGENDAMENTO.
        # ═══════════════════════════════════════════════════════════════════════════


        # 2.  Define a duração de 60 minutos
        DURACAO_MINUTOS = 60
        end_dt = start_dt + timedelta(minutes=DURACAO_MINUTOS)
        
        # 3.  Formata o horário de término para a API
        end_time_str = end_dt.isoformat()

        # 4. Define o Summary usando o chat_id (conforme solicitação do usuário)
        final_summary = f"CONSUL Nome:{name} - Cliente ID:{chat_id}"

        # Estrutura do evento (sem localização e descrição)
        event_body = {
            'summary': final_summary, 
            'start': {
                'dateTime': start_time_str, 
                'timeZone': time_zone,
            },
            'end': {
                'dateTime': end_time_str,   
                'timeZone': time_zone,
            },
            # Configuração de lembretes (para o dono da agenda - o doutor)
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        try:
            event = service.events().insert(
                calendarId=calendar_id, 
                body=event_body,
            ).execute()
            
            logging.info(f"Evento criado: {event.get('htmlLink')}")
            
            # Retorno estruturado de sucesso
            return {
                "status": "SUCCESS", 
                "event_link": event.get('htmlLink'), 
                "event_id": event.get('id'),
                "start_time": start_time_str
            }
            
        except Exception as e:
            logging.error(f"Erro ao criar evento na agenda: {e}")
            # Retorno estruturado de erro
            return {"status": "ERROR", "message": f"Falha ao criar o evento na agenda: {e}"}
        
    @staticmethod
    def deletar_evento(service, event_id: str):
        """
        Deleta um evento do Google Calendar pelo ID.
        """
        if not service:
            return {"status": "ERROR", "message": "Serviço de calendário não inicializado."}
            
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logging.info(f"Evento {event_id} deletado do Google Calendar com sucesso.")
            return {"status": "SUCCESS", "message": "Evento cancelado no Google Calendar."}
            
        except Exception as e:
            logging.error(f"Erro ao deletar evento {event_id}: {e}")
            # Se o erro for 404 (já deletado) ou 410 (gone), consideramos sucesso para não travar o banco
            if "404" in str(e) or "410" in str(e):
                return {"status": "SUCCESS", "message": "Evento já não existia no Google Calendar."}
                
            return {"status": "ERROR", "message": f"Erro ao deletar evento: {e}"}
        
    # service_api_calendar.py
# ... (código existente da classe ServicesCalendar)

    @staticmethod
    def buscar_proximos_disponiveis(service, limite_slots: int = 3, duracao_minutos: int = 60) -> dict:
        """
        Implementa a estratégia de busca escalonada (4->10->30 dias) para encontrar os próximos slots livres.
        
        Retorna um dicionário:
        - Sucesso: {'status': 'SUCCESS', 'available_slots': [{'iso_time': 'YYYY-MM-DDT...Z', 'legivel': 'DD/MM - HH:MM'}, ...]}
        - Erro:    {'status': 'ERROR', 'message': 'Mensagem de erro detalhada.'}
        """
        if not service:
            return {"status": "ERROR", "message": "Erro: Objeto de serviço do Google Calendar não inicializado."}

        # 1. Definição das margens de busca (Estratégia Escalonada Go Way)
        # Começa com 4 dias, depois expande para 10, e finalmente 30 dias.
        margens_dias = [4, 10, 30] 
        hoje = datetime.now(BR_TIMEZONE).date()
        
        slots_sugeridos = []
        
        # 2. Loop sobre as margens com Curto-Circuito
        for margem in margens_dias:
            logging.info(f"Iniciando busca flexível: Margem de +{margem} dias.")
            
            # Itera dia por dia dentro da margem (exclui o dia atual se já passou)
            for i in range(margem):
                data_atual = hoje + timedelta(days=i)
                data_str = data_atual.strftime("%Y-%m-%d")
                
                # Reutiliza a função de busca por dia (Responsabilidade Única)
                resultado = ServicesCalendar.buscar_horarios_disponiveis(
                    service=service, 
                    data=data_str, 
                    duracao_minutos=duracao_minutos
                )
                
                if resultado['status'] == 'SUCCESS':
                    for hora in resultado['available_slots']:
                        # Constrói o formato ISO 8601 completo (ESSENCIAL para a tool agendar_consulta_1h)
                        # Assumindo BR_TIMEZONE como -03:00 para o agendamento
                        data_hora_iso = f"{data_str}T{hora}:00-03:00"
                        
                        # Constrói a descrição legível para o usuário
                        data_hr_obj = datetime.strptime(f"{data_str} {hora}", "%Y-%m-%d %H:%M")
                        data_hr_legivel = data_hr_obj.strftime("%d/%m - %H:%M")
                        
                        slots_sugeridos.append({
                            'iso_time': data_hora_iso,
                            'legivel': data_hr_legivel
                        })
                        
                        # Curto-circuito: Se o limite for atingido, retornamos imediatamente
                        if len(slots_sugeridos) >= limite_slots:
                            logging.info(f"Limite de {limite_slots} slots atingido na margem de {margem} dias.")
                            return {
                                "status": "SUCCESS", 
                                "available_slots": slots_sugeridos
                            }
                            
            # Se o loop da margem terminar e não tivermos o suficiente, passamos para a próxima margem

        # 3. Retorno final (Se encontrou algo ou nada)
        if slots_sugeridos:
            return {
                "status": "SUCCESS", 
                # Mantém o padrão 'available_slots' para consistência
                "available_slots": slots_sugeridos
            }
        else:
            return {
                "status": "SUCCESS", 
                "available_slots": [],
                "message": "Nenhum horário disponível foi encontrado nas próximas quatro semanas."
            }
        
        