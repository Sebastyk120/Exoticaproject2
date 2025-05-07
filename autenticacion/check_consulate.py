import requests
from bs4 import BeautifulSoup
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, time
import time as time_module

def check_consulate_website():
    # Target text to search for
    target_text = "En este momento, la plataforma se encuentra cerrada. Se habilitará de lunes a viernes entre las 12:00 y 4:00 p.m. (la hora exacta en que se habilita para solicitar cita es aleatoria). Los días festivos no se habilita la plataforma."
    
    while True:
        # Get current time
        current_time = datetime.now().time()
        end_time = time(17, 30)  # 17:30
        
        # Check if we should stop
        if current_time >= end_time:
            print("Hora límite alcanzada (17:30). Deteniendo el script.")
            break
            
        try:
            print(f"Verificando página a las {datetime.now().strftime('%H:%M:%S')}")
            # Make request to the website
            response = requests.get('https://citasmadridconsulado.com/')
            response.raise_for_status()  # Raise an exception for bad status codes
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search for the target text
            if target_text not in response.text:
                # Send email notification
                send_mail(
                    'Alerta: Cambio en la página del Consulado',
                    'El texto de cierre de plataforma no se encontró en la página del consulado. Por favor, verifica manualmente.',
                    settings.DEFAULT_FROM_EMAIL,
                    ['sebastyk120@gmail.com'],  # Replace with your email
                    fail_silently=False,
                )
                print("Email notification sent - Target text not found")
            else:
                print("Target text found - No action needed")
                
        except Exception as e:
            # Send email in case of any error
            send_mail(
                'Error al verificar página del Consulado',
                f'Se produjo un error al verificar la página del consulado: {str(e)}',
                settings.DEFAULT_FROM_EMAIL,
                ['sebastyk120@gmail.com'],  # Replace with your email
                fail_silently=False,
            )
            print(f"Error occurred: {str(e)}")
        
        # Wait for 5 minutes before next check
        print("Esperando 5 minutos para la siguiente verificación...")
        time_module.sleep(300)  # 300 seconds = 5 minutes

if __name__ == "__main__":
    check_consulate_website() 