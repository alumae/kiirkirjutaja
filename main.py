import sys
import argparse
import logging
message_format = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(format=message_format, stream=sys.stderr, level=logging.INFO)

import time
import argparse
import re
import ray
import torch
import sherpa_onnx

# Needed for loading the speaker change detection model
from pytorch_lightning.utilities import argparse_utils
setattr(argparse_utils, "_gpus_arg_default", lambda x: 0)

from vad import SpeechSegmentGenerator
from turn import TurnGenerator
from asr import TurnDecoder
from lid import LanguageFilter
from online_scd.model import SCDModel
#import vosk
#from unk_decoder import UnkDecoder
#from compound import CompoundReconstructor
#from words2numbers import Words2Numbers
#from punctuate import Punctuate
from confidence import confidence_filter
from presenters import *
import utils
import gc
import tracemalloc
#date_strftime_format = "%y-%b-%d %H:%M:%S"


ray.init(num_cpus=4) 

#RemotePunctuate = ray.remote(Punctuate)
#RemoteWords2Numbers = ray.remote(Words2Numbers)

#unk_decoder = UnkDecoder()
#compound_reconstructor = CompoundReconstructor()
#remote_words2numbers = RemoteWords2Numbers.remote()
#remote_punctuate = RemotePunctuate.remote("models/punctuator/checkpoints/best.ckpt", "models/punctuator/tokenizer.json")


def process_result(result):
    #result = unk_decoder.post_process(result)    
    text = ""
    if "result" in result:
        result_words = []
        for word in result["result"]:
            if word["word"] in ",.!?" and len(result_words) > 0:
                result_words[-1]["word"] += word["word"]
            else:
                result_words.append(word)
        result["result"] = result_words
        #text = " ".join([wi["word"] for wi in result["result"]])

        #text = compound_reconstructor.post_process(text)
        #text = ray.get(remote_words2numbers.post_process.remote(text))
        #text = ray.get(remote_punctuate.post_process.remote(text))           
        #result = utils.reconstruct_full_result(result, text)
        #result = confidence_filter(result)
        return result
    else:
        return result

def main(args):
    
    if args.youtube_caption_url is not None:
        presenter = YoutubeLivePresenter(captions_url=args.youtube_caption_url)
    elif args.fab_speechinterface_url is not None:
        presenter = FabLiveWordByWordPresenter(fab_speech_iterface_url=args.fab_speechinterface_url)
    elif args.fab_bcast_url is not None:
        presenter = FabBcastWordByWordPresenter(fab_bcast_url=args.fab_bcast_url)
    elif args.zoom_caption_url is not None:
        presenter = ZoomPresenter(captions_url=args.zoom_caption_url)
    else:
        presenter = WordByWordPresenter(args.word_output_file, word_delay_secs=args.word_output_delay)
        #presenter = TerminalPresenter()
    
    scd_model = SCDModel.load_from_checkpoint("models/online-speaker-change-detector/checkpoints/epoch=102.ckpt")
    sherpa_model = sherpa_onnx.OnlineRecognizer(
            tokens="models/sherpa/tokens.txt",
            encoder="models/sherpa/encoder.onnx",
            decoder="models/sherpa/decoder.onnx",
            joiner="models/sherpa/joiner.onnx",
            num_threads=4,
            sample_rate=16000,
            feature_dim=80,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=300,  
            decoding_method="modified_beam_search",
            max_feature_vectors=1000,  # 10 seconds
        )


    speech_segment_generator = SpeechSegmentGenerator(args.input_file)
    language_filter = LanguageFilter()        
    
    def main_loop():
        for speech_segment in speech_segment_generator.speech_segments():
            presenter.segment_start()
            
            speech_segment_start_time = speech_segment.start_sample / 16000

            turn_generator = TurnGenerator(scd_model, speech_segment)        
            for i, turn in enumerate(turn_generator.turns()):
                if i > 0:
                    presenter.new_turn()
                turn_start_time = (speech_segment.start_sample + turn.start_sample) / 16000                
                
                turn_decoder = TurnDecoder(sherpa_model, language_filter.filter(turn.chunks()))            
                for res in turn_decoder.decode_results():
                    if "result" in res:
                        processed_res = process_result(res)
                        #processed_res = res
                        if res["final"]:
                            presenter.final_result(processed_res["result"])
                        else:
                            presenter.partial_result(processed_res["result"])
            presenter.segment_end()   
            gc.collect()   

    main_loop()        

if __name__ == '__main__':
    

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--youtube-caption-url', type=str)
    parser.add_argument('--fab-speechinterface-url', type=str)
    parser.add_argument('--fab-bcast-url', type=str)
    parser.add_argument('--zoom-caption-url', type=str)
    parser.add_argument('--word-output-file', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('--word-output-delay', default=0.0, type=float, help="Words are not outputted before that many seconds have passed since their actual start")
    parser.add_argument('input_file')

    args = parser.parse_args()

    main(args)
    
