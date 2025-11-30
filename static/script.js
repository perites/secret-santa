document.addEventListener('DOMContentLoaded', () => {
    const recipientsList = document.getElementById('recipients-list');
    const messageArea = document.getElementById('message-area');

    // Admin elements
    const loginSection = document.getElementById('login-section');
    const adminContent = document.getElementById('admin-content');
    const pinInput = document.getElementById('admin-pin');

    // Form elements
    const formTitle = document.getElementById('form-title');
    const editIdInput = document.getElementById('edit-recipient-id');
    const nameInput = document.getElementById('new-recipient-name');
    const imageInput = document.getElementById('new-recipient-image');
    const submitBtn = document.getElementById('submit-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    // Check if we are on admin page
    const isAdminPage = !!document.getElementById('admin-pin');

    if (isAdminPage) {
        checkAdminAuth();
    } else if (recipientsList) {
        loadRecipients();
    }

    function showMessage(msg, type = 'error') {
        if (!messageArea) return;
        messageArea.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
        setTimeout(() => {
            messageArea.innerHTML = '';
        }, 3000);
    }

    async function checkAdminAuth() {
        try {
            const response = await fetch('/api/admin/check_auth');
            const data = await response.json();
            if (data.authenticated) {
                showAdminContent();
            } else {
                loginSection.style.display = 'block';
            }
        } catch (e) {
            console.error(e);
        }
    }

    window.verifyPin = async () => {
        const pin = pinInput.value;
        try {
            const response = await fetch('/api/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin })
            });
            if (response.ok) {
                showAdminContent();
            } else {
                showMessage('Invalid PIN');
            }
        } catch (e) {
            showMessage('Error verifying PIN');
        }
    };

    window.handlePinEnter = (e) => {
        if (e.key === 'Enter') verifyPin();
    };

    function showAdminContent() {
        if (loginSection) loginSection.style.display = 'none';
        if (adminContent) adminContent.style.display = 'block';
        loadRecipients(true);
    }

    async function loadRecipients(isAdmin = false) {
        try {
            const response = await fetch('/api/recipients');
            if (!response.ok) throw new Error('Failed to load recipients');
            const recipients = await response.json();
            renderRecipients(recipients, isAdmin);
        } catch (error) {
            console.error(error);
            showMessage('Error loading recipients list.');
        }
    }

    function renderRecipients(recipients, isAdmin) {
        recipientsList.innerHTML = '';
        recipients.forEach(r => {
            const card = document.createElement('div');
            card.className = `recipient-card ${r.is_taken ? 'taken' : ''} ${r.taken_by_me ? 'taken-by-me' : ''}`;

            const avatarUrl = r.image_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(r.name) + '&background=random&color=fff&size=128';

            let content = `
                <img src="${avatarUrl}" class="recipient-avatar" alt="${r.name}">
                <div class="recipient-name">${r.name}</div>
            `;

            if (isAdmin) {
                content += `
                    <button class="btn-edit" onclick="editRecipient(${r.id}, '${r.name.replace(/'/g, "\\'")}')">Edit</button>
                    <button class="btn-danger" onclick="deleteRecipient(${r.id})">Delete</button>
                `;
            } else {
                let statusBadge = '';
                let actionButton = '';

                if (r.taken_by_me) {
                    statusBadge = '<span class="status-badge status-mine">Your Choice</span>';
                    actionButton = `<button class="btn-untake" onclick="untakeRecipient(${r.id})">Change Choice</button>`;
                } else if (r.is_taken) {
                    statusBadge = '<span class="status-badge status-taken">Taken</span>';
                    actionButton = `<button class="btn-disabled" disabled>Unavailable</button>`;
                } else {
                    statusBadge = '<span class="status-badge status-available">Available</span>';
                    actionButton = `<button class="btn-take" onclick="takeRecipient(${r.id})">Select this Person 🎁</button>`;
                }
                content += `${statusBadge}<div style="margin-top: 15px;">${actionButton}</div>`;
            }

            card.innerHTML = content;
            recipientsList.appendChild(card);
        });
    }

    window.takeRecipient = async (id) => {
        try {
            const response = await fetch(`/api/take/${id}`, { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                if (data.message) {
                    showMessage(data.message, 'info');
                } else {
                    loadRecipients();
                }
            } else {
                showMessage(data.error || 'Failed to take recipient');
            }
        } catch (error) {
            console.error(error);
            showMessage('An error occurred.');
        }
    };

    window.untakeRecipient = async (id) => {
        if (!confirm('Are you sure you want to change your choice?')) return;

        try {
            const response = await fetch(`/api/untake/${id}`, { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                loadRecipients();
            } else {
                showMessage(data.error || 'Failed to untake recipient');
            }
        } catch (error) {
            console.error(error);
            showMessage('An error occurred.');
        }
    };

    window.handleFormSubmit = async () => {
        const id = editIdInput.value;
        const name = nameInput.value.trim();
        const file = imageInput.files[0];

        if (!name) return;

        const formData = new FormData();
        formData.append('name', name);
        if (file) {
            formData.append('image', file);
        }

        const url = id ? `/api/admin/edit_recipient/${id}` : '/api/admin/add_recipient';

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                cancelEdit(); // Reset form
                loadRecipients(true);
                showMessage(id ? 'Recipient updated!' : 'Recipient added!', 'success');
            } else {
                showMessage('Operation failed');
            }
        } catch (error) {
            console.error(error);
            showMessage('Error submitting form');
        }
    };

    window.editRecipient = (id, name) => {
        editIdInput.value = id;
        nameInput.value = name;
        formTitle.textContent = 'Edit Recipient';
        submitBtn.textContent = 'Update Recipient';
        cancelBtn.style.display = 'inline-block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    window.cancelEdit = () => {
        editIdInput.value = '';
        nameInput.value = '';
        imageInput.value = '';
        formTitle.textContent = 'Add New Recipient';
        submitBtn.textContent = 'Add Recipient';
        cancelBtn.style.display = 'none';
    };

    window.deleteRecipient = async (id) => {
        if (!confirm('Delete this person?')) return;
        try {
            const response = await fetch(`/api/admin/delete_recipient/${id}`, { method: 'DELETE' });
            if (response.ok) {
                loadRecipients(true);
            } else {
                showMessage('Failed to delete');
            }
        } catch (e) {
            showMessage('Error deleting');
        }
    };
});
