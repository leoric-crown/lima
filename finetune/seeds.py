"""Seed matrix for synthetic voice-memo generation.

Diversity is the mode-collapse guard: persona x topic x length x disfluency
x mood x setting, sampled without replacement on (persona, topic) so no
pairing repeats. A small garbled quota teaches the production fallback rule.
"""

PERSONAS = [
    "a startup founder running a six-person B2B SaaS company",
    "a freelance graphic designer juggling three client projects",
    "a high-school chemistry teacher",
    "a parent of two who does most of the household cooking",
    "an indie game developer six months from launch",
    "a nurse who works night shifts at a regional hospital",
    "a PhD student in marine biology writing their dissertation",
    "a real-estate agent in a mid-size city",
    "a hobbyist woodworker with a garage workshop",
    "an amateur runner training for their first marathon",
    "a coffee-shop owner in a small town",
    "an IT consultant who travels to client sites most weeks",
    "a community-theater director rehearsing a spring production",
    "a farmer managing a small organic vegetable operation",
]

TOPICS = [
    "recap of a meeting that just ended",
    "brainstorm of ideas for a new project",
    "todo list for the next few days",
    "troubleshooting notes on a problem they just ran into",
    "reflections after a difficult conversation",
    "planning an upcoming trip",
    "notes on an article they just read or a video they just watched",
    "recap of a call with a customer or client",
    "money and budget planning",
    "planning a home repair or improvement",
    "preparing for an upcoming interview or presentation",
    "a health, diet, or training plan",
    "planning an event (a party, a wedding, a team offsite)",
    "capturing a product or business idea before it slips away",
    "post-mortem of a mistake or incident and what to change",
    "notes from a course, workshop, or tutorial they are taking",
    "errands and shopping they need to get done",
    "coordinating schedules with other people",
    "a note to their future self about a decision they just made and why",
    "recap of an appointment they just left (doctor, mechanic, bank, vet)",
]

# (name, min_words, max_words, sampling weight)
LENGTHS = [
    ("short", 60, 150, 0.25),
    ("medium", 150, 350, 0.50),
    ("long", 350, 700, 0.25),
]

# (name, sampling weight, instruction for the injection pass)
DISFLUENCY_LEVELS = [
    (
        "light",
        0.30,
        "a light touch: an occasional 'um' or 'you know', one or two minor self-corrections",
    ),
    (
        "medium",
        0.45,
        "a moderate amount: regular fillers (um, uh, like, you know), several false starts and "
        "self-corrections, occasional repeated words",
    ),
    (
        "heavy",
        0.25,
        "a heavy amount: frequent fillers, false starts mid-sentence, backtracking and rephrasing, "
        "repeated words, trailing off and picking the thread back up",
    ),
]

MOODS = ["rushed", "tired", "energized", "mildly annoyed", "calm and methodical", "distracted"]

SETTINGS = [
    "while walking somewhere",
    "sitting in a parked car",
    "in the kitchen while doing something else",
    "right after the event they are talking about",
    "late at night before bed",
    "during a short work break",
]

# memos that should trigger the production fallback ("Unclear memo").
#
# Shaped after what faster-whisper ACTUALLY emits on garbled/noisy audio —
# not the human-transcription [inaudible] convention, which Whisper never
# produces. Documented failure modes: verbatim phrase loops, polite-phrase
# hallucinations ("Thanks for watching!"), confident contentless prose,
# fragments that trail off. Two bracket-tag cells are kept only because the
# production system prompt names that shape as a fallback trigger.
#
# modes: loop (LLM seed sentence, repeated in code) | polite (composed in
# code from known Whisper hallucination strings) | llm (prompted)
GARBLED_CELLS = [
    {"mode": "loop", "repeats": 7},
    {"mode": "loop", "repeats": 5},
    {"mode": "polite"},
    {"mode": "polite"},
    # boundary=True: these two tend to come out borderline-extractable rather
    # than pure garbage. Training them with hard fallback labels would teach
    # over-fallback (Codex review 2026-07-04), so the split step routes
    # boundary cells to eval, never train.
    {
        "mode": "llm",
        "boundary": True,
        "prompt": (
            "Write a short (30-70 word) voice memo transcript that sounds fluent and "
            "confidently phrased but has no recoverable subject or point — vague references "
            "only ('the thing with the, you know, the other one'), no names, no actionable "
            "content, normal punctuation. Output ONLY the transcript."
        ),
    },
    {
        "mode": "llm",
        "boundary": True,
        "prompt": (
            "Write a short (25-60 word) voice memo transcript made of half-started thoughts "
            "that trail off, like: 'So the... and then if we... yeah. Maybe the other, um.' "
            "No clear subject anywhere. Output ONLY the transcript."
        ),
    },
    {
        "mode": "llm",
        "prompt": (
            "Write a short (30-80 word) voice memo transcript that is mostly noise markers "
            "like [inaudible], [music], [crosstalk] with a few scattered real words between "
            "them. Vary the markers; do not alternate word-marker-word mechanically. No "
            "recoverable subject. Output ONLY the transcript."
        ),
    },
    {
        "mode": "llm",
        "prompt": (
            "Write a short (30-80 word) voice memo transcript of overlapping conversation "
            "captured by accident: interleaved half-sentences from two distant voices plus "
            "[crosstalk] and [inaudible] markers, no recoverable subject. Output ONLY the "
            "transcript."
        ),
    },
]

GARBLED_COUNT = len(GARBLED_CELLS)

# verbatim strings faster-whisper is known to hallucinate on noise/silence
POLITE_HALLUCINATIONS = [
    "Thanks for watching!",
    "Thank you.",
    "Subtitles by the Amara.org community",
    "Please subscribe to my channel.",
    "Thank you for watching. See you in the next video.",
    "Bye.",
]
