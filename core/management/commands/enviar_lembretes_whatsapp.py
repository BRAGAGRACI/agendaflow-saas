from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from agendaflow.core.models import ConfiguracaoLembrete, Agendamento
from agendaflow.core.views import enviar_whatsapp_headless


class Command(BaseCommand):
    help = 'Envia lembretes de WhatsApp automáticos'

    def add_arguments(self, parser):
        parser.add_argument('--tipo', type=str, default='headless', help='Tipo: headless ou normal')
        parser.add_argument('--estabelecimento', type=int, help='ID do estabelecimento específico')

    def handle(self, *args, **options):
        self.stdout.write('Iniciando envio de lembretes WhatsApp...')

        hoje = timezone.now().date()

        # Filtrar por estabelecimento se especificado
        if options['estabelecimento']:
            configuracoes = ConfiguracaoLembrete.objects.filter(
                ativo=True,
                estabelecimento_id=options['estabelecimento']
            )
        else:
            configuracoes = ConfiguracaoLembrete.objects.filter(ativo=True)

        total_enviados = 0
        total_erros = 0

        for config in configuracoes:
            self.stdout.write(f'Processando: {config.estabelecimento.nome}')

            data_agendamento = hoje + timedelta(days=config.dias_antecedencia)

            agendamentos = Agendamento.objects.filter(
                estabelecimento=config.estabelecimento,
                data=data_agendamento
            )

            self.stdout.write(f'Agendamentos encontrados: {agendamentos.count()}')

            for agendamento in agendamentos:
                if agendamento.cliente.telefone:
                    try:
                        # CORREÇÃO: Importar função corretamente
                        if options['tipo'] == 'headless':
                            sucesso, mensagem = enviar_whatsapp_headless(agendamento, config)
                        else:
                            # Importar da view
                            from agendaflow.core.views import enviar_whatsapp_real
                            sucesso, mensagem = enviar_whatsapp_real(agendamento, config)

                        if sucesso:
                            self.stdout.write(f'✅ {mensagem}')
                            total_enviados += 1
                        else:
                            self.stdout.write(f'❌ {mensagem}')
                            total_erros += 1

                    except Exception as e:
                        self.stdout.write(f'❌ Erro: {str(e)}')
                        total_erros += 1

                    # Delay entre envios
                    import time
                    time.sleep(2)

        self.stdout.write(f'Envio concluído! Total enviados: {total_enviados}, Erros: {total_erros}')


