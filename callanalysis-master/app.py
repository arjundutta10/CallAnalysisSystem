# -*- coding: utf-8 -*-
import os
import time
import json
import logging
import requests
from datetime import datetime
from collections import defaultdict
from flask import Flask, request, render_template, send_from_directory, url_for, redirect, flash, make_response, session, send_file
from io import BytesIO

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        pass

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
except ImportError:
    print("WARNING: ReportLab not installed. PDF generation will not work.")
    print("Install with: pip install reportlab")

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()
API_KEY = os.getenv('ASSEMBLYAI_API_KEY')

if not API_KEY:
    print("WARNING: ASSEMBLYAI_API_KEY not found in environment variables!")
    print("Please set your AssemblyAI API key in a .env file or environment variable")
    API_KEY = 'your-api-key-here'

# Setup folders
UPLOAD_FOLDER = 'static/uploads'
DEMO_FOLDER = 'static/demo'
DATA_FOLDER = 'data'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DEMO_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# Sample demo file
DEMO_FILE = os.path.join(DEMO_FOLDER, 'sample_call.mp3')

# Emotion colors for visualization
EMOTION_COLORS = {
    'joy': '#10B981',
    'anger': '#EF4444',
    'sadness': '#6B7280',
    'surprise': '#F59E0B',
    'fear': '#7C3AED',
    'neutral': '#9CA3AF'
}

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "dev-secret-key-change-in-production"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Initialize call logs file
CALL_LOGS_FILE = 'call_logs.json'
if not os.path.exists(CALL_LOGS_FILE):
    with open(CALL_LOGS_FILE, 'w') as f:
        json.dump([], f)

# AssemblyAI API endpoints
ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"

