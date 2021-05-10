from scipy.ndimage.filters import uniform_filter1d
import numpy as np
import logging


def confidence_filter(full_result, threshold=0.75):
    if "result" in full_result:
        confidences = np.array([wi["conf"] for wi in full_result["result"]])
        smoothed_confidences = uniform_filter1d(confidences, size=5)
        for i, c in enumerate(smoothed_confidences):
            if c < threshold:
                #logging.info(f'Hiding word {full_result["result"][i]["word"]} because its smoothed confidence is {c}')
                full_result["result"][i]["word"] = "---"

    return full_result
