import logging
from compounder import Compounder
import pywrapfst as fst

class CompoundReconstructor():

    def __init__(self):
        self.compounder = Compounder("models/compounderlm/G.fst", "models/compounderlm/words.txt")


    def post_process(self, str):
        words = str.split()
        result = self.compounder.apply_compounder(words)
        result = " ".join(result)
        result = result.replace(" +C+ ", "")
        result = result.replace(" +D+ ", "-")
        return result


