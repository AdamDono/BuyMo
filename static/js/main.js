document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const menuToggle = document.querySelector('.menu-toggle');
    const siteNav = document.querySelector('.site-nav');
    
    menuToggle.addEventListener('click', function() {
        this.classList.toggle('active');
        siteNav.classList.toggle('active');
    });
    
    // Close flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });

    // Quick add to cart with flying animation
    const quickAddForms = document.querySelectorAll('.quick-add-form');
    
    quickAddForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const button = this.querySelector('.quick-add');
            // Try to find product card parent, or just use the button position
            const productCard = this.closest('.product-thumb-wrap') || this.closest('.product-card') || this.parentElement; 
            const productImage = productCard.querySelector('img');
            
            if (productImage) {
                // Create flying image
                const flyingImg = document.createElement('img');
                flyingImg.src = productImage.src;
                flyingImg.className = 'cart-item-flying';
                
                // Position at product image
                const rect = productImage.getBoundingClientRect();
                flyingImg.style.position = 'fixed';
                flyingImg.style.left = rect.left + 'px';
                flyingImg.style.top = rect.top + 'px';
                flyingImg.style.width = rect.width + 'px';
                flyingImg.style.height = rect.height + 'px';
                flyingImg.style.objectFit = 'contain';
                flyingImg.style.background = 'white';
                flyingImg.style.padding = '5px';
                flyingImg.style.borderRadius = '12px';
                flyingImg.style.boxShadow = '0 10px 30px rgba(0,0,0,0.2)';
                flyingImg.style.zIndex = '9999';
                flyingImg.style.transition = 'all 0.8s cubic-bezier(0.2, 1, 0.3, 1)'; // Smooth fly
                
                document.body.appendChild(flyingImg);
                
                // Fly to cart
                requestAnimationFrame(() => {
                    const cartLink = document.querySelector('.cart-link');
                    if (cartLink) {
                        const cartRect = cartLink.getBoundingClientRect();
                        flyingImg.style.left = (cartRect.left + 10) + 'px';
                        flyingImg.style.top = (cartRect.top + 10) + 'px';
                        flyingImg.style.width = '30px';
                        flyingImg.style.height = '30px';
                        flyingImg.style.opacity = '0';
                    }
                });

                // Remove after animation
                setTimeout(() => {
                    flyingImg.remove();
                }, 800);
            }

            // Pulse cart icon
            const cartLink = document.querySelector('.cart-link');
            if (cartLink) {
                cartLink.classList.add('cart-pulse');
                setTimeout(() => {
                    cartLink.classList.remove('cart-pulse');
                }, 300);
            }
            
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    if (typeof showToast === 'function') {
                        showToast('✓ Added to cart!', 'success');
                    }
                    
                    // Button success feedback
                    const originalHTML = button.innerHTML;
                    button.innerHTML = '<i class="fas fa-check"></i>';
                    button.style.background = '#10b981';
                    
                    // Fetch updated cart count
                    fetch('/api/cart-count')
                        .then(res => res.json())
                        .then(data => {
                             const cartLink = document.querySelector('.cart-link');
                             if (cartLink && data.count > 0) {
                                 let badge = document.getElementById('cart-badge');
                                 if (!badge) {
                                     badge = document.createElement('span');
                                     badge.className = 'cart-badge';
                                     badge.id = 'cart-badge';
                                     cartLink.appendChild(badge);
                                 }
                                 badge.textContent = data.count;
                             }
                        });

                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.style.background = '#076850';
                    }, 1500);
                } else {
                    if (typeof showToast === 'function') showToast('Error adding to cart', 'error');
                }
            })
            .catch(error => {
                console.error(error);
                if (typeof showToast === 'function') showToast('Error adding to cart', 'error');
            });
        });
    });
    
    // Auto-submit search and filters for "instant" feel
    const searchForm = document.querySelector('.search-form');
    const filterForm = document.querySelector('.filter-form');
    
    if (searchForm && filterForm) {
        const queryInput = searchForm.querySelector('input[name="query"]');
        const filterInputs = filterForm.querySelectorAll('select, input');
        
        // Debounce function to limit rapid submissions
        let debounceTimer;
        const debounceSubmit = () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                // Combine query and filters for full filtering
                const params = new URLSearchParams(new FormData(filterForm));
                params.set('query', queryInput.value);
                window.location.href = `${window.location.pathname}?${params.toString()}`;
            }, 500); // 500ms delay
        };

        // When user types in search
        queryInput.addEventListener('input', debounceSubmit);

        // When user changes a category or price
        filterInputs.forEach(input => {
            input.addEventListener('input', () => {
                // For select, we can submit immediately, for numbers debounce
                if (input.tagName === 'SELECT') {
                    const params = new URLSearchParams(new FormData(filterForm));
                    params.set('query', queryInput.value);
                    window.location.href = `${window.location.pathname}?${params.toString()}`;
                } else {
                    debounceSubmit();
                }
            });
        });

        // Prevent Enter from doing a default form submit (let our logic handle it)
        searchForm.addEventListener('submit', (e) => e.preventDefault());
        filterForm.addEventListener('submit', (e) => e.preventDefault());
    }
});