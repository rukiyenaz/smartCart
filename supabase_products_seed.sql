-- 1. Ürünler tablosunu oluştur
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    img TEXT NOT NULL
);

-- 2. Güvenlik politikalarını (RLS) ayarla: Herkesin ürünleri okumasına izin ver
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access" 
ON products 
FOR SELECT 
USING (true);

-- 3. Örnek ürün verilerini ekle
INSERT INTO products (name, price, img) VALUES
('Biscolata Mood Bardak 125 G', 56.00, 'migros_dataset_merged/snack_Biscolata Mood Bardak 125 G.jpg'),
('Doritos Storm Flamin Hot 125 G', 58.95, 'migros_dataset_merged/snack_Doritos Storm Flamin Hot Süper Boy 125 G.jpg'),
('Eti Karam Gurme Bitter Gofret 50 G', 29.95, 'migros_dataset_merged/snack_Eti Karam Gurme Bitter Çikolatalı Gofret 50 g.jpg'),
('Tadelle Fındıklı Sütlü Çikolata 3x52G', 187.50, 'migros_dataset_merged/snack_Tadelle Fındık Dolgulu Sütlü Çikolata 3 x 52 G.jpg'),
('Eti Crax Çubuk Kraker 40 G', 7.50, 'migros_dataset_merged/snack_Eti Crax Çubuk Kraker 40 G.jpg'),
('Doritos Nacho Süper Boy 130 G', 54.95, 'migros_dataset_merged/snack_Doritos Nacho Süper Boy 130 G.jpg'),
('Kahve Dünyası Tambol Fındıklı 77 G', 84.95, 'migros_dataset_merged/snack_Kahve Dünyası Tambol Fındıklı Sütlü Çikolata 77 G.jpg'),
('Migros İç Ceviz 150 G', 109.00, 'migros_dataset_merged/snack_Migros İç Ceviz 150 G.jpg');
