from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def plano_required(funcao_verificacao):
    """
    Decorator para verificar limitações do plano
    funcao_verificacao deve retornar True se o usuário pode acessar a funcionalidade
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            try:
                estabelecimento = request.user.estabelecimento
                if not funcao_verificacao(estabelecimento):
                    messages.error(
                        request,
                        "Esta funcionalidade não está disponível no seu plano atual. "
                        "Atualize seu plano para ter acesso."
                    )
                    return redirect('planos')
            except:
                messages.error(request, "Erro ao verificar permissões do plano.")
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def pode_adicionar_profissional(estabelecimento):
    """Função para verificar se pode adicionar profissional"""
    return estabelecimento.pode_adicionar_profissional()


def tem_integracao_pagseguro(estabelecimento):
    """Função para verificar se tem integração PagSeguro"""
    return estabelecimento.plano.tem_integracao_pagseguro


def tem_controle_estoque(estabelecimento):
    """Função para verificar se tem controle de estoque"""
    return estabelecimento.plano.tem_controle_estoque


def tem_insights_ia(estabelecimento):
    """Função para verificar se tem insights IA"""
    return estabelecimento.plano.tem_insights_ia