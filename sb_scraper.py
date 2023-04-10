import cloudscraper
import requests
from bs4 import BeautifulSoup
import time
from tqdm import tqdm
import os

config_path = 'config.txt'
if not os.path.exists(config_path):
    # Create the folder if it doesn't exist
    folder_path = os.path.join(os.environ['APPDATA'], 'CB_DL')
    os.makedirs(folder_path, exist_ok=True)

    # Set the config_path to the new location
    config_path = os.path.join(folder_path, 'config.txt')

    # Create the config file with the default content
    with open(config_path, 'w') as config_file:
        config_file.write("ALREADY_DL_TXT: %APPDATA%\\CB_DL\\already_dl.txt")


# Read the config.txt file and get the path to already_dl.txt

already_dl_path = None
with open(config_path, 'r') as config_file:
    for line in config_file:
        if line.startswith('ALREADY_DL_TXT:'):
            already_dl_path = line.split(':', 1)[1].strip().replace('%APPDATA%', os.environ['APPDATA'])
            break

# Check if the path was found
if already_dl_path is None:
    print("Could not find the path to already_dl.txt in the config.txt file.")

# Check if the folder for already_dl.txt exists, and if not, create it
folder_path = os.path.dirname(already_dl_path)
os.makedirs(folder_path, exist_ok=True)

# Check if the already_dl.txt file exists, and if not, create it
if not os.path.exists(already_dl_path):
    print("Creating already_dl.txt file at the specified path.")
    with open(already_dl_path, 'w'):
        pass

with open(already_dl_path, 'r') as al_dl_file:
    al_dl_urls = al_dl_file.readlines()

line_num = 0
    
with open("input.txt", "r") as input_file:
    lines = input_file.readlines()
    
for line in lines:
    if line in al_dl_urls:
        print(f"The URL {line.strip()} already exists in already_dl.txt")

lines = [line for line in lines if line not in al_dl_urls]

with open(already_dl_path, 'a') as al_dl_file:
    for line in lines:
        al_dl_file.write(line)

