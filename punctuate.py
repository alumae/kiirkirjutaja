
from streaming_punctuator.model import StreamingPunctuatorModel
import logging

class Punctuate():

    def __init__(self, model_checkpoint, tokenizer_file):
      self.model = StreamingPunctuatorModel.load_from_checkpoint(model_checkpoint, tokenizer_file=tokenizer_file)
      self.model.eval()

    def post_process(self, text):
      return self.model.process_line(text)
