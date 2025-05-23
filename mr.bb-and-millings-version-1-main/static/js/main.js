// Main JavaScript file for the Festival Logistics application

const toggleTransfer = (id) => {
    const form = document.getElementById(id);
    if (form) form.classList.toggle('active');
};

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        document.querySelectorAll('.alert').forEach(function(alert) {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        });
    }, 5000);

    // Toggle Add Item Form on inventory page if it exists
    const addItemBtn = document.getElementById('add-item-btn');
    const addItemForm = document.getElementById('add-item-form');
    
    if (addItemBtn && addItemForm) {
        addItemBtn.addEventListener('click', function() {
            if (addItemForm.style.display === 'none') {
                addItemForm.style.display = 'block';
                addItemBtn.textContent = 'Cancel';
                addItemBtn.classList.remove('btn-primary');
                addItemBtn.classList.add('btn-secondary');
            } else {
                addItemForm.style.display = 'none';
                addItemBtn.textContent = 'Add New Item';
                addItemBtn.classList.remove('btn-secondary');
                addItemBtn.classList.add('btn-primary');
            }
        });
    }

    // Quantity validation for transfers
    const transferForms = document.querySelectorAll('.transfer-form');
    
    transferForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const quantityInput = form.querySelector('[name="quantity"]');
            const maxQuantity = parseInt(quantityInput.getAttribute('max'), 10);
            const quantity = parseInt(quantityInput.value, 10);
            
            if (quantity <= 0) {
                e.preventDefault();
                alert('Quantity must be greater than zero');
            } else if (quantity > maxQuantity) {
                e.preventDefault();
                alert(`Maximum available quantity is ${maxQuantity}`);
            }
        });
    });
    
    // Confirm delete actions
    const deleteButtons = document.querySelectorAll('.delete-btn');
    
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });

    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', (event) => {
            const requiredFields = form.querySelectorAll('[required]');
            let valid = true;
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    valid = false;
                    field.classList.add('error');
                } else {
                    field.classList.remove('error');
                }
            });
            if (!valid) {
                event.preventDefault();
                alert('Please fill in all required fields.');
            }
        });
    });
});
