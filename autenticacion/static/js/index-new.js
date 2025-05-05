// Material Design 3 Enhanced JavaScript for L&M Exotic Fruits
document.addEventListener('DOMContentLoaded', function() {
    // Get product items
    const productItems = document.querySelectorAll('.product-item');
    
    // Initialize AOS (Animate On Scroll) if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-in-out',
            once: true,
            mirror: false,
            disable: 'mobile'
        });
    }

    // Header scroll effect
    const header = document.querySelector('.header');
    if (header) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });
    }
    
    // Initialize Swiper if available
    if (typeof Swiper !== 'undefined') {
        const swiperContainer = document.querySelector('.product-swiper');
        
        if (swiperContainer) {
            const productSwiper = new Swiper('.product-swiper', {
                direction: 'horizontal',
                loop: true,
                slidesPerView: 1,
                spaceBetween: 30,
                centeredSlides: true,
                autoplay: {
                    delay: 5000,
                    disableOnInteraction: false,
                },
                speed: 800,
                effect: 'coverflow',
                coverflowEffect: {
                    rotate: 0,
                    stretch: 0,
                    depth: 100,
                    modifier: 1,
                    slideShadows: false,
                },
                breakpoints: {
                    640: {
                        slidesPerView: 2,
                        spaceBetween: 20
                    },
                    1024: {
                        slidesPerView: 3,
                        spaceBetween: 30
                    }
                },
                navigation: {
                    nextEl: '.swiper-button-next',
                    prevEl: '.swiper-button-prev',
                },
                pagination: {
                    el: '.swiper-pagination',
                    clickable: true,
                    dynamicBullets: true,
                },
            });
        }
    }

    // Enhanced Modal functionality
    const modal = document.getElementById('productModal');
    if (!modal) return; // Si no existe el modal, no continuamos
    
    const modalCloseButtons = document.querySelectorAll('.modal__close, .modal__close-btn');
    const modalTitle = document.getElementById('modalTitle');
    const modalImage = document.getElementById('modalImage');
    const modalDescription = document.getElementById('modalDescription');
    const modalFeatures = document.getElementById('modalFeatures');

    // Default features para frutas
    const defaultFeatures = [
        'Alta calidad garantizada',
        'Selección premium',
        'Importada directamente',
        'Disponible según temporada',
        'Máxima frescura'
    ];
    
    // Abrir modal con detalles del producto
    document.querySelectorAll('.btn--view-details').forEach(button => {
        button.addEventListener('click', () => {
            // Obtener datos directamente del producto en el HTML
            const productItem = button.closest('.product-item');
            if (!productItem) {
                return;
            }
            
            const productId = button.getAttribute('data-product');
            
            // Obtener datos básicos del producto desde el HTML
            const productTitle = productItem.querySelector('h3')?.textContent;
            const productImageElement = productItem.querySelector('.product-item__image');
            
            if (!productImageElement) {
                return;
            }
            
            const productImage = productImageElement.src;
            
            // Obtener descripción completa del producto desde el data attribute
            const productDesc = productItem.dataset.fullDescription || productItem.querySelector('p')?.textContent || 'Sin descripción disponible'; // Fallback just in case
            
            // Actualizar el modal con los datos
            modalTitle.textContent = productTitle || 'Fruta Exótica';
            modalImage.src = productImage;
            modalImage.alt = productTitle || 'Fruta Exótica';
            
            // Establecer la descripción completa
            modalDescription.textContent = productDesc;
            
            // Generar características (usar predeterminadas)
            if (modalFeatures) {
                modalFeatures.innerHTML = '';
                defaultFeatures.forEach(feature => {
                    const li = document.createElement('li');
                    li.textContent = feature;
                    modalFeatures.appendChild(li);
                });
            }
            
            // Mostrar el modal con transición suave
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
            
            // Focus en el botón de cerrar para accesibilidad
            setTimeout(() => {
                const closeBtn = modal.querySelector('.modal__close');
                if (closeBtn) closeBtn.focus();
            }, 100);
        });
    });

    // Función para cerrar el modal con transición suave
    function closeModal() {
        // Primero reducimos la opacidad
        modal.style.opacity = '0';
        modal.querySelector('.modal__dialog').style.transform = 'translateY(-20px)';
        
        // Luego de la transición, ocultamos el modal
        setTimeout(() => {
            modal.classList.remove('open');
            modal.style.opacity = '';
            modal.querySelector('.modal__dialog').style.transform = '';
            document.body.style.overflow = '';
        }, 300);
    }

    // Cerrar modal con animación mejorada
    modalCloseButtons.forEach(button => {
        button.addEventListener('click', closeModal);
    });

    // Cerrar modal al hacer clic fuera
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Cerrar con tecla ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('open')) {
            closeModal();
        }
    });

    // Navegación móvil
    const navToggle = document.querySelector('.nav__toggle');
    const navMenu = document.querySelector('.nav__list');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
            navToggle.setAttribute('aria-expanded', 
                navToggle.getAttribute('aria-expanded') === 'false' ? 'true' : 'false'
            );
        });
    }

    // Desplazamiento suave para enlaces de navegación
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                const headerOffset = document.querySelector('.header').offsetHeight;
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
                
                // Cerrar el menú móvil si está abierto
                if (navMenu && navMenu.classList.contains('active')) {
                    navMenu.classList.remove('active');
                    navToggle.setAttribute('aria-expanded', 'false');
                }
            }
        });
    });
});
