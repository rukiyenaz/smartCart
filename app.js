// =====================================================
// SmartCart – Gerçek Görüntü İşleme ile Ürün Tanıma
// =====================================================

const API_BASE = "http://localhost:5000/api";

// =====================================================
// ÜRÜN VERİSİ
// =====================================================
let productsData = [];

async function fetchProducts() {
    try {
        // Önce backend API'ye bak
        const resp = await fetch(`${API_BASE}/products`, { signal: AbortSignal.timeout(3000) });
        if (resp.ok) {
            productsData = await resp.json();
            console.log("✅ Ürünler backend'den yüklendi:", productsData.length);
            return;
        }
    } catch (_) {
        console.warn("⚠️ Backend bağlantısı yok, CSV'den yüklenecek.");
    }

    // Fallback: metadata.csv
    try {
        const resp = await fetch("migros_dataset_merged/metadata.csv");
        if (!resp.ok) throw new Error();
        const text = await resp.text();
        const lines = text.split("\n").slice(1);
        const parsed = [];
        for (const line of lines) {
            const cols = line.trim().split(",");
            if (cols.length >= 6) {
                const name  = cols[0];
                const price = parseFloat(cols[2]) || 0;
                const file  = cols[cols.length - 1].trim();
                if (name && file) {
                    parsed.push({ name, price, img: "migros_dataset_merged/" + file });
                }
            }
        }
        if (parsed.length) {
            productsData = parsed;
            console.log("✅ Ürünler CSV'den yüklendi:", productsData.length);
        }
    } catch (e) {
        console.error("❌ Ürün verisi yüklenemedi:", e);
    }
}

fetchProducts();

// =====================================================
// DURUM
// =====================================================
let cart = [];
let currentProduct = null;
let currentScanQuantity = 1;
let cameraStream = null;
let isScanning = false;
let backendAvailable = false;

const scanStatusEl = document.getElementById("scan-status");

// Backend durumunu kontrol et
async function checkBackend() {
    try {
        const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
        if (resp.ok) {
            const data = await resp.json();
            backendAvailable = true;
            console.log(`✅ Backend aktif | Mod: ${data.mode} | Ürün: ${data.products}`);
            
            // Mod göster
            const modeEl = document.getElementById("scan-mode-badge");
            if (modeEl) {
                modeEl.textContent = data.mode === "ai" ? "🤖 AI Modu" : "🎲 Demo Modu";
                modeEl.className   = data.mode === "ai" ? "mode-badge ai" : "mode-badge demo";
            }
        }
    } catch (_) {
        backendAvailable = false;
        const modeEl = document.getElementById("scan-mode-badge");
        if (modeEl) {
            modeEl.textContent = "🎲 Demo Modu";
            modeEl.className   = "mode-badge demo";
        }
    }
}

// =====================================================
// GÖRÜNÜM SİSTEMİ
// =====================================================
const views = {
    login:    document.getElementById("login-view"),
    register: document.getElementById("register-view"),
    home:     document.getElementById("home-view"),
    scanner:  document.getElementById("scanner-view"),
    cart:     document.getElementById("cart-view"),
};

function showView(viewName) {
    Object.values(views).forEach(v => v && v.classList.remove("active"));
    if (views[viewName]) views[viewName].classList.add("active");
    if (viewName === "cart") renderCart();
    if (viewName === "scanner") {
        startCamera();
        checkBackend();
    } else {
        stopCamera();
        hideDetection();
    }
}

// =====================================================
// KAMERA
// =====================================================
const videoEl    = document.getElementById("camera-feed");
const canvasEl   = document.getElementById("capture-canvas");

async function startCamera() {
    if (cameraStream) return; // Zaten açık
    try {
        setScanStatus("📷 Kamera başlatılıyor...", true);
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: "environment" }, // Arka kamera
                width:  { ideal: 1280 },
                height: { ideal: 720 },
            },
            audio: false,
        });
        cameraStream = stream;
        if (videoEl) {
            videoEl.srcObject = stream;
            videoEl.play();
        }
        setScanStatus("Tara butonuna basın");
        console.log("✅ Kamera başlatıldı");
    } catch (err) {
        console.error("❌ Kamera hatası:", err);
        setScanStatus("❌ Kamera erişimi reddedildi");
        showCameraError(err);
    }
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
        cameraStream = null;
        if (videoEl) videoEl.srcObject = null;
    }
}

function captureFrame() {
    if (!videoEl || !canvasEl) return null;
    canvasEl.width  = videoEl.videoWidth  || 640;
    canvasEl.height = videoEl.videoHeight || 480;
    const ctx = canvasEl.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
    return canvasEl.toDataURL("image/jpeg", 0.85);
}

