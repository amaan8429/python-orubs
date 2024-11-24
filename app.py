from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2
import io
import requests
from bs4 import BeautifulSoup
import base64

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return ""

@app.route('/generate_paper', methods=['POST'])
def generate_paper():
    data = request.json
    if not data:
        return jsonify({'error': 'Missing data'}), 400
    exam_type = data.get('exam_type')
    paper_format = data.get('paper_format', '')
    pdfs = data.get('pdfs', [])
    urls = data.get('urls', [])
    notes = data.get('notes', '')

    if not exam_type:
        return jsonify({'error': 'Missing exam type'}), 400

    texts = []

    # Process PDFs
    for pdf_data in pdfs:
        filename = pdf_data['filename']
        file_content = pdf_data['content'].split(',')[1]  # Remove the "data:application/pdf;base64," part
        pdf_file = io.BytesIO(base64.b64decode(file_content))
        text = extract_text_from_pdf(pdf_file)
        texts.append({"filename": filename, "text": text})

    # Process URLs
    for url in urls:
        text = extract_text_from_url(url)
        texts.append({"filename": url, "text": text})

    # Add notes
    if notes:
        texts.append({"filename": "Notes", "text": notes})

    if not texts:
        return jsonify({'error': 'No valid content provided'}), 400

    combined_text = "\n\n".join([text["text"] for text in texts])

    prompt = f"""
    You are an AI assistant helping a teacher create an exam paper. 
    The following text contains content from various sources:

    {combined_text}

    Please generate a {exam_type} exam paper based on this content.
    Use the following format for the exam paper:

    {paper_format}

    Ensure the questions are challenging but fair, and cover a range of topics from the provided content.
    """

    try:
        response = requests.post(
            "https://phi.us.gaianet.network/v1/chat/completions",
            json={
                "model": "llama",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an AI assistant helping a teacher create an exam paper based on provided content.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            }
        )
        response.raise_for_status()
        generated_paper = response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        print(f"Error calling AI API: {e}")
        return jsonify({'error': 'Failed to generate exam paper'}), 500

    return jsonify({
        'paper': generated_paper,
        'extracted_texts': texts
    }), 200

if __name__ == '__main__':
    app.run(debug=True)