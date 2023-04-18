# About

Kiirkirjutaja is a realtime speech-to-text tool designed for real-time subtitling of TV broadcasts
and streaming media.

It's architecture is almost monolithic and therefore quite ugly, as the different components are hardwired to each other.

Some of the components are specific to Estonian, but it should be relatively easy to adapt this tool
to other languages.

It consists of the following components:

  * Speech activity detector (https://github.com/snakers4/silero-vad)
  * Online speaker change detector (https://github.com/alumae/online_speaker_change_detector)
  * Speech recognition: we use streaming transducer models trained using [Icefall](https://github.com/k2-fsa/icefall). Speech recognition model
  includes punctuation insertion. [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx) is used for decoding.
  

## News
  * 2023-04-18: fixed an issue which caused words at sentence ends not to be recognizer correctly in some cases.

  * 2023-03-30: *Major rewrite*: Now uses end-to-end streaming transducer models trained using [Icefall](https://github.com/k2-fsa/icefall).
  The model includes punctuation restoration. Should provide 30% less ASR errors and much improved punctuation accuracy.
  Also, the Docker image size reduced to from ~14 GB to 3.2 GB, as we don't need Kaldi any more.
  * 2023-01-01: Fixed a bug in Youtube presenter that caused timings to be sometimes messed up. Also introduced
  a new command line argument `--word-output-delay <seconds>' that can be used to set a minimum time between a word
  occurring in speech and word appearing in subtitles. Recommended value is smth like 5. This makes word-by-word output
  timing more consistent and makes reading more comfortable. 
  Otherwise, words in utterance ends can be displayed all very 'abruptly'.

  * 2021-11-16: fixed a memory leak, increased robustness against cases when the network API endpoint that receives
  subtitles is down

  * 2021-12-08: implemented presenter for FAB Subtitler BCAST 

  * 2021-12-06: language ID check is done after 3 seconds of speech; if a non-target language is detected,
  another check is done after 5 seconds (new). This is to filter out false negatives when an utterance starts with 
  some hesitation sounds or otherwise non-standard words that sometimes confuse the language ID module.

  * 2021-10-08: integrated language identification module that filters out speech that is not in the target language.
  The filtering works so: each new turn is buffered until 3 seconds of audio is received, at which point language ID
  is performed. If the language is the target language, the buffer is forwarded to the ASR module and all the rest of the chunks
  are sent to the ASR as usual. The prior probability of the target language can be tuned (usually we expect most of 
  the data to be in the target language).

## Demo

Government press conference with live subtitles, generated using the YouTube presenter (see below):
https://www.youtube.com/watch?v=ZN03kzEo-V8

## Hardware requirements

  - Around 16 GB memory should be enough (probably you can do with less)
  - Fairly modern fast CPU (development machine has Intel(R) Xeon(R) CPU E5-2699 v4 @ 2.20GHz)
  - 4 free CPU cores


## Using

Kiirkirjutaja has a lot of dependencies and therefore the recommended way to run it is though the Docker container. 
If you want to run it outside the container, please check the docker/Dockerfile file for how to
install all the dependencies.

Running and using the Docker container (with generic Estonian models) is outlined below:

Pull the Docker image:

    docker pull alumae/kiirkirjutaja:latest

Start Docker container (use the `--shm-size 2GB` argument because the program uses shared memory between for IPC):

    docker run --shm-size 2GB --name kiirkirjutaja --rm -d -t alumae/kiirkirjutaja:latest

Decode a Vikerraadio real-time stream (it takes 10-20 seconds to load the models, and you'll get some warnings that can be usually ignored):

    docker exec -it kiirkirjutaja python main.py https://icecast.err.ee/vikerraadio.mp3

By default, Kiirkirjutaja writes recognized words to stdout, word by word. Note that there is a delay 
in recognition results, around 2-3 seconds, because of two factors:

  - We use a speaker change detection model that needs a lookahead buffer of 1 second, which delays the recognition by 1 second;
  - We use various postprocessing steps (compound word reconstruction, punctuation, words to numbers) which change the decoded
  words, but the changes are dependent on future words, therefore the already recognized words could change, 
  depending on the words in the close future (sorry about the bad explanation). Anyway, that's why Kiirkirjutaja outputs
  a word only after 3 more words have been recognized, because only then it's relativey sure that it won't change
  (unless it's a segment end, in which case we can output everything, since
  each segment will be post-processed independently).

You can also write the word-by-word output to a file (can be a named pipe, if you want to process the generated
subtitles using some external program). E.g.:

    docker exec -it kiirkirjutaja python main.py --word-output-file out.txt https://icecast.err.ee/vikerraadio.mp3

But of course this file will be on the Docker container filesystem.

If you want to pipe the word-by-word output to another program, you can just capture the stdout from the decoding process,
as all the warning and informatuon messages are written to stderr. For example:

      docker exec -it kiirkirjutaja python main.py https://icecast.err.ee/vikerraadio.mp3 | some_external_program

Kiirkirjutaja uses `ffmpeg` to decode the given file/stream and convert it to mono, 16-bit, 16 kHz audio stream. 

If the input stream
is called "-", it is assumed to be an already decoded mono/16-bit/16kHz raw audio stream. This way you can stream raw audio to it. For example, to stream
audio directly from the microphone, use something like this:

    rec -t raw -r 16k -e signed -b 16 -c 1 - | docker exec -i kiirkirjutaja python main.py -

If the server with Kiirkirjutaja resides on a remote machine, you can stream audio via network using `netcat`. On server:

    nc -l 8022 | docker exec -i kiirkirjutaja python main.py -

On desktop:

    rec -t raw -r 16k -e signed -b 16 -c 1 - | nc server_name 8022

If the server port (8022) is behind a firewall, it has to done via an SSH tunnel, but this left as an exercise to the reader :)

There are a few other output mechanisms (or 'presenters', as we call them) implemented:

  - YouTube Live captions
  - FAB Live speech interface


### Generating captions for YouTube Live

In order to generate captions to a YouTube Live stream, "Go Live" on YouTube, select "Streaming Software" (i.e., not "Webcam"), turn on "Closed captions",
select the "POST captions to URL" and copy/paste the "Captions ingestion URL".

Now, start streaming video to the YouTube input streaming URL (e.g., from some external RTMP source), using a script that does something like this:

    VBR="2500k"
    FPS="30"   
    QUAL="medium"
    YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2"

    SOURCE=rtmp://your-source-video
    KEY=<YOUR-YOUTUBE-LIVE-ID>

    ffmpeg \
        -i $SOURCE -deinterlace \
        -vcodec libx264 -pix_fmt yuv420p -preset $QUAL -r $FPS -g $(($FPS * 2)) -b:v $VBR \
        -acodec libmp3lame -ar 44100 -threads 6 -qscale 3 -b:a 712000 -bufsize 512k \
        -f flv "$YOUTUBE_URL/$KEY"


At the same time, start Kiirkirjutaja, using the following arguments (i.e., it should get the same external video stream as input):

    docker exec -it kiirkirjutaja python main.py --youtube-caption-url <YOUR-CAPTIONS-INGESTION-URL> rtmp://your-source-video

It is recommended to use a 30 second delay setting for YouTube live streams, otherwise the subtitles display somewhat
sporadically.

### Generating captions for FAB Live

FAB Live is professional media subtitling software. 

In order to use Kiirkirjutaja with FAB Live, first go to "Options -> Special -> Speech interface" in FAB, and set "Send mode" to "Word by word".

Now set the "Mode" in FAB to "Speech" and start Kiirkirjutaja with the following options (change localhost to the machine where FAB is running,
and make sure the port is accessible to the machine running Kiirkirjutaja):

    docker exec -it kiirkirjutaja python main.py --fab-speechinterface-url http://localhost:8001/speechinterface rtmp://your-source-video



 