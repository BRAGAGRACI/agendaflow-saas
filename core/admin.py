from django.contrib import admin
from .models import Cliente, Agendamento, BloqueioHorario, ListaEspera, Prontuario, Plano, Estabelecimento, \
    Profissional, Servico, LancamentoFinanceiro, Assinatura, PagBankTransaction, InsightIA, Pagamento, \
    AgendamentoRecorrenteProduto, MovimentacaoEstoque, AgendamentoProduto, Produto, Venda, VendaProduto

admin.site.register(Cliente)
admin.site.register(Agendamento)
admin.site.register(BloqueioHorario)
admin.site.register(ListaEspera)
admin.site.register(Prontuario)
admin.site.register(Plano)
admin.site.register(Estabelecimento)
admin.site.register(Servico)
admin.site.register(Profissional)
admin.site.register(LancamentoFinanceiro)
admin.site.register(Assinatura)
admin.site.register(PagBankTransaction)
admin.site.register(Pagamento)
admin.site.register(AgendamentoRecorrenteProduto)
admin.site.register(InsightIA)
admin.site.register(MovimentacaoEstoque)
admin.site.register(AgendamentoProduto)
admin.site.register(Produto)
admin.site.register(Venda)
admin.site.register(VendaProduto)



