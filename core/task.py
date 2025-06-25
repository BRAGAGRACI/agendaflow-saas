from django.core.mail import send_mail
from .models import Agendamento
from datetime import datetime, timedelta
from django.conf import settings


def enviar_lembrete_consulta():
    amanha = datetime.now() + timedelta(days=1)
    agendamentos = Agendamento.objects.filter(data_hora__date=amanha.date())

    for agendamento in agendamentos:
        mensagem = (
            f"Olá {agendamento.cliente.username},\n\n"
            f"Lembrete: você tem uma consulta agendada para amanhã, "
            f"dia {agendamento.data_hora.strftime('%d/%m/%Y')} às {agendamento.data_hora.strftime('%H:%M')}, "
            f"para o serviço: {agendamento.servico}.\n\n"
            f"Estamos ansiosos para atendê-lo(a)!"
        )
        send_mail(
            'Lembrete de Consulta - Clínica',
            mensagem,
            settings.DEFAULT_FROM_EMAIL,
            [agendamento.cliente.email],
            fail_silently=True,
        )

        # tasks.py - Crie este arquivo
        from celery import shared_task
        from django.utils import timezone
        from datetime import timedelta

        @shared_task
        def enviar_lembretes_async():
            """Task do Celery para envio automático"""
            from .models import ConfiguracaoLembrete, Agendamento
            from .views import enviar_whatsapp_headless

            hoje = timezone.now().date()
            configuracoes = ConfiguracaoLembrete.objects.filter(ativo=True)

            for config in configuracoes:
                data_agendamento = hoje + timedelta(days=config.dias_antecedencia)

                agendamentos = Agendamento.objects.filter(
                    estabelecimento=config.estabelecimento,
                    data=data_agendamento
                )

                for agendamento in agendamentos:
                    if agendamento.cliente.telefone:
                        try:
                            enviar_whatsapp_headless(agendamento, config)
                        except Exception as e:
                            print(f"Erro Celery: {str(e)}")

        @shared_task
        def enviar_massa_async(estabelecimento_id, data_envio):
            """Task para envio em massa assíncrono"""
            from .models import Estabelecimento, ConfiguracaoLembrete, Agendamento
            from .views import enviar_whatsapp_headless
            from datetime import datetime

            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            config = ConfiguracaoLembrete.objects.get(estabelecimento=estabelecimento)
            data_obj = datetime.strptime(data_envio, '%Y-%m-%d').date()

            agendamentos = Agendamento.objects.filter(
                estabelecimento=estabelecimento,
                data=data_obj
            )

            for agendamento in agendamentos:
                if agendamento.cliente.telefone:
                    try:
                        enviar_whatsapp_headless(agendamento, config)
                        # Delay entre envios
                        import time
                        time.sleep(3)
                    except Exception as e:
                        print(f"Erro massa async: {str(e)}")
