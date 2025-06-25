from django.shortcuts import get_object_or_404
from .models import Estabelecimento, Plano


class PlanoMiddleware:
    """Middleware para adicionar informações do plano ao request"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                estabelecimento = request.user.estabelecimento
                request.plano_ativo = estabelecimento.plano
                request.estabelecimento = estabelecimento
            except Estabelecimento.DoesNotExist:
                request.plano_ativo = None
                request.estabelecimento = None
        else:
            request.plano_ativo = None
            request.estabelecimento = None

        response = self.get_response(request)
        return response