# signals.py - Para ações automáticas quando limites são atingidos
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Profissional, Estabelecimento


@receiver(pre_save, sender=Profissional)
def verificar_limite_antes_salvar(sender, instance, **kwargs):
    """Signal para verificar limite antes de salvar profissional"""
    if not instance.pk:  # Apenas para novos profissionais
        estabelecimento = instance.estabelecimento
        profissionais_atuais = estabelecimento.profissional_set.filter(ativo=True).count()

        if profissionais_atuais >= estabelecimento.plano.max_profissionais:
            raise Exception(
                f"Limite de {estabelecimento.plano.max_profissionais} profissionais "
                f"atingido para o plano {estabelecimento.plano.get_nome_display()}."
            )


@receiver(post_save, sender=Profissional)
def notificar_limite_proximo(sender, instance, created, **kwargs):
    """Notificar quando estiver próximo do limite"""
    if created:
        estabelecimento = instance.estabelecimento
        total_profissionais = estabelecimento.profissional_set.filter(ativo=True).count()
        limite = estabelecimento.plano.max_profissionais

        # Notificar quando atingir 80% do limite
        if total_profissionais / limite >= 0.8:
            # Aqui você pode enviar um email ou notificação
            print(f"AVISO: {estabelecimento.nome} está próximo do limite de profissionais!")
