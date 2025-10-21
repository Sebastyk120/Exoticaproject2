# Generated migration for EmailLog attachments support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0010_venta_origen'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='archivo_adjunto',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='email_attachments/',
                verbose_name='Archivo Adjunto'
            ),
        ),
        migrations.AlterField(
            model_name='emaillog',
            name='documentos_adjuntos',
            field=models.TextField(
                blank=True,
                help_text='Nombres de archivos adjuntos separados por coma (heredado)',
                null=True,
                verbose_name='Documentos Adjuntos (Heredado)'
            ),
        ),
    ]
