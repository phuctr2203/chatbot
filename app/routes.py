from flask import Blueprint, render_template, request, jsonify

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    bot_response = f"You said: {user_input}"
    return jsonify({'response': bot_response})
