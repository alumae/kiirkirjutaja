# About

Kiirkirjutaja is a realtime speech-to-text tool designed for real-time subtitling of TV broadcasts
and streaming media.

It's architecture is almost monolithic and therefore quite ugly, as the different components are hardwired to each other.

Some of the components are specific to Estonian, but it should be relatively easy to adapt this tool
to other languages.

It consists of the following components:

  * Speech activity detector (https://github.com/snakers4/silero-vad)
  * Online speaker change detector (https://github.com/alumae/online_speaker_change_detector)
  * Speech recognition: we use a forked version of Vosk API (https://github.com/alphacep/vosk-api), which is in turn based on Kaldi
  * Unknown word reconstuctor (words not in the speech recognition vocabulary are reconstructed using a phoneme-to-grapheme tool, which is based on FSTs and an n-gram model -- https://github.com/alumae/et-g2p-fst)
  * Compound word recognizer: for glueing together compound word tokens, using an n-gram model
  * Puncutator, LSTM-based (https://github.com/alumae/streaming-punctuator)
  * Words-to-numbers converter (FST-based, using Pynini)

## Using

Kiirkirjutaja has a lot of dependencies and therefore the recommended way to run it is though the Docker container. 
If you want to run it outside the container, please check the docker/Dockerfile file for how
install all the dependencies.

Running and using the Docker container is outlined below:

  - Start Docker container

    docker run --shm-size 2GB --name kiirkirjutaja --rm -d -t kiirkirjutaja

  - Decode a Vikerraadio real-time stream:

    docker exec -it kiirkirjutaja python main.py https://icecast.err.ee/vikerraadio.mp3

By default, Kiirkirjutaja writes recognized words to stdout, word by word. Note that there is a delay 
in recognition results, around 2-3 seconds, because ow two factors:

  - We use a speaker change detection model that needs a lookahead buffer of 1 second, which delays the recognition by 1 second;
  - We use various postprocessing steps (compound word reconstruction, punctuation, words to numbers) which change the decoded
  words, but the way how the changes are dependent on future words, therefore the already recognized words would change, 
  depending on the words in the close future (sorry about the bad explanation). Anyway, that's why Kiirkirjutaja outputs
  a word only after 3 more words have been recognized (unless it's a segment end, in which case we can output everything, since
  each segment will be post-processed in isolation).

You can also write the word-by-word output to a file (can be a named pipe, if you want to process the generated
subtitles using some external program):

    docker exec -it kiirkirjutaja python main.py --word-output-file out.txt https://icecast.err.ee/vikerraadio.mp3

  or pipe it to extrnal program that reads the word-by-word output from stdin:

    docker exec -it kiirkirjutaja python main.py --word-output-file >(some-external-program) https://icecast.err.ee/vikerraadio.mp3

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


### Generating captions for FAB Live

FAB Live is professional media subtitling software. 

In order to use Kiirkirjutaja with FAB Live, first go to "Options -> Special -> Speech interface" in FAB, and set "Send mode" to "Word by word".

Now set the "Mode" in FAB to "Speech" and start Kiirkirjutaja with the following options (change localhost to the machine where FAB is running,
and make sure the port is accessible ro the machine running Kiirkirjutaja):

    docker exec -it kiirkirjutaja python main.py --fab-speechinterface-url http://localhost:8001/speechinterface rtmp://your-source-video



 