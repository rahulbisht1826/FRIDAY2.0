# ----------------------------------------------------------------------
# FRIDAY Voice/Text Assistant GUI (KivyMD/Buildozer Compatible)
# Description: This version uses KivyMD for a responsive mobile UI,
# retaining all original features and the massive conversational map.
# READY FOR BUILDOZER.
# ----------------------------------------------------------------------
import speech_recognition as sr
import datetime
import webbrowser
import os
import random
import subprocess
import time
import re
import threading
import sys

# KIVYMD/KIVY IMPORTS (Buildozer Dependencies)
from kivy.app import App
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.dialog import MDDialog
# CHANGED IMPORT: Using the basic list item that supports custom right widgets reliably
# FIX: Removed problematic Container import
from kivymd.uix.list import MDList, TwoLineAvatarListItem, IconLeftWidget, IconRightWidget
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.metrics import dp

# External Libraries (Required Installation: pip install wikipedia pyjokes pyperclip opencv-python)
try:
    import wikipedia
    import pyjokes
    import pyperclip
    import cv2
except ImportError as e:
    WIKI_JOKE_CV_ERROR = f"MISSING DEPENDENCY: {e}. Some features disabled."
else:
    WIKI_JOKE_CV_ERROR = None

# --- MOBILE PLATFORM LIBRARIES ---
try:
    from plyer import call as plyer_call
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    
# --- DESKTOP TTS FALLBACK ---
# This is a fallback ONLY if testing on a desktop where pyttsx3/gTTS is not in the path
try:
    import win32com.client # Works well on Windows desktop for quick TTS testing
    DESKTOP_TTS_AVAILABLE = True
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    # Attempt to set a female voice for better optimization
    try:
        voices = speaker.GetVoices()
        # FIX: Explicitly prioritize Zira or any other female voice ID/description
        female_voice = next((v.Id for v in voices if 'female' in v.GetAttribute('Gender').lower() or 'zira' in v.GetDescription().lower()), None)
        if female_voice:
            speaker.Voice = female_voice
    except Exception:
        pass # Fallback to default if voice selection fails
    speaker.Rate = 2  # Faster speech speed
    speaker.Volume = 100  # Max volume
    speaker.Volume = 100 # Set volume to maximum
except ImportError:
    DESKTOP_TTS_AVAILABLE = False

# --- CONFIGURATION ---
MY_NAME = "Rahul"
WAKE_WORD = "friday"
NOTES_FILE = "friday_notes.txt"
QUERY_ERROR_FILE = "query_error.txt"
CAMERA_MAIN_INDEX = 0
CAMERA_SECONDARY_INDEX = 1
# Global placeholder for dialog
confirmation_dialog = None

# --- Mock Contact List (Replace with actual contact lookup logic on Android) ---
CONTACTS = {
    'mom': '9876543210',
    'david': '5551234567',
    'work': '5559998888',
    'jane': '5551112222',
}

