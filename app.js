// Supabase istemcisi auth.js'de tanımlandı (supabaseClient)

// =====================================================
// ÖRNEK ÜRÜN VERİSİ (Simülasyon)
// =====================================================
const mockData = [
    { name: "Biscolata Mood Bardak 125 G",          price: 56.00,  img: "migros_dataset_merged/snack_Biscolata Mood Bardak 125 G.jpg" },
    { name: "Doritos Storm Flamin Hot 125 G",        price: 58.95,  img: "migros_dataset_merged/snack_Doritos Storm Flamin Hot Süper Boy 125 G.jpg" },
    { name: "Eti Karam Gurme Bitter Gofret 50 G",   price: 29.95,  img: "migros_dataset_merged/snack_Eti Karam Gurme Bitter Çikolatalı Gofret 50 g.jpg" },
    { name: "Tadelle Fındıklı Sütlü Çikolata 3x52G",price: 187.50, img: "migros_dataset_merged/snack_Tadelle Fındık Dolgulu Sütlü Çikolata 3 x 52 G.jpg" },
    { name: "Eti Crax Çubuk Kraker 40 G",           price: 7.50,   img: "migros_dataset_merged/snack_Eti Crax Çubuk Kraker 40 G.jpg" },
    { name: "Doritos Nacho Süper Boy 130 G",         price: 54.95,  img: "migros_dataset_merged/snack_Doritos Nacho Süper Boy 130 G.jpg" },
    { name: "Kahve Dünyası Tambol Fındıklı 77 G",   price: 84.95,  img: "migros_dataset_merged/snack_Kahve Dünyası Tambol Fındıklı Sütlü Çikolata 77 G.jpg" },
    { name: "Migros İç Ceviz 150 G",                price: 109.00, img: "migros_dataset_merged/snack_Migros İç Ceviz 150 G.jpg" }
];

// =====================================================
// DURUM
// =====================================================
let cart = [];
let currentProduct = null;
let currentScanQuantity = 1;
const scanStatusEl = document.getElementById('scan-status');

// =====================================================
// GÖRÜNÜM SİSTEMİ
// =====================================================
const views = {
    login:    document.getElementById('login-view'),
    register: document.getElementById('register-view'),
    home:     document.getElementById('home-view'),
    scanner:  document.getElementById('scanner-view'),
    cart:     document.getElementById('cart-view')
};

function showView(viewName) {
    Object.values(views).forEach(v => v.classList.remove('active'));
    views[viewName].classList.add('active');
    if (viewName === 'cart') renderCart();
    if (viewName !== 'scanner') hideDetection();
}

// =====================================================
// DOM ELEMANLARI
// =====================================================
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
    bottomNav:        document.getElementById('bottom-nav'),
    btnCheckout:      document.getElementById('btn-checkout')
};

// =====================================================
// TARAMA SİMÜLASYONU
// =====================================================
function setScanStatus(msg, active = false) {
    if (!scanStatusEl) return;
    scanStatusEl.textContent = msg;
    scanStatusEl.classList.toggle('detecting', active);
}

function triggerScan() {
    if (currentProduct) return;

    elements.scanTrigger.disabled = true;
    setScanStatus('🔍 Ürün tanımlanıyor...', true);

    setTimeout(() => {
        const product = mockData[Math.floor(Math.random() * mockData.length)];
        currentProduct = { ...product };
        elements.scanTrigger.disabled = false;
        showDetection(currentProduct);
    }, 1400);
}

// =====================================================
// ÜRÜN TESPİT / GİZLE
// =====================================================
function showDetection(product) {
    currentScanQuantity = 1;
    elements.scanQuantity.innerText = currentScanQuantity;

    elements.detectedImg.src = product.img;
    elements.detectedImg.alt = product.name;
    elements.detectedImg.style.display = 'block';
    elements.productName.innerText = product.name;
    elements.productPrice.innerText = `${Number(product.price).toFixed(2)} TL`;

    setScanStatus('✅ Ürün bulundu!', true);

    elements.detectionLabel.classList.remove('hidden');
    elements.popup.classList.remove('hidden');
    elements.bottomNav.style.opacity = '0';
    elements.bottomNav.style.pointerEvents = 'none';

    requestAnimationFrame(() => elements.popup.classList.add('active'));
}

function hideDetection() {
    elements.detectionLabel.classList.add('hidden');
    elements.popup.classList.remove('active');
    elements.bottomNav.style.opacity = '1';
    elements.bottomNav.style.pointerEvents = 'auto';
    setTimeout(() => elements.popup.classList.add('hidden'), 400);
    currentProduct = null;
    setScanStatus('Tara butonuna basın');
}

// =====================================================
// SEPET
// =====================================================
function addToCart() {
    if (!currentProduct) return;
    const existing = cart.find(i => i.name === currentProduct.name);
    if (existing) {
        existing.quantity = (existing.quantity || 1) + currentScanQuantity;
    } else {
        cart.push({ ...currentProduct, quantity: currentScanQuantity });
    }
    updateCartBadge();
    hideDetection();
}

function updateCartBadge() {
    const total = cart.reduce((s, i) => s + (i.quantity || 1), 0);
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
        return `
        <div class="cart-item">
            <img src="${item.img}" class="item-img" alt="${item.name}"
                 onerror="this.style.display='none'">
            <div class="item-info">
                <h4>${item.name}${qty > 1
                    ? ` <span style="color:var(--migros);font-weight:800">x${qty}</span>`
                    : ''}</h4>
                <p>${total.toFixed(2)} TL${qty > 1
                    ? ` <span style="font-size:12px;color:var(--text-dim)">(${item.price.toFixed(2)} TL/adet)</span>`
                    : ''}</p>
            </div>
            <button class="btn-icon" onclick="removeFromCart(${index})">×</button>
        </div>`;
    }).join('');

    const grand = cart.reduce((s, i) => s + (i.price * (i.quantity || 1)), 0);
    elements.totalAmount.innerText = `${grand.toFixed(2)} TL`;
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
    if (currentScanQuantity > 1) {
        currentScanQuantity--;
        elements.scanQuantity.innerText = currentScanQuantity;
    }
});
elements.btnQtyPlus.addEventListener('click', () => {
    currentScanQuantity++;
    elements.scanQuantity.innerText = currentScanQuantity;
});
elements.btnCheckout.addEventListener('click', () => {
    if (cart.length === 0) {
        alert('Sepetiniz boş!');
        return;
    }
    const grand = cart.reduce((s, i) => s + (i.price * (i.quantity || 1)), 0);
    alert(`Toplam tutar: ${grand.toFixed(2)} TL\nBizi tercih ettiğiniz için teşekkürler!`);
    cart = [];
    updateCartBadge();
    renderCart();
    showView('home');
});

// =====================================================
// BAŞLANGIÇ
// =====================================================
updateCartBadge();
