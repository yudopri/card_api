import cv2
import numpy as np
import os

def normalize_image(image_path):
    """
    Normalizes the image to handle differences in lighting, ink, and material.
    Step: Grayscale -> Gaussian Blur (to reduce noise/ink dithering) -> CLAHE (to normalize contrast).
    """
    try:
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            return None
            
        # 1. Convert to Grayscale (removes ink color variation)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Reduce noise (ink dithering/material texture noise)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 3. CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Better than global histogram equalization because it handles local lighting differences.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        normalized = clahe.apply(blurred)
        
        return normalized
    except Exception as e:
        print(f"Error in normalizing image: {e}")
        return None

def compute_feature_match_score(img1_path, img2_path):
    """
    Compares two images using ORB (Oriented FAST and Rotated BRIEF).
    Returns a confidence score (0.0 to 1.0).
    ORB is invariant to rotation and scaling.
    """
    try:
        # Normalize both images
        img1 = normalize_image(img1_path)
        img2 = normalize_image(img2_path)
        
        if img1 is None or img2 is None:
            return 0.0
            
        # Initialize ORB detector
        orb = cv2.ORB_create(nfeatures=1000)
        
        # Find the keypoints and descriptors
        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)
        
        if des1 is None or des2 is None:
            return 0.0
            
        # Use BFMatcher with Hamming distance
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # Match descriptors
        matches = bf.match(des1, des2)
        
        # Sort them in the order of their distance
        matches = sorted(matches, key=lambda x: x.distance)
        
        # Calculate score
        # We consider "good" matches those with low distance.
        # Max potential matches is limited by the minimum number of keypoints detected.
        min_keypoints = min(len(kp1), len(kp2))
        if min_keypoints == 0:
            return 0.0
            
        # Filter good matches (distance threshold)
        good_matches = [m for m in matches if m.distance < 50]
        
        # Ratio of good matches to keypoints
        score = len(good_matches) / min_keypoints if min_keypoints > 0 else 0
        
        # Cap score at 1.0
        return min(float(score), 1.0)
        
    except Exception as e:
        print(f"Error in feature matching: {e}")
        return 0.0