def save_session_data(session_id, data):
    """Save session data to file for persistence"""
    try:
        session_file = os.path.join(DATA_FOLDER, f'session_{session_id}.json')
        with open(session_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logging.info(f"Session data saved to {session_file}")
        return True
    except Exception as e:
        logging.error(f"Error saving session data: {e}")
        return False

def load_session_data(session_id):
    """Load session data from file"""
    try:
        session_file = os.path.join(DATA_FOLDER, f'session_{session_id}.json')
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                data = json.load(f)
            logging.info(f"Session data loaded from {session_file}")
            return data
        else:
            logging.warning(f"Session file not found: {session_file}")
            return None
    except Exception as e:
        logging.error(f"Error loading session data: {e}")
        return None

def get_or_create_session_id():
    """Get or create a unique session ID"""
    if 'session_id' not in session:
        session['session_id'] = f"session_{int(time.time())}_{os.urandom(4).hex()}"
    return session['session_id']

def upload_file_to_assemblyai(filepath):
    """Upload audio file to AssemblyAI and return the upload URL"""
    headers = {
        'authorization': API_KEY,
        'content-type': 'application/octet-stream'
    }
    
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(ASSEMBLYAI_UPLOAD_URL, headers=headers, data=f)
        
        if response.status_code == 200:
            upload_url = response.json()['upload_url']
            logging.info(f"File uploaded successfully: {upload_url}")
            return upload_url
        else:
            logging.error(f"Upload failed: {response.status_code} - {response.text}")
            raise Exception(f"Upload failed: {response.status_code}")
            
    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        raise

def request_transcription(audio_url):
    """Request transcription from AssemblyAI"""
    headers = {
        'authorization': API_KEY,
        'content-type': 'application/json'
    }
    
    # Configuration for transcription
    data = {
        'audio_url': audio_url,
        'speaker_labels': True,  # Enable speaker diarization
        'speakers_expected': 2,  # Expect 2 speakers for call analysis
        'sentiment_analysis': True,  # Enable sentiment analysis
        'entity_detection': True,  # Enable entity detection
        'iab_categories': True,  # Enable topic detection
        'auto_highlights': True,  # Enable key phrase detection
        'punctuate': True,  # Add punctuation
        'format_text': True,  # Format text properly
        'dual_channel': False,  # Set to True if stereo audio with speakers on different channels
        'webhook_url': None,  # Optional: webhook for completion notification
        'word_boost': ['LambdaTest', 'Browserstack', 'demo', 'pricing'],  # Boost recognition of these words
        'boost_param': 'high'  # High boost for better recognition
    }
    
    try:
        response = requests.post(ASSEMBLYAI_TRANSCRIPT_URL, headers=headers, json=data)
        
        if response.status_code == 200:
            transcript_id = response.json()['id']
            logging.info(f"Transcription requested successfully: {transcript_id}")
            return transcript_id
        else:
            logging.error(f"Transcription request failed: {response.status_code} - {response.text}")
            raise Exception(f"Transcription request failed: {response.status_code}")
            
    except Exception as e:
        logging.error(f"Error requesting transcription: {e}")
        raise

def get_transcription_result(transcript_id, max_retries=60, retry_interval=5):
    """Poll AssemblyAI for transcription results"""
    headers = {
        'authorization': API_KEY,
        'content-type': 'application/json'
    }
    
    url = f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                status = result['status']
                
                logging.info(f"Transcription status (attempt {attempt + 1}): {status}")
                
                if status == 'completed':
                    logging.info("Transcription completed successfully")
                    return result
                elif status == 'error':
                    error_msg = result.get('error', 'Unknown error occurred')
                    logging.error(f"Transcription failed: {error_msg}")
                    raise Exception(f"Transcription failed: {error_msg}")
                elif status in ['queued', 'processing']:
                    # Still processing, wait and retry
                    time.sleep(retry_interval)
                    continue
                else:
                    logging.warning(f"Unknown status: {status}")
                    time.sleep(retry_interval)
                    continue
            else:
                logging.error(f"API request failed: {response.status_code} - {response.text}")
                raise Exception(f"API request failed: {response.status_code}")
                
        except Exception as e:
            if attempt == max_retries - 1:
                logging.error(f"Max retries reached. Last error: {e}")
                raise
            else:
                logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                time.sleep(retry_interval)
    
    raise Exception("Transcription timed out after maximum retries")

def format_transcript_with_speakers(transcription_data):
    """Format transcript with speaker information from AssemblyAI response"""
    transcript_segments = []
    
    if 'utterances' in transcription_data and transcription_data['utterances']:
        # Use speaker-labeled utterances if available
        for utterance in transcription_data['utterances']:
            speaker_label = utterance.get('speaker', 'Unknown')
            # Map speaker labels to more friendly names
            if speaker_label == 'A':
                speaker_name = 'Speaker 1'
            elif speaker_label == 'B':
                speaker_name = 'Speaker 2'
            else:
                speaker_name = f'Speaker {speaker_label}'
            
            transcript_segments.append({
                'speaker': speaker_name,
                'text': utterance['text'],
                'start': utterance['start'],
                'end': utterance['end'],
                'confidence': utterance.get('confidence', 0.0)
            })
    else:
        # Fallback: split by sentences if no speaker diarization
        text = transcription_data.get('text', '')
        if text:
            # Simple sentence splitting - in production you might want more sophisticated splitting
            sentences = text.split('. ')
            current_time = 0
            sentence_duration = 3000  # 3 seconds per sentence (rough estimate)
            
            for i, sentence in enumerate(sentences):
                if sentence.strip():
                    speaker_name = 'Speaker 1' if i % 2 == 0 else 'Speaker 2'
                    transcript_segments.append({
                        'speaker': speaker_name,
                        'text': sentence.strip() + ('.' if not sentence.endswith('.') else ''),
                        'start': current_time,
                        'end': current_time + sentence_duration,
                        'confidence': 0.8
                    })
                    current_time += sentence_duration
    
    return transcript_segments

def analyze_sentiment_from_assemblyai(transcription_data):
    """Extract sentiment analysis from AssemblyAI response with improved accuracy"""
    sentiment_results = transcription_data.get('sentiment_analysis_results', [])
    
    if not sentiment_results:
        return "Neutral", {}, False, [], []
    
    # Aggregate sentiment scores
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    speaker_sentiments = defaultdict(list)
    positive_highlights = []
    negative_highlights = []
    
    # Process sentiment results
    for result in sentiment_results:
        sentiment = result.get('sentiment', 'NEUTRAL')
        speaker = result.get('speaker', 'Unknown')
        text = result.get('text', '')
        
        # Map speaker to generic name
        speaker_name = 'Speaker 1' if speaker == 'A' else 'Speaker 2' if speaker == 'B' else f'Speaker {speaker}'
        
        if sentiment == 'POSITIVE':
            positive_count += 1
            speaker_sentiments[speaker_name].append('positive')
            
            if len(text) > 10:
                context = get_context_for_highlight(transcription_data, result)
                positive_highlights.append({
                    'speaker': speaker_name,
                    'text': context,
                    'highlight': text
                })
        elif sentiment == 'NEGATIVE':
            negative_count += 1
            speaker_sentiments[speaker_name].append('negative')
            
            if len(text) > 10:
                context = get_context_for_highlight(transcription_data, result)
                negative_highlights.append({
                    'speaker': speaker_name,
                    'text': context,
                    'highlight': text
                })
        else:
            neutral_count += 1
            speaker_sentiments[speaker_name].append('neutral')
    
    # Limit highlights to top 3 for each category
    positive_highlights = sorted(positive_highlights, key=lambda x: len(x['highlight']), reverse=True)[:3]
    negative_highlights = sorted(negative_highlights, key=lambda x: len(x['highlight']), reverse=True)[:3]
    
    # Determine overall sentiment with better logic
    total_sentiments = positive_count + negative_count + neutral_count
    if total_sentiments == 0:
        overall_sentiment = "Neutral"
    else:
        # Calculate percentages
        positive_pct = positive_count / total_sentiments
        negative_pct = negative_count / total_sentiments
        
        # More aggressive sentiment detection
        if positive_pct > 0.4 and positive_pct > negative_pct:
            overall_sentiment = "Positive"
        elif negative_pct > 0.3 or negative_pct > positive_pct:
            overall_sentiment = "Negative"
        else:
            overall_sentiment = "Neutral"
    
    # Improved customer interest detection
    full_text = transcription_data.get('text', '').lower()
    
    # Positive interest indicators
    positive_keywords = ['interested', 'demo', 'pricing', 'schedule', 'meeting', 'yes', 'sounds good', 'tell me more', 'when can', 'how much', 'sign up', 'let\'s do it']
    
    # Negative interest indicators
    negative_keywords = ['not interested', 'no thank you', 'not now', 'busy', 'don\'t need', 'already have', 'not me', 'sorry', 'confused', 'wrong person', 'mistake', 'don\'t understand', 'who are you', 'what do you want']
    
    # Neutral/uncertain indicators  
    uncertain_keywords = ['maybe', 'think about it', 'call back later', 'not sure', 'let me check', 'need to discuss']
    
    positive_matches = sum(1 for keyword in positive_keywords if keyword in full_text)
    negative_matches = sum(1 for keyword in negative_keywords if keyword in full_text)
    uncertain_matches = sum(1 for keyword in uncertain_keywords if keyword in full_text)
    
    # Determine customer interest based on keywords and sentiment
    if negative_matches > positive_matches or negative_pct > 0.4:
        customer_interest = False
    elif positive_matches > 0 and positive_pct > negative_pct:
        customer_interest = True
    elif uncertain_matches > 0:
        customer_interest = False  # Uncertain = low interest for now
    else:
        customer_interest = positive_count > negative_count and positive_count > 0
    
    # Convert speaker sentiments to emotions for compatibility
    speaker_emotions = {}
    for speaker, sentiments in speaker_sentiments.items():
        emotions = []
        for sentiment in sentiments:
            if sentiment == 'positive':
                emotions.extend(['joy', 'optimism'])
            elif sentiment == 'negative':
                emotions.extend(['sadness', 'concern'])
            else:
                emotions.append('neutral')
        speaker_emotions[speaker] = emotions
    
    return overall_sentiment, speaker_emotions, customer_interest, positive_highlights, negative_highlights

def generate_dynamic_summary(transcript_segments, sentiment, customer_interest, audio_filename):
    """Generate dynamic summary based on actual call content"""
    if not transcript_segments or len(transcript_segments) == 0:
        return f"Call analysis attempted for {audio_filename or 'uploaded file'}. No transcript content was successfully generated from the audio file."
    
    # Basic stats
    total_speakers = len(set(segment.get('speaker', 'Unknown') for segment in transcript_segments))
    
    # Calculate duration
    start_times = [segment.get('start', 0) for segment in transcript_segments if segment.get('start')]
    end_times = [segment.get('end', 0) for segment in transcript_segments if segment.get('end')]
    
    if start_times and end_times:
        total_duration = max(end_times) - min(start_times)
        duration_minutes = total_duration / 60000
    else:
        duration_minutes = 0
    
    # Analyze conversation content
    all_text = ' '.join([segment.get('text', '') for segment in transcript_segments if segment.get('text')]).lower()
    
    # Detect conversation type and content
    conversation_type = "general conversation"
    key_topics = []
    
    # Sales call detection
    if any(word in all_text for word in ['introduce', 'platform', 'product', 'service', 'company']):
        conversation_type = "sales/introduction call"
    
    # Support call detection  
    if any(word in all_text for word in ['problem', 'issue', 'help', 'support', 'not working']):
        conversation_type = "support call"
    
    # Meeting/scheduling detection
    if any(word in all_text for word in ['meeting', 'schedule', 'calendar', 'appointment']):
        key_topics.append("scheduling")
    
    # Product/demo discussion
    if any(word in all_text for word in ['demo', 'demonstration', 'show', 'features']):
        key_topics.append("product demonstration")
    
    # Pricing discussion
    if any(word in all_text for word in ['price', 'pricing', 'cost', 'expensive', 'cheap']):
        key_topics.append("pricing discussion")
    
    # Confusion/misunderstanding detection
    confusion_indicators = ['confused', 'don\'t understand', 'who are you', 'what do you want', 'wrong person', 'mistake', 'not me']
    if any(indicator in all_text for indicator in confusion_indicators):
        conversation_type = "confused/misdirected call"
        key_topics.append("call confusion")
    
    # Generate summary based on analysis
    summary = f"This {conversation_type} contains {len(transcript_segments)} conversation segments between {total_speakers} speakers"
    
    if duration_minutes > 0:
        summary += f", lasting approximately {duration_minutes:.1f} minutes"
    
    summary += f". The overall sentiment is {sentiment.lower()}"
    
    # Add customer interest context
    if customer_interest:
        summary += " with positive customer engagement and interest in proceeding"
    else:
        if sentiment.lower() == "negative":
            summary += " with the customer showing disinterest or confusion"
        else:
            summary += " with neutral customer engagement"
    
    # Add key topics if found
    if key_topics:
        summary += f". Key discussion topics include: {', '.join(key_topics)}"
    
    summary += "."
    
    return summary

def generate_dynamic_action_items(transcript_segments, sentiment, customer_interest):
    """Generate dynamic action items based on actual conversation content"""
    if not transcript_segments or len(transcript_segments) == 0:
        return "• No specific action items identified - transcript unavailable"
    
    all_text = ' '.join([segment.get('text', '') for segment in transcript_segments if segment.get('text')]).lower()
    
    action_items = []
    
    # Negative sentiment or confusion - different actions needed
    confusion_indicators = ['confused', 'don\'t understand', 'who are you', 'wrong person', 'mistake', 'not me']
    if any(indicator in all_text for indicator in confusion_indicators):
        action_items.extend([
            "• Verify contact information and correct target audience",
            "• Review lead qualification process to avoid misdirected calls",
            "• Update contact database with correct information"
        ])
    elif sentiment.lower() == "negative" and not customer_interest:
        action_items.extend([
            "• Mark lead as not qualified for current offering",
            "• Review call approach and messaging for future improvements", 
            "• Consider alternative solutions or timing for re-engagement"
        ])
    elif customer_interest:
        # Positive engagement - standard follow-up actions
        if any(word in all_text for word in ['demo', 'demonstration', 'show me']):
            action_items.append("• Schedule and prepare demonstration as discussed")
        
        if any(word in all_text for word in ['follow up', 'call back', 'contact', 'reach out']):
            action_items.append("• Follow up with customer as requested")
        
        if any(word in all_text for word in ['pricing', 'price', 'cost', 'quote']):
            action_items.append("• Provide pricing information and quotes")
        
        if any(word in all_text for word in ['meeting', 'schedule', 'calendar']):
            action_items.append("• Send calendar invite for scheduled meeting")
        
        if any(word in all_text for word in ['document', 'information', 'material', 'send']):
            action_items.append("• Send requested documentation and materials")
        
        action_items.append("• Prioritize follow-up due to positive customer interest")
    else:
        # Neutral engagement
        action_items.extend([
            "• Review conversation for potential re-engagement opportunities",
            "• Update customer records with call summary and sentiment",
            "• Consider nurture campaign for future interest development"
        ])
    
    return "<br/>".join(action_items) if action_items else "• No specific action items identified"

def generate_dynamic_topics(transcript_segments):
    """Generate dynamic topics based on actual conversation content"""
    if not transcript_segments or len(transcript_segments) == 0:
        return []
    
    all_text = ' '.join([segment.get('text', '') for segment in transcript_segments if segment.get('text')]).lower()
    
    topics = []
    
    # Detect specific topics with counts
    if 'intro' in all_text or 'introduce' in all_text or 'hello' in all_text:
        intro_count = all_text.count('intro') + all_text.count('introduce') + all_text.count('hello')
        topics.append(f"Introductions ({intro_count})")
    
    if 'demo' in all_text or 'demonstration' in all_text:
        demo_count = all_text.count('demo') + all_text.count('demonstration')
        topics.append(f"Demo Discussion ({demo_count})")
    
    if 'price' in all_text or 'pricing' in all_text or 'cost' in all_text:
        price_count = all_text.count('price') + all_text.count('pricing') + all_text.count('cost')
        topics.append(f"Pricing ({price_count})")
    
    if 'meeting' in all_text or 'schedule' in all_text:
        meeting_count = all_text.count('meeting') + all_text.count('schedule')
        topics.append(f"Scheduling ({meeting_count})")
    
    # Detect confusion/problems
    confusion_words = ['confused', 'don\'t understand', 'who are you', 'wrong', 'mistake', 'not me', 'sorry']
    confusion_count = sum(all_text.count(word) for word in confusion_words)
    if confusion_count > 0:
        topics.append(f"Call Confusion ({confusion_count})")
    
    # Detect objections/concerns
    objection_words = ['but', 'however', 'concern', 'problem', 'issue', 'not sure', 'already have']
    objection_count = sum(all_text.count(word) for word in objection_words)
    if objection_count > 0:
        topics.append(f"Objections ({objection_count})")
    
    # Platform/product discussion
    if 'platform' in all_text or 'product' in all_text or 'service' in all_text:
        platform_count = all_text.count('platform') + all_text.count('product') + all_text.count('service')
        topics.append(f"Product Discussion ({platform_count})")
    
    return topics[:6]  # Limit to 6 topics maximum

def get_context_for_highlight(transcription_data, sentiment_result):
    """Get surrounding context for a sentiment highlight"""
    text = sentiment_result.get('text', '')
    
    # Try to find this text in the full transcript to get context
    full_text = transcription_data.get('text', '')
    if text in full_text:
        # Find position of the text in full transcript
        pos = full_text.find(text)
        
        # Get some context before and after (about 20 chars each)
        start = max(0, pos - 20)
        end = min(len(full_text), pos + len(text) + 20)
        
        # Create context with ellipsis if needed
        context = ""
        if start > 0:
            context += "... "
        context += full_text[start:end]
        if end < len(full_text):
            context += " ..."
            
        return context
    
    return f"... {text} ..."

def get_call_logs():
    """Get saved call logs"""
    try:
        with open(CALL_LOGS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_call_log(audio_filename, sentiment, customer_interest, speaker_emotions):
    """Save call log to file"""
    logs = get_call_logs()
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "audio_file": audio_filename,
        "sentiment": sentiment,
        "customer_interest": customer_interest,
        "speaker_emotions": speaker_emotions
    })
    
    with open(CALL_LOGS_FILE, 'w') as f:
        json.dump(logs, f, indent=2)

