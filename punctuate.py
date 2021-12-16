
from streaming_punctuator.model import StreamingPunctuatorModel
import logging
import torch

class Punctuate():

    def __init__(self, model_checkpoint, tokenizer_file):
      self.model = StreamingPunctuatorModel.load_from_checkpoint(model_checkpoint, tokenizer_file=tokenizer_file)
      self.model.eval()

    def post_process(self, text):
      with torch.no_grad():
        return self.model.process_line(text)
