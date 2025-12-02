import logging
from datetime import datetime
from django.db import transaction
from django. utils import timezone
from chatbot_api.models import UserRegister
from chatbot_api.services. services_agents.service_api_calendar import ServicesCalendar
from chatbot_api. services.metrics import registrar_evento

logger = logging.getLogger(__name__)

class ConsultaService:
    
    @staticmethod
    def criar_agendamento_db(chat_id: str, google_event_id: str, start_time_iso: str):
        """
        Salva o agendamento no UserRegister.  Checa os slots (1 e 2) e o limite de 2 consultas futuras.
        Registra métrica de agendamento no PostgreSQL.
        """
        try:
            with transaction.atomic():
                user = UserRegister.objects.select_for_update().get(chat_id=chat_id)
                new_datetime = datetime.fromisoformat(start_time_iso)
                agora = timezone.now()
                
                is_slot1_free = not user.appointment1_gcal_id or (user.appointment1_datetime and user.appointment1_datetime < agora)
                
                if is_slot1_free:
                    user.appointment1_datetime = new_datetime
                    user.appointment1_gcal_id = google_event_id
                    user.save(update_fields=['appointment1_datetime', 'appointment1_gcal_id'])
                    
                    registrar_evento(
                        cliente_id=chat_id,
                        event_id=google_event_id,
                        tipo_metrica='agendamento',
                        status='success',
                        detalhes=f"Agendamento criado para {new_datetime.strftime('%d/%m/%Y às %H:%M')}"
                    )
                    
                    logger.info(f"✅ Agendamento salvo no slot 1 - Cliente: {chat_id}")
                    return "SUCESSO: Agendamento salvo no slot 1."

                is_slot2_free = not user.appointment2_gcal_id or (user.appointment2_datetime and user.appointment2_datetime < agora)
                
                if is_slot2_free:
                    user.appointment2_datetime = new_datetime
                    user.appointment2_gcal_id = google_event_id
                    user.save(update_fields=['appointment2_datetime', 'appointment2_gcal_id'])

                    registrar_evento(
                        cliente_id=chat_id,
                        event_id=google_event_id,
                        tipo_metrica='agendamento',
                        status='success',
                        detalhes=f"Agendamento criado para {new_datetime.strftime('%d/%m/%Y às %H:%M')}"
                    )
                    
                    logger.info(f"✅ Agendamento salvo no slot 2 - Cliente: {chat_id}")
                    return "SUCESSO: Agendamento salvo no slot 2."
                else:
                    raise ValueError("Limite de agendamentos atingido.  Você pode ter no máximo 2 consultas ativas.")
                    
        except UserRegister.DoesNotExist:
            registrar_evento(
                cliente_id=chat_id,
                event_id=google_event_id,
                tipo_metrica='agendamento',
                status='failed',
                detalhes="Usuário não encontrado no banco de dados"
            )
            logger.error(f"❌ Usuário {chat_id} não registrado ao tentar salvar agendamento")
            raise ValueError("Usuário não registrado.")
            
        except ValueError as e:
            registrar_evento(
                cliente_id=chat_id,
                event_id=google_event_id,
                tipo_metrica='agendamento',
                status='failed',
                detalhes=str(e)
            )
            logger.error(f"❌ Erro de validação ao salvar agendamento: {e}")
            raise
            
        except Exception as e:
            registrar_evento(
                cliente_id=chat_id,
                event_id=google_event_id,
                tipo_metrica='agendamento',
                status='failed',
                detalhes=f"Erro inesperado: {str(e)}"
            )
            logger.error(f"❌ Erro ao salvar agendamento no DB: {e}")
            raise

    @staticmethod
    def listar_agendamentos(chat_id: str) -> list:
        """
        Retorna uma lista de consultas futuras agendadas (max 2), formatada para a IA.
        """
        try:
            user = UserRegister.objects.get(chat_id=chat_id)
            consultas = []
            agora = timezone.now()

            if user.appointment1_gcal_id and user.appointment1_datetime and user.appointment1_datetime >= agora:
                local_dt1 = timezone.localtime(user.appointment1_datetime)
                
                consultas.append({
                    "appointment_number": 1, 
                    "data": local_dt1.strftime("%d/%m/%Y"),
                    "hora": local_dt1.strftime("%H:%M"),
                    "slot": 1 
                })

            if user. appointment2_gcal_id and user.appointment2_datetime and user.appointment2_datetime >= agora:
                local_dt2 = timezone.localtime(user. appointment2_datetime)

                consultas.append({
                    "appointment_number": 2, 
                    "data": local_dt2.strftime("%d/%m/%Y"),
                    "hora": local_dt2. strftime("%H:%M"),
                    "slot": 2
                })

            consultas.sort(key=lambda x: datetime.strptime(f"{x['data']} {x['hora']}", "%d/%m/%Y %H:%M"))

            return consultas
            
        except UserRegister.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao listar agendamentos: {e}")
            return []
            
    @staticmethod
    def cancelar_agendamento_por_id_ux(chat_id: str, numero_consulta: int):
        """
        Cancela a consulta baseada no número UX do slot (1 ou 2).
        Deleta no Google Calendar e limpa os campos no DB.
        Registra métrica de cancelamento no PostgreSQL.
        """
        try:
            with transaction.atomic():
                user = UserRegister.objects.select_for_update().get(chat_id=chat_id)
                event_id_to_cancel = None

                if numero_consulta == 1 and user.appointment1_gcal_id:
                    event_id_to_cancel = user. appointment1_gcal_id
                    appointment_datetime = user.appointment1_datetime

                    user.appointment1_datetime = None
                    user.appointment1_gcal_id = None
                    user.save(update_fields=['appointment1_datetime', 'appointment1_gcal_id'])
                    
                elif numero_consulta == 2 and user.appointment2_gcal_id:
                    event_id_to_cancel = user. appointment2_gcal_id
                    appointment_datetime = user. appointment2_datetime

                    user.appointment2_datetime = None
                    user.appointment2_gcal_id = None
                    user. save(update_fields=['appointment2_datetime', 'appointment2_gcal_id'])
                
                if not event_id_to_cancel:
                    return f"Não encontrei nenhuma consulta ativa no número {numero_consulta} para cancelar."

                if not ServicesCalendar.service:
                    ServicesCalendar.inicializar_servico()
                    
                resp_google = ServicesCalendar.deletar_evento(
                    ServicesCalendar.service, 
                    event_id_to_cancel
                )
                
                if resp_google['status'] == 'ERROR':
                    registrar_evento(
                        cliente_id=chat_id,
                        event_id=event_id_to_cancel,
                        tipo_metrica='cancelamento',
                        status='failed',
                        detalhes=f"Erro ao cancelar no Google: {resp_google. get('message', 'Desconhecido')}"
                    )
                    return f"Erro ao cancelar no Google Calendar: {resp_google['message']}"
                local_dt = timezone.localtime(appointment_datetime)
                registrar_evento(
                    cliente_id=chat_id,
                    event_id=event_id_to_cancel,
                    tipo_metrica='cancelamento',
                    status='success',
                    detalhes=f"Cancelamento da consulta agendada para {local_dt.strftime('%d/%m/%Y às %H:%M')}"
                )
                
                logger.info(f"✅ Cancelamento registrado - Cliente: {chat_id}, Slot: {numero_consulta}")
                return "SUCESSO: Consulta cancelada e removida da agenda."

        except UserRegister.DoesNotExist:
            registrar_evento(
                cliente_id=chat_id,
                event_id=f"slot_{numero_consulta}",
                tipo_metrica='cancelamento',
                status='failed',
                detalhes="Usuário não encontrado"
            )
            return "Usuário não encontrado."
            
        except Exception as e:
            logger.error(f"❌ Erro no fluxo de cancelamento para slot {numero_consulta}: {e}")
            registrar_evento(
                cliente_id=chat_id,
                event_id=f"slot_{numero_consulta}",
                tipo_metrica='cancelamento',
                status='failed',
                detalhes=f"Erro inesperado: {str(e)}"
            )
            return "Ocorreu um erro interno ao tentar cancelar."