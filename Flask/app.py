from flask import Flask,render_template, request, jsonify
  
app = Flask(__name__,template_folder="templates")
  
@app.route("/")
def hello():
    return render_template('index.html')
  
@app.route('/process-data', methods=['POST'])
def process_data():
    data = request.json['data']
    print(data)
    return('/')
  
if __name__ == '__main__':
    app.run(debug=True)