import os
import sys
import django
from datetime import datetime, timezone

from agendaflow.core.models import HistoricoLembrete, Agendamento, ConfiguracaoEmail
from agendaflow.core.views import enviar_email_lembrete

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agendaflow.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    print(f"[{datetime.now()}] Executando envio de lembretes...")
    call_command('enviar_lembretes')
    print(f"[{datetime.now()}] Envio concluído!")


def enviar_lembretes_automaticos():
    """Função para ser chamada diariamente via cron job ou Celery"""
    from datetime import date, timedelta

    print("🤖 INICIANDO ENVIO AUTOMÁTICO DE LEMBRETES")

    # Data para enviar lembretes (amanhã, depois de amanhã, etc.)
    configs_ativas = ConfiguracaoEmail.objects.filter(ativo=True)

    total_enviados = 0

    for config in configs_ativas:
        print(f"📧 Processando: {config.estabelecimento.nome}")

        # Calcular data alvo baseada na antecedência
        data_alvo = date.today() + timedelta(days=config.dias_antecedencia)

        # Buscar agendamentos da data alvo
        agendamentos = Agendamento.objects.filter(
            estabelecimento=config.estabelecimento,
            data=data_alvo
        )

        print(f"📅 Data alvo: {data_alvo.strftime('%d/%m/%Y')} - {agendamentos.count()} agendamentos")

        if agendamentos:
            # Verificar se é o horário certo
            agora = timezone.now().time()
            if agora >= config.horario_envio:

                # Verificar se já enviou hoje
                ja_enviou_hoje = HistoricoLembrete.objects.filter(
                    estabelecimento=config.estabelecimento,
                    tipo='email',
                    status='enviado',
                    data_envio__date=date.today()
                ).exists()

                if not ja_enviou_hoje:
                    # Enviar para todos os agendamentos
                    for agendamento in agendamentos:
                        if agendamento.cliente.email:
                            sucesso, mensagem = enviar_email_lembrete(agendamento, config)
                            if sucesso:
                                total_enviados += 1
                                print(f"✅ {mensagem}")
                            else:
                                print(f"❌ {mensagem}")
                else:
                    print("⏭️ Já enviou lembretes hoje")
            else:
                print(f"⏰ Aguardando horário: {config.horario_envio}")

    print(f"🏁 ENVIO AUTOMÁTICO CONCLUÍDO - {total_enviados} emails enviados")
    return total_enviados