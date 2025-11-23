import logging
from datetime import datetime
from django.db import transaction
from django.utils import timezone # ESSENCIAL para lidar com DateTimeField
from chatbot_api.models import UserRegister
from chatbot_api.services.services_agents.service_api_calendar import ServicesCalendar # Assumindo este import

logger = logging.getLogger(__name__)

class ConsultaService:
    
    @staticmethod
    def criar_agendamento_db(chat_id: str, google_event_id: str, start_time_iso: str):
        """
        Salva o agendamento no UserRegister. Checa os slots (1 e 2) e o limite de 2 consultas futuras.
        """
        try:
            with transaction.atomic():
                user = UserRegister.objects.select_for_update().get(chat_id=chat_id)
                
                # CORREÇÃO CRÍTICA: Converte string ISO 8601 para um objeto datetime
                # O fromisoformat já lida com o fuso horário (TZ-aware)
                new_datetime = datetime.fromisoformat(start_time_iso)
                
                # --- CHECAGEM DE LIMITE E ESCOLHA DE SLOT ---
                agora = timezone.now()
                
                # Slot 1 está vazio OU a consulta no slot 1 é passada (precisa ser limpo)
                is_slot1_free = not user.appointment1_gcal_id or (user.appointment1_datetime and user.appointment1_datetime < agora)
                
                if is_slot1_free:
                    user.appointment1_datetime = new_datetime
                    user.appointment1_gcal_id = google_event_id
                    user.save(update_fields=['appointment1_datetime', 'appointment1_gcal_id'])
                    return "SUCESSO: Agendamento salvo no slot 1."

                # Slot 2 está vazio OU a consulta no slot 2 é passada (precisa ser limpo)
                is_slot2_free = not user.appointment2_gcal_id or (user.appointment2_datetime and user.appointment2_datetime < agora)
                
                if is_slot2_free:
                    user.appointment2_datetime = new_datetime
                    user.appointment2_gcal_id = google_event_id
                    user.save(update_fields=['appointment2_datetime', 'appointment2_gcal_id'])
                    return "SUCESSO: Agendamento salvo no slot 2."

                else:
                    # Ambos os slots estão cheios e são consultas futuras
                    # Esta lógica nunca deve ser atingida, pois a IA deve ser treinada para não permitir
                    raise ValueError("Limite de agendamentos atingido. Você pode ter no máximo 2 consultas ativas.")
                    
        except UserRegister.DoesNotExist:
            logger.error(f"Usuário {chat_id} não registrado ao tentar salvar agendamento.")
            raise ValueError("Usuário não registrado.")
        except Exception as e:
            logger.error(f"Erro ao salvar agendamento no DB: {e}")
            raise

    @staticmethod
    def listar_agendamentos(chat_id: str) -> list[dict]:
        """
        Retorna uma lista de consultas futuras agendadas (max 2), formatada para a IA.
        """
        try:
            user = UserRegister.objects.get(chat_id=chat_id)
            consultas = []
            agora = timezone.now()
            
            # Checagem do Slot 1 (apenas se for futuro e tiver ID)
            if user.appointment1_gcal_id and user.appointment1_datetime and user.appointment1_datetime >= agora:
                
                # 🚨 CORREÇÃO CRÍTICA AQUI 🚨
                local_dt1 = timezone.localtime(user.appointment1_datetime) # Converte de UTC (DB) para fuso local (settings.TIME_ZONE)
                
                consultas.append({
                    "appointment_number": 1, 
                    "data": local_dt1.strftime("%d/%m/%Y"), # Usa o DT LOCALIZADO
                    "hora": local_dt1.strftime("%H:%M"),    # Usa o DT LOCALIZADO
                    "slot": 1 
                })
                
            # Checagem do Slot 2 (apenas se for futuro e tiver ID)
            if user.appointment2_gcal_id and user.appointment2_datetime and user.appointment2_datetime >= agora:
                
                # 🚨 CORREÇÃO CRÍTICA AQUI 🚨
                local_dt2 = timezone.localtime(user.appointment2_datetime) # Converte de UTC (DB) para fuso local (settings.TIME_ZONE)

                consultas.append({
                    "appointment_number": 2, 
                    "data": local_dt2.strftime("%d/%m/%Y"),
                    "hora": local_dt2.strftime("%H:%M"),
                    "slot": 2
                })
                
            # Garante que a lista seja sempre em ordem cronológica para UX
            consultas.sort(key=lambda x: datetime.strptime(f"{x['data']} {x['hora']}", "%d/%m/%Y %H:%M"))

            return consultas
            
        except UserRegister.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Erro ao listar agendamentos: {e}")
            return []
            
    # FUNÇÃO RENOMEADA (CORRIGINDO O ERRO DO AGENTE DE CANCELAMENTO)
    @staticmethod
    def cancelar_agendamento_por_id_ux(chat_id: str, numero_consulta: int):
        """
        Cancela a consulta baseada no número UX do slot (1 ou 2), deletando no Google e limpando os campos no DB.
        """
        try:
            with transaction.atomic():
                user = UserRegister.objects.select_for_update().get(chat_id=chat_id)
                event_id_to_cancel = None
                
                # Identifica qual slot deve ser cancelado
                if numero_consulta == 1 and user.appointment1_gcal_id:
                    event_id_to_cancel = user.appointment1_gcal_id
                    # Limpa o slot 1
                    user.appointment1_datetime = None
                    user.appointment1_gcal_id = None
                    user.save(update_fields=['appointment1_datetime', 'appointment1_gcal_id'])
                    
                elif numero_consulta == 2 and user.appointment2_gcal_id:
                    event_id_to_cancel = user.appointment2_gcal_id
                    # Limpa o slot 2
                    user.appointment2_datetime = None
                    user.appointment2_gcal_id = None
                    user.save(update_fields=['appointment2_datetime', 'appointment2_gcal_id'])
                
                if not event_id_to_cancel:
                    return f"Não encontrei nenhuma consulta ativa no número {numero_consulta} para cancelar."
                
                # Tenta deletar no Google
                # (Assumindo que ServicesCalendar.inicializar_servico e deletar_evento existem)
                if not ServicesCalendar.service:
                    ServicesCalendar.inicializar_servico()
                    
                resp_google = ServicesCalendar.deletar_evento(
                    ServicesCalendar.service, 
                    event_id_to_cancel
                )
                
                if resp_google['status'] == 'ERROR':
                    # Se falhou no Google, o slot jÁ está limpo no DB
                    return f"Erro ao cancelar no Google Calendar: {resp_google['message']}"

                return "SUCESSO: Consulta cancelada e removida da agenda."

        except UserRegister.DoesNotExist:
             return "Usuário não encontrado."
        except Exception as e:
            logger.error(f"Erro no fluxo de cancelamento para slot {numero_consulta}: {e}")
            return "Ocorreu um erro interno ao tentar cancelar."