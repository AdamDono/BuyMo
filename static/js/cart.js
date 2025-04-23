// Confirm before removing items
document.querySelectorAll('.btn-danger').forEach(button => {
    button.addEventListener('click', function(e) {
        if (!confirm('Are you sure you want to remove this item?')) {
            e.preventDefault();
        }
    });
});

// AJAX quantity updates (optional)
document.querySelectorAll('form[action^="/update-cart"]').forEach(form => {
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        
        fetch(this.action, {
            method: 'POST',
            body: new URLSearchParams(formData)
        })
        .then(response => {
            if (response.redirected) {
                window.location.href = response.url;
            }
        })
        .catch(error => console.error('Error:', error));
    });
});