
from streaming_punctuator.model import StreamingPunctuatorModel

class Punctuate():

    def __init__(self, model_checkpoint):
      self.model = StreamingPunctuatorModel.load_from_checkpoint(model_checkpoint)
      self.model.eval()


    def post_process(self, text):
      return self.model.process_line(text)
