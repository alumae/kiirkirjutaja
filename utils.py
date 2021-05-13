import difflib
import logging
import sys

def reconstruct_full_result(result, processed_text):
    words_full_postprocessed = []
    words_full = result["result"]
    words = [wi["word"] for wi in words_full]

    words_postprocessed = processed_text.split()
    #print(f"seq matching: {words} --- {words_postprocessed}")

    s = difflib.SequenceMatcher(None, words, words_postprocessed)
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag in ["delete"]:
            print("Warning: postprocessor should only replace or insert words (or word blocks), but [%s] detected" % tag, file=sys.stderr)
            words_full_postprocessed = words_full
            break
        else:
            if tag == "equal":
                words_full_postprocessed.extend(words_full[i1:i2])
            elif tag == "insert":
                if len(words_full_postprocessed) > 0:
                    words_full_postprocessed[-1]["word"] += " " + " ".join(words_postprocessed[j1:j2])
            elif tag == "replace":
                new_word = {"word" : " ".join(words_postprocessed[j1:j2])}
                new_word["start"] = words_full[i1]["start"]
                for key in words_full[i2-1].keys():
                    if key not in ["word", "start", "phones"]:
                        new_word[key] = words_full[i2-1][key]
                if "word_with_punctuation" in new_word:
                    new_word["word_with_punctuation"] = new_word["word"] + new_word["punctuation"]
                new_word["unnormalized_words"] = words_full[i1:i2]
                if "confidence" in new_word:
                    new_word["confidence"] = min([w["confidence"] for w in words_full[i1:i2]])
                    
                words_full_postprocessed.append(new_word)
    result["result"] = words_full_postprocessed
    result["text"] = " ".join(wi["word"] for wi in result["result"])
    return result

def test_reconstruct():

    result = {
        "final" : False,
        "result" : [{
            "conf" : 0.998515,
            "end" : 0.750000,
            "phones" : "l_B uu_I l_I e_E",
            "start" : 0.270000,
            "word" : "luule"
            }, {
            "conf" : 0.995148,
            "end" : 1.379826,
            "phones" : "k_B o_I k_I u_E",
            "start" : 0.750000,
            "word" : "__kogu"
            }, {
            "conf" : 1.000000,
            "end" : 2.100000,
            "phones" : "t_B o_I l_I m_I u_I s_I t_E",
            "start" : 1.560000,
            "word" : "tolmust"
            }, {
            "conf" : 1.000000,
            "end" : 2.220000,
            "phones" : "j_B a_E",
            "start" : 2.100000,
            "word" : "ja"
            }, {
            "conf" : 1.000000,
            "end" : 3.000000,
            "phones" : "v_B ae_I r_I v_I i_I t_I e_I s_I t_E",
            "start" : 2.220000,
            "word" : "värvidest"
            }],
        "text" : "luule __kogu tolmust ja värvidest"
        }

    post_processed = "luulekogu tolmust ja värvidest ."

    result2 = reconstruct_full_result(result, post_processed)
    assert result2["text"] == "luulekogu tolmust ja värvidest ."
    assert result2["result"][0]["word"] == "luulekogu"
    assert result2["result"][0]["start"] == 0.27
    assert result2["result"][0]["end"] == 1.379826
    #breakpoint()