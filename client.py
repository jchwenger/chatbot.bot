from base64 import b64encode
from gpt import Model
import socketio
import argparse
import random
import regex

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
    "--local",
    action="store_true",
    help="Run with local server, port 5000.",
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
print("run name:", args.run_name)
print("rank rank_threshold", args.rank_threshold)
print("-"*40)

length_desired = 250

replique_re = regex.compile("<\|s\|>\n(.*?)\n<\|e\|>\n", regex.DOTALL)
separators = "\n<|e|>\n<|s|>\n"
end = "\n<|e|>\n"
start = "<|s|>\n"

messages = []
prefix = ""

def generate(rank_threshold=25):

    global marker_re
    global pref_re
    global prefix
    global start

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

    l = le_model.gen(prefix=prefix, length=length_desired)[0]
    generated = l[end_pref:]

    print(l[:end_pref])
    print("-"*40)
    print("generated:")
    print(generated)
    print("-"*40)

    r = regex.search(replique_re, generated)

    if r:
        repl = r.group(1)
        char = repl[:repl.find("\n")]
        message = repl[repl.find("\n") + 1:]
        print(char)
        print(message)
        le_rank = le_model.get_rank(repl)[0]
        print("\trank of repl:", le_rank)
        if le_rank < rank_threshold:
            send_message({ "character": char, "message": message, "sender": "Monsieur Py"})
            prefix = f"{prefix}{start}{char}\n{message}"
        else:
            print("\tnot answering")
    else:
        print("\tnot answering")

@sio.event
def connect():
    print("\tconnection established")
    # sio.emit("new user", "le py server")

@sio.event
def disconnect():
    print("\tconnection lost")

@sio.on("received")
def on_chat_message(data):

    global prefix

    if data["character"]: print(data["character"])
    if data["message"]: print(data["message"])

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
    print("random has spoken:", rand)
    if rand > 0:
        # print("random has been bountiful, let's generate")
        generate(rank_threshold=args.rank_threshold)

def send_message(data):
    # print("-"*40)
    # print("sending message:")
    # print(data)
    # print("-"*40)
    sio.emit("chat message", data)

user_pass = b64encode(b"username:password").decode("ascii")
if args.local:
    url = "http://localhost:5000"
    print(f"connecting to: {url}")
    print("-"*40)
    sio.connect(url)
else:
    # url = "***HEROKU WEB ADDRESS***"
    # print(f"connecting to: {url}")
    # print("-"*40)
    # sio.connect(url)
    user_pass = b64encode(b"username:password").decode("ascii")
    sio.connect("https://spark.theatrophone.fr",  { "Authorization" : "Basic %s" % user_pass})
sio.wait()
