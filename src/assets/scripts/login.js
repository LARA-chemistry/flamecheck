// Allauth-specific JavaScript and styles
import '../styles/allauth_styles.css';

// Add any allauth-specific JavaScript here
console.log('Login bundle loaded');

// You can add form validation, UX enhancements, etc. here
document.addEventListener('DOMContentLoaded', function() {
    // Example: Add loading states to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.classList.add('loading');
                submitBtn.disabled = true;
            }
        });
    });
});
