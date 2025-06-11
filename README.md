# CallAnalysisSystem
It is a call analyser website where you can upload your call recording and it analysis your call recording and provides sentiment of the call recording whether it was a positive, negative or neutral call.
It also provides the summary of the call recording and the next action which tells you what you should do after the call recording.
You can also download a pdf of the file which tells you about all the key aspects of the call.

ReadMe
1. Open Visual Studio
2. Open the CallAnalysisSystem folder
3. Open a new terminal
4. Delete the old venv folder and create a new venv folder using 
pip install venv venv
(Make sure you're downloading the venv file in the CallAnalysisSystem folder only)
5. Install all pip libraries using
pip install flask requests python-dotenv textblob transformers torch reportlab
6. Run venv environment using
.\venv\Scripts\activate
7. Run the program using 
python app.py
