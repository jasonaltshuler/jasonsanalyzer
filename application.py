import os

from flask import Flask, flash, jsonify, redirect, render_template, request, session, redirect, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError

from helpers import short, thesaurus, decode

# Told about "Counter" from a friend https://docs.python.org/2/library/collections.html
from collections import Counter

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["short"] = short

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        # Check if a file was uploaded
        if not request.files["thefile"]:
            # Check if any text was pasted
            if not request.form.get("thetext"):
                # If no file or pasted text, pass this message through instead
                unchanged_text = "No type entered or file uploaded!"
                return render_template("after.html", unchanged_text = unchanged_text, words="", favorites="", punctuationrefined="")
            else:
                rawtext = request.form.get("thetext")
                # If text was pasted, remove line space escape characters
                text = rawtext.replace('\n', ' ').replace('\r', '')
                # Preserve a variable "unchanged_text" to be displayed for the user, even as "text" is modified for counting purposes
                unchanged_text = text

        else:
            # Check if text was pasted in addition to an uploaded file
            if request.form.get("thetext"):
                # If that's the case, pass this message through
                text = "Please upload a file OR enter text (not both)"
            else:
                # If a .docx file was uploaded, parse it as text
                file = request.files["thefile"]
                if file.filename.endswith('.docx'):
                    # This is all from http://etienned.github.io/posts/extract-text-from-word-docx-simply/
                    try:
                        from xml.etree.cElementTree import XML
                    except ImportError:
                        from xml.etree.ElementTree import XML
                    import zipfile


                    """
                    Module that extract text from MS XML Word document (.docx).
                    (Inspired by python-docx <https://github.com/mikemaccana/python-docx>)
                    """

                    WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                    PARA = WORD_NAMESPACE + 'p'
                    TEXT = WORD_NAMESPACE + 't'


                    def get_docx_text(path):
                        """
                        Take the path of a docx file as argument, return the text in unicode.
                        """
                        document = zipfile.ZipFile(path)
                        xml_content = document.read('word/document.xml')
                        document.close()
                        tree = XML(xml_content)

                        paragraphs = []
                        for paragraph in tree.getiterator(PARA):
                            texts = [node.text
                                     for node in paragraph.getiterator(TEXT)
                                     if node.text]
                            if texts:
                                paragraphs.append(''.join(texts))

                        return '\n\n'.join(paragraphs)

                    rawtext = get_docx_text(file)
                    # Take away any line break escape characters
                    text = rawtext.replace('\n', ' ').replace('\r', '')
                    # Preserve a variable "unchanged_text" to be displayed for the user, even as "text" is modified for counting purposes
                    unchanged_text = text

        # Record counts for these 11 types of puntuaction
        punctuation = []
        period=0
        semicolon=0
        colon=0
        dash=0
        mdash=0
        comma=0
        exclamation=0
        question=0
        slash=0
        parenthesis=0
        quotation=0

        # Count how much each punctuation was used
        for character in text:
            if character ==".":
                period +=1
            elif character ==";":
                semicolon +=1
            elif character ==":":
                colon +=1
            elif character =="-":
                dash +=1
            elif character =="—":
                mdash +=1
            elif character ==",":
                comma +=1
            elif character =="!":
                exclamation +=1
            elif character =="?":
                question +=1
            elif character =="/":
                slash +=1
            elif character =="(":
                parenthesis +=1
            elif character =='“':
                quotation +=1
            elif character =='"':
                quotation +=1

        # Add the counts for each mark (in the form of a dict) to the centralized punctuation list
        # AND update text to wipe out any punctuation that could mess up word counting
            # For instance, so "Hi (I'm Jason)" is counted as Hi, I'm, and Jason... not Jason), (I'm, and Hi
            # If a punctuation mark is usually next to a space (like ?) just remove it; if usually touching letters (like -), replace it with a space to keep words separate
        punctuation.append({'Mark': ".", 'Count': period})
        text = text.replace('.', ' ')
        punctuation.append({'Mark': ";", 'Count': semicolon})
        text = text.replace(';', ' ')
        punctuation.append({'Mark': ":", 'Count': colon})
        text = text.replace(':', ' ')
        punctuation.append({'Mark': "-", 'Count': dash})
        text = text.replace('-', '')
        punctuation.append({'Mark': "—", 'Count': mdash})
        text = text.replace('—', ' ')
        punctuation.append({'Mark': ",", 'Count': comma})
        text = text.replace(',', ' ')
        punctuation.append({'Mark': "!", 'Count': exclamation})
        text = text.replace('!', ' ')
        punctuation.append({'Mark': "?", 'Count': question})
        text = text.replace('?', ' ')
        punctuation.append({'Mark': "/", 'Count': slash})
        text = text.replace('/', '')
        punctuation.append({'Mark': "( )", 'Count': parenthesis})
        text = text.replace('(', ' ')
        text = text.replace(')', ' ')
        punctuation.append({'Mark': '" "', 'Count': quotation})
        text = text.replace('“', ' ')
        text = text.replace('”', ' ')
        text = text.replace('"', ' ')


        # Got this from here https://www.geeksforgeeks.org/ways-sort-list-dictionaries-values-python-using-itemgetter/
        # and https://www.geeksforgeeks.org/python-removing-dictionary-from-list-of-dictionaries/
        from operator import itemgetter
        # Sort the punctuation marks by count from highest to lowest
        punctuationsorted = sorted(punctuation, key=itemgetter('Count'), reverse = True)
        # Remove any punctuation counts that are 0 (doesn't need to be displayed)
        punctuationrefined = [i for i in punctuationsorted if not (i['Count'] == 0)]

        # Make all of the text lowercase, to make counting case insensitive
        nocase = text.lower()
        # Split up the text into words (by spaces)
        allWords = nocase.split()
        # Get word count
        words=len(allWords)

        # From https://docs.python.org/2/library/collections.html
        import re

        # Read text file with 100 most common English words from wikipedia https://en.wikipedia.org/wiki/Most_common_words_in_English
        commons = open('commonwords.txt').read().split()

        # Read text file with 1000 most common English words from https://1000mostcommonwords.com/1000-most-common-english-words/
        morecommons = open('morewords.txt').read().split()

        # Check if there are any words to be exempted (from Advanced)
        if request.form.get("exemptions"):
            exceptions = request.form.get("exemptions")
            # If there are, make them lowercase and split them into individual words
            exceptions = exceptions.lower().split()
        else:
            exceptions = []

        # Count how many times every repeated word is used
        cnt = Counter()
        for word in (allWords):
            cnt[word] += 1
        counted = cnt

        # Make a list of all the keys counted (words counted)
        keys=counted.keys()
        key_array=[]
        for key in keys:
            key_array.append(key)

        # Screen any words necessary
        for i in range(0, len(key_array)):
            # If no screening was requested, move on
            if request.form.get("strictness") == "no":
                continue
            # If weak screening was requested, only use 100 word database
            elif request.form.get("strictness") == "weak":
                # Check if word in the sample is in 100 word database
                for common in commons:
                    if key_array[i] == common:
                        # If the key/word is in the database, delete the key/word
                        del counted[key_array[i]]
                        continue
            # If strong screening was requested, use 100 and 1000 word databases
            elif request.form.get("strictness") == "strong":
                # Check if word in the sample is in 100 word database
                for common in commons:
                    if key_array[i] == common:
                        # If the key/word is in the database, delete the key/word
                        del counted[key_array[i]]
                        continue
                # Check if word in the sample is in 1000 word database
                for morecommon in morecommons:
                    if key_array[i] == morecommon:
                        # If the key/word is in the database, delete the key/word
                        del counted[key_array[i]]

            # Check if the word in the sample is a word the user specifically disrequested
            for exception in exceptions:
                if key_array[i] == exception:
                    # If so, delete the key/word
                    del counted[key_array[i]]

        if request.form.get("quantity"):
            # If the user specified a number of words to show, record that in the variable "number"
            number = request.form.get("quantity")
            number = int(number)
        else:
            # If nothing specified, set default number of words shown to 10
            number = 10

        # From the main list of word counts, only take the top ones (depending on "number", as defined above)
        most=counted.most_common(number)

        # Create empty list favorites (to hold words and their counts)
        favorites=[]
        # Set "favoritestotal" to 0, which will come to equal the total number of times any of the favorites was used
        favoritestotal = 0
        # Set "favoritescount" to 0, which will come to equal the total count of favorite words, once any word with a count less than 3 is removed
        favoritescount = 0


        for i in range(0, len(most)):
            # Check if word was used more than twice
            if most[i][1] >= 3:
                # Check if the word is a single letter, that isn't "a" or "I"... if so, don't include it
                if len(most[i][0]) < 2 and most[i][0].upper() != "A" and most[i][0].upper() != "I":
                    continue
                else:
                    # Add a dictionary to favorites with 'Word' and 'Count' for every valid word in most
                    favorites.append({'Word': most[i][0].upper(), 'Count': most[i][1]})
                    # Add the count (times used) for each word to favoritestotal
                    favoritestotal += most[i][1]
                    # Add one to favoritescount, to get the total count of favorite words
                    favoritescount += 1

        # Calculate the portion of the total word count that was accounted for by the top words displayed
        percentage = round(((favoritestotal / words) * 100), 2)

        return render_template("after.html", favoritescount=favoritescount, percentage=percentage, unchanged_text = unchanged_text,
        words=words, favorites=favorites, punctuationrefined=punctuationrefined)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("index.html")

