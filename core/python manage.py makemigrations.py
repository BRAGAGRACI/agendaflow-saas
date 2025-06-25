from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ('seu_app', '0001_initial'),  # Substitua pelo número da sua última migração
    ]

    operations = [
        # Adicionar novos campos um por vez para evitar conflitos
        migrations.AddField(
            model_name='pagamentotransacao',
            name='valor_desconto',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='valor_taxa',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='valor_liquido',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='gateway_transacao_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='gateway_resposta',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='cartao_ultimos_digitos',
            field=models.CharField(blank=True, max_length=4, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='cartao_bandeira',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='pix_qr_code',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='pix_chave_destino',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='boleto_codigo_barras',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='boleto_linha_digitavel',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='boleto_vencimento',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='tentativas_pagamento',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='data_vencimento',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='observacoes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='ip_origem',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pagamentotransacao',
            name='user_agent',
            field=models.TextField(blank=True, null=True),
        ),

        # Atualizar choices dos campos existentes
        migrations.AlterField(
            model_name='pagamentotransacao',
            name='metodo',
            field=models.CharField(
                choices=[
                    ('CREDIT_CARD', 'Cartão de Crédito'),
                    ('DEBIT_CARD', 'Cartão de Débito'),
                    ('PIX', 'PIX'),
                    ('BOLETO', 'Boleto'),
                    ('MONEY', 'Dinheiro'),
                    ('BANK_TRANSFER', 'Transferência Bancária'),
                ],
                max_length=50
            ),
        ),
        migrations.AlterField(
            model_name='pagamentotransacao',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pendente'),
                    ('PROCESSING', 'Processando'),
                    ('PAID', 'Pago'),
                    ('FAILED', 'Falhou'),
                    ('CANCELLED', 'Cancelado'),
                    ('REFUNDED', 'Estornado'),
                ],
                default='PENDING',
                max_length=20
            ),
        ),

        # Adicionar índices para performance
        migrations.RunSQL(
            "CREATE INDEX idx_pagamento_status_data ON seu_app_pagamentotransacao(status, criado_em);",
            reverse_sql="DROP INDEX idx_pagamento_status_data;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_pagamento_codigo ON seu_app_pagamentotransacao(codigo_transacao);",
            reverse_sql="DROP INDEX idx_pagamento_codigo;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_pagamento_gateway ON seu_app_pagamentotransacao(gateway_transacao_id);",
            reverse_sql="DROP INDEX idx_pagamento_gateway;"
        ),
    ]

