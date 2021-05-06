
from g2p import P2G
import logging
class UnkDecoder():

    def __init__(self):
        self.p2g = P2G("models/char_lm/train.fst")


    def post_process(self, full_result):
        if "result" in full_result:
            for word_info in full_result["result"]:
                if word_info["word"] == "<unk>":
                    phones = " ".join([p.partition("_")[0] for p in word_info["phones"].split()])
                    word_result = self.p2g.process(phones, num_nbest=1)
                    word = word_result[0][0]
                    word_info["word"] = word
                    word_info["was_unk"] = True
        return full_result
