# management/commands/criar_planos.py
from django.core.management.base import BaseCommand

from agendaflow.core.models import Plano


#from .models import Plano


class Command(BaseCommand):
    help = 'Cria os planos padrão do sistema'

    def handle(self, *args, **options):
        planos_data = [
            {
                'nome': 'basico',
                'valor_mensal': 67.00,
                'valor_anual': 57.00,
                'max_profissionais': 2,
                'tem_dashboard_financeiro': True,
                'tem_agendamento_ilimitado': True,
                'suporte_email': True,
            },
            {
                'nome': 'profissional',
                'valor_mensal': 97.00,
                'valor_anual': 87.00,
                'max_profissionais': 5,
                'tem_integracao_pagseguro': True,
                'tem_dashboard_financeiro': True,
                'tem_agendamento_ilimitado': True,
                'suporte_email': True,
                'suporte_whatsapp': True,
            },
            {
                'nome': 'empresarial',
                'valor_mensal': 187.00,
                'valor_anual': 167.00,
                'max_profissionais': 10,
                'tem_integracao_pagseguro': True,
                'tem_lembrete_automatico': True,
                'tem_dashboard_financeiro': True,
                'tem_controle_estoque': True,
                'tem_agendamento_ilimitado': True,
                'suporte_email': True,
                'suporte_whatsapp': True,
            },
            {
                'nome': 'enterprise',
                'valor_mensal': None,
                'valor_anual': None,
                'max_profissionais': 999,  # Ilimitado
                'tem_integracao_pagseguro': True,
                'tem_lembrete_automatico': True,
                'tem_dashboard_financeiro': True,
                'tem_controle_estoque': True,
                'tem_agendamento_ilimitado': True,
                'tem_insights_ia': True,
                'suporte_email': True,
                'suporte_whatsapp': True,
            }
        ]

        for plano_data in planos_data:
            plano, created = Plano.objects.get_or_create(
                nome=plano_data['nome'],
                defaults=plano_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Plano "{plano.get_nome_display()}" criado com sucesso!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Plano "{plano.get_nome_display()}" já existe.')
                )