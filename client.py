from base64 import b64encode
from gpt import Model
import socketio
import argparse
import textwrap
import random
import regex
import time

parser = argparse.ArgumentParser(
    description="""
    """,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

parser.add_argument(
    "--model",
    type=str,
    default="117M",
    help="Model for forward model. Defaults to '117M'.",
)

parser.add_argument(
    "--run_name",
    type=str,
    default="run1",
    help="Run name for forward model. Defaults to 'run1'.",
)

parser.add_argument(
    "--server_name",
    type=str,
    default="Le Serveur",
    help="Server name used in message.",
)

parser.add_argument(
    "--temperature",
    type=float,
    default=0.9,
    help="Temperature when sampling.",
)

parser.add_argument(
    "--top_p",
    type=float,
    default=0.998,
    help="Nucleus sampling when sampling.",
)

parser.add_argument(
    "--network_print_speed",
    type=float,
    default=0.1,
    help="Length of pause for each step of interactive print loop, in ms.",
)

parser.add_argument(
    "--local",
    action="store_true",
    help="Run with local server, port 5100.",
)

parser.add_argument(
    "--heroku",
    action="store_true",
    help="Run with heroku. Default: https://spark.theatrophone.fr/.",
)

parser.add_argument(
    "--rank_threshold",
    type=int,
    default=25,
    help="Rank under which sentences are allowed to be sent. Defaults to 25.",
)

args = parser.parse_args()

sio = socketio.Client(logger=False, reconnection_delay_max=50)

le_model = Model(model_name=args.model, run_name=args.run_name)
print("-"*40)
print("(settings:)")
print()
for k, v in vars(args).items():
    print(f"- {k}: {v}")
print()

is_generating = False
length_desired = 250

replique_re = regex.compile("<\|s\|>\n(.*?)\n+<\|e\|>", regex.DOTALL)
separators = "\n<|e|>\n<|s|>\n"
end = "\n<|e|>\n"
start = "<|s|>\n"

resetting_session = False
messages = []
prefix = ""

def generate(rank_threshold=25):

    global is_generating
    global marker_re
    global pref_re
    global prefix
    global start

    is_generating = True

    if should_sess_be_reset(): return

    # print("-"*40)
    # print("prefix:")
    # print(prefix)
    # print("-"*40)

    prefix_enc = le_model.encode(prefix)
    max_len = 1024 - length_desired
    if len(prefix_enc) > max_len:
        prefix_enc = prefix_enc[-max_len:]
        prefix = le_model.decode(prefix_enc)

    # add end of answer, store length of prefix
    end_pref = len(prefix)

    l = le_model.gen(prefix=prefix,
                     temperature=args.temperature,
                     top_p=args.top_p,
                     length=length_desired)[0]
    l = regex.sub(r"<\|endoftext\|>", "", l) # no openai marker
    generated = l[end_pref:]

    print()
    print("\t\t\t" + "-"*40)
    print("\t\t\t(raw)")
    print()
    msg = "\n\t\t\t".join(textwrap.wrap(generated, width=40))
    print(f"\t\t\t{msg}")
    print()

    r = regex.search(replique_re, generated)

    if r:
        repl = r.group(1)
        if repl.find("\n") == -1:
            char = ""
            message = regex.sub("<\|[es]\|>", "", repl)
        else:
            char = regex.sub("<\|[es]\|>", "", repl[:repl.find("\n")])
            message = regex.sub("<\|[es]\|>", "", repl[repl.find("\n") + 1:])

        print("\t\t" + "-"*40)
        print("\t\t(generated)")
        print()
        rmsg = "\n\t\t".join(textwrap.wrap(repl, width=40))
        print(f"\t\t{rmsg}")
        print()

        print("\t" + "-"*40)
        print("\t(char)")
        print()
        print(f"\t{char}")
        print()
        msg = "\n\t".join(textwrap.wrap(message, width=40))
        print("\t(message)")
        print()
        print(f"\t{msg}")
        le_rank = le_model.get_rank(repl)[0]
        print(f"\t(rank: {le_rank})")
        print()

        if le_rank < rank_threshold:
            print("-"*40)
            print(char)
            msg = "\n".join(textwrap.wrap(message, width=40))
            print(msg)
            print()

            if args.network_print_speed > 0:
                for i in range(len(message) + 1):

                    if should_sess_be_reset(): return

                    # print({ "id": sio.sid, "character": char, "message": # message[:i], "user": args.server_name})
                    send_typing({ "id": sio.sid, "character": char, "message": message[:i], "user": args.server_name})
                    time.sleep(args.network_print_speed)

            if should_sess_be_reset(): return

            send_message({ "character": char, "message": message, "user": args.server_name})
            prefix = f"{prefix}{start}{char}\n{message}"
        else:
            print()
            print("\t(RANK INSUFFICIENT: NOT ANSWERING)")
            print()
    else:
        msg = "\n\t\t".join(textwrap.wrap(l, width=40))
        print("\t\t" + "-"*40)
        print("\t\t(generated:)")
        print("\t\t" + msg)
        print("\t\t(MARKERS NOT FOUND: NOT ANSWERING)")
        print()

    is_generating = False
    if should_sess_be_reset(): return

def should_sess_be_reset():
    global resetting_session
    global is_generating
    if resetting_session:
        print(f"generation interrupted")
        print()
        print("="*40)
        is_generating = False
        resetting_session = False
        return True

@sio.event
def connect():
    print("connection established")
    print("-"*40)
    print()
    sio.emit("new user", args.server_name)

@sio.event
def connect_error(e):
    print("The connection failed!")
    print(e)

@sio.event
def disconnect():
    print("connection lost")
    print("-"*40)

@sio.on("erase messages")
def reset_session():

    global resetting_session
    global messages
    global prefix

    print()
    print("="*40)
    print()
    print("resetting session")
    print()
    print("="*40)
    messages = []
    prefix = ""
    if is_generating:
        resetting_session = True
    else:
        print()
        print("="*40)

@sio.on("received")
def on_chat_message(data):

    global is_generating
    global prefix

    char = data["character"].replace("\n", "\t\n")
    msg = data["message"].replace("\n", "\t\n")

    print("\t" + "-"*40)
    print("\t(received)")
    print()
    if data["character"]: print(f"\t{char}")
    if data["message"]: print(f"\t{msg}")

    messages.append(data)
    character = data["character"]
    message = data["message"]
    if character:
        prefix = f"{prefix}{separators}{character}\n{message}{end}"
    else:
        prefix = f"{prefix}{separators}{message}{end}"
    # print("prefix now:")

    # print(prefix)
    # print("-"*40)

    rand = random.random()
    print("\t" + "-"*40)
    print(f"\trandom has spoken: {rand}")
    if not is_generating:
        if rand > 0:
            print("\t(random is bountiful, let's generate)")
            print()
            generate(rank_threshold=args.rank_threshold)
    else:
        print("\t(is generating, not answering...)")
        print()


def send_typing(data):
    sio.emit("typing", data)

def send_message(data):
    # print("-"*40)
    # print("sending message:")
    # print(data)
    # print("-"*40)
    sio.emit("chat message", data)

user_pass = b64encode(b"guest:vuVpm77e").decode("ascii")
if args.local:
    url = "http://localhost:5100"
    print("-"*40)
    print(f"connecting to: {url}")
    sio.connect(url)
else:
    if args.heroku:
        url = "https://shrouded-stream-73690.herokuapp.com/"
        print("-"*40)
        print(f"connecting to: {url}")
        sio.connect(url)
    else:
        user_pass = b64encode(b"guest:vuVpm77e").decode("ascii")
        url = "https://spark.theatrophone.fr"
        print("-"*40)
        print(f"connecting to: {url}")
        sio.connect(url,  { "Authorization" : "Basic %s" % user_pass})
sio.wait()
