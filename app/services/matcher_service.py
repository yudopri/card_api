import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision import models, transforms


THRESHOLD_LULUS = 0.85
ROTATIONS = (0, 90, 180, 270)

print("Memuat model ResNet50 ke dalam memori server...")
weights = models.ResNet50_Weights.DEFAULT
model = models.resnet50(weights=weights)
model.fc = nn.Identity()
model.eval()

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
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


def ekstrak_fitur(image_path):
    """Mengubah gambar crop RGB menjadi vektor fitur ResNet50."""
    img = Image.open(image_path).convert("RGB")
    img_tensor = preprocess(img)
    img_batch = torch.unsqueeze(img_tensor, 0)

    with torch.no_grad():
        vektor = model(img_batch)
    return F.normalize(vektor, p=2, dim=1)


def compute_feature_match_score(img1_path, img2_path):
    """
    Compares two crop images using ResNet50 embeddings + cosine similarity.
    Returns a similarity score between 0.0 and 1.0.
    """
    try:
        master_vectors = [
            _extract_feature_from_image(img)
            for img in _prepare_image_variants(img1_path)
        ]
        scan_vectors = [
            _extract_feature_from_image(img)
            for img in _prepare_image_variants(img2_path)
        ]

        best_score = 0.0
        for vektor_a in master_vectors:
            for vektor_b in scan_vectors:
                kemiripan = F.cosine_similarity(vektor_a, vektor_b).item()
                best_score = max(best_score, float(kemiripan))

        return max(0.0, min(best_score, 1.0))
    except Exception as e:
        print(f"Error in ResNet50 feature matching: {e}")
        return 0.0
