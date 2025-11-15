import django_tables2 as tables
from .models import TranferenciasExportador, TranferenciasAduana, TranferenciasCarga
from comercial.models import TranferenciasCliente

class TranferenciasExportadorTable(tables.Table):
    actions = tables.TemplateColumn(
        template_name='transferencias/includes/actions_column.html',
        verbose_name='Acciones',
        orderable=False
    )

    class Meta:
        model = TranferenciasExportador
        template_name = "django_tables2/bootstrap5.html"
        fields = ('id', 'exportador', 'referencia', 'fecha_transferencia', 'valor_transferencia', 'valor_transferencia_eur', 'trm', 'concepto', 'saldo_disponible', 'actions')
        attrs = {"class": "table table-striped table-hover"}
        order_by = ('-fecha_transferencia',)

class TranferenciasAduanaTable(tables.Table):
    actions = tables.TemplateColumn(
        template_name='transferencias/includes/actions_column.html',
        verbose_name='Acciones',
        orderable=False
    )

    class Meta:
        model = TranferenciasAduana
        template_name = "django_tables2/bootstrap5.html"
        fields = ('id', 'agencia_aduana', 'referencia', 'fecha_transferencia', 'valor_transferencia', 'concepto', 'saldo_disponible', 'actions')
        attrs = {"class": "table table-striped table-hover"}
        order_by = ('-fecha_transferencia',)

class TranferenciasCargaTable(tables.Table):
    actions = tables.TemplateColumn(
        template_name='transferencias/includes/actions_column.html',
        verbose_name='Acciones',
        orderable=False
    )

    class Meta:
        model = TranferenciasCarga
        template_name = "django_tables2/bootstrap5.html"
        fields = ('id', 'agencia_carga', 'referencia', 'fecha_transferencia', 'valor_transferencia', 'valor_transferencia_eur', 'trm', 'concepto', 'saldo_disponible', 'actions')
        attrs = {"class": "table table-striped table-hover"}
        order_by = ('-fecha_transferencia',)

class TranferenciasClienteTable(tables.Table):
    actions = tables.TemplateColumn(
        template_name='transferencias/includes/actions_column.html',
        verbose_name='Acciones',
        orderable=False
    )

    class Meta:
        model = TranferenciasCliente
        template_name = "django_tables2/bootstrap5.html"
        fields = ('id', 'cliente', 'referencia', 'fecha_transferencia', 'valor_transferencia', 'concepto', 'saldo_disponible', 'actions')
        attrs = {"class": "table table-striped table-hover"}
        order_by = ('-fecha_transferencia',)
