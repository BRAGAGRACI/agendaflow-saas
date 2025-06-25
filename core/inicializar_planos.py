from django.core.management.base import BaseCommand
from django.apps import apps
from decimal import Decimal

class Command(BaseCommand):
    help = 'Inicializa ou atualiza os planos no banco de dados.'

    def handle(self, *args, **options):
        Plano = apps.get_model('seuapp', 'Plano')  # Substitua 'seuapp' pelo nome da sua aplicação

        # Lista de planos com seus atributos
        planos_data = [
            {
                'nome': 'Básico',
                'valor': Decimal('57.00'),
                'max_profissionais': 2,
                'tem_integracao_pagseguro': False,
                'tem_lembrete_automatico': False,
                'tem_controle_estoque': False,
                'tem_insights_ia': False,
                'suporte_whatsapp': False
            },
            {
                'nome': 'Profissional',
                'valor': Decimal('87.00'),
                'max_profissionais': 5,
                'tem_integracao_pagseguro': True,
                'tem_lembrete_automatico': False,
                'tem_controle_estoque': False,
                'tem_insights_ia': False,
                'suporte_whatsapp': True
            },
            {
                'nome': 'Empresarial',
                'valor': Decimal('167.00'),
                'max_profissionais': 10,
                'tem_integracao_pagseguro': True,
                'tem_lembrete_automatico': True,
                'tem_controle_estoque': True,
                'tem_insights_ia': False,
                'suporte_whatsapp': True
            },
            {
                'nome': 'Enterprise',
                'valor': None,  # Sob consulta
                'max_profissionais': 0,  # 0 indica ilimitado (ajuste conforme lógica)
                'tem_integracao_pagseguro': True,
                'tem_lembrete_automatico': True,
                'tem_controle_estoque': True,
                'tem_insights_ia': True,
                'suporte_whatsapp': True
            },
        ]

        # Cria ou atualiza os planos
        for plano_data in planos_data:
            plano, created = Plano.objects.update_or_create(
                nome=plano_data['nome'],
                defaults={
                    'valor': plano_data['valor'],
                    'max_profissionais': plano_data['max_profissionais'],
                    'tem_integracao_pagseguro': plano_data['tem_integracao_pagseguro'],
                    'tem_lembrete_automatico': plano_data['tem_lembrete_automatico'],
                    'tem_controle_estoque': plano_data['tem_controle_estoque'],
                    'tem_insights_ia': plano_data['tem_insights_ia'],
                    'suporte_whatsapp': plano_data['suporte_whatsapp']
                }
            )
            action = 'Criado' if created else 'Atualizado'
            self.stdout.write(self.style.SUCCESS(f'{action} plano: {plano.nome}'))