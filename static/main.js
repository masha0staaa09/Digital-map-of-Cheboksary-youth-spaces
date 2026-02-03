async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`Ошибка загрузки ${url}: ${res.status}`);
    }
    return await res.json();
}

function createElement(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text) el.textContent = text;
    return el;
}

async function loadNav() {
    const navEl = document.getElementById("nav");
    if (!navEl) return;
    const items = await fetchJSON("/nav");
    items.forEach(item => {
        const a = document.createElement("a");
        a.href = item.path || "#";
        a.textContent = item.title;
        if (item.is_active) a.classList.add("active");
        a.addEventListener("click", () => {
            document.querySelectorAll(".nav a").forEach(x => x.classList.remove("active"));
            a.classList.add("active");
        });
        navEl.appendChild(a);
    });
}

async function loadPlaces() {
    const container = document.getElementById("places");
    if (!container) return;
    try {
        const places = await fetchJSON("/places");
        if (!places.length) {
            container.textContent = "Пока нет локаций. Добавьте их через раздел Админка в Swagger.";
            return;
        }
        places.forEach(p => {
            const card = createElement("div", "card");
            const title = createElement("h3", null, p.name);
            const meta = createElement("div", "place-meta");
            meta.innerHTML = `<span class="badge">${p.category}</span> Координаты: ${p.lat}, ${p.lng} (ID: ${p.id})`;
            const desc = createElement("p", null, p.description || "Описание скоро появится.");
            card.appendChild(title);
            card.appendChild(meta);
            card.appendChild(desc);
            container.appendChild(card);
        });
    } catch (e) {
        container.textContent = "Ошибка загрузки локаций.";
        console.error(e);
    }
}

async function loadReviewsForPlace(placeId) {
    const container = document.getElementById("reviews-list");
    if (!container) return;
    container.innerHTML = "";
    try {
        const reviews = await fetchJSON(`/reviews?place_id=${encodeURIComponent(placeId)}`);
        if (!reviews.length) {
            container.textContent = "Для этой локации пока нет одобренных отзывов.";
            return;
        }
        reviews.forEach(r => {
            const card = createElement("div", "card");
            const title = createElement("h3", null, r.author_name || "Аноним");
            const rating = createElement("div", "rating", "★".repeat(r.rating));
            const text = createElement("p", null, r.text);
            const meta = createElement("div", "place-meta", new Date(r.created_at).toLocaleString("ru-RU"));
            card.appendChild(title);
            card.appendChild(rating);
            card.appendChild(text);
            card.appendChild(meta);
            if (r.photos && r.photos.length) {
                const photosWrap = createElement("div", "gallery-photos");
                r.photos.forEach(ph => {
                    const img = document.createElement("img");
                    img.src = ph.url;
                    img.alt = "Фото отзыва";
                    img.loading = "lazy";
                    photosWrap.appendChild(img);
                });
                card.appendChild(photosWrap);
            }
            container.appendChild(card);
        });
    } catch (e) {
        container.textContent = "Ошибка загрузки отзывов.";
        console.error(e);
    }
}

async function loadEvents() {
    const container = document.getElementById("events-list");
    if (!container) return;
    try {
        const events = await fetchJSON("/events");
        if (!events.length) {
            container.textContent = "Пока нет запланированных мероприятий.";
            return;
        }
        events.forEach(ev => {
            const card = createElement("div", "card");
            const title = createElement("h3", null, ev.title);
            const meta = createElement("div", "place-meta", new Date(ev.date).toLocaleDateString("ru-RU"));
            const info = createElement("p", null, ev.short_info);
            card.appendChild(title);
            card.appendChild(meta);
            card.appendChild(info);
            if (ev.cover_url) {
                const img = document.createElement("img");
                img.src = ev.cover_url;
                img.alt = "Обложка мероприятия";
                img.style.maxWidth = "100%";
                img.style.borderRadius = "8px";
                card.appendChild(img);
            }
            container.appendChild(card);
        });
    } catch (e) {
        container.textContent = "Ошибка загрузки мероприятий.";
        console.error(e);
    }
}

async function loadGallery() {
    const container = document.getElementById("gallery-list");
    if (!container) return;
    try {
        const sections = await fetchJSON("/gallery");
        if (!sections.length) {
            container.textContent = "Галерея пока пуста.";
            return;
        }
        sections.forEach(sec => {
            const wrap = createElement("div", "gallery-section");
            const title = createElement("h3", "gallery-title", sec.name);
            wrap.appendChild(title);
            if (sec.photos && sec.photos.length) {
                const photos = createElement("div", "gallery-photos");
                sec.photos.forEach(ph => {
                    const img = document.createElement("img");
                    img.src = ph.url;
                    img.alt = sec.name;
                    img.loading = "lazy";
                    photos.appendChild(img);
                });
                wrap.appendChild(photos);
            } else {
                wrap.appendChild(createElement("p", "place-meta", "Фото пока нет."));
            }
            container.appendChild(wrap);
        });
    } catch (e) {
        container.textContent = "Ошибка загрузки галереи.";
        console.error(e);
    }
}

function initReviewForm() {
    const form = document.getElementById("review-form");
    const messageEl = document.getElementById("review-form-message");
    if (!form) return;
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        messageEl.textContent = "";
        messageEl.className = "form-message";
        const formData = new FormData(form);
        const files = form.querySelector('input[name="files"]').files;
        if (files.length > 5) {
            messageEl.textContent = "Можно прикрепить не более 5 изображений.";
            messageEl.classList.add("error");
            return;
        }
        try {
            const res = await fetch("/reviews", {
                method: "POST",
                body: formData
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.detail || "Ошибка отправки отзыва");
            }
            const data = await res.json();
            messageEl.textContent = "Отзыв отправлен и ожидает модерации.";
            messageEl.classList.add("success");
            const placeId = formData.get("place_id");
            if (placeId) {
                await loadReviewsForPlace(placeId);
            }
            form.reset();
        } catch (err) {
            console.error(err);
            messageEl.textContent = err.message || "Произошла ошибка.";
            messageEl.classList.add("error");
        }
    });

    const placeInput = form.querySelector('input[name="place_id"]');
    if (placeInput) {
        placeInput.addEventListener("change", () => {
            const val = placeInput.value;
            if (val) {
                loadReviewsForPlace(val);
            }
        });
    }
}

function initFeedbackForm() {
    const form = document.getElementById("feedback-form");
    const messageEl = document.getElementById("feedback-form-message");
    if (!form) return;
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        messageEl.textContent = "";
        messageEl.className = "form-message";
        const payload = {
            name: form.name.value,
            contact: form.contact.value || null,
            message: form.message.value
        };
        try {
            const res = await fetch("/feedback", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload)
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.detail || "Ошибка отправки сообщения");
            }
            await res.json();
            messageEl.textContent = "Сообщение отправлено. Спасибо!";
            messageEl.classList.add("success");
            form.reset();
        } catch (err) {
            console.error(err);
            messageEl.textContent = err.message || "Произошла ошибка.";
            messageEl.classList.add("error");
        }
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    loadNav();
    loadPlaces();
    loadEvents();
    loadGallery();
    initReviewForm();
    initFeedbackForm();
});

