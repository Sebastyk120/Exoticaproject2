import requests
from bs4 import BeautifulSoup
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, time
import time as time_module

def check_consulate_website():
    # Target text to search for - more flexible search
    target_keywords = [
        "Las citas se habilitan de lunes a viernes",
        "partir de las 1:00 p.m hasta las 4:00 p.m",
        "Los dias festivos  no se habilita la plataforma"
    ]
    
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
            
            # Debug: Print part of the response to check content
            print(f"Status code: {response.status_code}")
            print(f"Content length: {len(response.text)}")
            
            # Check if ALL target keywords are present
            keywords_found = [keyword for keyword in target_keywords if keyword in response.text]
            all_keywords_present = len(keywords_found) == len(target_keywords)
            
            print(f"Keywords found: {len(keywords_found)}/{len(target_keywords)}")
            
            # Only send alert if keywords are missing (indicating real change)
            if not all_keywords_present:
                # Send email notification
                message = f'El texto de información sobre horarios de citas ha cambiado en la página del consulado. Keywords encontradas: {keywords_found}. Es posible que el sistema de citas esté ahora disponible.'
                subject = 'ALERTA: Cambio detectado - Consulado'
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    ['sebastyk120@gmail.com'],  # Replace with your email
                    fail_silently=False,
                )
                print("Email notification sent - Target keywords missing")
            else:
                print("All target keywords found - No action needed")
                
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