for line in lines:
    line = line.strip()
    line_num+=1
    url = line
    if 'https://spankbang.com/' not in line and 'http://spankbang.com/' not in line:
        print("SpankBang is not in line " + str(line_num))
        print(line)
        continue
    for attempt in range(7):
        
        scraper = cloudscraper.create_scraper()  # returns a CloudScraper instance
        html = scraper.get(url).text  # return html

        soup = BeautifulSoup(html, 'html.parser')


        # Find the ul element with class "video_toolbar"
        ul_video_toolbar = soup.find('ul', class_='video_toolbar')
        if ul_video_toolbar:
            # Find the a tag inside the ul element
            a_tag = soup.find('a', class_='ul')

            if a_tag and 'href' in a_tag.attrs:
                # Extract the uploader name from the href attribute
                uploader_name = a_tag['href'].replace('/profile/', '')
                if '/kc/channel/' in uploader_name:
                    uploader_name = uploader_name.replace('/kc/channel/', '')
                if '/' in uploader_name:
                    uploader_name = uploader_name.replace('/', '')
                
                # Store the uploader name in a variable
                print("Uploader name:", uploader_name)
                if uploader_name:
                    break
                else:
                    time.sleep(5)
            else:
                print("Hmm...")
        else:
            print("Hold...")
        time.sleep(1)
    else:
        print("Failed to find uploader name")
        uploader_name = "_"

    # Find the video tag with the id "main_video_player" and get the source tag within it
    video_tag = soup.find('video', {'id': 'main_video_player'})
    source_tag = video_tag.find('source') if video_tag else None

    if source_tag:
        # Get the video URL from the source tag
        video_url = source_tag['src']
        if "720p.mp4" in video_url:
            #print("720p found in URL...")
            video_url_1080p = video_url.replace("720p.mp4", "1080p.mp4")
            #print("1080p URL: " + video_url_1080p)
            video_url_720p = video_url
            #print("720p URL: " + video_url_720p)
        if "480p.mp4" in video_url:
            #print("480p found in URL...")
            video_url_1080p = video_url.replace("480p.mp4", "1080p.mp4")
            #print("1080p URL: " + video_url_1080p)
            video_url_720p = video_url.replace("480p.mp4", "720p.mp4")
            #print("720p URL: " + video_url_720p)
            video_url_480p = video_url
        if "320p.mp4" in video_url:
            print("320 in url..........")
            video_url_1080p = video_url.replace("320p.mp4", "1080p.mp4")
            video_url_720p = video_url.replace("320p.mp4", "720p.mp4")
            video_url_480p = video_url.replace("320p.mp4", "480p.mp4")
            video_url_320p = video_url
        if "240p.mp4" in video_url:
            video_url_1080p = video_url.replace("240p.mp4", "1080p.mp4")
            video_url_720p = video_url.replace("240p.mp4", "720p.mp4")
            video_url_480p = video_url.replace("240p.mp4", "480p.mp4")
            video_url_320p = video_url.replace("240p.mp4", "320p.mp4")
            video_url_240p = video_url
        #if 1080p is available
        if requests.head(video_url_1080p).status_code != 404:
            #print("1080p exists...")
            video_url = video_url_1080p
        #if not, go down to 720p
        elif requests.head(video_url_720p).status_code != 404:
            video_url = video_url_720p
        elif requests.head(video_url_480p).status_code != 404:
            video_url = video_url_480p
        elif requests.head(video_url_320p).status_code != 404:
            video_url = video_url_320p
        elif requests.head(video_url_240p).status_code != 404:
            print("240p :(")
            video_url = video_url_240p
        print("Video URL:", video_url)
    else:
        print("Failed to find the source tag.")
        continue


    video_title_tag = soup.find('title')
    if video_title_tag:
        video_title_text = video_title_tag.text
        video_title_text, _, _ = video_title_text.rpartition('-')
        image_title_text, _, _ = video_title_text.rpartition('-')
        #remove trailing space
        video_title_text = video_title_text.rstrip()
        video_title_text = video_title_text.replace("Watch ", "", 1)
        
        image_title_text = image_title_text.rstrip()
        image_title_text = image_title_text.replace("Watch ", "", 1)
        image_title_text = image_title_text.replace(": ", " ", 1)
        image_title_text = image_title_text.replace(" :", " ", 1)
        image_title_text = image_title_text.replace(":", "", 1)
        image_title_text = image_title_text.replace("/", "-", 1)
        image_title_text = image_title_text.replace("?", "-", 1)
        image_title_text = image_title_text.replace("|", "-", 1)
        image_title_text = image_title_text.replace("<", "-", 1)
        image_title_text = image_title_text.replace(">", "-", 1)
        image_title_text = image_title_text.replace("*", "", 1)
        image_title_text = image_title_text.replace("\\", "", 1)
        image_title_text = image_title_text.replace("\"", "", 1)
        if video_title_text != 'Free Porn Videos and Movies':
            print(video_title_text)
        else:
            print('Failed to find title.')
    else:
        print("Failed to find title.")




    # find and dl image
    img_tag = soup.find('div', class_='play_cover').find('img')
    img_url = img_tag['src'].replace('w:300', 'w:1600')


    img_response = requests.get(img_url)

    # Check if the request was successful
    if img_response.status_code == 200:
        # Save the image to a file
        with open(f'{uploader_name} - {image_title_text}.jpg', 'wb') as f:
            f.write(img_response.content)
            print("Image downloaded successfully.")
    else:
        print("Failed to download the image.")


    #dl vid
    response = requests.get(video_url, stream=True)

    total_size = int(response.headers.get('Content-Length', 0))

    # Check if the request was successful
    if response.status_code == 200:
        # Save the video to a file
        with open(f'{uploader_name} - {video_title_text}.mp4', 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading video") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    # Update the progress bar
                    pbar.update(len(chunk))
        print("Video downloaded successfully.")
