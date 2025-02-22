import streamlit as st
import googleapiclient.discovery
import pandas as pd
from datetime import datetime
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

YOUTUBE_API_KEY = 'AIzaSyCbpOpZNZAW49tRz5SWK7u5ydP8JOgyZsQ'  # Replace with your key
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

def extract_email(description):
    if description:
        email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
        match = re.search(email_pattern, description)
        return match.group(0) if match else "Not found"
    return "Not found"

def get_channel_info(keyword, age_limit_months, sub_limit, max_results=100):
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    search_response = youtube.search().list(q=keyword, part='id,snippet', type='channel', maxResults=50).execute()
    channels_data = []
    count = 0
    current_date = datetime.now()

    for search_result in search_response.get('items', []):
        if count >= max_results:
            break
        channel_id = search_result['id']['channelId']
        channel_response = youtube.channels().list(part='snippet,statistics,contentDetails', id=channel_id).execute()

        if channel_response.get('items'):
            channel = channel_response['items'][0]
            snippet = channel['snippet']
            stats = channel['statistics']
            creation_date = datetime.strptime(snippet['publishedAt'], '%Y-%m-%dT%H:%M:%SZ')
            age_in_months = (current_date - creation_date).days / 30.44
            subscriber_count = int(stats.get('subscriberCount', 0))

            if (age_limit_months == "All" or age_in_months <= float(age_limit_months)) and \
               (sub_limit == "All" or subscriber_count <= int(sub_limit)):
                videos_response = youtube.search().list(channelId=channel_id, part='snippet', order='viewCount', maxResults=1).execute()
                most_popular = videos_response['items'][0]['snippet']['title'] if videos_response.get('items') else "Not found"
                channel_info = {
                    'Channel Name': snippet['title'],
                    'Subscribers': subscriber_count,
                    'Video Quantity': stats.get('videoCount', '0'),
                    'Creation Date': creation_date.strftime('%Y-%m-%d'),
                    'Most Popular Video': most_popular,
                    'Email': extract_email(snippet.get('description', ''))
                }
                channels_data.append(channel_info)
                count += 1
                st.write(f"Processed {count}/{max_results} channels")
    return channels_data

def upload_to_drive(file_path, as_google_sheet=False):
    creds = Credentials.from_authorized_user_file('credentials.json', SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')

    if as_google_sheet:
        sheets_service = build('sheets', 'v4', credentials=creds)
        file_metadata['mimeType'] = 'application/vnd.google-apps.spreadsheet'
        drive_service.files().copy(fileId=file_id, body=file_metadata).execute()
        drive_service.files().delete(fileId=file_id).execute()
        return f"Converted to Google Sheet (ID: {file_id})"
    return f"Uploaded to Google Drive (File ID: {file_id})"

# Streamlit UI
st.title("YouTube Channel Scraper")
keyword = st.text_input("Crime story", "crime case")
age_limit = st.selectbox("Channel Age (6)", ["All", "1", "2", "3", "6", "9", "12", "24"], index=0)
sub_limit = st.selectbox("2000", ["All", "1000", "5000", "10000", "50000", "100000"], index=0)
to_google_sheet = st.checkbox("Convert to Google Sheet (otherwise Excel on Drive)")

if st.button("Start Scraping"):
    if not keyword:
        st.error("Please enter a keyword.")
    else:
        with st.spinner("Fetching channel data..."):
            channel_data = get_channel_info(keyword, age_limit, sub_limit)
            df = pd.DataFrame(channel_data)
            file_name = f"{keyword.replace(' ', '_')}_youtube_data.xlsx"
            df.to_excel(file_name, index=False)
            st.success(f"Saved locally as {file_name}")
            upload_result = upload_to_drive(file_name, as_google_sheet=to_google_sheet)
            st.success(upload_result)
            st.write(f"Processed {len(channel_data)} channels")
