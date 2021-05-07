import textwrap
import requests
from datetime import datetime
import logging
import sys

import term

class ResultPresenter:

    def partial_result(self, text):
        pass

    def final_result(self, text):
        pass

    def segment_start(self):
        pass

    def segment_end(self):
        pass

    def new_turn(self):
        pass

def prettify(text, is_sentence_start):
    words = text.split()
    result = ""
    last_word = ""
    for word in words:
        if last_word in list(".?!"):
            word = word[0].upper() + word[1:]
        if word in list(",.!?"):
            result += word
        else:
            if len(result) > 0:
                result += " "
            result += word
        last_word = word
    if is_sentence_start and len(result) > 0:
        result = result[0].upper() + result[1:]
    return result


class SubtitlePresenter(ResultPresenter):

    def __init__(self, max_chars=80):
        self.max_chars = max_chars
        self.short_line_threshold = 15
        self.current_lines = ["", ""]        
        self.last_utt_lines = [""]        

    def _update(self):
        raise Exception("not implemented")

    def _show_result(self, text, is_final):
        
        if len(text) > 0 and text[-1] in list(",.?!") and not is_final:
            text = text[0:-1].strip()

        is_sentence_start = False
        if len(self.last_utt_lines) > 0 and len(self.last_utt_lines[-1]) > 0 and self.last_utt_lines[-1][-1] in list("!?."):
            is_sentence_start = True
        text = prettify(text, is_sentence_start)
        lines = self.last_utt_lines + textwrap.wrap(text, width=self.max_chars)
        if len(lines) == 0:
            return
        if not is_final and len(lines[-1]) < self.short_line_threshold and len(lines) > 1:
            # don't show very short last line of a partial result 
            lines.pop()

        if len(lines) > 1:
            self.current_lines = lines[-2:]
        else:
            self.current_lines[0] = self.current_lines[1]
            self.current_lines[1] = lines[0]
        self._update()
        if is_final:
            self.last_utt_lines = lines[-2:]


    def partial_result(self, text):
        self._show_result(text, False)

    def final_result(self, text):
        self._show_result(text, True)
        

class TerminalPresenter(SubtitlePresenter):
    def __init__(self, max_chars=80, ):
        super().__init__(max_chars)        
        term.clear()

    def _update(self):
        term.clear()
        term.homePos()
        term.writeLine(self.current_lines[0])
        term.writeLine(self.current_lines[1])



class FabLivePresenter(SubtitlePresenter):
    def __init__(self, fab_speech_iterface_url, max_chars=40):

        super().__init__(max_chars)        
        self.fab_speech_iterface_url = fab_speech_iterface_url
        
    def _update(self):
        logging.info("Sending captions to FAB")
        #server = ' region:reg1#cue1' 
        server = ""
        
        text = self.current_lines[0] + '{NL}' + self.current_lines[1]  + '{SEND}'
        logging.info(f"Sending text: {text}")
        resp = requests.get(url=self.fab_speech_iterface_url, params={"text": text})
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
        


class AbstractWordByWordPresenter(ResultPresenter):

    def __init__(self):
        self.word_delay = 3
        self.current_words = []
        self.num_sent_words = 0
        self.is_sentence_start = True
        

    def _send_word(self, word):
        pass
    
    def _send_final(self):
        pass

    def partial_result(self, text):
        text = prettify(text, self.is_sentence_start)
        words = text.split()
        if len(words) - self.word_delay > self.num_sent_words:
            for i in range(self.num_sent_words,  len(words) - self.word_delay):
                self._send_word(words[i])
                self.num_sent_words += 1

    def final_result(self, text):
        text = prettify(text, self.is_sentence_start)

        words = text.split()
        for i in range(self.num_sent_words,  len(words)):
            self._send_word(words[i])
            self.num_sent_words += 1
        
        self._send_final()
        self.num_sent_words = 0
        if len(text) > 0 and text[-1] in list("!?."):
            self.is_sentence_start = True
        else:
            self.is_sentence_start = False


    def segment_start(self):
        pass

    def segment_end(self):
        pass

    def new_turn(self):
        self._send_word("- ")


class WordByWordPresenter(AbstractWordByWordPresenter):
    def __init__(self, output_file):
        super().__init__()        
        self.output_file = output_file

    def _send_word(self, word):
        if self.num_sent_words > 0:
            print(" ", end="", file=self.output_file)
        print(word, end="", file=self.output_file)
        self.output_file.flush()
    
    def _send_final(self):
        print("", file=self.output_file)
        self.output_file.flush()


class YoutubeLivePresenter(AbstractWordByWordPresenter):
    def __init__(self, captions_url):
        super().__init__()        
        self.captions_url = captions_url
        self.seq = 1
        self.current_words = []
        self.min_num_chars = 42
        self.current_word_timestamps = []

    def _do_send(self):
        if len(self.current_words) == 0:
            return
        logging.info("Sending captions to Youtube")
        server = ' region:reg1#cue1' 
        headers = {'content-type': 'text/plain'}
        #Formatting the time properly
        post = "\n".join([time + '\n ' + word  for word, time in zip(self.current_words, self.current_word_timestamps)])
        post = post + '\n'
        ingestion_url =  self.captions_url + "&seq=" + str(self.seq)
        resp = requests.post(url=ingestion_url, data=post.encode('utf-8'), headers=headers)
        logging.info(f"Sent body: {post}")
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
        self.seq += 1
        self.current_words = []
        self.current_word_timestamps = []

    def _send_word(self, word):
        self.current_words.append(word)        
        self.current_word_timestamps.append(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3])
        text = " ".join(self.current_words)
        if len(text) > self.min_num_chars:
            self._do_send()

    def _send_final(self):        
        self._do_send()



class FabLiveWordByWordPresenter(AbstractWordByWordPresenter):
    def __init__(self, fab_speech_iterface_url):

        super().__init__()        
        self.fab_speech_iterface_url = fab_speech_iterface_url
        
    
    def _send_word(self, word):
        logging.info("Sending captions to FAB")
        if self.num_sent_words > 0:
            word = " " + word
        resp = requests.get(url=self.fab_speech_iterface_url, params={"text": word})
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
        
    
    def _send_final(self):
        pass
        #self._send_word("{SEND}")


class ZoomPresenter(AbstractWordByWordPresenter):

    def __init__(self, captions_url):
        super().__init__()        
        self.captions_url = captions_url
        self.seq = 10000
        self.current_words = []
        self.min_num_chars = 42

    def _do_send(self, text):
        logging.info("Sending captions to Zoom")
        headers = {'content-type': 'text/plain'}
        lang = "et-EE"

        ingestion_url =  self.captions_url + "&seq=" + str(self.seq)
        resp = requests.post(url=ingestion_url, data=text.encode('utf-8'), headers=headers)
        logging.info(f"Sent body: {text}")
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
        self.seq += 1

    def _send_word(self, word):
        self.current_words.append(word)
        text = " ".join(self.current_words)
        if len(text) > self.min_num_chars:
            self._do_send(text)
            self.current_words = []

    def _send_final(self):        
        text = " ".join(self.current_words)
        self._do_send(text)
        self.current_words = []
