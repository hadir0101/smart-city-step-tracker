from flask import Flask
from database import init_db, seed_from_xml
from routes import bp

app = Flask(__name__)
app.register_blueprint(bp)

if __name__ == '__main__':
    init_db()
    seed_from_xml()
    app.run(debug=True)
