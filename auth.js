// auth.js – Supabase kimlik doğrulama işlemleri

const { createClient } = supabase;
const supabaseClient = createClient(SUPABASE_URL, SUPABASE_KEY);

// Mevcut oturum kontrolü
async function checkSession() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (session) {
        const name = session.user.user_metadata?.full_name || session.user.email.split('@')[0];
        showAuthenticatedState(name);
    } else {
        showView('login');
    }
}

function showAuthenticatedState(name) {
    const nameEl = document.getElementById('user-name-display');
    if (nameEl) nameEl.innerText = `Merhaba, ${name} 👋`;
    showView('home');
}

// Giriş Yap
document.getElementById('btn-login').addEventListener('click', async () => {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const errorEl = document.getElementById('login-error');
    errorEl.classList.add('hidden');

    if (!email || !password) {
        showError(errorEl, 'Lütfen tüm alanları doldurun.');
        return;
    }

    const btn = document.getElementById('btn-login');
    btn.innerText = 'Giriş yapılıyor...';
    btn.disabled = true;

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

// Kayıt Ol
document.getElementById('btn-register').addEventListener('click', async () => {
    const name = document.getElementById('register-name').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value.trim();
    const errorEl = document.getElementById('register-error');
    const successEl = document.getElementById('register-success');
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

    // Supabase e-posta onayı açıksa kullanıcı direkt giriş yapamaz
    if (data.session) {
        showAuthenticatedState(name);
    } else {
        successEl.innerText = '✅ Kayıt başarılı! Lütfen e-postanıza gelen onay linkine tıklayın, ardından giriş yapın.';
        successEl.classList.remove('hidden');
    }
});

// Çıkış Yap
document.getElementById('btn-logout').addEventListener('click', async () => {
    await supabaseClient.auth.signOut();
    showView('login');
});

// Ekran Geçişleri
document.getElementById('go-to-register').addEventListener('click', () => showView('register'));
document.getElementById('go-to-login').addEventListener('click', () => showView('login'));

// Hata gösterici
function showError(el, msg) {
    el.innerText = msg;
    el.classList.remove('hidden');
}

// Sayfa açılışında oturumu kontrol et
checkSession();
