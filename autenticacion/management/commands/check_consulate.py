from django.core.management.base import BaseCommand
from autenticacion.check_consulate import check_consulate_website

class Command(BaseCommand):
    help = 'Checks the consulate website for changes and sends email notifications'

    def handle(self, *args, **options):
        check_consulate_website() 