/**
 * JunkOS Landing Page
 * Clean, refined interactions
 */

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Scroll Animations (Intersection Observer)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, index) => {
        if (entry.isIntersecting) {
            setTimeout(() => {
                entry.target.classList.add('visible');
            }, index * 100);
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll('[data-animate]');
    animatedElements.forEach(el => observer.observe(el));

    // Force video play on mobile
    const video = document.querySelector('.hero-video');
    if (video) {
        video.muted = true;
        video.setAttribute('playsinline', '');

        const tryPlay = () => {
            video.muted = true;
            const p = video.play();
            if (p) p.catch(() => {});
        };

        tryPlay();
        video.addEventListener('loadeddata', tryPlay);
        ['touchstart', 'touchend', 'click', 'scroll'].forEach(evt => {
            document.addEventListener(evt, tryPlay, { once: true });
        });
    }
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Smooth Scroll for Anchor Links
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Navbar Scroll Effect
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

let lastScrollY = window.scrollY;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    const currentScrollY = window.scrollY;

    if (currentScrollY > lastScrollY && currentScrollY > 100) {
        navbar.style.transform = 'translateY(-120%)';
    } else {
        navbar.style.transform = 'translateY(0)';
    }

    lastScrollY = currentScrollY;
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Hide Scroll Indicator After Scroll
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

window.addEventListener('scroll', () => {
    const scrollIndicator = document.querySelector('.scroll-indicator');
    if (scrollIndicator && window.scrollY > 100) {
        scrollIndicator.style.opacity = '0';
        scrollIndicator.style.pointerEvents = 'none';
    }
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Mobile Hamburger Menu
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const navToggle = document.querySelector('.nav-toggle');
const navLinks = document.querySelector('.nav-links');

if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
        const isOpen = navToggle.getAttribute('aria-expanded') === 'true';
        navToggle.setAttribute('aria-expanded', !isOpen);
        navLinks.classList.toggle('open');
    });

    // Close menu when a nav link is clicked
    navLinks.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            navToggle.setAttribute('aria-expanded', 'false');
            navLinks.classList.remove('open');
        });
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FAQ Accordion
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

document.querySelectorAll('.faq-question').forEach(button => {
    button.addEventListener('click', () => {
        const isExpanded = button.getAttribute('aria-expanded') === 'true';
        const answer = button.nextElementSibling;

        // Close all other FAQs
        document.querySelectorAll('.faq-question').forEach(otherBtn => {
            if (otherBtn !== button) {
                otherBtn.setAttribute('aria-expanded', 'false');
                otherBtn.nextElementSibling.style.maxHeight = null;
            }
        });

        // Toggle current
        button.setAttribute('aria-expanded', !isExpanded);
        if (!isExpanded) {
            answer.style.maxHeight = answer.scrollHeight + 'px';
        } else {
            answer.style.maxHeight = null;
        }
    });
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Analytics Event Tracking
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

document.querySelectorAll('a[href^="tel:"]').forEach(link => {
    link.addEventListener('click', function () {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'phone_call', {
                'phone_number': this.getAttribute('href')
            });
        }
    });
});

document.querySelectorAll('a[href^="sms:"]').forEach(link => {
    link.addEventListener('click', function () {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'sms_sent', {
                'phone_number': this.getAttribute('href')
            });
        }
    });
});
