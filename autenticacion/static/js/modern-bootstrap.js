// Modern Bootstrap JavaScript for L&M Exotic Fruits
document.addEventListener('DOMContentLoaded', function() {
    // Initialize AOS Animation
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-out-cubic',
            once: true,
            offset: 100
        });
    }

    // Progress Bar
    const progressBar = document.getElementById('progressBar');
    
    function updateProgressBar() {
        const scrolled = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
        progressBar.style.width = scrolled + '%';
    }
    
    window.addEventListener('scroll', updateProgressBar);

    // Navbar Scroll Effect
    const navbar = document.querySelector('.custom-navbar');
    let lastScrollY = window.scrollY;

    function handleNavbarScroll() {
        const currentScrollY = window.scrollY;
        
        if (currentScrollY > 100) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        
        // Hide/show navbar on scroll
        if (currentScrollY > lastScrollY && currentScrollY > 200) {
            navbar.style.transform = 'translateY(-100%)';
        } else {
            navbar.style.transform = 'translateY(0)';
        }
        
        lastScrollY = currentScrollY;
    }

    window.addEventListener('scroll', handleNavbarScroll);

    // Smooth Scrolling for Navigation Links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            
            if (target) {
                const offsetTop = target.getBoundingClientRect().top + window.pageYOffset - 80;
                
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
                
                // Close mobile menu if open
                const navbarCollapse = document.querySelector('.navbar-collapse');
                if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                    const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse);
                    if (bsCollapse) bsCollapse.hide();
                }
            }
        });
    });

    // Initialize Swiper
    if (typeof Swiper !== 'undefined') {
        const productSwiper = new Swiper('.product-swiper', {
            slidesPerView: 1,
            spaceBetween: 30,
            loop: true,
            autoplay: {
                delay: 4000,
                disableOnInteraction: false,
                pauseOnMouseEnter: true,
            },
            pagination: {
                el: '.swiper-pagination',
                clickable: true,
                dynamicBullets: true,
            },
            navigation: {
                nextEl: '.swiper-button-next',
                prevEl: '.swiper-button-prev',
            },
            breakpoints: {
                640: {
                    slidesPerView: 2,
                    spaceBetween: 20,
                },
                768: {
                    slidesPerView: 2,
                    spaceBetween: 30,
                },
                1024: {
                    slidesPerView: 3,
                    spaceBetween: 30,
                },
            }
        });
    }

    // Product Modal Functionality (Bootstrap 5)
    const productModalElement = document.getElementById('productModal');
    let productModal = null;
    
    if (productModalElement) {
        productModal = new bootstrap.Modal(productModalElement);
        
        const modalTitle = document.getElementById('productModalLabel');
        const modalImage = document.getElementById('modalImage');
        const modalDescription = document.getElementById('modalDescription');
        const modalFeatures = document.getElementById('modalFeatures');

        // Premium features for fruits
        const premiumFeatures = [
            'Calidad premium garantizada',
            'Selección cuidadosa y rigurosa',
            'Importación directa del origen',
            'Frescura máxima asegurada',
            'Disponibilidad según temporada',
            'Certificados de calidad',
            'Distribución especializada'
        ];

        // Handle product detail buttons
        document.querySelectorAll('.btn-view-details').forEach(button => {
            button.addEventListener('click', function() {
                const productCard = this.closest('.product-card');
                if (!productCard) return;
                
                const productTitle = productCard.querySelector('.product-title')?.textContent || 'Fruta Exótica';
                const productImage = productCard.querySelector('.product-image')?.src || '';
                const fullDescription = productCard.dataset.fullDescription || 
                                      productCard.querySelector('.product-description')?.textContent ||
                                      'Fruta exótica de alta calidad importada especialmente para nuestros clientes.';

                // Update modal content
                if (modalTitle) modalTitle.textContent = productTitle;
                if (modalImage) {
                    modalImage.src = productImage;
                    modalImage.alt = productTitle;
                }
                if (modalDescription) modalDescription.textContent = fullDescription;

                // Populate features
                if (modalFeatures) {
                    modalFeatures.innerHTML = '';
                    premiumFeatures.forEach(feature => {
                        const li = document.createElement('li');
                        li.className = 'd-flex align-items-center mb-2';
                        li.innerHTML = `<i class="fas fa-check text-primary me-2"></i>${feature}`;
                        modalFeatures.appendChild(li);
                    });
                }

                // Show modal
                productModal.show();
            });
        });
    }

    // Contact Form Enhancement
    const contactForm = document.querySelector('.contact-form');
    if (contactForm) {
        const submitButton = contactForm.querySelector('button[type="submit"]');
        const originalButtonText = submitButton?.innerHTML;

        contactForm.addEventListener('submit', function() {
            if (submitButton) {
                submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Enviando...';
                submitButton.disabled = true;

                // Reset button after timeout if form doesn't redirect
                setTimeout(() => {
                    if (originalButtonText) {
                        submitButton.innerHTML = originalButtonText;
                        submitButton.disabled = false;
                    }
                }, 5000);
            }
        });

        // Enhanced form field interactions
        const formControls = contactForm.querySelectorAll('.form-control');
        formControls.forEach(control => {
            control.addEventListener('focus', function() {
                this.parentElement.classList.add('focused');
            });

            control.addEventListener('blur', function() {
                if (!this.value.trim()) {
                    this.parentElement.classList.remove('focused');
                }
            });

            // Check if field has value on load
            if (control.value && control.value.trim()) {
                control.parentElement.classList.add('focused');
            }
        });
    }

    // Toast Notification System (Bootstrap 5)
    function showToast(message, type = 'success') {
        const toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) return;
        
        const toastId = 'toast-' + Date.now();
        const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-triangle';
        const bgClass = type === 'success' ? 'bg-success' : 'bg-danger';
        
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="5000">
                <div class="toast-header ${bgClass} text-white">
                    <i class="fas ${iconClass} me-2"></i>
                    <strong class="me-auto">${type === 'success' ? 'Éxito' : 'Error'}</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const bsToast = new bootstrap.Toast(toastElement);
        
        bsToast.show();
        
        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', function() {
            this.remove();
        });
    }

    // Check for Django messages and show as toasts
    const djangoMessages = document.querySelectorAll('.alert');
    djangoMessages.forEach(message => {
        const messageType = message.classList.contains('alert-success') ? 'success' : 'error';
        const messageText = message.textContent.trim();
        if (messageText) {
            showToast(messageText, messageType);
        }
        message.remove();
    });

    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-visible');
            }
        });
    }, observerOptions);

    // Observe elements for animation
    document.querySelectorAll('.stat-item, .value-card, .product-card, .contact-item').forEach(el => {
        observer.observe(el);
    });

    // Counter Animation for Stats
    function animateCounters() {
        const counters = document.querySelectorAll('.stat-number');
        
        counters.forEach(counter => {
            const target = parseInt(counter.textContent.replace(/\D/g, ''));
            if (isNaN(target)) return;
            
            let current = 0;
            const increment = target / 60;
            const hasPlus = counter.textContent.includes('+');
            
            const updateCounter = () => {
                if (current < target) {
                    current += increment;
                    counter.textContent = Math.ceil(current) + (hasPlus ? '+' : '');
                    requestAnimationFrame(updateCounter);
                } else {
                    counter.textContent = target + (hasPlus ? '+' : '');
                }
            };
            
            // Start animation when element is visible
            const counterObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        updateCounter();
                        counterObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.5 });
            
            counterObserver.observe(counter);
        });
    }

    // Initialize counter animations
    animateCounters();

    // WhatsApp button pulse animation
    const whatsappBtn = document.querySelector('.whatsapp-btn');
    if (whatsappBtn) {
        whatsappBtn.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
        });
        
        whatsappBtn.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    }

    // Lazy loading for images
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                    }
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Smooth reveal animations for sections
    const revealSections = document.querySelectorAll('section');
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, { threshold: 0.15 });

    revealSections.forEach(section => {
        revealObserver.observe(section);
    });

    // Performance optimization: Debounced scroll handler
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Apply debounced scroll for performance
    const debouncedScrollHandler = debounce(() => {
        updateProgressBar();
        handleNavbarScroll();
    }, 10);

    window.addEventListener('scroll', debouncedScrollHandler);

    // Keyboard navigation improvements
    document.addEventListener('keydown', function(e) {
        // Close modal with Escape key
        if (e.key === 'Escape' && productModal) {
            productModal.hide();
        }
        
        // Focus management for accessibility
        if (e.key === 'Tab' && document.querySelector('.modal.show')) {
            // Trap focus within modal when it's open
            const modal = document.querySelector('.modal.show');
            const focusableElements = modal.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (e.shiftKey && document.activeElement === firstElement) {
                lastElement.focus();
                e.preventDefault();
            } else if (!e.shiftKey && document.activeElement === lastElement) {
                firstElement.focus();
                e.preventDefault();
            }
        }
    });

    // Add loading states for buttons
    document.querySelectorAll('button[type="submit"]').forEach(button => {
        button.addEventListener('click', function() {
            if (this.form && this.form.checkValidity()) {
                this.classList.add('loading');
            }
        });
    });

    // Initialize tooltips (Bootstrap 5)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers (Bootstrap 5)
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    console.log('L&M Exotic Fruits - Modern Bootstrap functionality loaded successfully!');
});

// Global function to show toast notifications
window.showToast = function(message, type = 'success') {
    const event = new CustomEvent('showToast', {
        detail: { message, type }
    });
    document.dispatchEvent(event);
};

// Global toast event listener
document.addEventListener('showToast', function(e) {
    const { message, type } = e.detail;
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;
    
    const toastId = 'toast-' + Date.now();
    const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-triangle';
    const bgClass = type === 'success' ? 'bg-success' : 'bg-danger';
    
    const toastHtml = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="5000">
            <div class="toast-header ${bgClass} text-white">
                <i class="fas ${iconClass} me-2"></i>
                <strong class="me-auto">${type === 'success' ? 'Éxito' : 'Error'}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    const bsToast = new bootstrap.Toast(toastElement);
    
    bsToast.show();
    
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
});
