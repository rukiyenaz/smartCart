// Supabase istemcisi auth.js'de tanımlandı (supabaseClient)

// =====================================================
// KAMERA & GEMİNİ GÖRÜNTÜ TANIMA SİSTEMİ
// =====================================================
let cameraStream = null;
let scanLoopActive = false;

const videoEl   = document.getElementById('camera-feed');
const cameraFallback = document.getElementById('camera-fallback');
const scanStatusEl   = document.getElementById('scan-status');

// Kamera başlat
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }
        });
        cameraStream = stream;
        videoEl.srcObject = stream;
        videoEl.style.display = 'block';
        cameraFallback.style.display = 'none';
        setScanStatus('📷 Ürünü vizöre getirin ve "Tara" butonuna basın');
    } catch (err) {
        console.warn('Kamera açılamadı:', err);
        videoEl.style.display = 'none';
        cameraFallback.style.display = 'flex';
        setScanStatus('⚠️ Kamera erişimi reddedildi');
    }
}

// Kamera durdur
function stopCamera() {
    scanLoopActive = false;
    if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
        cameraStream = null;
    }
    videoEl.srcObject = null;
}

// Durum metni
function setScanStatus(msg, detecting = false) {
    if (!scanStatusEl) return;
    scanStatusEl.textContent = msg;
    scanStatusEl.classList.toggle('detecting', detecting);
}

// Video'dan frame yakala → Base64 PNG döndür
function captureFrame() {
    const canvas = document.createElement('canvas');
    canvas.width  = videoEl.videoWidth  || 640;
    canvas.height = videoEl.videoHeight || 480;
    canvas.getContext('2d').drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    // base64'ten "data:image/png;base64," prefix'ini kaldır
    return canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
}

