from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from importacion.models import Exportador
from productos.models import Fruta, Presentacion


# Modulo Ventas.




class Cliente(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    Domicilio = models.CharField(max_length=255, verbose_name="Domicilio:")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad", null=True, blank=True)
    cif = models.CharField(max_length=20, verbose_name="Código  CIF", null=True, blank=True)
    email = models.EmailField(verbose_name="Correo")
    email2 = models.EmailField(verbose_name="Correo 2", blank=True, null=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    dias_pago = models.IntegerField(max_length=2, verbose_name="Días de pago")

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']