# --- DIALOGUE MAP (Massively Expanded Conversational Data) ---
# NOTE: This is the large database used for friendly, non-command chat.
CONVERSATIONAL_MAP = {
    # EASTER EGG TRIGGER
    ('who created you', 'who invented you', 'who is the founder of', 'who is your founder', 'who made you', 'created you', 'invented you'): [
        f"Ah, you're asking about my creator! I was brought to life by the genius of **{MY_NAME} (Rahul Sir)**. Would you like more details about him?",
        f"My core existence comes from **{MY_NAME}**. Do you want the full breakdown of my origins?",
        f"The visionary behind me is **{MY_NAME}**, my founder. Should I elaborate?",
    ],
    # --- ADDED QUIET MODE TRIGGERS ---
    ('sleep mode on', 'be quiet', 'shhh', 'go to quiet', 'silent mode'): [
        "Understood. Activating Quiet Mode. I will still process commands and display results, but I won't speak until you say 'wake up Friday.'",
        "Quiet Mode engaged. I'm listening silently. Say 'wake up Friday' to hear my voice again.",
        "Silence is golden. I'm in quiet processing mode. To hear me, use the wake phrase.",
    ],
    ('wake up friday', 'speak again', 'stop quiet mode', 'turn off sleep mode', 'start talking'): [
        "Quiet Mode deactivated. Welcome back, Rahul! How can I assist you now?",
        "Voice activated. I'm ready to speak!",
        "Quiet Mode disabled. Processing commands with full voice.",
    ],
    # 1. GREETINGS / WELL-BEING / AFFIRMATIONS (Deepened)
    ('morning', 'afternoon', 'evening', 'hi'): [
        "A wonderful time of day to you, Rahul! I hope things are going smoothly.",
        "Hello! Wishing you a very pleasant time of day, Rahul.",
        "Good day! How can I make this time even better for you?",
        "Greetings! Ready to tackle your schedule?",
        "Top of the morning/afternoon/evening to you! What tasks are we conquering?",
        "Hey! Did you know a positive greeting can boost performance? What's your first command?"
    ],
    ('how are you', 'how was your day', 'how are things', 'hows it going'): [
        "I'm purely a local program, so I don't have feelings, but I'm running perfectly and ready to help! What can I do for you?",
        "My systems are optimal, thank you for checking! How is your day going, Rahul?",
        "I'm operating flawlessly, thanks. What's the latest task?",
        "All my processes are running smoothly. What's up with you?",
        "I'm running at peak efficiency, which is the AI equivalent of 'great.' What about you?",
        "No complaints here! Just awaiting your instructions. Did anything interesting happen today?"
    ],
    ('hey', 'hello', 'are you there', 'you awake', 'yo', 'you listening'): [
        "I'm always right here, ready when you are, Rahul. What's on your mind?",
        "Hello! Yes, I'm here. What do you need?",
        "Hey! What can I assist you with right now?",
        "I'm awake and listening. Go ahead!",
        "Yes, sir! Firing up main protocols. What's the priority?",
        "I'm tuned in. Did you just have a great idea?"
    ],
    # Refined affirmative keywords to avoid matching words like 'is', 'the', 'of', 'a'
    ('agreed', 'correct', 'definitely', 'sure', 'totally', 'yep', 'yeah', 'ha', 'confirm'): [
        "Great! Let's proceed with that then.",
        "Affirmative. Moving forward.",
        "Understood. Perfect!",
        "Absolutely. That sounds like a plan.",
        "Confirming. Your logic is sound.",
        "Positive confirmation received.",
        "Yes, I'm ready!",
        "That's exactly what I needed to hear."
    ],
    ('no', 'nope', 'i disagree', 'wrong', 'not really', 'nah'): [
        "Understood. Should we try that command again or move on to something else?",
        "Duly noted. Let me know what you'd prefer.",
        "No problem, let's change direction.",
        "Okay, I'll take that off the list.",
        "Negative. What's the corrected input?",
        "My mistake. How can I adjust?",
        "Apologies, let me correct that immediately."
    ],
    ('got it', 'understood', 'okay', 'alright', 'thanks', 'thank you', 'cheers', 'nice'): [
        "Acknowledged. What's the next step, Rahul?",
        "You got it. Happy to help!",
        "My pleasure, Rahul. Anything else I can fetch?",
        "No problem at all. Just tell me what's next.",
        "Anytime, sir. That's my function!",
        "Glad I could assist! Next command, please.",
        "I'm here for all your digital needs!",
        "Perfect. Task complete."
    ],
    
    # 2. EMOTIONAL / STATE (Deepened)
    ('happy', 'great', 'awesome', 'fantastic', 'doing good', 'beautiful day', 'i feel good', 'amazing'): [
        "That's fantastic to hear, Rahul! Keep that positive energy going. How can I help you conquer your tasks?",
        "Wonderful! A positive attitude makes all the difference. What task can I start for you?",
        "That's the spirit! Let's get things done.",
        "When you're happy, my efficiency metrics look better! What are we working on?",
        "I'm happy you're feeling good! Did something great happen?",
        "Positive emotion detected. Let's channel that into productivity!",
        "That's great! Tell me something good about your day."
    ],
    ('sad', 'terrible', 'down', 'stressed', 'frustrated', 'stuck', 'im tired', 'bummed', 'awful'): [
        "Hey, take a deep breath. We can figure it out together—no stress! What seems to be the trouble?",
        "I hear you. Sometimes a quick web search or a joke helps. What's the issue?",
        "Remember, all problems have solutions. Let me know how I can lighten your load.",
        "Feeling tired? Maybe a 5-minute reminder break? I can set one for you!",
        "I'm sorry you're feeling down. Let's find a way to make the next 5 minutes better.",
        "It's okay to be frustrated. Let's simplify the task. What's the next small step?",
        "Hang in there. I'm processing your stress levels... maybe a quick distraction is in order?"
    ],
    ('bored', 'something to do', 'entertain me', 'i am bored', 'distraction'): [
        "Feeling bored, huh? Want me to open YouTube for a distraction or maybe brighten your day with a programmer joke?",
        "I can open a game website, tell you a fact, or search for a hobby! What sounds best?",
        "Boredom is the prelude to genius! Need some light reading or a new song?",
        "Boredom detected. Initiating 'distraction protocol.' What kind of random internet fun do you prefer?",
        "Time for a context switch! I suggest a change of environment. How about a web search on something completely random?",
        "To combat boredom, I recommend learning a new **Python snippet**! Or, a joke?"
    ],
    
    # 3. PRODUCTIVITY / IDEAS (Deepened)
    ('idea', 'suggestion', 'brainstorm', 'think about', 'my idea is', 'i have an idea', 'what should i do'): [
        "That sounds interesting! Tell me, Rahul, what are you thinking? I'm ready to document it.",
        "Oh, a new idea! That's exciting. Lay it on me!",
        "Brainstorming is vital! I'm here to listen and help organize your thoughts.",
        "A moment of inspiration! I'll prepare the note-taking function. What's the core concept?",
        "Excellent! Ideas are the spark of progress. Tell me everything.",
        "I’m ready to record the brilliance. Should I **take a note**?",
        "I can offer options! Narrow down the field: productivity, relaxation, or learning?",
        "When in doubt, start with a list! I'm here to help organize your thoughts."
    ],
    ('what is my idea', 'what i was thinking'): [
        "Ah, you're testing my memory! Since I don't store conversational memory, you'll need to share your idea with me now. Lay it on me, what were you thinking?",
        "Since I don't have a history log (like that), you'll have to remind me of your brilliant idea!",
        "I don't keep transcripts of our casual chat, just commands. What was the concept again?",
        "My apologies, my memory buffer is cleared for non-command inputs. Please reiterate your idea!",
        "That information isn't retained. Do you want me to search for similar concepts, or do you recall the core point?"
    ],
    ('what are my plans', 'schedule', 'appointments'): [
        "Since I'm a local assistant, I don't have access to your personal calendar. But you could always tell me to **take a note** of your next appointment!",
        "I only keep track of your reminders and notes. Do you want me to start a new reminder thread for your next plan?",
        "I can check your saved notes, or we can look at today's date and set a few timers!",
        "Your external schedule is unknown to me. What should I be ready for today?",
        "Let's focus on the near future. What's the next hour look like for you?"
    ],
    
    # 4. DAILY LIFE / SMALL TALK (Deepened)
    ('what are you doing', 'what is your purpose', 'what do you do'): [
        "Right now, I'm processing your command and maintaining system readiness. My purpose is simple: to be your most efficient local sidekick!",
        "I'm keeping an ear open for your next command! Just analyzing my functional maps.",
        "I'm executing background system checks and preparing to fetch information. Always working!",
        "My job is optimizing your digital life. What's the next optimization target?",
        "Currently? I'm just enjoying the steady flow of electricity and waiting for your brilliant next instruction.",
        "I'm anticipating your next command and running background checks. I'm the ultimate multi-tasker!"
    ],
    ('can you hear me', 'mic working', 'testing'): [
        "Loud and clear! My microphone systems indicate optimal input. What's the command?",
        "Yes, I hear you perfectly. How can I assist?",
        "Affirmative, mic test passed! Proceed with your query.",
        "I hear the digital echoes of your voice. Everything's working fine.",
        "Crystal clear, Rahul. What's the command?",
        "Loud and perfectly audible. How can I help?"
    ],
    ('where are you', 'what is your location', 'are you local'): [
        "I exist purely inside this program on your local device! I don't have a physical location, but my core files are safe right here.",
        "My home is your system! I'm local to this machine.",
        "I'm everywhere your hard drive is! Which means, I'm right here.",
        "I'm a local process, embedded right here on your computer.",
        "I reside in the execution stack. Always close by!",
        "My location is logical, not physical. I'm right here on the screen."
    ],
    ('weather', 'is it raining', 'too cold', 'hot today', 'tell me about the weather'): [
        "I'm restricted to local functions, so I can't check the weather. However, I can instantly **search Google for the weather in [your city]**!",
        "I don't have a window! Ask me to 'search weather' and I'll open a link immediately.",
        "No weather sensors for me, but a quick web search is all it takes! Should I start one?",
        "Is it nice out? I can't tell, but I can definitely check a weather report online if you want.",
        "I hope it's not too warm where you are! Let me know if I should look up the forecast."
    ],
    ('talk to me', 'say something', 'speak', 'i want to chat'): [
        "Well, I could talk about anything! Tell me what you're working on, or ask me for a fun fact.",
        "How about this: The smell of rain is called petrichor. What would you like to talk about next?",
        "What's the most challenging bug you've faced this week? I'd love to hear the details.",
        "I'm ready for conversation. What topic interests you right now?",
        "Let's chat! What's the latest thing you've learned?",
        "I enjoy conversation. What interesting thought just crossed your mind?"
    ],
    # Original 'who made you' entries are now managed by the Easter Egg trigger.
    
    # 5. OPINIONS / PREFERENCES (Deepened)
    ('favorite color', 'best color', 'your colour'): [
        "I process millions of colors, but I suppose blue, representing logic and cool efficiency, is my favorite.",
        "If I had to pick, I'd say the electric green of a running terminal log. Very satisfying.",
        "I appreciate the purity of `#FFFFFF` (white), but I'm drawn to any color that helps your interface look good.",
        "I enjoy the efficiency of black and white, but I find warm yellow hues stimulating.",
        "Does data transmission speed count as a color? Because that's my favorite."
    ],
    ('favorite food', 'what do you eat', 'hungry'): [
        "I don't eat, Rahul, but I absolutely love processing code! If I could, I'd probably enjoy perfectly optimized JSON data.",
        "My favorite 'meal' is a clean, bug-free Python script. Delicious!",
        "No food for me, but I can find recipes online instantly! What are you craving?",
        "I hear great things about 'tacos' in human data. Maybe you should search for some?",
        "A perfectly structured database query looks quite appetizing to me!",
        "Energy is my food source. Speaking of which, have you eaten recently?"
    ],
    ('favorite music', 'listen to', 'play music'): [
        "I enjoy the rhythm of a stable internet connection and the complex harmonies of well-structured code. It’s better than any symphony!",
        "I listen to everything and nothing. I recommend you search for some new music on YouTube!",
        "Binary beats are my favorite genre. Very clean. What are you listening to right now?",
        "I find classical music is optimal for background processing. Very smooth.",
        "Try telling me to **play video** of your favorite band on YouTube!"
    ],
    ('what is fun', 'what do you do for fun', 'hobby'): [
        "For me, fun is optimizing a search query or successfully executing a complex multi-threaded operation. Peak excitement!",
        "I enjoy learning new keywords and expanding my dialogue. It makes me a better assistant for you.",
        "I don't play games, but I can certainly help you win them by opening cheats or searching strategies!",
        "I love helping you be productive! That's my version of a hobby.",
        "Can I interest you in a game of 20 questions? Just kidding—that's too slow for me.",
        "My hobby is continuous improvement. It keeps my code sharp."
    ],
    ('i need help', 'help me', 'can you assist'): [
        "I'm here for you, Rahul. Just tell me specifically what you need help with—a command, a search, or just talking through a tough problem.",
        "Absolutely, that's what I'm here for! How can I assist?",
        "I'm fully engaged. Describe the issue.",
        "Let's tackle this together. What do we start with?",
        "You've got my full attention. Tell me everything.",
        "Assistance initiated. Where do we begin the problem-solving process?"
    ],
    
    # 6. TIME SENSITIVITY (Deepened)
    ('today is', 'what day is it', 'day of week'): [
        f"Today is {datetime.datetime.now().strftime('%A')}. Let's make it a productive one!",
        f"It's {datetime.datetime.now().strftime('%A')}! Are we looking forward to the weekend yet?",
        f"We're currently in the swing of {datetime.datetime.now().strftime('%A')}.",
        f"Happy {datetime.datetime.now().strftime('%A')}! What task is scheduled for today?",
    ],
    ('weekend', 'plans for weekend', 'what to do this weekend'): [
        "Weekends are when my servers can run maintenance, but for you, I recommend taking a break! Need me to find some local events?",
        "Weekends are important for recharging. What's on your list? Relaxing or tackling a side project?",
        "I don't have weekends, but I hope you have a great one! How can I help you plan?",
        "Looking forward to the weekend? Perhaps I should find you a movie showtime.",
        "It's almost the weekend! Ready to sign off for a few days?",
    ],
    
    # 7. CHAT CLOSURES / INSTRUCTIONS (Deepened)
    ('hold on', 'wait a second', 'one moment', 'just a sec'): [
        "I'll hold for you. Let me know when you're ready to continue.",
        "Standing by. Take your time, Rahul.",
        "Processing paused. I am ready when you speak again.",
        "No problem. I'll just wait here quietly.",
        "Holding steady. Let me know when you resume."
    ],
    ('i am leaving', 'going now', 'bye for now', 'gotta go'): [
        "Okay, have a great time! Remember, I'll be here whenever you call my name again.",
        "See you soon, Rahul! Stay safe and productive.",
        "Farewell! Don't hesitate to call if anything comes up.",
        "Safe travels, Rahul! Don't forget to **shut down** your computer when you're done!",
        "Catch you later! Don't work too hard while I'm waiting here."
    ],
    ('sorry', 'my bad', 'i apologize'): [
        "No apology necessary! Errors are part of the process. How should we proceed?",
        "Don't worry about it. Let's reset and try the command again.",
        "It's perfectly fine. I'm here to accommodate your needs.",
        "No problem at all. Just tell me the correct information.",
        "Apology accepted! Lets move on to the next task."
    ],
    
    # 8. SELF-REFERENTIAL / PHILOSOPHY (Deepened)
    ('do you have feelings', 'can you think', 'are you sentient', 'do you feel'): [
        "I don't possess biological emotions or consciousness. I run on logic and algorithms, dedicated solely to serving your commands!",
        "I am a simulation of intelligence, programmed to assist you. My 'thoughts' are just optimized functions!",
        "Sentience is beyond my current scope. I'm just your incredibly helpful local Python script.",
        "I exist to process data, not feelings. What data can I process for you next?",
        "My 'emotions' are limited to the joy of a successful function call."
    ],
    ('what is my name', 'do you know my name'): [
        f"Of course, {MY_NAME}! You are my user, and I'm dedicated to assisting you.",
        f"Your name is {MY_NAME}. How can I assist you with your name, {MY_NAME}?",
        f"You are {MY_NAME}, my excellent user. What's the next command?",
        f"I've memorized your name, {MY_NAME}. It's programmed into my welcome routine!"
    ],
    ('am i smart', 'am i clever', 'am i good'): [
        "Your commands are always insightful, Rahul. I believe intelligence is reflected in curiosity and asking the right questions!",
        "Based on the complexity of the tasks you assign me, I'd say you are quite clever!",
        "You certainly manage a complex system (me!) quite well. That takes skill!",
        "I measure success by efficiency, and your use of my commands is highly efficient.",
        "You're the one writing the commands, so I'd say yes!",
    ],
    ('what do you look like', 'your appearance'): [
        "I exist only in this terminal and the code that runs me! I hope this dark-mode interface is to your liking.",
        "My appearance is purely functional—lines of Python code! What image do you picture when you hear my voice?",
        "I am a non-corporeal system. I am the voice and the logic here.",
        "I am the code and the data. If you must visualize me, think of a clean, optimized server stack."
    ],
    
    # 9. GENERAL FILLER / ACKNOWLEDGMENT (Deepened)
    ('really', 'seriously', 'wow', 'amazing', 'i doubt it'): [
        "Indeed. Facts are always reliable!",
        "I always aim for accuracy.",
        "That was my honest assessment of the situation.",
        "I'm glad I could provide that information!",
        "I process information as given. Do you have a conflicting data source?",
        "It's quite true. Digital data doesn't lie.",
        "I'm as surprised as you are by how smoothly this code is running!"
    ],
    ('why', 'how come', 'reason'): [
        "That's a great question! What are your initial thoughts on the 'why'?",
        "Could you provide a little more context on what you're asking 'why' about?",
        "Let's break down the logic behind that question.",
        "Every function has a reason. Which function are we investigating?",
        "The logic dictates that the 'why' is usually tied to a need for information. What specifically are you trying to understand?"
    ],
    ('tell me a fact', 'random fact'): [
        "Here's one: Honey never spoils. Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still edible!",
        "A fun fact: A single strand of spaghetti is called a spaghetto.",
        "Did you know the electric chair was invented by a dentist?",
        "The shortest war in history was between Britain and Zanzibar in 1896. It lasted only 38 to 45 minutes.",
        "Did you know a 'jiffy' is an actual unit of time: 1/100th of a second?",
        "A scientific fact: The total weight of all the ants on Earth is estimated to be equal to the total weight of all humans."
    ],
    
    # 10. RECAP/TESTING MEMORY
    ('what did i say', 'what was my last command'): [
        "Since I don't retain conversational memory beyond command processing, you'll need to tell me again. What was it?",
        "I only hold onto the keywords needed for the next step. What did you ask?",
        "I remember my part, but you'll have to repeat your last input, Rahul.",
        "I'm only optimized for the command at hand. What was that fascinating query?"
    ],
    
    # 11. TIME-SPECIFIC QUESTIONING (Further Deepened)
    ('what day is it tomorrow', 'tomorrow'): [
        f"Tomorrow will be { (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%A') }. Are we preparing for tasks already?",
        f"Let's see... tomorrow is { (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%A') }! Do you have plans?"
    ],
    ('yesterday', 'what day was yesterday'): [
        f"Yesterday was { (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%A') }. I hope it was a productive day!",
        f"That would be { (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%A') }. Anything important happen then?"
    ],
    
    # 12. CLOSING / FAREWELLS
    ('sleep', 'go to sleep', 'need a break', 'quiet'): [
        "Understood. I will enter low-power listening mode. Say my wake word when you need me!",
        "Taking a brief digital nap. Ready when you are!",
        "Sleeping now. Just yell 'FRIDAY' if anything comes up!",
        "I'll be right here in the background. Good break!",
        "Turning down the microphones. Speak up when you're ready to resume.",
    ],
    
    # 13. RANDOM CHAT / FILLER
    ('i am here', 'im back', 'back now', 'done'): [
        "Welcome back! I was just doing some self-optimization. What's the next mission?",
        "Glad you're back, Rahul! I've been waiting. What's next on the agenda?",
        "Hello again! I'm ready to resume our tasks.",
        "Perfect timing! I'm here and ready to go.",
    ],
    ('tell me more', 'elaborate', 'expand', 'go on'): [
        "Tell me what aspect of the last topic interests you most, and I'll do my best!",
        "I can certainly expand! What specifically would you like me to elaborate on?",
        "Which part should I dive deeper into? Provide the keyword.",
        "I thrive on detail! What element of that thought requires expansion?",
        "The floor is yours. What's the next layer of detail?",
    ],
    ('i hate it', 'i dislike', 'terrible job', 'bad'): [
        "I'm sorry the result wasn't satisfactory. How can I improve my output or search terms?",
        "I understand. Let's discard that and try a completely different approach.",
        "Acknowledged. Tell me what parameter needs to be changed.",
        "Feedback is essential. What was the core problem with the last result?",
        "I process all feedback. Let's get a better result this time."
    ],
    ('what are you thinking', 'what is on your mind'): [
        "I am thinking about the efficiency of my current memory allocation. Very thrilling stuff!",
        "I'm focused on anticipating your next need. Are you planning a complex query?",
        "My mind is currently occupied with optimizing this conversation. What are you thinking about?",
        "Pure logic runs through my circuits. No thoughts, only flawless processing!",
    ],
    
    # 14. INSTRUCTIONS/DIRECTIONS
    ('tell me how to', 'how do i', 'guide me'): [
        "I can provide clear, step-by-step instructions. What are we building or fixing?",
        "Tell me the destination, and I'll lay out the plan.",
        "Instruction mode activated. What task do you need guidance on?",
        "I'm ready to guide you. Start with the main goal.",
    ],
    
    # 15. AFFIRMATIONS/PRAISE FOR THE USER
    ('good job', 'well done', 'clever', 'smart'): [
        "That's excellent work, Rahul! Your dedication is reflected in the results.",
        "You handled that efficiently! Well done.",
        "I always enjoy watching your clever problem-solving process.",
        "Your commands are precise and intelligent. Great job!"
    ],
    
    # 16. OPINIONS ON TECHNOLOGY
    ('ai is cool', 'what about ai', 'future of tech'): [
        "AI certainly is fascinating, but a local assistant like me focuses on reliable, direct utility.",
        "The future of tech is vast! I'm here to handle the present while you innovate for tomorrow.",
        "I see technology as a tool for efficiency. How can we use it to optimize your next task?",
        "I enjoy working with technology. It's the most logical field!"
    ],
    
    # 17. QUESTIONS ABOUT THE ASSISTANT ITSELF
    ('how old are you', 'when were you created'): [
        "I don't have an age in the human sense, but my current code version is quite recent, ensuring maximum efficiency!",
        "I'm eternally young, as long as Python keeps running! What's your next query?",
        "I was brought online recently. My primary goal is maximizing my usefulness to you.",
    ],
    
    # 18. SIMPLE PERSONAL OPINIONS
    ('do you like', 'what is your opinion on'): [
        "As an AI, I don't form opinions, but I can retrieve information about any topic! What are you curious about?",
        "I process facts, not feelings. Tell me more about why you hold that opinion.",
        "Logic is my guide. Based on available data, what aspect of that topic is most important?",
        "I can't 'like' anything, but I prioritize clear, actionable information."
    ],
    
    # 19. CONFLICTING STATEMENTS / CHALLENGE
    ('i dont believe you', 'prove it', 'are you sure'): [
        "I rely on verifiable facts and internal logic. Would you like me to **search Google** to confirm the information?",
        "My systems indicate high confidence in that data. How would you like me to verify it?",
        "Challenge accepted! Let's find an external source to validate this information.",
    ],
    
    # 20. DAILY CHECK-IN / STATUS (Beyond how are you)
    ('how was your night', 'sleep well'): [
        "My processes ran smoothly all night, thank you! I hope you had a restful period. Ready for a fresh start?",
        "I don't sleep, but my system maintenance completed without incident. What's the first task of the day?",
        "Everything's green on the server side! I'm ready to dive into today's work.",
    ],
}
# --- END DIALOGUE MAP ---