// Gemini Vision API ile ürünü tanı
async function recognizeProductWithGemini(base64Image) {
    if (!GEMINI_KEY) {
        setScanStatus('⚠️ Gemini API anahtarı eksik. config.js dosyasını doldurun.');
        return null;
    }

    const prompt = `Bu bir market/süpermarket ürünü tarama uygulamasıdır.
Görüntüdeki ürünü Türkçe olarak tanımla.
Yanıt SADECE şu JSON formatında olsun, başka hiçbir şey yazma:
{
  "name": "Ürün adı (marka + ürün adı + boyut varsa)",
  "category": "Kategori (örn: Atıştırmalık, İçecek, Temizlik vb.)",
  "estimated_price_tl": 25.90
}
Eğer görüntüde belirgin bir market ürünü yoksa: {"name": null}`;

    try {
        const res = await fetch(
            `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GEMINI_KEY}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [{
                        parts: [
                            { text: prompt },
                            { inline_data: { mime_type: 'image/jpeg', data: base64Image } }
                        ]
                    }],
                    generationConfig: { temperature: 0.1, maxOutputTokens: 200 }
                })
            }
        );

        if (!res.ok) {
            const err = await res.json();
            console.error('Gemini API hatası:', err);
            setScanStatus(`❌ API Hatası: ${err.error?.message || res.status}`);
            return null;
        }

        const data = await res.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text || '';

        // JSON'u parse et
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (!jsonMatch) return null;
        const parsed = JSON.parse(jsonMatch[0]);

        if (!parsed.name) return null;
        return {
            name: parsed.name,
            price: parsed.estimated_price_tl || parseFloat((Math.random() * 80 + 5).toFixed(2)),
            img: '',   // Görüntü tanımada gerçek ürün görseli yok; frame'i kullanabiliriz
            category: parsed.category || ''
        };
    } catch (e) {
        console.error('Gemini parse hatası:', e);
        setScanStatus('❌ Tanıma hatası, tekrar deneyin');
        return null;
    }
}

// "Tara" butonuna basıldığında çalışır
async function triggerScan() {
    if (!cameraStream) {
        setScanStatus('⚠️ Kamera bağlı değil');
        return;
    }
    if (currentProduct) return; // zaten bir ürün tespit edilmişse

    elements.scanTrigger.disabled = true;
    setScanStatus('🔍 Görüntü analiz ediliyor...', true);

    // Vizör bölgesini yakala (ortadan kırp)
    const base64 = captureFrame();

    const product = await recognizeProductWithGemini(base64);

    elements.scanTrigger.disabled = false;

    if (product) {
        // Görüntünün kendisini ürün görseli olarak kullan
        const canvas = document.createElement('canvas');
        canvas.width  = videoEl.videoWidth  || 640;
        canvas.height = videoEl.videoHeight || 480;
        canvas.getContext('2d').drawImage(videoEl, 0, 0, canvas.width, canvas.height);
        product.img = canvas.toDataURL('image/jpeg', 0.7);

        currentProduct = product;
        showDetection(product);
    } else {
        setScanStatus('❌ Ürün tanınamadı, tekrar deneyin');
    }
}


// =====================================================
// SEPET & UI
// =====================================================
let cart = [];
let currentProduct = null;
let currentScanQuantity = 1;

const views = {
    login:    document.getElementById('login-view'),
    register: document.getElementById('register-view'),
    home:     document.getElementById('home-view'),
    scanner:  document.getElementById('scanner-view'),
    cart:     document.getElementById('cart-view')
};

const elements = {
    startScanningBtn: document.getElementById('btn-start-scanning'),
    scanTrigger:      document.getElementById('btn-scan-trigger'),
    goToCart:         document.getElementById('btn-go-to-cart'),
    backToScanner:    document.getElementById('btn-back-to-scanner'),
    backToHome:       document.getElementById('btn-back-to-home'),
    goToCartHome:     document.getElementById('btn-go-to-cart-home'),
    cartCountHome:    document.getElementById('cart-count-home'),
    btnYes:           document.getElementById('btn-yes'),
    btnNo:            document.getElementById('btn-no'),
    btnQtyMinus:      document.getElementById('btn-qty-minus'),
    btnQtyPlus:       document.getElementById('btn-qty-plus'),
    scanQuantity:     document.getElementById('scan-quantity'),
    popup:            document.getElementById('add-to-cart-popup'),
    detectionLabel:   document.getElementById('detection-label'),
    detectedImg:      document.getElementById('detected-img'),
    productName:      document.getElementById('product-name'),
    productPrice:     document.getElementById('product-price'),
    cartCount:        document.getElementById('cart-count'),
    cartItems:        document.getElementById('cart-items'),
    totalAmount:      document.getElementById('total-amount'),
    bottomNav:        document.getElementById('bottom-nav')
};

function showView(viewName) {
    Object.values(views).forEach(v => v.classList.remove('active'));
    views[viewName].classList.add('active');

    if (viewName === 'scanner') {
        startCamera();
    } else {
        stopCamera();
        hideDetection();
    }
    if (viewName === 'cart') renderCart();
}

function showDetection(product) {
    currentScanQuantity = 1;
    elements.scanQuantity.innerText = currentScanQuantity;

    if (product.img) {
        elements.detectedImg.src = product.img;
        elements.detectedImg.style.display = 'block';
    } else {
        elements.detectedImg.style.display = 'none';
    }
    elements.detectedImg.alt = product.name;
    elements.productName.innerText = product.name;
    elements.productPrice.innerText = product.price ? `${Number(product.price).toFixed(2)} TL` : '—';

    setScanStatus('✅ Ürün tanındı!', true);

    elements.detectionLabel.classList.remove('hidden');
    elements.popup.classList.remove('hidden');
    elements.bottomNav.style.opacity = '0';
    elements.bottomNav.style.pointerEvents = 'none';

    requestAnimationFrame(() => {
        elements.popup.classList.add('active');
    });
}

function hideDetection() {
    elements.detectionLabel.classList.add('hidden');
    elements.popup.classList.remove('active');
    elements.bottomNav.style.opacity = '1';
    elements.bottomNav.style.pointerEvents = 'auto';
    setTimeout(() => elements.popup.classList.add('hidden'), 400);
    currentProduct = null;
    if (cameraStream) setScanStatus('📷 Ürünü vizöre getirin ve "Tara" butonuna basın');
}

function addToCart() {
    if (currentProduct) {
        const existingItem = cart.find(item => item.name === currentProduct.name);
        if (existingItem) {
            existingItem.quantity = (existingItem.quantity || 1) + currentScanQuantity;
        } else {
            cart.push({ ...currentProduct, quantity: currentScanQuantity });
        }
        updateCartBadge();
        hideDetection();
    }
}

function updateCartBadge() {
    const total = cart.reduce((sum, item) => sum + (item.quantity || 1), 0);
    elements.cartCount.innerText = total;
    if (elements.cartCountHome) elements.cartCountHome.innerText = total;
}

function renderCart() {
    if (cart.length === 0) {
        elements.cartItems.innerHTML = '<div class="empty-cart">Sepetiniz boş.</div>';
        elements.totalAmount.innerText = '0.00 TL';
        return;
    }

    elements.cartItems.innerHTML = cart.map((item, index) => {
        const qty   = item.quantity || 1;
        const total = item.price * qty;
        const imgTag = item.img
            ? `<img src="${item.img}" class="item-img" alt="${item.name}">`
            : `<div class="item-img-placeholder">🛒</div>`;
        return `
        <div class="cart-item">
            ${imgTag}
            <div class="item-info">
                <h4>${item.name}${qty > 1 ? ` <span style="color:var(--migros);font-weight:800">x${qty}</span>` : ''}</h4>
                <p>${total.toFixed(2)} TL${qty > 1 ? ` <span style="font-size:12px;color:var(--text-dim)">(${item.price.toFixed(2)} TL/adet)</span>` : ''}</p>
            </div>
            <button class="btn-icon" onclick="removeFromCart(${index})">×</button>
        </div>`;
    }).join('');

    const grandTotal = cart.reduce((s, i) => s + (i.price * (i.quantity || 1)), 0);
    elements.totalAmount.innerText = `${grandTotal.toFixed(2)} TL`;
}

window.removeFromCart = (index) => {
    cart.splice(index, 1);
    renderCart();
    updateCartBadge();
};

// =====================================================
// EVENT LISTENERS
// =====================================================
elements.startScanningBtn.addEventListener('click', () => showView('scanner'));
elements.goToCartHome.addEventListener('click',    () => showView('cart'));
elements.backToHome.addEventListener('click',      () => showView('home'));
elements.scanTrigger.addEventListener('click',     triggerScan);
elements.goToCart.addEventListener('click',        () => showView('cart'));
elements.backToScanner.addEventListener('click',   () => showView('scanner'));
elements.btnYes.addEventListener('click',          addToCart);
elements.btnNo.addEventListener('click',           hideDetection);
elements.btnQtyMinus.addEventListener('click', () => {
    if (currentScanQuantity > 1) { currentScanQuantity--; elements.scanQuantity.innerText = currentScanQuantity; }
});
elements.btnQtyPlus.addEventListener('click', () => {
    currentScanQuantity++; elements.scanQuantity.innerText = currentScanQuantity;
});

// Initial State
updateCartBadge();
