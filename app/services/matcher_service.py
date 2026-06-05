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

def compute_fft_similarity(img1, img2):
    """
    Compares two normalized grayscale images in the frequency domain.
    Returns a similarity score between 0.0 and 1.0.
    """
    try:
        def fft_magnitude(image):
            rows, cols = image.shape
            optimal_rows = cv2.getOptimalDFTSize(rows)
            optimal_cols = cv2.getOptimalDFTSize(cols)

            padded = cv2.copyMakeBorder(
                image,
                0,
                optimal_rows - rows,
                0,
                optimal_cols - cols,
                cv2.BORDER_CONSTANT,
                value=0,
            )

            float_img = np.float32(padded)
            dft = cv2.dft(float_img, flags=cv2.DFT_COMPLEX_OUTPUT)
            dft_shift = np.fft.fftshift(dft)
            magnitude = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])
            magnitude = np.log1p(magnitude)
            magnitude = cv2.normalize(magnitude, None, 0, 1, cv2.NORM_MINMAX)
            return magnitude

        mag1 = fft_magnitude(img1)
        mag2 = fft_magnitude(img2)

        # Align shapes if padding resulted in slight differences.
        min_rows = min(mag1.shape[0], mag2.shape[0])
        min_cols = min(mag1.shape[1], mag2.shape[1])
        mag1 = mag1[:min_rows, :min_cols]
        mag2 = mag2[:min_rows, :min_cols]

        diff = np.mean(np.abs(mag1 - mag2))
        similarity = 1.0 - float(diff)
        return max(0.0, min(similarity, 1.0))
    except Exception as e:
        print(f"Error in FFT similarity: {e}")
        return 0.0

def compute_feature_match_score(img1_path, img2_path):
    """
    Compares two images using SIFT + FLANN.
    Returns a confidence score (0.0 to 1.0).
    SIFT is more robust for textured, feature-rich images and FLANN speeds up nearest-neighbor matching.
    """
    try:
        # Normalize both images
        img1 = normalize_image(img1_path)
        img2 = normalize_image(img2_path)
        
        if img1 is None or img2 is None:
            return 0.0
            
        # Initialize SIFT detector
        if hasattr(cv2, "SIFT_create"):
            sift = cv2.SIFT_create()
        else:
            sift = cv2.xfeatures2d.SIFT_create()
        
        # Find the keypoints and descriptors
        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)
        
        if des1 is None or des2 is None:
            return 0.0

        # FLANN parameters for SIFT descriptors
        index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)

        # KNN matching with Lowe's ratio test
        matches = flann.knnMatch(des1, des2, k=2)
        
        # Calculate score
        # We consider "good" matches those with low distance.
        # Max potential matches is limited by the minimum number of keypoints detected.
        min_keypoints = min(len(kp1), len(kp2))
        if min_keypoints == 0:
            return 0.0

        # Filter good matches using Lowe's ratio test
        good_matches = []
        for pair in matches:
            if len(pair) < 2:
                continue
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
        
        # Ratio of good matches to keypoints
        score = len(good_matches) / min_keypoints if min_keypoints > 0 else 0
        
        # Cap score at 1.0
        sift_score = min(float(score), 1.0)
        fft_score = compute_fft_similarity(img1, img2)

        # Combine feature and frequency-domain signals.
        final_score = (0.75 * sift_score) + (0.25 * fft_score)
        return min(float(final_score), 1.0)
        
    except Exception as e:
        print(f"Error in feature matching: {e}")
        return 0.0
