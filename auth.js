// auth.js – Kimlik doğrulama (Supabase + Demo mod fallback)

let supabaseClient = null;
let demoMode = false;

// Supabase başlat (eğer config varsa)
try {
    if (
        typeof SUPABASE_URL !== 'undefined' &&
        typeof SUPABASE_ANON_KEY !== 'undefined' &&
        SUPABASE_URL !== 'https://your-project.supabase.co' &&
        SUPABASE_ANON_KEY !== 'your-anon-key-here'
    ) {
        const { createClient } = supabase;
        supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        console.log('✅ Supabase bağlantısı kuruldu.');
    } else {
        throw new Error('Supabase config eksik');
    }
} catch (e) {
    demoMode = true;
    console.warn('⚠️ Demo modu: Supabase bağlantısı yok. Giriş simüle edilecek.');
}

// ──────────────────────────────────────────────
// Oturum Kontrolü
// ──────────────────────────────────────────────
async function checkSession() {
    // Demo modda: localStorage'dan kullanıcıyı al
    if (demoMode) {
        const saved = localStorage.getItem('demo_user');
        if (saved) {
            showAuthenticatedState(saved);
        } else {
            showView('login');
        }
        return;
    }

    // Supabase modu
    try {
        const { data: { session } } = await supabaseClient.auth.getSession();
        if (session) {
            const name = session.user.user_metadata?.full_name || session.user.email.split('@')[0];
            showAuthenticatedState(name);
        } else {
            showView('login');
        }
    } catch {
        showView('login');
    }
}

function showAuthenticatedState(name) {
    const nameEl = document.getElementById('user-name-display');
    if (nameEl) nameEl.innerText = `Merhaba, ${name} 👋`;
    showView('home');
}

// ──────────────────────────────────────────────
// Giriş Yap
// ──────────────────────────────────────────────
document.getElementById('btn-login').addEventListener('click', async () => {
    const email    = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const errorEl  = document.getElementById('login-error');
    errorEl.classList.add('hidden');

    if (!email || !password) {
        showError(errorEl, 'Lütfen tüm alanları doldurun.');
        return;
    }

    const btn = document.getElementById('btn-login');
    btn.innerText = 'Giriş yapılıyor...';
    btn.disabled = true;

    // Demo modu
    if (demoMode) {
        await new Promise(r => setTimeout(r, 600));
        const name = email.split('@')[0];
        localStorage.setItem('demo_user', name);
        btn.innerText = 'Giriş Yap';
        btn.disabled = false;
        showAuthenticatedState(name);
        return;
    }

    // Supabase modu
    const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
    btn.innerText = 'Giriş Yap';
    btn.disabled = false;

    if (error) {
        showError(errorEl, 'E-posta veya şifre hatalı.');
        return;
    }

    const name = data.user.user_metadata?.full_name || data.user.email.split('@')[0];
    showAuthenticatedState(name);
});

// ──────────────────────────────────────────────
// Kayıt Ol
// ──────────────────────────────────────────────
document.getElementById('btn-register').addEventListener('click', async () => {
    const name     = document.getElementById('register-name').value.trim();
    const email    = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value.trim();
    const errorEl  = document.getElementById('register-error');
    const successEl= document.getElementById('register-success');
    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');

    if (!name || !email || !password) {
        showError(errorEl, 'Lütfen tüm alanları doldurun.');
        return;
    }
    if (password.length < 6) {
        showError(errorEl, 'Şifre en az 6 karakter olmalıdır.');
        return;
    }

    const btn = document.getElementById('btn-register');
    btn.innerText = 'Kayıt yapılıyor...';
    btn.disabled = true;

    // Demo modu
    if (demoMode) {
        await new Promise(r => setTimeout(r, 600));
        localStorage.setItem('demo_user', name);
        btn.innerText = 'Kayıt Ol';
        btn.disabled = false;
        showAuthenticatedState(name);
        return;
    }

    // Supabase modu
    const { data, error } = await supabaseClient.auth.signUp({
        email,
        password,
        options: { data: { full_name: name } }
    });

    btn.innerText = 'Kayıt Ol';
    btn.disabled = false;

    if (error) {
        showError(errorEl, error.message.includes('already registered')
            ? 'Bu e-posta zaten kayıtlı.'
            : 'Kayıt sırasında hata oluştu: ' + error.message);
        return;
    }

    if (data.session) {
        showAuthenticatedState(name);
    } else {
        successEl.innerText = '✅ Kayıt başarılı! Lütfen e-postanıza gelen onay linkine tıklayın.';
        successEl.classList.remove('hidden');
    }
});

// ──────────────────────────────────────────────
// Çıkış Yap
// ──────────────────────────────────────────────
document.getElementById('btn-logout').addEventListener('click', async () => {
    if (demoMode) {
        localStorage.removeItem('demo_user');
    } else if (supabaseClient) {
        await supabaseClient.auth.signOut();
    }
    showView('login');
});

// ──────────────────────────────────────────────
// Ekran Geçişleri
// ──────────────────────────────────────────────
document.getElementById('go-to-register').addEventListener('click', () => showView('register'));
document.getElementById('go-to-login').addEventListener('click',    () => showView('login'));

// ──────────────────────────────────────────────
// Yardımcı
// ──────────────────────────────────────────────
function showError(el, msg) {
    el.innerText = msg;
    el.classList.remove('hidden');
}

// Başlangıçta oturumu kontrol et
checkSession();
