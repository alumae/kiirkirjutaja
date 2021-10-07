import sys
import torch
import torch.nn.functional as F
from itertools import repeat
from collections import deque
from queue import Queue
import threading
import logging
import numpy as np
import ray
import subprocess
import json

class LanguageFilter():
    def __init__(self, target_language="et", prior=0.99):
        self.target_language = target_language
        self.model = torch.jit.load("models/lang_classifier_95/lang_classifier_95.jit")
        lang_dict = json.load(open("models/lang_classifier_95/lang_dict_95.json"))
        self.languages = [v[1] for v in sorted(lang_dict.items(), key=lambda i: int(i[0]))]
        self.target_language_id = [idx for idx, element in enumerate(self.languages) if element.startswith(self.target_language)][0]
        self.target_prior = prior
        self.lid_min_seconds = 3.0

    def get_language_probs(self, buffer):
        lang_logits, lang_group_logits = self.model(buffer.unsqueeze(0))
        softm = torch.softmax(lang_logits, dim=1).squeeze()
        return softm


    def filter(self, chunk_generator):
        buffer = torch.tensor([])
        language = None
        for chunk in chunk_generator:
            buffer = torch.cat([buffer, chunk])
            if (language is None) and (len(buffer) > self.lid_min_seconds * 16000):
                logging.info("Doing LID")
                probs = self.get_language_probs(buffer)
                logging.info(f"Original prob for languge {self.target_language}: {probs[self.target_language_id]:.2f}")
                priors0 = torch.ones(len(probs)) / len(probs)
                true_priors = torch.ones(len(probs)) * 1 - self.target_prior
                true_priors[self.target_language_id] = self.target_prior
                numerator = true_priors/priors0 * probs
                corrected_probs = numerator / numerator.sum()
                logging.info(f"Corrected prob for languge {self.target_language}: {corrected_probs[self.target_language_id]:.2f}")
                language = corrected_probs.argmax()
                logging.info(f"Detected language: {self.languages[language]}")
            if language is not None:
                if language == self.target_language_id:
                    yield chunk
                else:
                    # filter out the rest of this chunk                    
                    pass 
            else:
                yield chunk

        


