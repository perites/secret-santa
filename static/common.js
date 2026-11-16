// Helpers shared by main.js and admin.js.

/**
 * Create a DOM element. Strings among the children become text nodes, so
 * user-provided text is never parsed as HTML.
 *   el('button', { class: 'btn', onclick: handler }, 'Click me')
 */
function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
        if (value === undefined || value === null || value === false) continue;
        if (key === 'class') {
            node.className = value;
        } else if (key.startsWith('on')) {
            node.addEventListener(key.slice(2), value);
        } else if (key in node) {
            node[key] = value;
        } else {
            node.setAttribute(key, value);
        }
    }
    for (const child of children.flat()) {
        if (child !== null && child !== undefined && child !== false) node.append(child);
    }
    return node;
}

/**
 * Call a JSON API endpoint. Throws an Error with the server's message on failure.
 * Pass `json` to send a JSON body, or `body` for FormData.
 */
async function api(url, { json, ...options } = {}) {
    if (json !== undefined) {
        options.headers = { 'Content-Type': 'application/json', ...options.headers };
        options.body = JSON.stringify(json);
    }

    let response;
    try {
        response = await fetch(url, options);
    } catch {
        throw new Error('Network error. Check your connection and try again.');
    }

    let data = {};
    try {
        data = await response.json();
    } catch {
        // Not a JSON response.
    }
    if (!response.ok) {
        throw new Error(data.error || `Request failed (${response.status}).`);
    }
    return data;
}

let messageTimer;

/** Show a short toast at the top of the page. type: 'error' | 'success' | 'info'. */
function showMessage(text, type = 'error') {
    const area = document.getElementById('message-area');
    if (!area) return;
    area.replaceChildren(el('div', { class: `toast toast-${type}`, role: 'status' }, text));
    clearTimeout(messageTimer);
    messageTimer = setTimeout(() => area.replaceChildren(), 3500);
}

/** Uploaded photo, or a festive circle with the person's initials. */
function avatar(person) {
    if (person.image_url) {
        return el('img', { src: person.image_url, class: 'avatar', alt: '' });
    }
    const initials = person.name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((word) => Array.from(word)[0])
        .join('')
        .toUpperCase();
    const hash = Array.from(person.name).reduce((sum, char) => sum + char.codePointAt(0), 0);
    return el('div', { class: `avatar avatar-${hash % 4}`, 'aria-hidden': 'true' }, initials);
}

function wishList(wishes) {
    const filled = wishes.filter(Boolean);
    if (filled.length === 0) {
        return el('p', { class: 'no-wishes' }, 'No wishes yet');
    }
    return el('ul', { class: 'wish-list' }, filled.map((wish) => el('li', {}, linkify(wish))));
}

// ------------------------------------------------------------- links

const URL_PATTERN = /\b(?:https?:\/\/|www\.)[^\s<>"]+/gi;

function count(text, char) {
    return text.split(char).length - 1;
}

/** Drop punctuation that ends the sentence rather than the link: "see x.com/a." */
function trimTrailingPunctuation(raw) {
    while (
        /[.,!?;:'"\]]$/.test(raw)
        || (raw.endsWith(')') && count(raw, '(') < count(raw, ')'))
    ) {
        raw = raw.slice(0, -1);
    }
    return raw;
}

/** A link chip showing just the site name, e.g. "amazon.de ↗". Null if not a web URL. */
function linkChip(raw) {
    let url;
    try {
        url = new URL(/^www\./i.test(raw) ? `https://${raw}` : raw);
    } catch {
        return null;
    }
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    return el('a', {
        href: url.href,
        class: 'wish-link',
        target: '_blank',
        rel: 'noopener noreferrer',
        title: url.href,
    }, url.hostname.replace(/^www\./, ''));
}

/** Split text into plain strings and link chips, so links can sit anywhere in a wish. */
function linkify(text) {
    const parts = [];
    let last = 0;
    for (const match of text.matchAll(URL_PATTERN)) {
        const raw = trimTrailingPunctuation(match[0]);
        const chip = linkChip(raw);
        if (!chip) continue;
        parts.push(text.slice(last, match.index), chip);
        last = match.index + raw.length;
    }
    parts.push(text.slice(last));
    return parts.filter((part) => part !== '');
}
