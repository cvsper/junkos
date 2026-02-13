/**
 * Umuve Marketing Landing Page - Interactive Features
 * - Smooth scroll navigation
 * - Mobile menu toggle
 * - FAQ accordion
 * - Demo modal
 * - Form validation
 * - Scroll animations
 */

// ========== DOM READY ==========
document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
    initSmoothScroll();
    initMobileMenu();
    initFAQ();
    initModal();
    initFormValidation();
    initScrollAnimations();
});

// ========== NAVBAR ==========
function initNavbar() {
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
}

// ========== SMOOTH SCROLL ==========
function initSmoothScroll() {
    // Handle all anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            
            // Skip if it's just "#" or for modal/non-section links
            if (href === '#' || href === '#demo') {
                return;
            }
            
            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                
                const navbarHeight = document.querySelector('.navbar').offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navbarHeight - 20;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
                
                // Close mobile menu if open
                const mobileMenu = document.querySelector('.nav-links');
                if (mobileMenu && mobileMenu.classList.contains('active')) {
                    mobileMenu.classList.remove('active');
                    document.querySelector('.mobile-menu-toggle').classList.remove('active');
                }
            }
        });
    });
}

// ========== MOBILE MENU ==========
function initMobileMenu() {
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    const navActions = document.querySelector('.nav-actions');
    
    if (!menuToggle) return;
    
    menuToggle.addEventListener('click', () => {
        menuToggle.classList.toggle('active');
        navLinks.classList.toggle('active');
        navActions.classList.toggle('active');
        
        // Prevent body scroll when menu is open
        document.body.style.overflow = menuToggle.classList.contains('active') ? 'hidden' : '';
    });
    
    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.navbar') && menuToggle.classList.contains('active')) {
            menuToggle.classList.remove('active');
            navLinks.classList.remove('active');
            navActions.classList.remove('active');
            document.body.style.overflow = '';
        }
    });
}

// ========== FAQ ACCORDION ==========
function initFAQ() {
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        
        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            
            // Close all other FAQ items
            faqItems.forEach(otherItem => {
                if (otherItem !== item) {
                    otherItem.classList.remove('active');
                }
            });
            
            // Toggle current item
            if (isActive) {
                item.classList.remove('active');
            } else {
                item.classList.add('active');
            }
        });
    });
}

// ========== MODAL ==========
function initModal() {
    const modal = document.getElementById('demo-modal');
    const modalTriggers = document.querySelectorAll('a[href="#demo"]');
    const modalClose = document.querySelector('.modal-close');
    
    if (!modal) return;
    
    // Open modal
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    });
    
    // Close modal
    if (modalClose) {
        modalClose.addEventListener('click', () => {
            closeModal();
        });
    }
    
    // Close on outside click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeModal();
        }
    });
    
    function closeModal() {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// ========== FORM VALIDATION ==========
function initFormValidation() {
    const form = document.getElementById('demo-form');
    
    if (!form) return;
    
    // Real-time validation
    const inputs = form.querySelectorAll('input[required], select[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', () => {
            validateInput(input);
        });
        
        input.addEventListener('input', () => {
            if (input.classList.contains('error')) {
                validateInput(input);
            }
        });
    });
    
    // Form submission
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        
        let isValid = true;
        
        // Validate all required fields
        inputs.forEach(input => {
            if (!validateInput(input)) {
                isValid = false;
            }
        });
        
        if (isValid) {
            handleFormSubmit(form);
        } else {
            // Scroll to first error
            const firstError = form.querySelector('.error');
            if (firstError) {
                firstError.focus();
            }
        }
    });
}

function validateInput(input) {
    const value = input.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // Remove existing error
    removeError(input);
    
    // Check if required field is empty
    if (input.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'This field is required';
    }
    
    // Email validation
    if (input.type === 'email' && value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        }
    }
    
    // Phone validation
    if (input.type === 'tel' && value) {
        const phoneRegex = /^[\d\s\-\+\(\)]{10,}$/;
        if (!phoneRegex.test(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid phone number';
        }
    }
    
    if (!isValid) {
        showError(input, errorMessage);
    }
    
    return isValid;
}

function showError(input, message) {
    input.classList.add('error');
    
    // Create error message element if it doesn't exist
    let errorEl = input.parentElement.querySelector('.error-message');
    if (!errorEl) {
        errorEl = document.createElement('span');
        errorEl.className = 'error-message';
        errorEl.style.color = 'var(--error)';
        errorEl.style.fontSize = '12px';
        errorEl.style.marginTop = '4px';
        input.parentElement.appendChild(errorEl);
    }
    errorEl.textContent = message;
}

function removeError(input) {
    input.classList.remove('error');
    const errorEl = input.parentElement.querySelector('.error-message');
    if (errorEl) {
        errorEl.remove();
    }
}

function handleFormSubmit(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    // Show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Submitting...';
    submitBtn.disabled = true;
    
    // Simulate API call (replace with actual endpoint)
    setTimeout(() => {
        console.log('Form submitted:', data);
        
        // Show success message
        alert('Thank you! We\'ll be in touch within 24 hours to schedule your demo.');
        
        // Reset form
        form.reset();
        
        // Close modal
        const modal = document.getElementById('demo-modal');
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        
        // Reset button
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
        
        // In production, replace with actual API call:
        // fetch('/api/demo-request', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(data)
        // })
        // .then(response => response.json())
        // .then(data => {
        //     // Handle success
        // })
        // .catch(error => {
        //     // Handle error
        // });
    }, 1500);
}

// ========== SCROLL ANIMATIONS ==========
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe elements for animation
    const animatedElements = document.querySelectorAll(
        '.feature-card, .testimonial-card, .pricing-card, .faq-item'
    );
    
    animatedElements.forEach(el => {
        observer.observe(el);
    });
}

// ========== UTILITY FUNCTIONS ==========

// Track CTA clicks (for analytics)
function trackCTAClick(ctaName) {
    console.log('CTA clicked:', ctaName);
    
    // In production, integrate with analytics:
    // gtag('event', 'click', {
    //     event_category: 'CTA',
    //     event_label: ctaName
    // });
}

// Add click tracking to CTA buttons
document.querySelectorAll('.btn-cta').forEach(btn => {
    btn.addEventListener('click', () => {
        trackCTAClick(btn.textContent);
    });
});

// ========== PERFORMANCE ==========

// Lazy load images (if you add images later)
if ('loading' in HTMLImageElement.prototype) {
    const images = document.querySelectorAll('img[loading="lazy"]');
    images.forEach(img => {
        img.src = img.dataset.src;
    });
} else {
    // Fallback for browsers that don't support lazy loading
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/lazysizes/5.3.2/lazysizes.min.js';
    document.body.appendChild(script);
}

// Preload critical fonts
const fontPreload = document.createElement('link');
fontPreload.rel = 'preload';
fontPreload.as = 'font';
fontPreload.type = 'font/woff2';
fontPreload.crossOrigin = 'anonymous';

// ========== CONSOLE WELCOME MESSAGE ==========
console.log(
    '%c🚛 Umuve Marketing Site',
    'font-size: 20px; font-weight: bold; color: #6366F1;'
);
console.log(
    '%cBuilt with ❤️ for junk removal professionals',
    'font-size: 12px; color: #64748B;'
);
