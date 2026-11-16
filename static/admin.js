// Admin page: PIN login, add/edit/delete participants, personal links.

document.addEventListener('DOMContentLoaded', () => {
    const loginSection = document.getElementById('login-section');
    const loginForm = document.getElementById('login-form');
    const pinInput = document.getElementById('admin-pin');
    const adminContent = document.getElementById('admin-content');
    const logoutBtn = document.getElementById('admin-logout-btn');
    const logoutDot = document.getElementById('admin-logout-dot');

    const form = document.getElementById('participant-form');
    const formEyebrow = document.getElementById('form-eyebrow');
    const formTitle = document.getElementById('form-title');
    const editIdInput = document.getElementById('edit-id');
    const nameInput = document.getElementById('participant-name');
    const imageInput = document.getElementById('participant-image');
    const wishInputs = [...form.querySelectorAll('.wish-input')];
    const submitBtn = document.getElementById('submit-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    const list = document.getElementById('participants-list');
    const progress = document.getElementById('pick-progress');

    // ---------------------------------------------------------------- auth

    async function init() {
        try {
            const { authenticated } = await api('/api/admin/check_auth');
            authenticated ? showAdmin() : showLogin();
        } catch (error) {
            showMessage(error.message);
        }
    }

    function setLoggedIn(loggedIn) {
        loginSection.hidden = loggedIn;
        adminContent.hidden = !loggedIn;
        logoutBtn.hidden = !loggedIn;
        logoutDot.hidden = !loggedIn;
    }

    function showLogin() {
        setLoggedIn(false);
        pinInput.value = '';
        pinInput.focus();
    }

    function showAdmin() {
        setLoggedIn(true);
        loadParticipants();
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
            await api('/api/admin/login', { method: 'POST', json: { pin: pinInput.value } });
            showAdmin();
        } catch (error) {
            showMessage(error.message);
        }
    });

    logoutBtn.addEventListener('click', async () => {
        try {
            await api('/api/admin/logout', { method: 'POST' });
            showLogin();
        } catch (error) {
            showMessage(error.message);
        }
    });

    // -------------------------------------------------------- participants

    async function loadParticipants() {
        try {
            const { participants, picked_count } = await api('/api/admin/participants');
            progress.textContent = `${picked_count} of ${participants.length} have picked someone`;
            renderParticipants(participants);
        } catch (error) {
            showMessage(error.message);
        }
    }

    function renderParticipants(participants) {
        if (participants.length === 0) {
            list.replaceChildren(el('p', { class: 'empty' }, 'No participants yet. Add the first one above.'));
            return;
        }

        list.replaceChildren(...participants.map((person) => {
            const linkInput = el('input', {
                type: 'text',
                class: 'input invite-link',
                value: person.link,
                readOnly: true,
                'aria-label': `Personal link for ${person.name}`,
                onfocus: (event) => event.target.select(),
            });

            return el('article', { class: 'person-card' },
                person.joined
                    ? el('span', { class: 'badge badge-available' }, 'Joined')
                    : el('span', { class: 'badge badge-taken' }, 'Not joined'),
                avatar(person),
                el('h3', { class: 'person-name' }, person.name),
                wishList(person.wishes),
                el('div', { class: 'card-actions' },
                    el('div', { class: 'invite' },
                        linkInput,
                        el('button', { class: 'btn btn-primary btn-small', onclick: () => copyLink(linkInput) }, 'Copy'),
                    ),
                    el('div', { class: 'button-row' },
                        el('button', { class: 'btn btn-secondary btn-small', onclick: () => startEdit(person) }, 'Edit'),
                        el('button', { class: 'btn btn-secondary btn-small', onclick: () => regenerateLink(person) }, 'New link'),
                        el('button', { class: 'btn btn-danger btn-small', onclick: () => deleteParticipant(person) }, 'Delete'),
                    ),
                ),
            );
        }));
    }

    async function copyLink(input) {
        try {
            await navigator.clipboard.writeText(input.value);
        } catch {
            // Clipboard API needs HTTPS or localhost; fall back to the old way.
            input.select();
            if (!document.execCommand('copy')) {
                showMessage('Could not copy. Select the link and copy it manually.');
                return;
            }
        }
        showMessage('Link copied!', 'success');
    }

    async function regenerateLink(person) {
        const ok = confirm(
            `Create a new link for ${person.name}?\n\n`
            + 'The old link stops working and signs them out. Their pick and wishlist are kept.',
        );
        if (!ok) return;
        try {
            await api(`/api/admin/participants/${person.id}/regenerate`, { method: 'POST' });
            showMessage(`New link created. Send it to ${person.name}.`, 'success');
        } catch (error) {
            showMessage(error.message);
        }
        loadParticipants();
    }

    async function deleteParticipant(person) {
        if (!confirm(`Delete ${person.name}? If someone picked them, that person will need to pick again.`)) return;
        try {
            await api(`/api/admin/participants/${person.id}`, { method: 'DELETE' });
            if (editIdInput.value === String(person.id)) resetForm();
        } catch (error) {
            showMessage(error.message);
        }
        loadParticipants();
    }

    // ---------------------------------------------------------- add / edit

    function startEdit(person) {
        editIdInput.value = person.id;
        nameInput.value = person.name;
        imageInput.value = '';
        wishInputs.forEach((input, i) => { input.value = person.wishes[i] || ''; });
        formEyebrow.textContent = 'Editing';
        formTitle.textContent = person.name;
        submitBtn.textContent = 'Save changes';
        cancelBtn.hidden = false;
        form.closest('section').scrollIntoView({ behavior: 'smooth', block: 'start' });
        nameInput.focus({ preventScroll: true });
    }

    function resetForm() {
        form.reset();
        editIdInput.value = '';
        formEyebrow.textContent = 'New participant';
        formTitle.textContent = 'Add someone';
        submitBtn.textContent = 'Add participant';
        cancelBtn.hidden = true;
    }

    cancelBtn.addEventListener('click', resetForm);

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const id = editIdInput.value;
        const url = id ? `/api/admin/participants/${id}` : '/api/admin/participants';
        try {
            await api(url, { method: 'POST', body: new FormData(form) });
            showMessage(id ? 'Changes saved!' : 'Participant added!', 'success');
            resetForm();
            loadParticipants();
        } catch (error) {
            showMessage(error.message);
        }
    });

    init();
});
