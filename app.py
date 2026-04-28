import requests
import re
import os
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS # এডেড: অ্যাপ থেকে কানেকশন সহজ করার জন্য

app = Flask(__name__)
CORS(app) # এটি অ্যাপের সাথে সার্ভারের যোগাযোগ নিশ্চিত করবে

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "http://www.educationboardresults.gov.bd/index.php"
}

def solve_captcha(session):
    url = "http://www.educationboardresults.gov.bd/index.php"
    try:
        res = session.get(url, headers=headers)
        match = re.search(r'(\d+\s*\+\s*\d+)', res.text)
        if match:
            return str(eval(match.group(1)))
    except: pass
    return None

@app.route('/check', methods=['GET'])
def check():
    exam = request.args.get('exam', 'ssc')
    year = request.args.get('year')
    board = request.args.get('board')
    roll = request.args.get('roll')
    reg = request.args.get('reg')

    session = requests.Session()
    ans = solve_captcha(session)
    if not ans: return jsonify({"error": "Captcha Error"}), 500

    payload = {
        "sr": "3", "et": "2", "exam": exam, "year": year,
        "board": board.lower(), "roll": roll, "reg": reg,
        "value_s": ans, "button2": "Submit"
    }

    try:
        res = session.post("http://www.educationboardresults.gov.bd/result.php", data=payload, headers=headers)
        if "Result" not in res.text: return jsonify({"error": "Not Found"}), 404
        
        soup = BeautifulSoup(res.text, "html.parser")
        def get_v(label):
            tag = soup.find(string=re.compile(label))
            return tag.find_next().text.strip() if tag else "N/A"

        return jsonify({
            "name": get_v("Name"),
            "father": get_v("Father's Name"),
            "mother": get_v("Mother's Name"),
            "gpa": get_v("GPA"),
            "result": get_v("Result"),
            "institute": get_v("Institute")
        })
    except: return jsonify({"error": "Server Error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
