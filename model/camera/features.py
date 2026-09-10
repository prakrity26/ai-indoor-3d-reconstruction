"""ORB detection and ratio-tested matching."""

from __future__ import annotations

import cv2
import numpy as np


def detect_orb(
    image_bgr: np.ndarray,
    nfeatures: int,
) -> tuple[list[cv2.KeyPoint], np.ndarray | None]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=nfeatures)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    return list(keypoints), descriptors


def match_descriptors(
    desc_a: np.ndarray | None,
    desc_b: np.ndarray | None,
    ratio: float,
) -> list[cv2.DMatch]:
    if desc_a is None or desc_b is None:
        return []
    if len(desc_a) < 2 or len(desc_b) < 2:
        return []
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    knn = matcher.knnMatch(desc_a, desc_b, k=2)
    good: list[cv2.DMatch] = []
    for pair in knn:
        if len(pair) < 2:
            continue
        best, second = pair
        if best.distance < ratio * second.distance:
            good.append(best)
    return good


def matched_points(
    keypoints_a: list[cv2.KeyPoint],
    keypoints_b: list[cv2.KeyPoint],
    matches: list[cv2.DMatch],
) -> tuple[np.ndarray, np.ndarray]:
    pts_a = np.array([keypoints_a[m.queryIdx].pt for m in matches], dtype=np.float64)
    pts_b = np.array([keypoints_b[m.trainIdx].pt for m in matches], dtype=np.float64)
    return pts_a, pts_b
