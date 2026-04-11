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
    // Intelligent Video Deferral
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    function initVideo() {
        if (window.videoInitialized) return;
        window.videoInitialized = true;
        const video = document.getElementById('bg-video');
        if (video) {
            const source = video.querySelector('source');
            if (source && source.dataset.src) {
                source.src = source.dataset.src;
                video.load();
                video.play().catch(() => {});
            }
        }
    }

    // Load video after LCP or on interaction
    window.addEventListener('load', () => setTimeout(initVideo, 2000));
    ['mousedown', 'scroll', 'touchstart'].forEach(e => {
        window.addEventListener(e, initVideo, { once: true, passive: true });
    });

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

    // Use a fixed multiplier for parallax to avoid all geometric queries
    function onScroll() {
        const currentScrollY = window.scrollY;

        if (navbar) {
            if (currentScrollY < 80) {
                navbar.classList.add('navbar--top');
                navbar.classList.remove('navbar--scrolled');
            } else {
                navbar.classList.remove('navbar--top');
                navbar.classList.add('navbar--scrolled');
            }

            // Simple logic for navbar show/hide
            if (currentScrollY > 800) { // Assume hero is ~800px to avoid query
                if (currentScrollY > lastScrollY) {
                    navbar.style.transform = 'translateY(-120%)';
                } else {
                    navbar.style.transform = 'translateY(0)';
                }
            } else {
                navbar.style.transform = 'translateY(0)';
            }
        }

        // Parallax using translate3d for GPU acceleration
        if (currentScrollY < 1000) {
            const transformValue = `translate3d(0, ${Math.round(currentScrollY * 0.3)}px, 0)`;
            if (heroVideo) heroVideo.style.transform = transformValue;
            if (heroMobileImg) heroMobileImg.style.transform = transformValue;
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

    // Google Ads conversion label — replace with your actual label from:
    // Google Ads > Goals > Conversions > click conversion > "Use Google tag" > copy the label
    // The label is the part after the slash, e.g. 'AbC123xYz' from 'AW-17954201120/AbC123xYz'
    var GADS_CONVERSION_LABEL = 'REPLACE_WITH_CONVERSION_LABEL';
    var GADS_CONVERSION_ID = 'AW-17954201120';

    /**
     * Fire a Google Ads conversion event.
     * Only fires if the conversion label has been set (not the placeholder).
     */
    function fireGadsConversion(eventLabel) {
        if (typeof gtag === 'undefined') return;
        if (GADS_CONVERSION_LABEL === 'REPLACE_WITH_CONVERSION_LABEL') return;
        gtag('event', 'conversion', {
            send_to: GADS_CONVERSION_ID + '/' + GADS_CONVERSION_LABEL,
            event_label: eventLabel,
        });
    }

    document.querySelectorAll('a[href^="tel:"]').forEach((link) => {
        link.addEventListener('click', function () {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'phone_call', {
                    phone_number: this.getAttribute('href'),
                });
                fireGadsConversion('phone_call');
            }
        });
    });

    document.querySelectorAll('a[href^="sms:"]').forEach((link) => {
        link.addEventListener('click', function () {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'sms_sent', {
                    phone_number: this.getAttribute('href'),
                });
                fireGadsConversion('sms_sent');
            }
        });
    });

    // Track clicks on "Book Online" CTAs that lead to app.goumuve.com/book
    document.querySelectorAll('a[href*="app.goumuve.com/book"]').forEach((link) => {
        link.addEventListener('click', function () {
            if (typeof gtag !== 'undefined') {
                gtag('event', 'book_online_click', {
                    link_url: this.getAttribute('href'),
                });
                fireGadsConversion('book_online_click');
            }
        });
    });

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Price Estimator Logic
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    const slider = document.getElementById('volume-slider');
    const label = document.getElementById('volume-label');
    const price = document.getElementById('price-display');
    const desc = document.getElementById('fits-description');

    if (slider && label && price && desc) {
        const mapping = {
            '1': { label: 'Single Item', price: '$89', desc: 'Perfect for a single couch, a large fridge, or a pile of 3-4 chairs.' },
            '2': { label: '1/4 Truckload', price: '$179', desc: 'Fits a sofa, a mattress set, and a few boxes. Ideal for a small closet clear-out.' },
            '3': { label: '1/2 Truckload', price: '$329', desc: 'About the size of a small bedroom or a standard kitchen cleanout.' },
            '4': { label: 'Full Truckload', price: '$579', desc: 'Maximum capacity (14 cubic yards). Great for full garage or estate cleanouts.' }
        };

        slider.addEventListener('input', function() {
            const val = this.value;
            const data = mapping[val];
            label.textContent = data.label;
            price.textContent = data.price;
            desc.textContent = data.desc;
        });
    }
})();
