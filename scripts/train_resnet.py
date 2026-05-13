import os
import csv
import argparse
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from sklearn.preprocessing import LabelEncoder
import joblib

# Ayarlar
IMG_SIZE = 224  # ResNet için
BATCH_SIZE = 8
EPOCHS = 50
LEARNING_RATE = 0.001
DEVICE = torch.device('cpu')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory',
    )
    return parser.parse_args()


class ProductDataset(Dataset):
    """Ürün dataset"""
    def __init__(self, items, transform=None):
        self.items = items
        self.transform = transform
        self.labels = [item[1] for item in items]
        
    def __len__(self):
        return len(self.items)
    
    def __getitem__(self, idx):
        img_path, label = self.items[idx]
        img = Image.open(img_path).convert('RGB')
        
        if self.transform:
            img = self.transform(img)
        
        return img, label


def load_split(split_name, processed, split_root):
    """Veri seti yükle"""
    meta = os.path.join(split_root, f'{split_name}_metadata.csv')
    items = []
    
    if not os.path.isfile(meta):
        return items
    
    with open(meta, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        for r in reader:
            pf = r.get('processed_file')
            if not pf:
                continue
            img_path = os.path.join(processed, os.path.basename(pf))
            if os.path.isfile(img_path):
                label = r.get('label') or r.get('name') or 'unknown'
                items.append((img_path, label))
    
    return items


def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    
    print("Veri seti yükleniyor...")
    train_items = load_split('train', processed, split_root)
    val_items = load_split('val', processed, split_root)
    test_items = load_split('test', processed, split_root)
    
    if not train_items:
        print("Eğitim verisi yok!")
        return
    
    print(f"Eğitim: {len(train_items)}, Val: {len(val_items)}, Test: {len(test_items)}")
    
    # Label encoder
    all_labels = [item[1] for item in train_items + val_items + test_items]
    le = LabelEncoder()
    le.fit(all_labels)
    print(f"Sınıflar: {list(le.classes_)}")
    
    # Transform
    train_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
    # Dataset ve DataLoader
    train_dataset = ProductDataset(train_items, train_transform)
    val_dataset = ProductDataset(val_items, val_transform)
    test_dataset = ProductDataset(test_items, val_transform)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE)
    
    # Model - ResNet18 pretrained
    print("\nResNet18 pretrained modeli yükleniyor...")
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    
    # Son layer'ı değiştir
    num_classes = len(le.classes_)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    model = model.to(DEVICE)
    
    # Loss ve optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    # Eğitim loop
    print(f"\nEğitim başlıyor ({EPOCHS} epoch)...")
    best_val_acc = 0
    
    for epoch in range(EPOCHS):
        # Train
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0
        
        for images, labels in train_loader:
            labels_enc = torch.tensor([le.transform([l])[0] for l in labels])
            images, labels_enc = images.to(DEVICE), labels_enc.to(DEVICE)
            
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels_enc)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            train_total += labels_enc.size(0)
            train_correct += (predicted == labels_enc).sum().item()
        
        train_acc = train_correct / train_total
        
        # Validation
        model.eval()
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for images, labels in val_loader:
                labels_enc = torch.tensor([le.transform([l])[0] for l in labels])
                images, labels_enc = images.to(DEVICE), labels_enc.to(DEVICE)
                
                outputs = model(images)
                _, predicted = torch.max(outputs, 1)
                val_total += labels_enc.size(0)
                val_correct += (predicted == labels_enc).sum().item()
        
        val_acc = val_correct / val_total if val_total > 0 else 0
        
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{EPOCHS}] - Train Acc: {train_acc:.4f}, Val Acc: {val_acc:.4f}")
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_state = model.state_dict()
    
    # Test
    model.load_state_dict(best_model_state)
    model.eval()
    test_correct = 0
    test_total = 0
    
    with torch.no_grad():
        for images, labels in test_loader:
            labels_enc = torch.tensor([le.transform([l])[0] for l in labels])
            images, labels_enc = images.to(DEVICE), labels_enc.to(DEVICE)
            
            outputs = model(images)
            _, predicted = torch.max(outputs, 1)
            test_total += labels_enc.size(0)
            test_correct += (predicted == labels_enc).sum().item()
    
    test_acc = test_correct / test_total if test_total > 0 else 0
    
    print(f"\n{'='*50}")
    print(f"SONUÇLAR:")
    print(f"{'='*50}")
    print(f"Train Acc: {train_acc:.4f}")
    print(f"Val Acc: {best_val_acc:.4f}")
    print(f"Test Acc: {test_acc:.4f}")
    
    # Modeli kaydet
    model_path = os.path.join(split_root, 'resnet18_model.pth')
    torch.save({
        'model_state': model.state_dict(),
        'class_names': le.classes_
    }, model_path)
    
    # LabelEncoder'ı ayrı kaydet
    le_path = os.path.join(split_root, 'label_encoder.joblib')
    joblib.dump(le, le_path)
    
    print(f"Model kaydedildi: {model_path}")
    print(f"Label encoder kaydedildi: {le_path}")
    print("✓ Eğitim tamamlandı!")


if __name__ == '__main__':
    main()
