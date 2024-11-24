from flask import Flask, request, session, redirect, render_template_string, url_for
from datetime import datetime
from store import KeyValueStore
from entities import User, Message, Friend, Chat

# App initialization
app = Flask(__name__)
app.secret_key = "your_secret_key"

# Key-Value Store initialization
stores=KeyValueStore()
def handle_incoming_messages(messages):
    print(messages)

# kv_store = KeyValueStore()

# kv_store_test = KeyValueStore(handle_incoming_messages,"test","test")
# stores["test"]=kv_store_test
# stores["test"]=kv_store

# test_user = User(stores["test"])
test_user = User(stores)
test_user.set("username","test")
test_user.set("password","test")
test_user.set("friends",[])
test_user.set("outgoing",[])
test_user.set("incoming",[])
test_user.save("test")


# Templates (move these to separate HTML files in a `templates/` directory for larger projects)
LOGIN_TEMPLATE = """
<h1>Login</h1>
<form method="post">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <input type="text" name="server" placeholder="Server" required>
    <button type="submit">Login</button>
</form>
"""

MANAGE_FRIENDS_TEMPLATE = """
<h1>Manage Friends</h1>
<ul>
{% for friend in friends %}
    <li><a href="{{ url_for('viewChats', friendname=friend) }}">{{ friend }}</a></li>
{% endfor %}
</ul>
"""

CHATS_TEMPLATE = """
<h1>Chat with {{ friendname }}</h1>
<ul>
{% for chat in all_chats %}
    <li><strong>{{ chat['from'] }}:</strong> {{ chat['content'] }} ({{ chat['timestamp'] }})</li>
{% endfor %}
</ul>
<form method="post" action="/addChat/{{ friendname }}">
    <input type="text" name="content" placeholder="Type your message" required>
    <button type="submit">Send</button>
</form>
"""

# Routes
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('manageFriends'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        server = request.form['server']
        try:
            # Mock client creation for login validation
            # client = Client(username, server, 12345, message_handler=None, username=username, password=password)
            user_data = stores.get(username)
            if user_data:  # Assume user exists in the stores
                user= User(stores)
                user.load(username, stores)
                if user.get("password") == password:
                    session['username'] = username
                    return redirect(url_for('manageFriends'))
            else:
                
                # stores=KeyValueStore(handle_incoming_messages,username,password)
                # stores=kv_store
                
                user= User(stores)  
                user.set("username",username)
                user.set("password",password)
                user.set("friends",[])
                user.set("outgoing",[])
                user.set("incoming",[])
                
                test_friend = Friend(stores)
                test_friend.set("username","test")
                test_friend.set("key","123")
                test_friend.set("public_key","test")
                test_friend.set("chat","")
                key=stores.new()
                test_friend.save(key)
                
                friends = user.get("friends")
                friends.append(key)
                user.set("friends",friends)
                
                me_as_friend = Friend(stores)
                me_as_friend.set("username",username)
                me_as_friend.set("key","123")
                me_as_friend.set("public_key","test")
                me_as_friend.set("chat","")
                key=stores.new()
                me_as_friend.save(key)
                
                test_user = User(stores)
                test_user.load("test",stores)
                friends = test_user.get("friends")
                friends.append(key)
                test_user.set("friends",friends)
                test_user.save("test")
                
                user.save(username)
                
                
                
                session['username'] = username

                return redirect(url_for('manageFriends'))
                
        except Exception as e:
            return f"Login failed: {str(e)}"
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/manageFriends')
def manageFriends():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    user = User(stores)
    user.load(username, stores)
    friends_keys = user.get("friends")
    friends = []
    for key in friends_keys:
        friend=Friend(stores)
        friend.load(key, stores)
        friends.append(friend.get("username"))
    return render_template_string(MANAGE_FRIENDS_TEMPLATE, friends=friends)

@app.route('/viewChats/<friendname>')
def viewChats(friendname):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    friend = Friend(stores)
    user = User(stores)
    user.load(username, stores)
    for key in user.get("friends"):
        friend.load(key, stores)
        if friend.get("username") == friendname:
            break
    
    chat=Chat(stores)
    if friend.get("chat") == "":
        chat_key = stores.new()
        chat.set("messages",[])
        chat.save(chat_key)
        friend.set("chat",chat_key)
        friend.save(key)
    else:
        chat.load(friend.get("chat"),stores)
    
    sent_messages = []
    received_messages = []
    
    messages = chat.get("messages")
    for key in messages:
        message=Message(stores)
        message.load(key,stores)
        if message.get("to")==username:
            received_messages.append({
                'from': message.get("from"),
                'content': message.get("content"),
                'timestamp': message.get("timestamp"),
                'read': True
            })
        else:
            sent_messages.append({
                'from': message.get("from"),
                'content': message.get("content"),
                'timestamp': message.get("timestamp"),
                'read': True
            })
            
    # Combine and sort messages by timestamp
    all_chats = sorted(sent_messages + received_messages, key=lambda x: x['timestamp'])
    return render_template_string(CHATS_TEMPLATE, friendname=friendname, all_chats=all_chats)

@app.route('/addChat/<friendname>', methods=['POST'])
def addChat(friendname):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    content = request.form.get('content')

    if not content:
        return redirect(url_for('viewChats', friendname=friendname))

    # Create a new message
    message = {
        'content': content,
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    send_message(message, friendname)
    return redirect(url_for('viewChats', friendname=friendname))

# Helper functions
def send_message(content, friendname):
    username = session['username']
    friend = Friend(stores)
    user = User(stores)
    user.load(username, stores)
    for key in user.get("friends"):
        friend.load(key, stores)
        if friend.get("username") == friendname:
            break
    chat=Chat(stores)
    if friend.get("chat") == "":
        chat_key = stores.new()
        chat.set("messages",[])
        chat.save(chat_key)
        friend.set("chat",chat_key)
        friend.save(key)
    else:
        chat.load(friend.get("chat"),stores)
    messages = chat.get("messages")
    message=Message(stores)
    key=stores.new()
    message.set("to",friendname)
    message.set("from",username)
    message.set("content",content)
    message.set("timestamp",datetime.now().isoformat())
    message.save(key)
    messages.append(key)
    chat.set("messages",messages)
    chat.save(friend.get("chat"))

# Run the app
if __name__ == "__main__":
    app.run(debug=True)