@app.route("/synonyms", methods=["GET"])
def synonyms():
    # Get the word to find synonyms for from the URL
    theword = request.args.get('word')
    # Look up the word with the thesaurus function (using the API)
    synonyms = thesaurus(theword)

    if synonyms == None:
        # If nothing is found, go to the synonyms page with no info
        return render_template("synonyms.html", theword=theword, noun_synonyms="", adjective_synonyms="", verb_synonyms="", adverb_synonyms="")
    else:
        # If the word has noun synonyms, populate "noun_synonyms" with them; otherwise, leave it blank
        if 'noun' in synonyms:
            noun_synonyms = synonyms["noun"]["syn"]
        else:
            noun_synonyms = ""
        # If the word has adjective synonyms, populate "adjective_synonyms" with them; otherwise, leave it blank
        if 'adjective' in synonyms:
            adjective_synonyms = synonyms["adjective"]["syn"]
        else:
            adjective_synonyms = ""
        # If the word has verb synonyms, populate "verb_synonyms" with them; otherwise, leave it blank
        if 'verb' in synonyms:
            verb_synonyms = synonyms["verb"]["syn"]
        else:
            verb_synonyms = ""
        # If the word has adverb synonyms, populate "adverb_synonyms" with them; otherwise, leave it blank
        if 'adverb' in synonyms:
            adverb_synonyms = synonyms["adverb"]["syn"]
        else:
            adverb_synonyms = ""

        return render_template("synonyms.html", theword=theword, noun_synonyms=noun_synonyms, adjective_synonyms=adjective_synonyms, verb_synonyms=verb_synonyms, adverb_synonyms=adverb_synonyms)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return render_template("index.html")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
