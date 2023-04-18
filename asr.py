import sys
import os
import sys
import torch
import torchaudio
import json
from queue import Queue
import threading

def text2result(text):
    words = text.split()
    return {"result": [{"word": word} for word in words]}

def add_pseudo_timestamps(result, start_sample, end_sample):
    #print(result)
    if len(result["result"]) == 0:
        return result
    num_chars = sum([len(w["word"]) for w in result["result"]])
    num_samples_per_char = (end_sample  - start_sample) / num_chars
    pos = start_sample
    for w in result["result"]:
        w["start"] = pos / 16000
        pos += len(w["word"]) * num_samples_per_char
    #print(result)        
    return result



class TurnDecoder():
    def __init__(self, recognizer, chunk_generator):
        self.recognizer = recognizer
        self.chunk_generator = chunk_generator
        self.send_chunk_length = 16000 // 10  # how big are the chunks that we send to Kaldi
        self.result_queue = Queue(10)
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def decode_results(self):
        while True:
            result = self.result_queue.get()
            if result is not None:
                yield result
            else:
                return

    def run(self):
        buffer = torch.tensor([])
        tail_padding = torch.rand(
            int(16000 * 0.3), dtype=torch.float32
        )
        
        stream = self.recognizer.create_stream()
        last_result = ""
        segment_id = 0
        current_start_sample = 0
        num_samples_consumed = 0
        for chunk in self.chunk_generator:
            buffer = torch.cat([buffer, chunk])
            
            if len(buffer) >= self.send_chunk_length:
                stream.accept_waveform(16000, buffer.numpy())
                num_samples_consumed += len(buffer)
                while self.recognizer.is_ready(stream):
                    self.recognizer.decode_stream(stream)

                is_endpoint = self.recognizer.is_endpoint(stream)                    
                result = self.recognizer.get_result(stream)            
                jres = text2result(result)
                jres = add_pseudo_timestamps(jres, current_start_sample, num_samples_consumed)
                if result and (last_result != result) or is_endpoint:  
                    last_result = result
                    jres["final"] = is_endpoint
                    self.result_queue.put(jres)
                
                if is_endpoint:
                    if result:
                        segment_id += 1
                    current_start_sample = num_samples_consumed
                    self.recognizer.reset(stream)                

                buffer = torch.tensor([])                    

        
        if len(buffer) > 0:
            stream.accept_waveform(16000, buffer.numpy())
            num_samples_consumed += len(buffer)        
        stream.accept_waveform(16000, tail_padding.numpy())   
        num_samples_consumed += len(tail_padding)        
        stream.input_finished()        
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)
                
        text = self.recognizer.get_result(stream)            
        self.recognizer.reset(stream)            
        jres = text2result(text)
        jres = add_pseudo_timestamps(jres, current_start_sample, num_samples_consumed)
        jres["final"] = True
        self.result_queue.put(jres)
        self.result_queue.put(None)

