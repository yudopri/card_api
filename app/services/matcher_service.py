import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms


THRESHOLD_LULUS = 0.70

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


def ekstrak_fitur(image_path):
    """Mengubah gambar crop menjadi vektor fitur ResNet50."""
    img = Image.open(image_path).convert("RGB")
    img_tensor = preprocess(img)
    img_batch = torch.unsqueeze(img_tensor, 0)

    with torch.no_grad():
        vektor = model(img_batch)
    return vektor


def compute_feature_match_score(img1_path, img2_path):
    """
    Compares two crop images using ResNet50 embeddings + cosine similarity.
    Returns a similarity score between 0.0 and 1.0.
    """
    try:
        vektor_a = ekstrak_fitur(img1_path)
        vektor_b = ekstrak_fitur(img2_path)
        kemiripan = F.cosine_similarity(vektor_a, vektor_b).item()
        return max(0.0, min(float(kemiripan), 1.0))
    except Exception as e:
        print(f"Error in ResNet50 feature matching: {e}")
        return 0.0
