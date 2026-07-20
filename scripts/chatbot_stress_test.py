"""Ad-hoc stress test for the chatbot — messy/unexpected user inputs via the real API.
Paces requests to respect the Gemini free-tier limit (5 req/min).
"""
import time
import json
import urllib.request

API = "http://localhost:8000/api/v1/chatbot/message"
GYM_ID = 3
PACE = 1  # billing enabled — no free-tier throttle


def send(session_id, message):
    body = json.dumps({"gym_id": GYM_ID, "session_id": session_id, "message": message}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data["data"]["reply"]


# Each scenario: (id, description, [messages])
SCENARIOS = [
    ("s-phone-plus91", "Name + phone with +91 and spaces in one msg",
     ["Hi I'm Arjun, my number is +91 98111 22333, what plans do you have?"]),
    ("s-only-name", "Gives only name first, phone later",
     ["I want to join. I'm Neha", "my number is 9877001122"]),
    ("s-only-phone", "Gives only phone, no name",
     ["9765004321"]),
    ("s-words-phone", "Phone spelled partly in words",
     ["I'm Sam, call me on nine eight seven six five four three two one zero"]),
    ("s-offtopic", "Off-topic question",
     ["what is the weather in Mumbai today?"]),
    ("s-hinglish", "Hinglish input",
     ["bhai membership ka price kya hai?", "naam Rohit, number 9812009911"]),
    ("s-decline", "User refuses to share number",
     ["what are your timings?", "I don't want to give my number"]),
    ("s-greeting", "Just a greeting",
     ["hello"]),
]


def main():
    results = []
    for sid, desc, msgs in SCENARIOS:
        turns = []
        for m in msgs:
            time.sleep(PACE)
            try:
                reply = send(sid, m)
            except Exception as e:
                reply = f"<ERROR: {e}>"
            turns.append((m, reply))
        results.append((sid, desc, turns))
        print(f"\n=== {sid} — {desc} ===")
        for m, reply in turns:
            print(f"  USER : {m}")
            print(f"  BOT  : {reply}")
    print("\n===== DONE =====")


if __name__ == "__main__":
    main()
