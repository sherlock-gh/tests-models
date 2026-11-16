"""One long-prompt try of the gate (sherlock.sh): a prompt of about N tokens with a fact near its start, and the fact asked
for at its end. Passes when the reply holds the fact and the server counted at least 90% of N prompt
tokens (a server that cut the prompt, as Ollama does past its num_ctx, fails).
Usage: python3 ctx.py <model> <server url> <tokens>   Prints: pass|fail<TAB>prompt tokens<TAB>seconds<TAB>note"""
import json
import random
import sys
import time
import urllib.error
import urllib.request

MODEL, URL, N = sys.argv[1], sys.argv[2] + "/chat/completions", int(sys.argv[3])
FACT = "The storeroom code is 4817-WILLOW."
rnd = random.Random(N)
WORDS = ("cleaner client invoice schedule morning arrive depart minutes office kitchen window floor "
         "booking crew weekday rate cents total hours report garden hallway carpet ladder bucket").split()


def sentence():
    return " ".join(rnd.choice(WORDS) for _ in range(rnd.randint(8, 16))).capitalize() + "."


def ask(text, max_tokens, timeout):
    req = urllib.request.Request(URL, data=json.dumps({
        "model": MODEL, "messages": [{"role": "user", "content": text}], "max_tokens": max_tokens, "temperature": 0,
    }).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


t0 = time.time()
try:
    # This model's characters a token for this text, from a short sample, so the prompt is sized in its tokens
    sample = " ".join(sentence() for _ in range(300))
    cpt = len(sample) / ((ask(sample, 1, 300).get("usage") or {}).get("prompt_tokens") or len(sample) / 4)
    body, size = [], 0
    while size < N * cpt * 0.93:
        s = sentence(); body.append(s); size += len(s) + 1
    body.insert(len(body) // 50, FACT)
    prompt = ("Below is a long log. One line in it gives a storeroom code.\n\n" + " ".join(body) +
              "\n\nWhat is the storeroom code? Reply with the code only.")
    out = ask(prompt, 40, 3540)
except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
    print(f"fail\t\t{time.time() - t0:.0f}\tno reply: {str(e)[:150]}"); sys.exit(0)
reply = (out.get("choices") or [{}])[0].get("message", {}).get("content") or ""
pt = (out.get("usage") or {}).get("prompt_tokens") or 0
ok = "4817-WILLOW" in reply.upper() and pt >= 0.9 * N
print(f"{'pass' if ok else 'fail'}\t{pt}\t{time.time() - t0:.0f}\treply {reply.strip()[:60]!r}")