function showCameraError(err) {
    const camArea = document.getElementById("camera-area");
    if (!camArea) return;
    let msg = "Kamera açılamadı.";
    if (err.name === "NotAllowedError")  msg = "Kamera izni reddedildi. Tarayıcı ayarlarından izin verin.";
    if (err.name === "NotFoundError")    msg = "Kamera bulunamadı.";
    if (err.name === "NotReadableError") msg = "Kamera başka uygulama tarafından kullanılıyor.";
    camArea.innerHTML = `
        <div class="camera-error">
            <div class="camera-error-icon">📷</div>
            <p>${msg}</p>
            <button class="btn-retry" onclick="startCamera()">Tekrar Dene</button>
        </div>`;
}

// =====================================================
// TARAMA (GERÇEK AI)
// =====================================================
function setScanStatus(msg, active = false) {
    if (!scanStatusEl) return;
    scanStatusEl.textContent = msg;
    scanStatusEl.classList.toggle("detecting", active);
}

async function triggerScan() {
    if (currentProduct || isScanning) return;
    isScanning = true;

    const scanBtn = document.getElementById("btn-scan-trigger");
    if (scanBtn) { scanBtn.disabled = true; scanBtn.textContent = "⏳ Tanıyor..."; }

    setScanStatus("🔍 Görüntü analiz ediliyor...", true);

    try {
        let product = null;

        if (backendAvailable) {
            // Gerçek AI tanıma
            const imageB64 = captureFrame();
            if (!imageB64) throw new Error("Kamera görüntüsü alınamadı");

            const resp = await fetch(`${API_BASE}/recognize`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({ image: imageB64 }),
                signal:  AbortSignal.timeout(15000),
            });

            if (!resp.ok) throw new Error(`API hatası: ${resp.status}`);
            const result = await resp.json();

            if (result.found && result.product) {
                product = result.product;
                const confPct = Math.round((result.confidence || 0.9) * 100);
                setScanStatus(`✅ Tanındı (%${confPct} güven)`, true);
            } else {
                setScanStatus("❓ Ürün listede bulunamadı");
                showNotFoundMessage(result.ai_raw || "");
            }
        } else {
            // Demo modu: simülasyon
            await new Promise(r => setTimeout(r, 1400));
            if (productsData.length) {
                product = { ...productsData[Math.floor(Math.random() * productsData.length)] };
            }
            setScanStatus("✅ Ürün bulundu! (Demo)", true);
        }

        if (product) {
            currentProduct = product;
            showDetection(product);
        }

    } catch (err) {
        console.error("Tarama hatası:", err);
        setScanStatus("❌ Hata oluştu");
        
        // Hata durumunda demo moda düş
        if (productsData.length) {
            await new Promise(r => setTimeout(r, 500));
            const product = { ...productsData[Math.floor(Math.random() * productsData.length)] };
            currentProduct = product;
            setScanStatus("✅ Ürün bulundu! (Demo)", true);
            showDetection(product);
        }
    } finally {
        isScanning = false;
        if (scanBtn) { scanBtn.disabled = false; scanBtn.textContent = "📷 Ürünü Tara"; }
    }
}

function showNotFoundMessage(raw) {
    const notFoundEl = document.getElementById("not-found-msg");
    if (notFoundEl) {
        notFoundEl.textContent = "Ürün tanınamadı. Lütfen ürünü kameraya daha yakın tutun.";
        notFoundEl.classList.remove("hidden");
        setTimeout(() => notFoundEl.classList.add("hidden"), 3000);
    }
}

// =====================================================
// ÜRÜN TESPİT / GİZLE
// =====================================================
function showDetection(product) {
    currentScanQuantity = 1;
    const scanQuantityEl = document.getElementById("scan-quantity");
    if (scanQuantityEl) scanQuantityEl.innerText = currentScanQuantity;

    const detectedImg   = document.getElementById("detected-img");
    const productNameEl = document.getElementById("product-name");
    const productPriceEl= document.getElementById("product-price");
    const detectionLbl  = document.getElementById("detection-label");
    const popup         = document.getElementById("add-to-cart-popup");
    const bottomNav     = document.getElementById("bottom-nav");

    if (detectedImg) {
        detectedImg.src  = product.img;
        detectedImg.alt  = product.name;
        detectedImg.style.display = "block";
        detectedImg.onerror = () => { detectedImg.style.display = "none"; };
    }
    if (productNameEl)  productNameEl.innerText  = product.name;
    if (productPriceEl) productPriceEl.innerText = product.price
        ? `${Number(product.price).toFixed(2)} TL`
        : "Fiyat bilgisi yok";

    if (detectionLbl) detectionLbl.classList.remove("hidden");
    if (popup) {
        popup.classList.remove("hidden");
        requestAnimationFrame(() => popup.classList.add("active"));
    }
    if (bottomNav) {
        bottomNav.style.opacity = "0";
        bottomNav.style.pointerEvents = "none";
    }
}

