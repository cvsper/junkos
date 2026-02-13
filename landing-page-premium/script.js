/**
 * Umuve Landing Page
 * Clean, refined interactions with stagger animations,
 * counter animation, parallax hero, and smart navbar.
 */

(function () {
    'use strict';

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Cached DOM references
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    const navbar = document.querySelector('.navbar');
    const heroVideo = document.querySelector('.hero-video');
    const heroMobileImg = document.querySelector('.hero-mobile-img');
    const scrollIndicator = document.querySelector('.scroll-indicator');
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Scroll Animation (IntersectionObserver)
    // Handles both standard [data-animate] and
    // staggered [data-animate-stagger] containers.
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    const animObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;

                const el = entry.target;

                // Stagger containers: add visible to parent,
                // then stagger-reveal each direct child.
                if (el.hasAttribute('data-animate-stagger')) {
                    el.classList.add('visible');
                    Array.from(el.children).forEach((child, i) => {
                        setTimeout(() => {
                            child.classList.add('visible');
                        }, i * 80);
                    });
                } else {
                    el.classList.add('visible');
                }

                animObserver.unobserve(el);
            });
        },
        { root: null, rootMargin: '0px', threshold: 0.1 }
    );

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-animate]').forEach((el) => {
            animObserver.observe(el);
        });

        // Force video play on mobile
        if (heroVideo) {
            heroVideo.muted = true;
            heroVideo.setAttribute('playsinline', '');

            const tryPlay = () => {
                heroVideo.muted = true;
                const p = heroVideo.play();
                if (p) p.catch(() => {});
            };

            tryPlay();
            heroVideo.addEventListener('loadeddata', tryPlay);
            ['touchstart', 'touchend', 'click', 'scroll'].forEach((evt) => {
                document.addEventListener(evt, tryPlay, { once: true });
            });
        }

        // Initialize navbar state on load
        if (navbar) {
            if (window.scrollY < 80) {
                navbar.classList.add('navbar--top');
                navbar.classList.remove('navbar--scrolled');
            } else {
                navbar.classList.remove('navbar--top');
                navbar.classList.add('navbar--scrolled');
            }
        }
    });

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Counter Animation for Hero Stats
    // Animates [data-count] elements from 0 to target
    // over ~2 seconds with ease-out curve. Runs once.
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    let counterAnimated = false;

    const counterObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting || counterAnimated) return;
                counterAnimated = true;
                counterObserver.unobserve(entry.target);
                animateCounters();
            });
        },
        { root: null, rootMargin: '0px', threshold: 0.3 }
    );

    const heroStats = document.querySelector('.hero-stats');
    if (heroStats) {
        counterObserver.observe(heroStats);
    }

    function animateCounters() {
        const counters = document.querySelectorAll('[data-count]');
        const duration = 2000; // ms

        counters.forEach((counter) => {
            const target = parseInt(counter.getAttribute('data-count'), 10);
            if (isNaN(target)) return;

            const start = performance.now();

            function tick(now) {
                const elapsed = now - start;
                const progress = Math.min(elapsed / duration, 1);

                // Ease-out cubic: 1 - (1 - t)^3
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.round(eased * target);

                counter.textContent = current;

                if (progress < 1) {
                    requestAnimationFrame(tick);
                } else {
                    // Append "+" after reaching the target
                    counter.textContent = target + '+';
                }
            }

            requestAnimationFrame(tick);
        });
    }

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Smooth Scroll for Anchor Links
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                });
            }
        });
    });

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Consolidated Scroll Handler
    // One listener for navbar, parallax, and scroll
    // indicator. Uses requestAnimationFrame for perf.
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    let lastScrollY = window.scrollY;
    let ticking = false;

    function onScroll() {
        const currentScrollY = window.scrollY;

        // --- Navbar scroll state ---
        if (navbar) {
            // Transparent at top, solid after 80px
            if (currentScrollY < 80) {
                navbar.classList.add('navbar--top');
                navbar.classList.remove('navbar--scrolled');
            } else {
                navbar.classList.remove('navbar--top');
                navbar.classList.add('navbar--scrolled');
            }

            // Hide on scroll down / show on scroll up (only past hero)
            const heroHeight = window.innerHeight;
            if (currentScrollY > heroHeight) {
                if (currentScrollY > lastScrollY) {
                    // Scrolling down — hide navbar
                    navbar.style.transform = 'translateY(-120%)';
                } else {
                    // Scrolling up — show navbar
                    navbar.style.transform = 'translateY(0)';
                }
            } else {
                // Within hero — always show navbar
                navbar.style.transform = 'translateY(0)';
            }
        }

        // --- Parallax on hero background ---
        if (currentScrollY < window.innerHeight) {
            const offset = Math.round(currentScrollY * 0.3);
            const transformValue = 'translateY(' + offset + 'px)';

            if (heroVideo) {
                heroVideo.style.transform = transformValue;
            }
            if (heroMobileImg) {
                heroMobileImg.style.transform = transformValue;
            }
        }

        // --- Hide scroll indicator after scrolling ---
        if (scrollIndicator && currentScrollY > 100) {
            scrollIndicator.style.opacity = '0';
            scrollIndicator.style.pointerEvents = 'none';
        }

        lastScrollY = currentScrollY;
        ticking = false;
    }

    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(onScroll);
            ticking = true;
        }
    }, { passive: true });

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Mobile Hamburger Menu
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            const isOpen = navToggle.getAttribute('aria-expanded') === 'true';
            navToggle.setAttribute('aria-expanded', !isOpen);
            navLinks.classList.toggle('open');
        });

        // Close menu when a nav link is clicked
        navLinks.querySelectorAll('.nav-link').forEach((link) => {
            link.addEventListener('click', () => {
                navToggle.setAttribute('aria-expanded', 'false');
                navLinks.classList.remove('open');
            });
        });
    }

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // FAQ Accordion
    // Close others when opening one.
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    document.querySelectorAll('.faq-question').forEach((button) => {
        button.addEventListener('click', () => {
            const isExpanded = button.getAttribute('aria-expanded') === 'true';
            const answer = button.nextElementSibling;

            // Close all other FAQs
            document.querySelectorAll('.faq-question').forEach((otherBtn) => {
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
    // Analytics Event Tracking (gtag)
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    document.querySelectorAll('a[href^="tel:"]').forEach((link) => {
        link.addEventListener('click', function () {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'phone_call', {
                    phone_number: this.getAttribute('href'),
                });
            }
        });
    });

    document.querySelectorAll('a[href^="sms:"]').forEach((link) => {
        link.addEventListener('click', function () {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'sms_sent', {
                    phone_number: this.getAttribute('href'),
                });
            }
        });
    });
})();
