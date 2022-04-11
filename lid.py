import sys
import torch
import logging
import numpy as np
import json

class LanguageFilter():
    def __init__(self, target_language="et", prior=0.50, alternative_targets=[]):
        self.target_language = target_language
        self.model = torch.jit.load("models/lang_classifier_95/lang_classifier_95.jit")
        lang_dict = json.load(open("models/lang_classifier_95/lang_dict_95.json"))
        self.languages = [v[1] for v in sorted(lang_dict.items(), key=lambda i: int(i[0]))]
        self.target_language_id = [idx for idx, element in enumerate(self.languages) if element.startswith(self.target_language)][0]
        self.alternative_language_ids = [idx for idx, element in enumerate(self.languages) if element[:2] in alternative_targets]
        self.target_prior = prior
        self.lid_min_seconds = 3.0
        self.lid_min_seconds_2 = 5.0

    def get_language_probs(self, buffer):
        lang_logits, lang_group_logits = self.model(buffer.unsqueeze(0))
        softm = torch.softmax(lang_logits, dim=1).squeeze()
        return softm

    def get_language(self, buffer):
        logging.debug("Doing LID")
        probs = self.get_language_probs(buffer)
        logging.debug(f"Original prob for languge {self.target_language}: {probs[self.target_language_id]:.2f}")
        priors0 = torch.ones(len(probs), requires_grad=False) / len(probs)
        true_priors = (torch.ones(len(probs), requires_grad=False) - self.target_prior) / (len(probs) - 1)
        true_priors[self.target_language_id] = self.target_prior
        numerator = true_priors/priors0 * probs
        corrected_probs = numerator / numerator.sum()
        logging.debug(f"Corrected prob for languge {self.target_language}: {corrected_probs[self.target_language_id]:.2f}")
        language_id = corrected_probs.argmax()
        logging.debug(f"Detected language: {self.languages[language_id]}: {corrected_probs[language_id]:.2f}")
        return language_id

    def filter(self, chunk_generator):
        with torch.no_grad():
            buffer = torch.tensor([], requires_grad=False)
            buffering = True
            did_1st_check = False
            non_target_turn = False
            for chunk in chunk_generator:
                if buffering:                                   
                    buffer = torch.cat([buffer, chunk])
                    del chunk
                    if (len(buffer) > self.lid_min_seconds * 16000) and not did_1st_check:
                        language_id = self.get_language(buffer)
                        did_1st_check = True
                        if language_id == self.target_language_id or language_id in self.alternative_language_ids:
                            yield buffer    
                            buffering = False
                            del buffer
                        else:
                            logging.info("Non-target language chunk? Waiting for more data to confirm...")

                    elif (len(buffer) > self.lid_min_seconds_2 * 16000):
                        buffering = False
                        language_id = self.get_language(buffer)
                        if language_id == self.target_language_id or language_id in self.alternative_language_ids:
                            yield buffer    
                            del buffer
                        else:
                            logging.info("Consuming non-target language speech turn...")
                            del buffer
                            non_target_turn = True
                else:
                    if non_target_turn:
                        pass
                    else:
                        yield chunk
                    del chunk
            if buffering:
                if len(buffer) > 0:
                    language_id = self.get_language(buffer)
                    if language_id == self.target_language_id:
                        yield buffer   
                del buffer 


    # def filter(self, chunk_generator):
    #     buffer = torch.tensor([])
    #     buffering = True
    #     did_1st_check = False
    #     while True:
    #         try:
    #             chunk = next(chunk_generator)
    #             if buffering:                                   
    #                 buffer = torch.cat([buffer, chunk])
    #                 if (len(buffer) > self.lid_min_seconds * 16000) and not did_1st_check:
    #                     language_id = self.get_language(buffer)
    #                     did_1st_check = True
    #                     if language_id == self.target_language_id or language_id in self.alternative_language_ids:
    #                         yield buffer    
    #                         del buffer
    #                         buffering = False
    #                     else:
    #                         logging.info("Non-target language chunk? Waiting for more data to confirm...")

    #                 elif (len(buffer) > self.lid_min_seconds_2 * 16000):
    #                     buffering = False
    #                     language_id = self.get_language(buffer)
    #                     if language_id == self.target_language_id or language_id in self.alternative_language_ids:
    #                         yield buffer    
    #                         del buffer
    #                     else:
    #                         logging.info("Consuming non-target language speech turn...")
    #                         while True:
    #                             next(chunk_generator)
    #             else:
    #                 yield chunk
    #                 del chunk
    #         except StopIteration:
    #             break
    #     if buffering:
    #         if len(buffer) > 0:
    #             language_id = self.get_language(buffer)
    #             if language_id == self.target_language_id:
    #                 yield buffer    
    #                 del buffer
                



        