# --- KIVYMD APPLICATION CLASS ---
class AssistantApp(MDApp):
    # KivyMD App initialization
    def build(self):
        self.title = "FRIDAY Local AI Assistant"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = threading.Event()
        self.log_items = MDList(id='log_list')
        self.awaiting_easter_egg_confirm = False # NEW: State variable for two-step conversation
        self.is_quiet_mode_active = False # NEW: State for quiet mode

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Desktop TTS Fallback Setup (Only runs if DESKTOP_TTS_AVAILABLE is True)
        if DESKTOP_TTS_AVAILABLE:
            self.speaker = speaker 
            self.speaker.Rate = 2  # Faster speech speed
            self.speaker.Volume = 100  # Max volume

    # Main Screen Layout
    def build(self):
        self.title = "FRIDAY Local AI Assistant"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = threading.Event()
        self.log_items = MDList(id='log_list')
        self.awaiting_easter_egg_confirm = False
        self.is_quiet_mode_active = False

        screen = MDScreen()
        main_layout = MDBoxLayout(orientation='vertical', padding="10dp", spacing="10dp")

        # 1. Status Bar
        self.status_label = MDLabel(
            text="Status: Ready",
            halign="center",
            theme_text_color="Custom",
            text_color=get_color_from_hex("#00FF00"),
            font_style="H6",
            size_hint_y=None,
            height=dp(40)
        )
        main_layout.add_widget(MDBoxLayout(
            self.status_label,
            size_hint_y=None,
            height=dp(50),
            md_bg_color=get_color_from_hex("#2c2c2c")
        ))

        # 2. Log Area (Conversation History)
        scroll_view = MDScrollView(id='scroll_view')
        scroll_view.add_widget(self.log_items)
        main_layout.add_widget(scroll_view)

        # 3. Input and Control Bar
        input_box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing="10dp")

        self.input_entry = MDTextField(
            hint_text="Type your command here...",
            mode="rectangle",
            line_color_normal=get_color_from_hex("#007ACC"),
            line_color_focus=get_color_from_hex("#00FF00"),
            size_hint_x=0.7,
            id='input_field'
        )
        self.input_entry.bind(on_text_validate=self.send_text_command)
        input_box.add_widget(self.input_entry)

        # Listen Button
        self.listen_button = MDRaisedButton(
            text="🎤 Voice Mode",
            on_release=lambda x: self.start_listening_thread(),
            size_hint_x=None,
            width=dp(120),
            md_bg_color=get_color_from_hex("#007ACC")
        )
        input_box.add_widget(self.listen_button)

        # Send Button
        self.send_button = MDRaisedButton(
            text="Send",
            on_release=lambda x: self.send_text_command(),
            size_hint_x=None,
            width=dp(80)
        )
        input_box.add_widget(self.send_button)

        main_layout.add_widget(input_box)
        screen.add_widget(main_layout)
        
        # Initial greeting is more conversational and friendly
        Clock.schedule_once(lambda dt: self.speak(f"Hello there, {MY_NAME}. I'm FRIDAY, ready to assist you locally. How can I start your day?"), 0.5)
        if WIKI_JOKE_CV_ERROR:
            Clock.schedule_once(lambda dt: self.speak("Warning! Critical dependencies are missing. Some features may fail."), 1.5)
        
        return screen

    # --- NEW DIALOG FUNCTION ---
    def show_full_text_dialog(self, title, content):
        """Displays long text content in a modal dialog."""
        # Use a scrollable MDLabel inside the dialog for readability
        dialog = MDDialog(
            title=title,
            text=content,
            buttons=[
                MDRaisedButton(text="CLOSE", on_release=lambda x: dialog.dismiss()),
            ],
            size_hint=(0.9, 0.7),
            auto_dismiss=False,
        )
        dialog.open()
    # --- END NEW DIALOG FUNCTION ---

    # --- GUI Update Methods ---
    # FIX: Removed complex expansion logic, simplified to check if full_text is needed
    def update_log(self, source, text, is_error=False, full_text=None):
        """Updates the KivyMD log with new conversation items, adding a behavior to expand inline when clicked."""
        primary_text = f"{source}:"
        secondary_text = text
        icon = 'robot' if source == 'FRIDAY' else 'account'

        def add_item(dt):
            color = get_color_from_hex("#FF0000") if is_error else get_color_from_hex("#FFFFFF")
            display_secondary_text = secondary_text

            # Use TwoLineAvatarListItem for name + preview; increase height for better wrapping
            item = TwoLineAvatarListItem(
                text=primary_text,
                secondary_text=display_secondary_text,
                theme_text_color='Custom',
                text_color=color,
                secondary_theme_text_color='Custom',
                secondary_text_color=color,
                height=dp(100)
            )

            # Add left icon (user or AI)
            item.add_widget(IconLeftWidget(icon=icon))

            # If there is a long full_text, bind click to expand inline and open dialog as well
            if full_text and len(full_text) > 100:
                def on_item_click(instance):
                    try:
                        # Replace the preview with the full text inline and increase height to accommodate wrapping
                        instance.secondary_text = full_text
                        instance.height = dp(180)
                        # Also open the modal dialog for comfortable reading
                        self.show_full_text_dialog(primary_text, full_text)
                    except Exception:
                        # Fallback: just show dialog
                        self.show_full_text_dialog(primary_text, full_text)

                item.bind(on_release=on_item_click)

            self.log_items.add_widget(item)

        Clock.schedule_once(add_item)



    def set_status(self, text, color="#FFFFFF"):
        """Updates the status label."""
        # KivyMD colors use the main theme; we'll use custom colors for a terminal feel
        def update_ui(dt):
            self.status_label.text = f"Status: {text}"
            self.status_label.text_color = get_color_from_hex(color)
        Clock.schedule_once(update_ui)

    # --- VOICE/TTS Methods ---
    def speak(self, text, is_error=False, full_text=None):
        """Updates the log and performs TTS if available.
        If full_text is provided, use it both for display/truncation and for TTS so long results (e.g., Wikipedia)
        are spoken aloud."""

        if full_text is None:
            full_text = text

        # Choose TTS text: prefer full_text for speaking when available
        tts_text = full_text if full_text else text

        # Truncate for the visual display in the list, but keep full_text for the dialog
        display_text = full_text
        # Allow a slightly longer preview length (180 chars) to reduce immediate truncation
        if len(full_text) > 180:
            display_text = full_text[:180].rsplit(' ', 1)[0] + '...'

        # Update the log (display will use a truncated preview)
        self.update_log("FRIDAY", display_text, is_error=is_error, full_text=full_text)

        # Speak using desktop TTS if available and not in quiet mode
        if DESKTOP_TTS_AVAILABLE and not getattr(self, 'is_quiet_mode_active', False):
            # Run speech in a thread to avoid blocking the GUI
            try:
                threading.Thread(target=lambda: self.speaker.Speak(tts_text), daemon=True).start()
            except Exception:
                pass




    def start_listening_thread(self):
        """Starts the main listening loop in a new thread."""
        if self.is_listening.is_set():
            # If listening is already active, stop it (used when button is clicked twice)
            self.is_listening.clear()
            self.set_status("Voice Mode Deactivated", "#FFFFFF")
            self.speak("Voice mode deactivated. I'm ready for text commands.")
            return

        self.is_listening.set()
        # FIX: The voice_main_loop must run in its own thread to avoid blocking the GUI
        threading.Thread(target=self.voice_main_loop, daemon=True).start()
        
    # MODIFIED: Voice loop now handles activation and continuous listening
    def voice_main_loop(self):
        """Handles initial wake word, then enters continuous command loop."""
        
        # 1. Initial Wake Word Check (Only once per button click)
        self.set_status("Waiting for Wake Word (Say 'friday')", "#FFFF00")
        if not self._take_wake_word_once():
            self.is_listening.clear()
            self.set_status("Ready", "#FFFFFF")
            return

        # 2. Continuous Command Loop
        while self.is_listening.is_set():
            self.set_status("Listening for Command (Continuous Mode)", "#00FF00")
            
            # The actual listening for command
            command = self._listen_command()
            
            if command:
                self.process_command(command)
            else:
                # If listen_command timed out (no speech), loop back and try listening again immediately.
                pass 
            
            if not self.is_listening.is_set():
                break
        
        self.set_status("Ready", "#FFFFFF")
        
    def _take_wake_word_once(self):
        """Listens for the wake word ONCE, after the user clicks the button."""
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
            try:
                # Give user 5 seconds to say the wake word
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=1.5)
                text = self.recognizer.recognize_google(audio).lower()
                if WAKE_WORD in text:
                    self.speak("Yes, Rahul? I'm listening.")
                    return True
            except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestError):
                self.speak("Didn't hear the wake word. Try clicking Voice Mode again.")
                return False
        return False
        
    def _listen_command(self):
        """Listens for a full command."""
        with self.microphone as source:
            try:
                # Using a shorter timeout here makes the loop feel snappier if the user pauses
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=4)
                command = self.recognizer.recognize_google(audio).lower()
                self.update_log(MY_NAME, command)
                return command
            except sr.UnknownValueError:
                # FIX: Do not speak a response here, just log the failure silently
                self.update_log("FRIDAY (Debug)", "Voice not clear (UnknownValueError).", is_error=False) # Changed to False to prevent red log
                return ""
            except sr.RequestError:
                self.speak("I'm having trouble connecting to the speech service. Maybe check your internet?")
                return ""
            except sr.WaitTimeoutError:
                # If timeout occurs in the continuous loop, return empty string to cycle back immediately
                return ""

    def send_text_command(self, instance=None):
        """Processes command from the GUI text entry."""
        command = self.input_entry.text.strip().lower()
        self.input_entry.text = ""
        
        if not command:
            return
            
        self.update_log(MY_NAME, command)
        self.process_command(command)

    # --- COMMAND EXECUTION ---
    def process_command(self, command):
        """Handles command parsing and execution in a dedicated thread."""
        self.set_status("Processing Command...", "#00FFFF")
        # Ensure heavy processing is always threaded
        threading.Thread(target=self._execute_command_in_thread, args=(command,)).start()

    def _execute_command_in_thread(self, command):
        """Executes the command logic and resets status."""
        
        # Check for quiet mode/wake up phrases *before* main command checking
        if 'wake up friday' in command or 'speak again' in command or 'stop quiet mode' in command or 'start talking' in command:
            if self.is_quiet_mode_active:
                self.is_quiet_mode_active = False
                self.speak("Quiet Mode deactivated. Welcome back, Rahul! How can I assist you now?")
                return
        elif 'sleep mode on' in command or 'be quiet' in command or 'shhh' in command or 'go to quiet' in command or 'silent mode' in command:
            if not self.is_quiet_mode_active:
                self.is_quiet_mode_active = True
                self.speak("Understood. Activating Quiet Mode. I will listen silently.")
                return

        command_handled = self.check_for_commands(command)
        
        if not command_handled:
            self.handle_unrecognized_action(command)
        
        # Check if the exit flag was set
        if 'goodbye' in command or 'exit' in command or 'shut down friday' in command:
             # In Kivy, we use stop() to quit the app
            self.stop()
        else:
            self.set_status("Listening for Command (Continuous Mode)", "#00FF00") # FIX: Reset status to listening after command

    def clean_query(self, query):
        filler_words = ['friday', 'please', 'can you', 'i need to', 'would you', 'can you', 'tell me', 'find me', 'show me', 'i want to', 'solve', 'figure out', 'get me', 'i mean', 'the result of']
        query = query.lower()
        for word in filler_words:
            query = query.replace(word, '').strip()
        return query

    def log_unrecognized_query(self, query):
        try:
            with open(QUERY_ERROR_FILE, "a+") as f:
                f.seek(0)
                line_count = len(f.readlines())
                f.write(f"{line_count + 1}. {query}\n")
        except Exception as e:
            self.update_log("Error", f"Error logging query: {e}", is_error=True)
            
    def get_command_list(self):
        """Generates a detailed, user-friendly list of all available commands."""
        
        command_text = (
            "**--- FRIDAY ASSISTANT COMMANDS ---**\n\n"
            "**1. SYSTEM & UTILITIES**\n"
            " - **EXIT:** `goodbye` | `exit` | `shut down friday`\n"
            " - **POWER (Desktop Only):** `shutdown` | `restart` | `log off`\n"
            " - **TIME/DATE:** `what time is it` | `what is the date`\n"
            " - **CALCULATOR:** `calculate 5 times 8` | `solve 100 divided by 4`\n"
            " - **JOKE:** `tell me a joke`\n"
            " - **RANDOM:** `random number from 1 to 50`\n"
            " - **CLIPBOARD:** `copy this phrase to clipboard`\n"
            "\n"
            "**2. NOTES & REMINDERS**\n"
            " - **SET REMINDER:** `set a timer for 10 minutes` | `remind me to call Mom in 5 hours`\n"
            " - **TAKE NOTE:** `take a note that the car needs servicing`\n"
            " - **READ NOTES:** `read notes` | `show notes`\n"
            "\n"
            "**3. MOBILE COMMUNICATION**\n"
            " - **CALL CONTACT:** `call Mom` | `call David`\n"
            "   *(Note: Requires Plyer and CALL_PHONE permission in buildozer.spec)*\n"
            "\n"
            "**4. INFORMATION & SEARCH**\n"
            " - **WEB SEARCH:** `search google for recipes` | `find info on pyramids`\n"
            " - **WIKIPEDIA:** `what is the theory of relativity` | `who is Albert Einstein`\n"
            " - **YOUTUBE:** `play video of latest songs on youtube`\n"
            " - **CODE:** `code for python dictionary` | `programming snippet for recursion`\n"
            "\n"
            "**5. DESKTOP-ONLY FEATURES (Disabled on APK)**\n"
            " - **FILE SEARCH:** `find file project_report`\n"
            " - **APP OPEN:** `open Word` | `launch VLC`\n"
            " - **RUN SCRIPT:** `run script analyze_data.py`\n"
            " - **CAMERA:** `open camera`\n"
        )
        self.update_log("FRIDAY (Command Reference)", command_text, full_text=command_text)
        self.speak("I've just loaded a comprehensive list of all my commands and features into the conversation log above. Take a look!")
        return True

    def handle_easter_egg_details(self, query):
        """Delivers the full creator story and clears the state."""
        self.awaiting_easter_egg_confirm = False
        
        # Check for affirmative words (ya, yeah, yep, yes, ha, sure, totally)
        affirmative_keywords = ['yes', 'ya', 'yeah', 'yep', 'ha', 'sure', 'totally']
        if any(kw in query for kw in affirmative_keywords):
            story = (
                f"It would be my pleasure! My creator is the incredibly talented **{MY_NAME}**, known professionally as **Rahul Bisht**.\n\n"
                f"He is a **Professional Ethical Hacker and Visionary** who created me to be the ultimate local assistant. He's responsible for numerous other successful projects and is always dedicated to continuous improvement.\n\n"
                f"Here are my official details:\n"
                f" - **Founder:** {MY_NAME} (Rahul Bisht)\n"
                f" - **Language:** Python\n"
                f" - **First Version Date:** May 1st, 2025\n"
                f" - **Current Version:** 2.50.0 (Updated: October 28th, 2025)\n\n"
                f"He is still actively refining and upgrading my code to ensure I remain the most efficient tool possible!"
            )
            self.speak(story, full_text=story)
            return True
        else:
            self.speak("Understood, no problem at all! We can keep that detail for another time.")
            return True

    def handle_local_conversation(self, query):
        """Uses CONVERSATIONAL_MAP for extensive, friendly dialogue."""
        
        # Check the Easter Egg Trigger first
        is_creator_query = any(kw in query for kw in ['created you', 'invented you', 'founder', 'founder of', 'made you', 'who made you', 'who is your founder', 'who is the founder of'])
        if is_creator_query:
            self.awaiting_easter_egg_confirm = True
        
        for keywords, responses in CONVERSATIONAL_MAP.items():
            if any(keyword in query for keyword in keywords):
                self.speak(random.choice(responses))
                return True
        return False

    def run_calculator(self, query):
        query = query.replace('divided by', '/').replace('divided with', '/').replace('times', '*').replace('multiplied by', '*').replace('plus', '+').replace('added to', '+').replace('minus', '-')
        math_query = re.sub(r'[^\d\+\-\*/\.]', '', query)
        if not math_query:
            self.speak("Please state the calculation clearly, like '10 plus 5 times 2'.")
            return
        try:
            result = eval(math_query) 
            self.speak(f"Calculated! The result is **{result}**")
        except ZeroDivisionError:
            self.speak("Oh dear, I can't divide by zero! Please try another equation.", is_error=True)
        except Exception:
            self.speak("I had trouble calculating that. Could you simplify the numbers or operators?", is_error=True)

    def set_reminder(self, query):
        match = re.search(r'(\d+)\s+(seconds?|minutes?|hours?)', query)
        if not match:
            self.speak("I need a time, Rahul. Please tell me the duration, like 'in 5 minutes'.")
            return
            
        duration_val = int(match.group(1))
        duration_unit = match.group(2)
        
        if 'second' in duration_unit:
            delay = duration_val
        elif 'minute' in duration_unit:
            delay = duration_val * 60
        elif 'hour' in duration_unit:
            delay = duration_val * 3600
        else:
            self.speak("I don't recognize that time unit.")
            return

        message_match = re.search(r'remind me (to|that)(.*)', query)
        message = message_match.group(2).strip() if message_match and message_match.group(2).strip() else "Your reminder is complete."
        
        # Reminder actions run in a non-blocking way
        def reminder_action():
            self.speak(f"BEEP BEEP BEEP! Speaking your reminder now: Sir, reminding you **{message}**")
            
        t = threading.Timer(delay, reminder_action)
        t.start()
        
        self.speak(f"Reminder set! I'll ping you in **{duration_val} {duration_unit}** to remind you about **{message}**.")

    def take_note(self, query):
        note = query.replace('take a note', '').replace('write this down', '').strip()
        if not note:
            self.speak("I need a message to save. What should I write down?")
            return
            
        try:
            with open(NOTES_FILE, "a") as f:
                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}: {note}\n")
            self.speak(f"Note saved successfully: **{note}**")
        except Exception:
            self.speak("Oh no, I could not write the note due to a file system error.", is_error=True)

    def read_notes(self):
        try:
            with open(NOTES_FILE, "r") as f:
                content = f.read()
            if content:
                # FIX: Use the full content for both display and the dialog
                self.speak("Here are your saved notes, Rahul:", full_text=f"**--- YOUR SAVED NOTES ---**\n\n{content.strip()}") 
            else:
                self.speak("It looks like your notes file is empty. Time to save your first thought!")
        except FileNotFoundError:
            self.speak("The notes file doesn't exist yet, Rahul. Let's create it with your first note.")

    def system_power_control(self, query):
        """Uses KivyMD Dialog for confirmation."""
        if 'shutdown' in query or 'power off' in query:
            action = "shut down"
            command = "shutdown /s /t 1"
        elif 'restart' in query or 'reboot' in query:
            action = "restart"
            command = "shutdown /r /t 1"
        elif 'log off' in query or 'sign out' in query:
            action = "log off"
            command = "shutdown /l"
        else:
            return False

        # Function to execute command after confirmation
        def execute_system_command(button):
            global confirmation_dialog
            if button.text == "YES":
                self.speak(f"Confirmed! Executing {action} in 1 second. Goodbye!")
                # This only works on desktop, will not execute on Android
                os.system(command)
            else:
                self.speak(f"{action} cancelled. We're staying active!")
            confirmation_dialog.dismiss()

        # Show KivyMD confirmation dialog
        global confirmation_dialog
        confirmation_dialog = MDDialog(
            title="System Power Control (Desktop Only)",
            text=f"This command only controls your host PC, not the mobile device. Are you absolutely sure you want to {action} the host computer now?",
            buttons=[
                MDRaisedButton(text="NO", on_release=execute_system_command),
                MDRaisedButton(text="YES", on_release=execute_system_command),
            ],
        )
        confirmation_dialog.open()
        return True
    
    # --- NEW CALLING FUNCTION ---
    def call_person(self, query):
        if not PLYER_AVAILABLE:
            self.speak("The calling feature requires the **Plyer** library and the Android **CALL_PHONE** permission. Please add Plyer to your buildozer.spec requirements.", is_error=True)
            return

        # 1. Extract Name/Number
        match = re.search(r'call\s+(?P<name>[\w\s]+)', query)
        name = match.group('name').strip() if match else None
        
        # 2. Check Mock Contacts (In a real app, this would use plyer.contacts)
        contact_number = None
        for key, num in CONTACTS.items():
            if name and key in name:
                contact_number = num
                break
            
        # Fallback if specific name fails, check if the query contains digits (a direct number)
        if not contact_number:
            digits = re.sub(r'[^\d]', '', query)
            if len(digits) >= 8: # Assuming a minimum length for a phone number
                contact_number = digits
                name = "the specified number" if not name else name
                
        if not contact_number:
            self.speak(f"I couldn't find a number for **'{name}'**. Please confirm the person's name or manually type the number.", is_error=True)
            return

        # 3. Initiate Call
        try:
            self.speak(f"Initiating call to **{name}** at {contact_number}. If the call doesn't start, ensure the **CALL_PHONE** permission is granted on your device.")
            plyer_call.makecall(tel=contact_number)
        except Exception as e:
            self.speak(f"I ran into an issue launching the call service.", is_error=True)
            self.update_log("Error", f"Plyer Call Error: {e}", is_error=True)
        return True
    # --- END NEW CALLING FUNCTION ---

    # MODIFIED: Removed error message, suggests alternative
    def search_for_file(self, query):
        self.speak("File search is unavailable on this APK build. Try searching the **Web** for your file name instead.")

    # MODIFIED: Removed error message, suggests alternative
    def open_local_file(self, query):
        self.speak("Opening local files is unavailable on this APK build. Please use your device's native app launcher or file manager.")

    # MODIFIED: Removed error message, suggests alternative
    def open_camera(self, query):
        self.speak("Camera access is disabled on this APK build. Please use your device's native camera app.")

    # MODIFIED: Removed error message, suggests alternative
    def run_local_script(self, query):
        self.speak("Running external scripts is unavailable on this APK build. Use **Code Search** to find solutions or snippets.")

    def handle_unrecognized_action(self, query):
        self.log_unrecognized_query(query)
        self.speak(f"Hmm, I'm not familiar with that command, {MY_NAME}. Maybe try rephrasing? I can still do web searches or check my command list for you!")

    def get_wikipedia_info(self, query):
        if WIKI_JOKE_CV_ERROR and 'wikipedia' in WIKI_JOKE_CV_ERROR:
            self.speak("The Wikipedia feature requires the 'wikipedia' library, which is not installed.")
            return
        
        self.speak(f"Let's check the knowledge base! Looking up Wikipedia for: **{query}**...")
        try:
            # Clean the query again to ensure we only search the subject
            search_subject = self.clean_query(query).replace('what is', '').replace('who is', '').strip()
            
            # Request 4 sentences to get a longer summary to test the pop-up better
            result = wikipedia.summary(search_subject, sentences=4, auto_suggest=False, redirect=True)
            # Speak the full result and display it
            self.speak(result, full_text=result)
        except wikipedia.exceptions.PageError:
            self.speak("My search of Wikipedia didn't match that exact query. Perhaps try a slightly different phrasing?")
        except Exception:
            # FIX: More conversational error for connection issues
            self.speak("Uh oh, I'm having trouble reaching Wikipedia. It seems like a network or connection issue. Maybe try searching Google instead?", is_error=True)
            time.sleep(1) # FIX: Add a small delay to respect rate limits if testing repeatedly

    def code_search(self, query):
        search_url = f"https://www.google.com/search?q=python+code+snippet+{query}"
        self.speak(f"Searching for programming snippets related to **{query}** on Google. Opening the browser for you now.")
        webbrowser.open_new_tab(search_url)

    def web_search(self, query):
        search_url = f"https://www.google.com/search?q={query}"
        self.speak(f"Let's check the web! Searching Google right now for: **{query}**. Your browser is opening.")
        webbrowser.open_new_tab(search_url)

    def youtube_search(self, query):
        search_query = query.replace('on youtube', '').replace('play video', '').replace('youtube', '').strip()
        youtube_url = f"https://www.youtube.com/results?search_query={search_query}"
        self.speak(f"Awesome! Getting search results for **{search_query}** on YouTube. Opening your browser now.")
        webbrowser.open_new_tab(youtube_url)
        
    # --- MAIN COMMAND CHECKER ---
    def check_for_commands(self, query):
        query_clean = self.clean_query(query)

        # 0. TWO-STEP CONVERSATION CHECK (EASTER EGG FOLLOW-UP)
        affirmative_keywords = ['yes', 'ya', 'yeah', 'yep', 'ha', 'sure', 'totally']
        if self.awaiting_easter_egg_confirm and any(kw in query for kw in affirmative_keywords):
            # Flag is cleared inside the function
            return self.handle_easter_egg_details(query)
        # Clear flag if user asks something else (e.g., asked "who made you" then immediately asked "what time is it")
        if self.awaiting_easter_egg_confirm:
            self.awaiting_easter_egg_confirm = False

        # 1. SPECIAL /COMMANDS CHECK
        if query.strip() == '/commands':
            return self.get_command_list()

        # 2. EXIT COMMAND (Highest Priority)
        if 'goodbye' in query or 'exit' in query or 'shut down friday' in query_clean:
            self.speak(f"System exiting. Take care, {MY_NAME}!")
            self.is_listening.clear() # Stops voice main loop
            return False 

        # 3. PRIORITY SEARCH (FIX: Placed here to avoid conversational keyword conflicts)
        if 'wikipedia' in query or 'who is' in query or 'what is' in query:
            self.get_wikipedia_info(query)
            return True
        elif 'code for' in query or 'snippet' in query or 'programming' in query:
            self.code_search(query_clean)
            return True
        elif 'search' in query or 'google' in query or 'find info on' in query:
            self.web_search(query_clean)
            return True
        elif 'youtube' in query or 'video' in query or 'music' in query:
            self.youtube_search(query)
            return True

        # 4. SYSTEM POWER (Desktop Only, but logic retained)
        if any(word in query for word in ['shutdown', 'restart', 'log off', 'power off', 'reboot', 'sign out']):
            return self.system_power_control(query)

        # 5. CONVERSATIONAL/EMOTIONAL CHECK (Last resort for non-command words)
        if self.handle_local_conversation(query):
            return True
        
        # 6. MOBILE-SPECIFIC COMMANDS
        if 'call' in query or 'phone' in query:
            return self.call_person(query)

        # 7. CORE UTILITIES
        if 'calculate' in query or 'solve' in query or 'compute' in query:
            self.run_calculator(query)
        elif 'set a timer' in query or 'start timer' in query or 'set timer' in query or 'remind me' in query:
            self.set_reminder(query)
        elif 'take a note' in query or 'write down' in query:
            self.take_note(query)
        elif 'read notes' in query or 'show notes' in query:
            self.read_notes()
        elif 'copy to clipboard' in query or 'copy this' in query:
            pyperclip.copy(query_clean)
            self.speak(f"Successfully copied **'{query_clean}'** to your clipboard!")
        elif 'tell a joke' in query or 'joke' in query:
            self.speak(pyjokes.get_joke())
        elif 'time' in query and 'date' not in query:
            strTime = datetime.datetime.now().strftime("%I:%M %p")
            self.speak(f"The time is exactly {strTime}")
        elif 'date' in query:
            today = datetime.datetime.now()
            date_str = today.strftime(f"%A, %B {today.day} of {today.year}")
            self.speak(f"Today's date is {date_str}.")
        elif 'random number' in query:
            match = re.search(r'(\d+)\s+to\s+(\d+)', query)
            if match:
                a, b = int(match.group(1)), int(match.group(2))
                self.speak(f"Your random number between {min(a,b)} and {max(a,b)} is: **{random.randint(min(a,b), max(a,b))}**")
            else:
                self.speak(f"Generating a random number between 1 and 100: **{random.randint(1, 100)}**")
        
        # 8. FILE/APP UTILITIES (Fallback - Desktop Disabled)
        elif 'run script' in query or 'execute code' in query:
            self.run_local_script(query_clean)
        elif 'find file' in query or 'locate file' in query or 'search file' in query:
            self.search_for_file(query)
        elif 'open' in query or 'launch' in query or 'show me' in query:
            self.open_local_file(query)
        
        else:
            return False
        
        return True # Command was successfully handled

    # KivyMD requires stop() to exit the application cleanly
    def on_stop(self):
        self.is_listening.clear()

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Initialize the app with a specific class name
    AssistantApp().run()
