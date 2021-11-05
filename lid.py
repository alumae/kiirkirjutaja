import sys
import torch
import logging
import numpy as np
import json



class LanguageFilter():
    def __init__(self, target_language="et", prior=0.80, alternative_targets=[]):
        self.target_language = target_language
        self.model = torch.jit.load("models/lang_classifier_95/lang_classifier_95.jit")
        lang_dict = json.load(open("models/lang_classifier_95/lang_dict_95.json"))
        self.languages = [v[1] for v in sorted(lang_dict.items(), key=lambda i: int(i[0]))]
        self.target_language_id = [idx for idx, element in enumerate(self.languages) if element.startswith(self.target_language)][0]
        self.alternative_language_ids = [idx for idx, element in enumerate(self.languages) if element[:2] in alternative_targets]
        self.target_prior = prior
        self.lid_min_seconds = 3.0

    def get_language_probs(self, buffer):
        lang_logits, lang_group_logits = self.model(buffer.unsqueeze(0))
        softm = torch.softmax(lang_logits, dim=1).squeeze()
        return softm

    def get_language(self, buffer):
        logging.info("Doing LID")
        probs = self.get_language_probs(buffer)
        logging.info(f"Original prob for languge {self.target_language}: {probs[self.target_language_id]:.2f}")
        priors0 = torch.ones(len(probs)) / len(probs)
        true_priors = (torch.ones(len(probs)) - self.target_prior) / (len(probs) - 1)
        true_priors[self.target_language_id] = self.target_prior
        numerator = true_priors/priors0 * probs
        corrected_probs = numerator / numerator.sum()
        logging.info(f"Corrected prob for languge {self.target_language}: {corrected_probs[self.target_language_id]:.2f}")
        language_id = corrected_probs.argmax()
        logging.info(f"Detected language: {self.languages[language_id]}: {corrected_probs[language_id]:.2f}")
        return language_id

    def filter(self, chunk_generator):
        buffer = torch.tensor([])
        buffering = True
        while True:
            try:
                chunk = next(chunk_generator)
                if buffering:               
                    buffer = torch.cat([buffer, chunk])
                    #del chunk
                    if (len(buffer) > self.lid_min_seconds * 16000):
                        buffering = False
                        language_id = self.get_language(buffer)
                        if language_id == self.target_language_id or language_id in self.alternative_language_ids:
                            yield buffer    
                            buffer = None
                        else:
                            logging.debug("Consuming non-target language speech turn...")
                            while True:
                                chunk = next(chunk_generator)                            
                else:
                    yield chunk
            except StopIteration:
                break
        if buffering:
            if len(buffer) > 0:
                language_id = self.get_language(buffer)
                if language_id == self.target_language_id:
                    yield buffer    
                



        