function hideDetection() {
    const detectionLbl = document.getElementById("detection-label");
    const popup        = document.getElementById("add-to-cart-popup");
    const bottomNav    = document.getElementById("bottom-nav");

    if (detectionLbl) detectionLbl.classList.add("hidden");
    if (popup) {
        popup.classList.remove("active");
        setTimeout(() => popup.classList.add("hidden"), 400);
    }
    if (bottomNav) {
        bottomNav.style.opacity = "1";
        bottomNav.style.pointerEvents = "auto";
    }
    currentProduct = null;
    setScanStatus("Tara butonuna basın");
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
    showToast(`✅ "${currentProduct?.name?.split(" ").slice(0,3).join(" ")}..." sepete eklendi`);
}

function updateCartBadge() {
    const total = cart.reduce((s, i) => s + (i.quantity || 1), 0);
    const cartCountEl     = document.getElementById("cart-count");
    const cartCountHomeEl = document.getElementById("cart-count-home");
    if (cartCountEl)     cartCountEl.innerText     = total;
    if (cartCountHomeEl) cartCountHomeEl.innerText = total;
}

function renderCart() {
    const cartItems  = document.getElementById("cart-items");
    const totalAmtEl = document.getElementById("total-amount");
    if (!cartItems) return;

    if (cart.length === 0) {
        cartItems.innerHTML = '<div class="empty-cart">🛒 Sepetiniz boş.</div>';
        if (totalAmtEl) totalAmtEl.innerText = "0.00 TL";
        return;
    }

    cartItems.innerHTML = cart.map((item, idx) => {
        const qty   = item.quantity || 1;
        const total = (item.price || 0) * qty;
        return `
        <div class="cart-item">
            <img src="${item.img}" class="item-img" alt="${item.name}" onerror="this.style.display='none'">
            <div class="item-info">
                <h4>${item.name}${qty > 1
                    ? ` <span style="color:var(--migros);font-weight:800">x${qty}</span>`
                    : ""}</h4>
                <p>${total.toFixed(2)} TL${qty > 1
                    ? ` <span style="font-size:12px;color:var(--text-dim)">(${(item.price||0).toFixed(2)} TL/adet)</span>`
                    : ""}</p>
            </div>
            <button class="btn-icon" onclick="removeFromCart(${idx})">×</button>
        </div>`;
    }).join("");

    const grand = cart.reduce((s, i) => s + ((i.price || 0) * (i.quantity || 1)), 0);
    if (totalAmtEl) totalAmtEl.innerText = `${grand.toFixed(2)} TL`;
}

window.removeFromCart = (idx) => {
    cart.splice(idx, 1);
    renderCart();
    updateCartBadge();
};

// =====================================================
// TOAST BİLDİRİM
// =====================================================
function showToast(msg) {
    let toast = document.getElementById("toast-msg");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast-msg";
        toast.className = "toast";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2800);
}

// =====================================================
// EVENT LISTENERS
// =====================================================
function safe(id, event, fn) {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, fn);
}

safe("btn-start-scanning", "click", () => showView("scanner"));
safe("btn-go-to-cart-home","click", () => showView("cart"));
safe("btn-back-to-home",   "click", () => showView("home"));
safe("btn-scan-trigger",   "click", triggerScan);
safe("btn-go-to-cart",     "click", () => showView("cart"));
safe("btn-back-to-scanner","click", () => showView("scanner"));
safe("btn-yes",            "click", addToCart);
safe("btn-no",             "click", hideDetection);

safe("btn-qty-minus", "click", () => {
    if (currentScanQuantity > 1) {
        currentScanQuantity--;
        const el = document.getElementById("scan-quantity");
        if (el) el.innerText = currentScanQuantity;
    }
});
safe("btn-qty-plus", "click", () => {
    currentScanQuantity++;
    const el = document.getElementById("scan-quantity");
    if (el) el.innerText = currentScanQuantity;
});

safe("btn-checkout", "click", () => {
    if (!cart.length) return;
    const grand = cart.reduce((s, i) => s + ((i.price || 0) * (i.quantity || 1)), 0);
    const modalTotalEl = document.getElementById("modal-total");
    const checkoutModal= document.getElementById("checkout-modal");
    if (modalTotalEl)  modalTotalEl.innerText = `${grand.toFixed(2)} TL`;
    if (checkoutModal) checkoutModal.classList.remove("hidden");
});

safe("btn-modal-ok", "click", () => {
    const checkoutModal = document.getElementById("checkout-modal");
    if (checkoutModal) checkoutModal.classList.add("hidden");
    cart = [];
    updateCartBadge();
    renderCart();
    showView("home");
});

// =====================================================
// BAŞLANGIÇ
// =====================================================
updateCartBadge();
