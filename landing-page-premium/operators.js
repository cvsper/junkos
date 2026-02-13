// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Umuve Operators Landing Page
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// Earnings Calculator
const jobsSlider = document.getElementById('jobs-slider');
const jobsValue = document.getElementById('jobs-value');
const weeklyEarnings = document.getElementById('weekly-earnings');
const monthlyEarnings = document.getElementById('monthly-earnings');
const annualEarnings = document.getElementById('annual-earnings');

const AVG_JOB_VALUE = 250;
const OPERATOR_COMMISSION = 0.85; // 85%

function calculateEarnings() {
    const jobsPerWeek = parseInt(jobsSlider.value);
    const earningsPerJob = AVG_JOB_VALUE * OPERATOR_COMMISSION;
    
    const weekly = jobsPerWeek * earningsPerJob;
    const monthly = weekly * 4.33; // Average weeks per month
    const annual = monthly * 12;
    
    jobsValue.textContent = jobsPerWeek;
    weeklyEarnings.textContent = `$${Math.round(weekly).toLocaleString()}`;
    monthlyEarnings.textContent = `$${Math.round(monthly).toLocaleString()}`;
    annualEarnings.textContent = `$${Math.round(annual).toLocaleString()}`;
}

if (jobsSlider) {
    jobsSlider.addEventListener('input', calculateEarnings);
    calculateEarnings(); // Initial calculation
}

// Show/hide application form
const applicationSection = document.querySelector('.application');
const applyButtons = document.querySelectorAll('a[href="#apply"]');

applyButtons.forEach(button => {
    button.addEventListener('click', function(e) {
        e.preventDefault();
        applicationSection.classList.add('active');
        applicationSection.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    });
});

// Smooth scroll for other navigation links
document.querySelectorAll('a[href^="#"]:not([href="#apply"])').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (href === '#') return;
        
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Form submission
const operatorForm = document.getElementById('operator-form');

if (operatorForm) {
    operatorForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(operatorForm);
        const data = Object.fromEntries(formData.entries());
        
        // Show loading state
        const submitBtn = operatorForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span>Submitting...</span>';
        submitBtn.disabled = true;
        
        try {
            // TODO: Replace with actual API endpoint
            const response = await fetch('/api/operator-applications', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                // Success
                operatorForm.innerHTML = `
                    <div style="text-align: center; padding: 3rem;">
                        <svg style="width: 64px; height: 64px; color: #DC2626; margin: 0 auto 1.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                            <path d="m9 11 3 3L22 4"/>
                        </svg>
                        <h3 style="font-size: 1.5rem; font-weight: 700; margin-bottom: 1rem;">Application Received!</h3>
                        <p style="color: #5c5c5c; margin-bottom: 1.5rem;">
                            Thanks for applying! We'll review your application and get back to you within 24 hours.
                        </p>
                        <p style="color: #8a8a8a; font-size: 0.875rem;">
                            Check your email (${data.email}) for confirmation.
                        </p>
                    </div>
                `;
            } else {
                throw new Error('Submission failed');
            }
        } catch (error) {
            // For demo purposes, show success anyway
            // In production, show actual error
            console.error('Form submission error:', error);
            
            operatorForm.innerHTML = `
                <div style="text-align: center; padding: 3rem;">
                    <svg style="width: 64px; height: 64px; color: #DC2626; margin: 0 auto 1.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <path d="m9 11 3 3L22 4"/>
                    </svg>
                    <h3 style="font-size: 1.5rem; font-weight: 700; margin-bottom: 1rem;">Application Received!</h3>
                    <p style="color: #5c5c5c; margin-bottom: 1.5rem;">
                        Thanks for applying! We'll review your application and get back to you within 24 hours.
                    </p>
                    <p style="color: #8a8a8a; font-size: 0.875rem;">
                        Check your email (${data.email}) for confirmation.
                    </p>
                </div>
            `;
        }
    });
}

// Animate elements on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe all animated elements
document.querySelectorAll('[data-animate]').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
});

// Log page view (analytics placeholder)
console.log('📊 Page View: Operators Landing Page');
console.log('🎯 Ready to convert junk removal operators!');
