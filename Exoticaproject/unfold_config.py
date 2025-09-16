from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    "SITE_TITLE": "L&M Exótica",
    "SITE_HEADER": "L&M Exótica SAS",
    "SITE_SUBHEADER": "Administración L&M Exótica",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("img/favicon.jpg"),
        "dark": lambda request: static("img/favicon.jpg"),
    },
    "SITE_LOGO": {
        "light": lambda request: static("img/favicon.jpg"),
        "dark": lambda request: static("img/favicon.jpg"),
    },
    "SITE_SYMBOL": "agriculture",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "href": lambda request: static("img/favicon.ico"),
        },
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "LOGIN": {
        "image": lambda request: static("img/login-bg.jpg"),
        "redirect_after": reverse_lazy("admin:index"),
    },
    "BORDER_RADIUS": "6px",
    "COLORS": {
        "base": {
            "50": "249 250 251",
            "100": "243 244 246",
            "200": "229 231 235",
            "300": "209 213 219",
            "400": "156 163 175",
            "500": "107 114 128",
            "600": "75 85 99",
            "700": "55 65 81",
            "800": "31 41 55",
            "900": "17 24 39",
            "950": "3 7 18",
        },
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-600)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Dashboard"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                        "permission": lambda request: request.user.is_staff,
                    },
                ],
            },
            {
                "title": _("Administración"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Usuarios"),
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": _("Grupos"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                    {
                        "title": _("Logs del Sistema"),
                        "icon": "history",
                        "link": reverse_lazy("admin:admin_logentry_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
            {
                "title": _("Productos"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Frutas"),
                        "icon": "nutrition",
                        "link": reverse_lazy("admin:productos_fruta_changelist"),
                    },
                    {
                        "title": _("Presentaciones"),
                        "icon": "category",
                        "link": reverse_lazy("admin:productos_presentacion_changelist"),
                    },
                    {
                        "title": _("Lista Precios Importación"),
                        "icon": "price_change",
                        "link": reverse_lazy("admin:productos_listapreciosimportacion_changelist"),
                    },
                    {
                        "title": _("Lista Precios Ventas"),
                        "icon": "sell",
                        "link": reverse_lazy("admin:productos_listapreciosventas_changelist"),
                    },
                ],
            },
            {
                "title": _("Importación"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Exportadores"),
                        "icon": "flight_takeoff",
                        "link": reverse_lazy("admin:importacion_exportador_changelist"),
                    },
                    {
                        "title": _("Pedidos"),
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:importacion_pedido_changelist"),
                    },
                    {
                        "title": _("Detalle Pedidos"),
                        "icon": "list_alt",
                        "link": reverse_lazy("admin:importacion_detallepedido_changelist"),
                    },
                    {
                        "title": _("Transferencias Exportador"),
                        "icon": "send_money",
                        "link": reverse_lazy("admin:importacion_tranferenciasexportador_changelist"),
                    },
                    {
                        "title": _("Balance Exportador"),
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:importacion_balanceexportador_changelist"),
                    },
                    {
                        "title": _("Agencias de Aduana"),
                        "icon": "verified_user",
                        "link": reverse_lazy("admin:importacion_agenciaaduana_changelist"),
                    },
                    {
                        "title": _("Gastos Aduana"),
                        "icon": "payments",
                        "link": reverse_lazy("admin:importacion_gastosaduana_changelist"),
                    },
                    {
                        "title": _("Transferencias Aduna"),
                        "icon": "swap_horiz",
                        "link": reverse_lazy("admin:importacion_tranferenciasaduana_changelist"),
                    },
                    {
                        "title": _("Balance Gastos Aduana"),
                        "icon": "balance",
                        "link": reverse_lazy("admin:importacion_balancegastosaduana_changelist"),
                    },
                    {
                        "title": _("Agencias de Carga"),
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:importacion_agenciacarga_changelist"),
                    },
                    {
                        "title": _("Gastos Carga"),
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:importacion_gastoscarga_changelist"),
                    },
                    {
                        "title": _("Transferencias Carga"),
                        "icon": "sync_alt",
                        "link": reverse_lazy("admin:importacion_tranferenciascarga_changelist"),
                    },
                    {
                        "title": _("Balance Gastos Carga"),
                        "icon": "stacked_bar_chart",
                        "link": reverse_lazy("admin:importacion_balancegastoscarga_changelist"),
                    },
                    {
                        "title": _("Bodega"),
                        "icon": "warehouse",
                        "link": reverse_lazy("admin:importacion_bodega_changelist"),
                    },
                ],
            },
            {
                "title": _("Comercial"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Clientes"),
                        "icon": "people_alt",
                        "link": reverse_lazy("admin:comercial_cliente_changelist"),
                    },
                    {
                        "title": _("Ventas"),
                        "icon": "point_of_sale",
                        "link": reverse_lazy("admin:comercial_venta_changelist"),
                    },
                    {
                        "title": _("Detalle Ventas"),
                        "icon": "receipt",
                        "link": reverse_lazy("admin:comercial_detalleventa_changelist"),
                    },
                    {
                        "title": _("Cotizaciones"),
                        "icon": "request_quote",
                        "link": reverse_lazy("admin:comercial_cotizacion_changelist"),
                    },
                    {
                        "title": _("Detalles Cotizaciones"),
                        "icon": "description",
                        "link": reverse_lazy("admin:comercial_detallecotizacion_changelist"),
                    },
                    {
                        "title": _("Transferencias Cliente"),
                        "icon": "currency_exchange",
                        "link": reverse_lazy("admin:comercial_tranferenciascliente_changelist"),
                    },
                    {
                        "title": _("Balance Cliente"),
                        "icon": "account_balance_wallet",
                        "link": reverse_lazy("admin:comercial_balancecliente_changelist"),
                    },
                    {
                        "title": _("Logs de Correos"),
                        "icon": "email",
                        "link": reverse_lazy("admin:comercial_emaillog_changelist"),
                    },
                ],
            },
        ],
    },
}
