const CACHE_NAME = 'eurasiametal-v1';
const STATIC_ASSETS = [
    '/price/',
    '/price/static/css/style.css',
    '/price/static/js/settings.js',
    '/price/static/js/rolling.js',
    '/price/static/js/grid.js',
    '/price/static/js/app.js',
];

// Install: pre-cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// Fetch strategy
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API calls: network-only (real-time data must be fresh)
    if (url.pathname.startsWith('/api/')) {
        return;
    }

    // Static assets: stale-while-revalidate
    event.respondWith(
        caches.open(CACHE_NAME).then((cache) =>
            cache.match(event.request).then((cached) => {
                const fetched = fetch(event.request).then((response) => {
                    if (response.ok) {
                        cache.put(event.request, response.clone());
                    }
                    return response;
                }).catch(() => cached);

                return cached || fetched;
            })
        )
    );
});