def generate_pdf_report(session_data=None):
    """Generate PDF report with transcript and analysis"""
    try:
        # Create a BytesIO buffer to hold the PDF
        buffer = BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20
        )
        
        # Build the PDF content
        story = []
        
        # Title
        story.append(Paragraph("Call Analysis Report", title_style))
        story.append(Spacer(1, 20))
        
        # Get data from session_data or defaults
        if session_data:
            transcript_segments = session_data.get('transcript_segments', [])
            sentiment = session_data.get('sentiment', 'Neutral')
            customer_interest = session_data.get('customer_interest', False)
            audio_filename = session_data.get('audio_filename', 'Unknown')
            dynamic_summary = session_data.get('dynamic_summary', '')
            dynamic_action_items = session_data.get('dynamic_action_items', '')
        else:
            # Fallback data
            transcript_segments = []
            sentiment = 'Neutral'
            customer_interest = False
            audio_filename = 'Unknown'
            dynamic_summary = ''
            dynamic_action_items = ''
        
        # Call Information
        story.append(Paragraph("Call Information", heading_style))
        call_info_data = [
            ['Audio File:', audio_filename],
            ['Analysis Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Overall Sentiment:', sentiment],
            ['Customer Interest:', 'High' if customer_interest else 'Low'],
            ['Transcript Segments:', str(len(transcript_segments)) if transcript_segments else '0']
        ]
        
        call_info_table = Table(call_info_data, colWidths=[2*inch, 4*inch])
        call_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(call_info_table)
        story.append(Spacer(1, 20))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", heading_style))
        
        if dynamic_summary:
            summary_text = dynamic_summary
        elif transcript_segments and len(transcript_segments) > 0:
            summary_text = generate_dynamic_summary(transcript_segments, sentiment, customer_interest, audio_filename)
        else:
            summary_text = f"Call analysis report generated for {audio_filename}. This appears to be a demo or test call with limited transcript data available."
        
        story.append(Paragraph(summary_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Transcript Section
        story.append(Paragraph("Call Transcript", heading_style))
        
        if transcript_segments and len(transcript_segments) > 0:
            logging.info(f"Adding {len(transcript_segments)} transcript segments to PDF")
            for i, segment in enumerate(transcript_segments):
                try:
                    # Format timestamp
                    start_time = segment.get('start', 0)
                    minutes = int(start_time // 60000)
                    seconds = int((start_time % 60000) // 1000)
                    timestamp = f"[{minutes}:{seconds:02d}]"
                    
                    speaker_text = f"<b>{segment.get('speaker', 'Unknown')} {timestamp}:</b> {segment.get('text', 'No text available')}"
                    story.append(Paragraph(speaker_text, styles['Normal']))
                    story.append(Spacer(1, 8))
                    
                except Exception as e:
                    logging.error(f"Error processing segment {i}: {e}")
                    story.append(Paragraph(f"<b>Segment {i+1}:</b> Error processing this segment", styles['Normal']))
                    story.append(Spacer(1, 8))
        else:
            # Demo content for when no real transcript is available
            logging.info("No transcript segments found, adding demo content")
            demo_transcript = [
                {"speaker": "Speaker 1", "text": "Hello. Hey. Hi, Eric. This is Anadja. I'm calling you from JustCall.", "time": "[0:04]"},
                {"speaker": "Speaker 2", "text": "Hi.", "time": "[0:09]"},
                {"speaker": "Speaker 1", "text": "How are you doing today?", "time": "[0:11]"},
                {"speaker": "Speaker 2", "text": "I'm fine. Thank you. How are you?", "time": "[0:12]"},
                {"speaker": "Speaker 1", "text": "Great! I wanted to introduce you to LambdaTest, our cross-browser testing platform.", "time": "[0:22]"},
                {"speaker": "Speaker 2", "text": "Interesting. We're currently using Browserstack, but we've been having some issues with it lately.", "time": "[0:28]"},
                {"speaker": "Speaker 1", "text": "That's exactly why I'm reaching out. Many teams switch to us for better reliability and performance.", "time": "[0:35]"},
                {"speaker": "Speaker 2", "text": "Could you tell me more about your pricing? And would it be possible to schedule a demo?", "time": "[0:42]"},
                {"speaker": "Speaker 1", "text": "Our pricing is very competitive. I'd be happy to show you a demo. When would work best for your team?", "time": "[0:48]"},
                {"speaker": "Speaker 2", "text": "Tuesday would work well for us. Could you send over a calendar invite and some documentation?", "time": "[0:55]"},
                {"speaker": "Speaker 1", "text": "Perfect! I'll send you the calendar invite and a one-pager about LambdaTest right after this call.", "time": "[1:02]"}
            ]
            
            story.append(Paragraph("<i>Note: This is demo content as no transcript was available from the uploaded audio.</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            
            for segment in demo_transcript:
                speaker_text = f"<b>{segment['speaker']} {segment['time']}:</b> {segment['text']}"
                story.append(Paragraph(speaker_text, styles['Normal']))
                story.append(Spacer(1, 8))
        
        story.append(Spacer(1, 20))
        
        # Action Items
        story.append(Paragraph("Next Action Items", heading_style))
        
        if dynamic_action_items:
            action_text = dynamic_action_items
        elif transcript_segments and len(transcript_segments) > 0:
            action_text = generate_dynamic_action_items(transcript_segments, sentiment, customer_interest)
        else:
            action_text = "• Demo is scheduled with Speaker 2's team on Tuesday<br/>• Speaker 1 to share the calendar invite and also a one-pager about LambdaTest<br/>• Follow up to confirm meeting details"
        
        story.append(Paragraph(action_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Footer
        story.append(Paragraph("Report generated by PrimeRole Call Analytics", styles['Normal']))
        
        # Build the PDF
        doc.build(story)
        
        # Get the PDF data
        buffer.seek(0)
        logging.info("PDF generated successfully")
        return buffer
        
    except Exception as e:
        logging.error(f"Error generating PDF: {e}")
        raise

@app.route("/", methods=["GET", "POST"])
def index():
    """Main route for the application"""
    theme = request.cookies.get("theme", "light")
    
    # Get or create session ID
    session_id = get_or_create_session_id()
    
    # Try to load existing session data
    session_data = load_session_data(session_id)
    if session_data:
        logging.info("Loaded existing session data")
        # Restore session variables
        for key, value in session_data.items():
            session[key] = value
    
    transcript_segments = session.get('transcript_segments')
    sentiment = session.get('sentiment')
    speaker_emotions = session.get('speaker_emotions')
    customer_interest = session.get('customer_interest')
    audio_filename = session.get('audio_filename')
    word_timings = session.get('word_timings', [])
    call_logs = get_call_logs()
    positive_highlights = session.get('positive_highlights', [])
    negative_highlights = session.get('negative_highlights', [])
    
    # Copy demo file if it doesn't exist
    if not os.path.exists(DEMO_FILE):
        with open(DEMO_FILE, 'w') as f:
            f.write("Demo audio file")

    if request.method == "POST":
        file = request.files.get('audio_file')
        if not file or file.filename == '':
            flash("No audio file uploaded", "error")
            return redirect(url_for('index'))

        # Validate file type
        allowed_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.webm'}
        if file.filename:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                flash(f"File type {file_ext} not supported. Please upload: {', '.join(allowed_extensions)}", "error")
                return redirect(url_for('index'))

            audio_filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
        else:
            flash("Invalid file name", "error")
            return redirect(url_for('index'))
        
        # Check if API key is configured
        if API_KEY == 'your-api-key-here' or not API_KEY:
            flash("AssemblyAI API key not configured. Please set ASSEMBLYAI_API_KEY environment variable.", "error")
            return redirect(url_for('index'))
        
        try:
            file.save(filepath)
            
            # Upload to AssemblyAI
            flash("Uploading audio file to AssemblyAI...", "info")
            audio_url = upload_file_to_assemblyai(filepath)
            
            # Request transcription
            flash("Processing transcription with speaker diarization...", "info")
            transcript_id = request_transcription(audio_url)
            
            # Get results (this will poll until completion)
            flash("Waiting for transcription to complete...", "info")
            transcription_data = get_transcription_result(transcript_id)

            if not transcription_data.get('text'):
                flash("Transcription returned empty result. Please check your audio file quality.", "warning")
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(url_for('index'))

            # Process transcript
            transcript_segments = format_transcript_with_speakers(transcription_data)
            
            if not transcript_segments:
                flash("No transcript segments found. The audio might be too quiet or unclear.", "warning")
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(url_for('index'))

            # Analyze sentiment and emotions
            sentiment, speaker_emotions, customer_interest, positive_highlights, negative_highlights = analyze_sentiment_from_assemblyai(transcription_data)

            # Extract word timings for audio synchronization
            for word in transcription_data.get("words", []):
                word_timings.append({
                    "start": word["start"] / 1000.0,  # Convert to seconds
                    "end": word["end"] / 1000.0,
                    "text": word["text"],
                    "speaker": word.get("speaker", ""),
                    "confidence": word.get("confidence", 0.0)
                })

            # Store in session
            session['transcript_segments'] = transcript_segments
            session['sentiment'] = sentiment
            session['speaker_emotions'] = speaker_emotions
            session['customer_interest'] = customer_interest
            session['audio_filename'] = audio_filename
            session['word_timings'] = word_timings
            session['positive_highlights'] = positive_highlights
            session['negative_highlights'] = negative_highlights
        
            # Generate dynamic content for UI
            session['dynamic_summary'] = generate_dynamic_summary(transcript_segments, sentiment, customer_interest, audio_filename)
            session['dynamic_action_items'] = generate_dynamic_action_items(transcript_segments, sentiment, customer_interest)
            session['dynamic_topics'] = generate_dynamic_topics(transcript_segments)

            # Save session data to file for persistence
            session_data = {
                'session_id': session_id,
                'transcript_segments': transcript_segments,
                'sentiment': sentiment,
                'speaker_emotions': speaker_emotions,
                'customer_interest': customer_interest,
                'audio_filename': audio_filename,
                'word_timings': word_timings,
                'positive_highlights': positive_highlights,
                'negative_highlights': negative_highlights,
                'dynamic_summary': session['dynamic_summary'],
                'dynamic_action_items': session['dynamic_action_items'],
                'dynamic_topics': session['dynamic_topics'],
                'timestamp': datetime.now().isoformat()
            }
            
            save_session_data(session_id, session_data)

            # Save to logs
            save_call_log(audio_filename, sentiment, customer_interest, speaker_emotions)
            call_logs = get_call_logs()
            
            flash("Transcription completed successfully!", "success")
            
            # Log some stats for debugging
            logging.info(f"Transcription completed:")
            logging.info(f"- Duration: {transcription_data.get('audio_duration', 0)} seconds")
            logging.info(f"- Confidence: {transcription_data.get('confidence', 0)}")
            logging.info(f"- Segments: {len(transcript_segments)}")
            logging.info(f"- Words: {len(word_timings)}")
            logging.info(f"- Session ID: {session_id}")

        except Exception as e:
            logging.error(f"Error during transcription: {e}")
            flash(f"Error during transcription: {str(e)}", "error")
            # Clean up uploaded file on error
            if os.path.exists(filepath):
                os.remove(filepath)
            return redirect(url_for('index'))

    return render_template('index.html',
        transcript=transcript_segments,
        sentiment=sentiment,
        speaker_emotions=speaker_emotions,
        customer_interest=customer_interest,
        audio_file=audio_filename,
        word_timings=word_timings,
        emotion_colors=EMOTION_COLORS,
        call_logs=call_logs,
        theme=theme,
        positive_highlights=positive_highlights,
        negative_highlights=negative_highlights,
        dynamic_summary=session.get('dynamic_summary'),
        dynamic_action_items=session.get('dynamic_action_items'),
        dynamic_topics=session.get('dynamic_topics')
    )

@app.route('/download-report', methods=['POST'])
def download_report():
    """Generate and download PDF report"""
    try:
        # Get session ID
        session_id = get_or_create_session_id()
        
        # Try to load session data from file first
        session_data = load_session_data(session_id)
        
        # If no file data, try to get from current session
        if not session_data:
            session_data = {
                'transcript_segments': session.get('transcript_segments', []),
                'sentiment': session.get('sentiment', 'Neutral'),
                'speaker_emotions': session.get('speaker_emotions', {}),
                'customer_interest': session.get('customer_interest', False),
                'audio_filename': session.get('audio_filename', 'Unknown'),
                'dynamic_summary': session.get('dynamic_summary', ''),
                'dynamic_action_items': session.get('dynamic_action_items', ''),
                'dynamic_topics': session.get('dynamic_topics', [])
            }
        
        logging.info(f"Generating PDF with session data: {session_data.get('audio_filename', 'Unknown')}")
        logging.info(f"Transcript segments: {len(session_data.get('transcript_segments', []))}")
        
        # Generate PDF
        pdf_buffer = generate_pdf_report(session_data)
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_name = session_data.get('audio_filename', 'call')
        if audio_name and '.' in audio_name:
            audio_name = audio_name.split('.')[0]  # Remove extension
        filename = f"call_analysis_{audio_name}_{timestamp}.pdf"
        
        logging.info(f"PDF generated successfully: {filename}")
        
        # Return PDF as download
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logging.error(f"Error generating PDF report: {e}")
        flash(f"Error generating PDF report: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/clear-session')
def clear_session():
    """Clear session data and return to upload page"""
    try:
        # Get session ID and audio filename
        session_id = get_or_create_session_id()
        audio_filename = session.get('audio_filename')
        
        # Delete audio file
        if audio_filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.info(f"Deleted audio file: {filepath}")
        
        # Delete session data file
        session_file = os.path.join(DATA_FOLDER, f'session_{session_id}.json')
        if os.path.exists(session_file):
            os.remove(session_file)
            logging.info(f"Deleted session file: {session_file}")
        
        # Clear all session data
        session.clear()
        
        flash("Recording deleted successfully. You can now upload a new file.", "success")
        
    except Exception as e:
        logging.error(f"Error clearing session: {e}")
        flash(f"Error deleting recording: {str(e)}", "error")
    
    return redirect(url_for('index'))

@app.route('/delete_log/<int:index>', methods=['POST'])
def delete_log(index):
    """Delete a call log"""
    try:
        logs = get_call_logs()
        if 0 <= index < len(logs):
            # Delete the associated audio file
            audio_file = logs[index].get('audio_file')
            if audio_file:
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_file)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            
            # Remove the log entry
            del logs[index]
            
            # Save updated logs
            with open(CALL_LOGS_FILE, 'w') as f:
                json.dump(logs, f, indent=2)
                
            flash("Call log deleted successfully", "success")
        else:
            flash("Invalid log index", "error")
    except Exception as e:
        logging.error(f"Error deleting log: {e}")
        flash(f"Error deleting log: {str(e)}", "error")
    
    return redirect(url_for('index'))

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/validate-session')
def validate_session():
    """Validate session data integrity"""
    try:
        session_id = get_or_create_session_id()
        
        # Try to load from file first
        session_data = load_session_data(session_id)
        
        if session_data:
            transcript_segments = session_data.get('transcript_segments', [])
            has_data = len(transcript_segments) > 0 or bool(session_data.get('dynamic_summary'))
        else:
            # Fallback to current session
            transcript_segments = session.get('transcript_segments', [])
            has_data = len(transcript_segments) > 0 or bool(session.get('dynamic_summary'))
        
        session_status = {
            'transcript_segments': len(transcript_segments),
            'sentiment': session_data.get('sentiment') if session_data else session.get('sentiment'),
            'customer_interest': session_data.get('customer_interest') if session_data else session.get('customer_interest'),
            'audio_filename': session_data.get('audio_filename') if session_data else session.get('audio_filename'),
            'has_session_file': session_data is not None,
            'session_id': session_id
        }
        
        return {
            'status': 'success',
            'data': session_status,
            'has_transcript': len(transcript_segments) > 0,
            'ready_for_pdf': True  # Always ready - we'll generate something
        }
        
    except Exception as e:
        logging.error(f"Session validation error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/debug-session')
def debug_session():
    """Debug route to check session contents"""
    session_id = get_or_create_session_id()
    session_data = load_session_data(session_id)
    
    debug_info = {
        'session_id': session_id,
        'session_file_exists': session_data is not None,
        'current_session': {
            'transcript_segments': len(session.get('transcript_segments', [])),
            'sentiment': session.get('sentiment'),
            'audio_filename': session.get('audio_filename'),
            'dynamic_summary': bool(session.get('dynamic_summary')),
        },
        'file_session': session_data if session_data else 'No file data'
    }
    
    return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre>"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
