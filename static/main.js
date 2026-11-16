// Participant page: wishlist, "giving to" card and the pick grid.

document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('participants-list');
    const givingTo = document.getElementById('giving-to');
    const givingToName = document.getElementById('giving-to-name');
    const givingToWishes = document.getElementById('giving-to-wishes');
    const givingToAvatar = document.getElementById('giving-to-avatar');
    const givingToActions = document.getElementById('giving-to-actions');
    const peopleSection = document.getElementById('people-section');
    const myAvatar = document.getElementById('my-avatar');
    const wishlistForm = document.getElementById('wishlist-form');
    const logoutForm = document.getElementById('logout-form');

    async function refresh() {
        try {
            const [me, participants] = await Promise.all([api('/api/me'), api('/api/participants')]);
            myAvatar.replaceChildren(avatar(me));
            renderGivingTo(me);
            renderParticipants(participants, me);
        } catch (error) {
            showMessage(error.message);
        }
    }

    function renderGivingTo(me) {
        const person = me.gives_to;
        givingTo.classList.toggle('is-empty', !person);
        if (person) {
            givingToAvatar.replaceChildren(avatar(person));
            givingToName.textContent = person.name;
            givingToWishes.replaceChildren(wishList(person.wishes));
            givingToActions.replaceChildren(me.deadline_passed ? '' :
                el('button', { class: 'btn btn-secondary', onclick: untake }, 'Change my pick'));
        } else {
            givingToAvatar.replaceChildren(el('div', { class: 'avatar avatar-empty', 'aria-hidden': 'true' }, '?'));
            givingToName.textContent = 'Nobody yet';
            givingToWishes.replaceChildren(el('p', { class: 'muted' },
                me.deadline_passed ? 'Picking is closed.' : 'Pick someone from the list below.'));
            givingToActions.replaceChildren();
        }
    }

    function renderParticipants(participants, me) {
        const locked = me.deadline_passed;

        // Once you've picked, the "Secret Santa for" card has everything you need.
        peopleSection.hidden = me.gives_to !== null;
        if (!peopleSection.hidden && participants.length === 0) {
            list.replaceChildren(el('p', { class: 'empty' }, 'Nobody else has been added yet.'));
            return;
        }

        list.replaceChildren(...participants.map((person) => {
            const action = !person.is_taken && !locked
                && el('button', { class: 'btn btn-primary', onclick: () => take(person) }, 'Pick 🎁');

            return el('article', { class: person.is_taken ? 'person-card is-taken' : 'person-card' },
                person.is_taken
                    ? el('span', { class: 'badge badge-taken' }, 'Taken')
                    : el('span', { class: 'badge badge-available' }, 'Available'),
                avatar(person),
                el('h3', { class: 'person-name' }, person.name),
                action && el('div', { class: 'card-actions' }, action),
            );
        }));
    }

    async function take(person) {
        if (!confirm(`Be the Secret Santa for ${person.name}?`)) return;
        try {
            const data = await api(`/api/take/${person.id}`, { method: 'POST' });
            showMessage(data.message || `You're Secret Santa for ${person.name}! 🎄`, data.message ? 'info' : 'success');
        } catch (error) {
            showMessage(error.message);
        }
        refresh();
    }

    async function untake() {
        if (!confirm('Are you sure you want to change your pick?')) return;
        try {
            await api('/api/untake', { method: 'POST' });
        } catch (error) {
            showMessage(error.message);
        }
        refresh();
    }

    wishlistForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const inputs = [...wishlistForm.querySelectorAll('[name="wish"]')];
        try {
            const data = await api('/api/me/wishes', {
                method: 'POST',
                json: { wishes: inputs.map((input) => input.value) },
            });
            inputs.forEach((input, i) => { input.value = data.wishes[i]; });
            showMessage('Wishlist saved!', 'success');
        } catch (error) {
            showMessage(error.message);
        }
    });

    // Wishes are one line each: Enter saves, like in a normal text field.
    wishlistForm.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey && event.target.tagName === 'TEXTAREA') {
            event.preventDefault();
            wishlistForm.requestSubmit();
        }
    });

    logoutForm.addEventListener('submit', (event) => {
        if (!confirm("Log out? You'll need your personal link to get back in.")) {
            event.preventDefault();
        }
    });

    refresh();
});
