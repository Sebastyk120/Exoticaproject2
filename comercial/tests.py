UNFOLD = {
    "SITE_TITLE": "Heavens Fruits",
    "SITE_HEADER": "Heavens Fruits SAS",
    "SITE_SUBHEADER": "Heavens Fruits SAS",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("img/favicon.png"),
        "dark": lambda request: static("img/favicon.png"),
    },
    "SITE_LOGO": {
        "light": lambda request: static("img/favicon.png"),
        "dark": lambda request: static("img/favicon.png"),
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
    # Desactivamos el control de login de Unfold para usar nuestro propio sistema
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
                "title": _("Inventarios"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Inventario"),
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:inventarios_inventario_changelist"),
                    },
                    {
                        "title": _("Items"),
                        "icon": "inventory",
                        "link": reverse_lazy("admin:inventarios_item_changelist"),
                    },
                    {
                        "title": _("Bodegas"),
                        "icon": "warehouse",
                        "link": reverse_lazy("admin:inventarios_bodega_changelist"),
                    },
                    {
                        "title": _("Proveedores"),
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:inventarios_proveedor_changelist"),
                    },
                    {
                        "title": _("Movimientos"),
                        "icon": "sync_alt",
                        "link": reverse_lazy("admin:inventarios_movimiento_changelist"),
                    },
                ],
            },
            {
                "title": _("Comercial"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Pedidos"),
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:comercial_pedido_changelist"),
                    },
                    {
                        "title": _("Detalle Pedidos"),
                        "icon": "list_alt",
                        "link": reverse_lazy("admin:comercial_detallepedido_changelist"),
                    },
                    {
                        "title": _("Clientes"),
                        "icon": "people_alt",
                        "link": reverse_lazy("admin:comercial_cliente_changelist"),
                    },
                    {
                        "title": _("Exportadores"),
                        "icon": "flight_takeoff",
                        "link": reverse_lazy("admin:comercial_exportador_changelist"),
                    },
                    {
                        "title": _("Referencias"),
                        "icon": "label",
                        "link": reverse_lazy("admin:comercial_referencias_changelist"),
                    },
                    {
                        "title": _("Frutas"),
                        "icon": "nutrition",
                        "link": reverse_lazy("admin:comercial_fruta_changelist"),
                    },
                    {
                        "title": _("Presentaciones"),
                        "icon": "category",
                        "link": reverse_lazy("admin:comercial_presentacion_changelist"),
                    },
                    {
                        "title": _("Tipos de Caja"),
                        "icon": "dataset",
                        "link": reverse_lazy("admin:comercial_tipocaja_changelist"),
                    },
                    {
                        "title": _("Contenedores"),
                        "icon": "forest",
                        "link": reverse_lazy("admin:comercial_contenedor_changelist"),
                    },
                    {
                        "title": _("Aerolíneas"),
                        "icon": "flight",
                        "link": reverse_lazy("admin:comercial_aerolinea_changelist"),
                    },
                    {
                        "title": _("Destinos IATA"),
                        "icon": "location_on",
                        "link": reverse_lazy("admin:comercial_iata_changelist"),
                    },
                    {
                        "title": _("Agencias de Carga"),
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:comercial_agenciacarga_changelist"),
                    },
                    {
                        "title": _("SubExportadoras"),
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:comercial_subexportadora_changelist"),
                    },
                    {
                        "title": _("Intermediarios"),
                        "icon": "person",
                        "link": reverse_lazy("admin:comercial_intermediario_changelist"),
                    },
                    {
                        "title": _("Presentacion Referencia"),
                        "icon": "category",
                        "link": reverse_lazy("admin:comercial_presentacionreferencia_changelist"),
                    },
                    {
                        "title": _("Autorizacion Cancelacion"),
                        "icon": "cancel",
                        "link": reverse_lazy("admin:comercial_autorizacioncancelacion_changelist"),
                    },
                    {
                        "title": _("Cliente Presentacion"),
                        "icon": "people",
                        "link": reverse_lazy("admin:comercial_clientepresentacion_changelist"),
                    },
                ],
            },
            {
                "title": _("Nacionales"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Compras Nacionales"),
                        "icon": "shopping_bag",
                        "link": reverse_lazy("admin:nacionales_compranacional_changelist"),
                    },
                    {
                        "title": _("Ventas Nacionales"),
                        "icon": "sell",
                        "link": reverse_lazy("admin:nacionales_ventanacional_changelist"),
                    },
                    {
                        "title": _("Reporte Calidad Exportador"),
                        "icon": "assessment",
                        "link": reverse_lazy("admin:nacionales_reportecalidadexportador_changelist"),
                    },
                    {
                        "title": _("Reporte Calidad Proveedor"),
                        "icon": "source",
                        "link": reverse_lazy("admin:nacionales_reportecalidadproveedor_changelist"),
                    },
                    {
                        "title": _("Proveedores Nacionales"),
                        "icon": "handshake",
                        "link": reverse_lazy("admin:nacionales_proveedornacional_changelist"),
                    },
                    {
                        "title": _("Empaques"),
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:nacionales_empaque_changelist"),
                    },
                    {
                        "title": _("Transferencias"),
                        "icon": "swap_horiz",
                        "link": reverse_lazy("admin:nacionales_transferenciasproveedor_changelist"),
                    },
                    {
                        "title": _("Facturación Exportadores"),
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:nacionales_facturacionexportadores_changelist"),
                    },
                    {
                        "title": _("Balance Proveedor"),
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:nacionales_balanceproveedor_changelist"),
                    },
                ],
            },
            {
                "title": _("Cartera"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Cotización Etnico"),
                        "icon": "attach_money",
                        "link": reverse_lazy("admin:cartera_cotizacionetnico_changelist"),
                    },
                    {
                        "title": _("Cotización Fieldex"),
                        "icon": "monetization_on",
                        "link": reverse_lazy("admin:cartera_cotizacionfieldex_changelist"),
                    },
                    {
                        "title": _("Cotización Juan"),
                        "icon": "paid",
                        "link": reverse_lazy("admin:cartera_cotizacionjuan_changelist"),
                    },
                ],
            },
        ],
    },
}