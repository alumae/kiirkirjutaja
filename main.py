import sys
import argparse
import logging
import argparse
import re
import ray

# Needed for loading the speaker change detection model
from pytorch_lightning.utilities import argparse_utils
setattr(argparse_utils, "_gpus_arg_default", lambda x: 0)

from vad import SpeechSegmentGenerator
from turn import TurnGenerator
from asr import TurnDecoder
from online_scd.model import SCDModel
import vosk
from unk_decoder import UnkDecoder
from compound import CompoundReconstructor
from words2numbers import Words2Numbers
from punctuate import Punctuate
#from confidence import confidence_filter
from presenters import *

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
ray.init(num_cpus=4) 

RemotePunctuate = ray.remote(Punctuate)
RemoteWords2Numbers = ray.remote(Words2Numbers)

unk_decoder = UnkDecoder()
compound_reconstructor = CompoundReconstructor()
remote_words2numbers = RemoteWords2Numbers.remote()
remote_punctuate = RemotePunctuate.remote("models/punctuator/checkpoints/best.ckpt", "models/punctuator/tokenizer.json")

def process_result(result):
    result = unk_decoder.post_process(result)
    text = ""
    if "result" in result:
        text = " ".join([wi["word"] for wi in result["result"]])
    
    text = compound_reconstructor.post_process(text)
    text = ray.get(remote_words2numbers.post_process.remote(text))
    text = ray.get(remote_punctuate.post_process.remote(text))   
    return text

def main(args):
    
    if args.youtube_caption_url is not None:
        presenter = YoutubeLivePresenter(captions_url=args.youtube_caption_url)
    elif args.fab_speechinterface_url is not None:
        presenter = FabLiveWordByWordPresenter(fab_speech_iterface_url=args.fab_speechinterface_url)
    elif args.zoom_caption_url is not None:
        presenter = ZoomPresenter(captions_url=args.zoom_caption_url)
    else:
        presenter = WordByWordPresenter(args.word_output_file)
    
    scd_model = SCDModel.load_from_checkpoint("models/online-speaker-change-detector/checkpoints/epoch=102.ckpt")
    vosk_model = vosk.Model("models/asr_model")

    speech_segment_generator = SpeechSegmentGenerator(args.input_file)
    for speech_segment in speech_segment_generator.speech_segments():
        #print("New segment")
        presenter.segment_start()

        speech_segment_start_time = speech_segment.start_sample / 16000

        turn_generator = TurnGenerator(scd_model, speech_segment)        
        for i, turn in enumerate(turn_generator.turns()):
            #print("New turn")
            if i > 0:
                presenter.new_turn()
            turn_start_time = (speech_segment.start_sample + turn.start_sample) / 16000
            
            turn_decoder = TurnDecoder(vosk_model, turn.chunks())            
            for res in turn_decoder.decode_results():
                #logging.info("Result: " + str(res))
                text = process_result(res)
                if res["final"]:
                    presenter.final_result(text)
                else:
                    presenter.partial_result(text)
        presenter.segment_end()
        

if __name__ == '__main__':
    

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--youtube-caption-url', type=str)
    parser.add_argument('--fab-speechinterface-url', type=str)
    parser.add_argument('--zoom-caption-url', type=str)
    parser.add_argument('--word-output-file', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('input_file')

    args = parser.parse_args()

    main(args)
    
