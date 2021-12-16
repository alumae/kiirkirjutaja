from online_scd.model import SCDModel
from online_scd.streaming import StreamingDecoder
from vad import SpeechSegment
from queue import Queue
import torch
import threading
import logging

class TurnGenerator:
    def __init__(self, model, chunk_generator):
        self.threshold = 0.1
        self.chunk_generator = chunk_generator
        self.model = model
        self.model.eval()
        self.speech_segment_queue = Queue(10)
        self.streaming_decoder = StreamingDecoder(self.model)
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def turns(self):
        while True:
            speech_segment = self.speech_segment_queue.get()
            if speech_segment is not None:
                yield speech_segment
            else:
                return

    def run(self):    
        with torch.no_grad():                    
            sample_pos = 0
            chunk_queue = Queue(10)
            speech_segment = SpeechSegment(sample_pos, chunk_queue)
            self.speech_segment_queue.put(speech_segment)                                                    
            buffer = torch.tensor([])

            for chunk in self.chunk_generator.chunks():
                buffer = torch.cat([buffer, chunk])
                pos = 0
                for i, probs in enumerate(self.streaming_decoder.process_audio(chunk.numpy())):
                    if probs[1] > self.threshold:     
                        chunk_queue.put(None)
                        logging.debug(f"Speaker change detected at sample {sample_pos}")
                        chunk_queue = Queue(10)
                        speech_segment = SpeechSegment(sample_pos, chunk_queue)
                        self.speech_segment_queue.put(speech_segment)                                                                        
                    else:
                        pass
                    chunk_queue.put(buffer[ : 1600])
                    buffer = buffer[1600: ]                    
                    
                    sample_pos += 1600 # 100 ms
                    pos += 1

            
            chunk_queue.put(buffer)            
            chunk_queue.put(None)                    
            self.speech_segment_queue.put(None)                                                                        
            logging.debug("Ending turn detector for this speech segment")
            
            

            


    