import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision import models, transforms
import numpy as np
from skimage.metrics import structural_similarity as ssim

THRESHOLD_LULUS = 0.85
ROTATIONS = (0, 90, 180, 270)

# BOBOT HYBRID (Dapat dirubah sesuai kebutuhan pengujian Anda)
# Total bobot harus sama dengan 1.0 (Contoh: SSIM 60% dan AI ResNet 40%)
BOBOT_SSIM = 0.60
BOBOT_AI = 0.40

print("Memuat model ResNet50 ke dalam memori server...")
weights = models.ResNet50_Weights.DEFAULT
model = models.resnet50(weights=weights)
model.fc = nn.Identity()
model.eval()

# Menggunakan BICUBIC tanpa CenterCrop agar detail tekstur gambar utuh masuk ke model AI
preprocess = transforms.Compose([
    transforms.Resize((224, 224), interpolation=transforms.InterpolationMode.BICUBIC),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def _prepare_image_variants(image_path):
    img = Image.open(image_path).convert("RGB")
    color_variants = [
        img,
        ImageOps.autocontrast(img),
    ]

    variants = []
    seen = set()
    for color_img in color_variants:
        for angle in ROTATIONS:
            rotated = color_img.rotate(angle, expand=True) if angle else color_img
            key = (angle, rotated.size, rotated.tobytes()[:64])
            if key in seen:
                continue
            seen.add(key)
            variants.append(rotated)
    return variants


def _extract_feature_from_image(img):
    img_tensor = preprocess(img)
    img_batch = torch.unsqueeze(img_tensor, 0)

    with torch.no_grad():
        vektor = model(img_batch)
    return F.normalize(vektor, p=2, dim=1)


def _hitung_skor_ssim(img1_path, img2_path):
    """Fungsi internal untuk menghitung kecocokan tekstur murni menggunakan SSIM."""
    img1 = Image.open(img1_path).convert("L")
    img2 = Image.open(img2_path).convert("L")
    
    # Resize presisi tinggi dengan LANCZOS agar serat printer terjaga
    TARGET_SIZE = (256, 256)
    img1 = img1.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
    img2 = img2.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    
    score, _ = ssim(arr1, arr2, full=True, win_size=7)
    return max(0.0, min(float((score + 1.0) / 2.0), 1.0))


def compute_feature_match_score(img1_path, img2_path, method="hybrid_cosine"):
    """
    Membandingkan dua gambar dengan pilihan metode:
    - 'ssim'            : Fokus pada tekstur/serat mikro printer.
    - 'cosine'          : Fokus pada fitur geometri makro AI (Cosine).
    - 'euclidean'       : Fokus pada fitur geometri makro AI (L2 Distance).
    - 'hybrid_cosine'   : Kombinasi Bobot SSIM + Cosine (Sangat Direkomendasikan).
    - 'hybrid_euclidean': Kombinasi Bobot SSIM + Euclidean.
    """
    try:
        # Pilihan 1: SSIM Murni
        if method == "ssim":
            return _hitung_skor_ssim(img1_path, img2_path)

        # Hitung skor berbasis AI (Cosine / Euclidean)
        master_vectors = [_extract_feature_from_image(img) for img in _prepare_image_variants(img1_path)]
        scan_vectors = [_extract_feature_from_image(img) for img in _prepare_image_variants(img2_path)]

        best_ai_score = 0.0
        for vektor_a in master_vectors:
            for vektor_b in scan_vectors:
                
                if method in ["euclidean", "hybrid_euclidean"]:
                    jarak = torch.dist(vektor_a, vektor_b, p=2).item()
                    kemiripan = 1.0 - (jarak / 2.0)
                else:  # Bawaan default: Cosine
                    kemiripan = F.cosine_similarity(vektor_a, vektor_b).item()
                
                best_ai_score = max(best_ai_score, float(kemiripan))
        
        best_ai_score = max(0.0, min(best_ai_score, 1.0))

        # Pilihan 2: Cosine Murni atau Euclidean Murni
        if method in ["cosine", "euclidean"]:
            return best_ai_score

        # Pilihan 3: Metode Hybrid (Gabungan Tekstur + Geometri AI)
        skor_ssim = _hitung_skor_ssim(img1_path, img2_path)
        
        # Rumus Kombinasi Berbobot
        skor_hybrid = (BOBOT_SSIM * skor_ssim) + (BOBOT_AI * best_ai_score)
        
        print(f"[LOG] Detail Skor -> SSIM: {skor_ssim:.4f} | AI: {best_ai_score:.4f} | Hybrid: {skor_hybrid:.4f}")
        return max(0.0, min(skor_hybrid, 1.0))
    
    except Exception as e:
        print(f"Error in feature matching: {e}")
        return 0.0
