import textwrap
import requests
from datetime import datetime, timedelta
import logging
import sys
import re
import term
import time

from event_scheduler import EventScheduler

class ResultPresenter:

    def partial_result(self, words):
        pass

    def final_result(self, words):
        pass

    def segment_start(self):
        #logging.info("New segment")        
        self.turn_start_time = datetime.utcnow()

    def segment_end(self):
        pass

    def new_turn(self):
        #logging.info("New turn")
        self.turn_start_time = datetime.utcnow()
        


def prettify(words, is_sentence_start):
    #return words

    for word in words:
        if is_sentence_start:
            word["word"] = word["word"][0].upper() + word["word"][1:]
        is_sentence_start = False

        #if word["word"][0] in list("?.!"):
        #    word["word"] = word["word"].title()

        if word["word"][-1] in ".!?":
            is_sentence_start = True
        #word["word"] = re.sub(r"(.*) ([,.?!])$", r"\1\2", word["word"])

    return words


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
        text = " ".join([w["word"] for w in prettify(text, is_sentence_start)])
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


class AbstractWordByWordPresenter(ResultPresenter):

    def __init__(self, word_delay_secs=3.0):
        self.word_delay = 2
        self.word_delay_secs = word_delay_secs
        self.current_words = []
        self.num_sent_words = 0
        self.is_sentence_start = True
        self.event_scheduler = EventScheduler()
        self.event_scheduler.start()
        self.last_word_send_time = 0


    def _send_word(self, word, is_final):
        #logging.info(f'{self.turn_start_time.timestamp()} --- {word["start"]} --- {word["word"]}')
        word_output_time = self.turn_start_time.timestamp() + word["start"] + self.word_delay_secs
        if word_output_time < self.last_word_send_time:
            word_output_time = self.last_word_send_time + 0.1
        #logging.info(f"Difference beteen current time and word output time: {word_output_time - datetime.utcnow().timestamp()}" )
        self.event_scheduler.enter(word_output_time - datetime.utcnow().timestamp(), priority=1, action=self._send_word_impl, arguments=(word, self.num_sent_words, self.turn_start_time, is_final))        
        self.last_word_send_time = word_output_time
    
    def _send_word_impl(self, word, num_sent_words, turn_start_time, is_final):
        pass

    def partial_result(self, words):
        words = prettify(words, self.is_sentence_start)
        #print(words)
        
        if len(words) - self.word_delay > self.num_sent_words:
            for i in range(self.num_sent_words,  len(words) - self.word_delay):
                try:
                    self._send_word(words[i], False)
                except Exception:
                    logging.error("Couldn't send word to output", exc_info=True)
                self.num_sent_words += 1

    def final_result(self, words):
        words = prettify(words, self.is_sentence_start)
        
        for i in range(self.num_sent_words,  len(words)):
            try:
                self._send_word(words[i], i==len(words)-1)
            except Exception:
                logging.error("Couldn't send word to output", exc_info=True)
            self.num_sent_words += 1

        self.num_sent_words = 0
        if len(words) > 0 and words[-1]["word"][-1] in list("!?.,"):
            self.is_sentence_start = True
        else:
            self.is_sentence_start = False


    def new_turn(self):
        super().new_turn()
        try:
            self._send_word({"word" : "- ", "start": 0.0}, False)
        except Exception:
            logging.error("Couldn't send word to output", exc_info=True)
        self.is_sentence_start = True


class WordByWordPresenter(AbstractWordByWordPresenter):
    def __init__(self, output_file, word_delay_secs=3.0):
        super().__init__(word_delay_secs)        
        self.output_file = output_file
        

    def _send_word_impl(self, word, num_sent_words, turn_start_time, is_final):
        if num_sent_words > 0 and word["word"][0] not in list(",.!?"):
            print(" ", end="", file=self.output_file)
        print(word["word"], end="", file=self.output_file)
        if is_final:
            print("", file=self.output_file)
        self.output_file.flush()
    


class YoutubeLivePresenter(AbstractWordByWordPresenter):
    def __init__(self, captions_url):
        super().__init__()        
        self.captions_url = captions_url
        self.seq = 1
        self.current_words = []
        self.min_num_chars = 100
        self.current_word_timestamps = []
       

    def _do_send(self):
        if len(self.current_words) == 0:
            return
        logging.info("Sending captions to Youtube")
        server = ' region:reg1#cue1' 
        headers = {'content-type': 'text/plain'}
        #Formatting the time properly
    
        post = "\n".join([time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '\n ' + word  for word, time in zip(self.current_words, self.current_word_timestamps)])
        post = post + '\n'
        ingestion_url =  self.captions_url + "&lang=et-EE&seq=" + str(self.seq)
        resp = requests.post(url=ingestion_url, data=post.encode('utf-8'), headers=headers)
        logging.info(f"Sent body: {post}")
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
        self.seq += 1
        self.current_words = []
        self.current_word_timestamps = []

    def _send_word_impl(self, word, num_sent_words, turn_start_time, is_final):
        self.current_words.append(word["word"])        
        word_timestamp = turn_start_time + timedelta(seconds=word["start"])
        if len(self.current_word_timestamps) > 0 and self.current_word_timestamps[-1] > word_timestamp:
            word_timestamp = self.current_word_timestamps[-1] + timedelta(seconds=0.1)
        self.current_word_timestamps.append(word_timestamp)
        text = " ".join(self.current_words)
        if len(text) > self.min_num_chars or is_final:
            self._do_send()



class FabLiveWordByWordPresenter(AbstractWordByWordPresenter):
    def __init__(self, fab_speech_interface_url):
        super().__init__()        
        self.fab_speech_interface_url = fab_speech_interface_url
    
    def _send_word_impl(self, word, num_sent_words, turn_start_time, is_final):
        logging.info("Sending captions to FAB")
        text = word["word"]
        if num_sent_words > 0:
            text = " " + text
        resp = requests.get(url=self.fab_speech_interface_url, params={"text": text})
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
        
    


class FabBcastWordByWordPresenter(AbstractWordByWordPresenter):
    def __init__(self, fab_bcast_url):
        super().__init__()        
        self.fab_bcast_url = fab_bcast_url

    def _send_word_impl(self, word, num_sent_words, turn_start_time, is_final):
        logging.info("Sending captions to  FAB Subtitler BCAST")
        text = word["word"]
        if num_sent_words > 0:
            text = " " + text
        resp = requests.get(url=f"{self.fab_bcast_url}/send", params={"text": text})
        logging.info(f"Response status {resp.status_code} {resp.reason}: {resp.text}")
         


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

    def _send_word_impl(self, word, num_sent_words, turn_start_time, is_final):
        self.current_words.append(word)
        text = " ".join(self.current_words)
        if len(text) > self.min_num_chars or is_final:
            self._do_send(text)
            self.current_words = []
