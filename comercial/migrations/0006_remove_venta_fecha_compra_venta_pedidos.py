# Generated by Django 5.2 on 2025-04-29 13:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0005_cotizacion_detallecotizacion'),
        ('importacion', '0003_alter_tranferenciascarga_trm_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='venta',
            name='fecha_compra',
        ),
        migrations.AddField(
            model_name='venta',
            name='pedidos',
            field=models.ManyToManyField(to='importacion.pedido', verbose_name='Pedidos'),
        ),
    ]
